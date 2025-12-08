"""
Architect Agent for migration planning and code transformation.

The Architect agent is responsible for the planning phase:
- Generating migration plans
- Creating code transformation proposals
- Coordinating with LLM for intelligent migration suggestions
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.agents.architect.planner import MigrationPlan, MigrationPlanner
from src.agents.architect.prompts import (
    ANALYSIS_PROMPT,
    MIGRATION_PROMPT,
    SYSTEM_PROMPT,
    VALIDATION_PROMPT,
)
from src.agents.base import AgentResult, BaseAgent
from src.shared.config import get_settings
from src.shared.logger import get_logger
from src.tmg import TypedMigrationGraph
from src.tmg.models import MigrationProposal, NodeState

logger = get_logger(__name__, component="architect")


@dataclass
class ArchitectOutput:
    """
    Output from the Architect agent.
    
    Attributes:
        plan: The generated migration plan.
        proposals: List of migration proposals for code changes.
        analysis_results: Results from code analysis.
        llm_calls: Number of LLM API calls made.
        total_tokens: Total tokens used.
    """
    plan: MigrationPlan | None = None
    proposals: list[MigrationProposal] = field(default_factory=list)
    analysis_results: list[dict[str, Any]] = field(default_factory=list)
    llm_calls: int = 0
    total_tokens: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "plan": self.plan.to_dict() if self.plan else None,
            "proposals": [p.to_dict() for p in self.proposals],
            "analysis_results": self.analysis_results,
            "llm_calls": self.llm_calls,
            "total_tokens": self.total_tokens,
        }


class ArchitectAgent(BaseAgent):
    """
    Agent responsible for migration planning and code transformation.
    
    The Architect uses LLM capabilities to:
    - Analyze deprecated APIs and suggest replacements
    - Generate migration code transformations
    - Create detailed migration plans
    
    Supports both OpenAI and Anthropic as LLM providers.
    
    Attributes:
        planner: MigrationPlanner for creating migration plans.
        llm_provider: Which LLM provider to use.
    
    Example:
        >>> tmg = TypedMigrationGraph(name="MyProject")
        >>> agent = ArchitectAgent(tmg=tmg)
        >>> result = agent.execute(mode="plan")
        >>> print(f"Generated {len(result.data.plan.steps)} steps")
    """
    
    def __init__(
        self,
        tmg: TypedMigrationGraph | None = None,
        llm_provider: str | None = None,
    ) -> None:
        """
        Initialize the Architect agent.
        
        Args:
            tmg: The Typed Migration Graph to work with.
            llm_provider: LLM provider ('openai' or 'anthropic').
                         Defaults to config setting.
        """
        super().__init__(name="Architect", tmg=tmg)
        
        settings = get_settings()
        self.llm_provider = llm_provider or settings.llm_provider
        self._llm_client: Any = None
        self._total_tokens = 0
        self._llm_calls = 0
    
    @property
    def planner(self) -> MigrationPlanner:
        """Get the migration planner for the current TMG."""
        return MigrationPlanner(self.tmg)
    
    def _get_llm_client(self) -> Any:
        """
        Get or create the LLM client.
        
        Returns:
            Configured LLM client (OpenAI or Anthropic).
        """
        if self._llm_client is not None:
            return self._llm_client
        
        settings = get_settings()
        
        if self.llm_provider == "openai":
            try:
                from openai import OpenAI
                self._llm_client = OpenAI(api_key=settings.get_llm_api_key())
                logger.info("llm_client_initialized", provider="openai")
            except Exception as e:
                logger.warning("openai_init_failed", error=str(e))
                self._llm_client = None
        else:
            try:
                from anthropic import Anthropic
                self._llm_client = Anthropic(api_key=settings.get_llm_api_key())
                logger.info("llm_client_initialized", provider="anthropic")
            except Exception as e:
                logger.warning("anthropic_init_failed", error=str(e))
                self._llm_client = None
        
        return self._llm_client
    
    def _call_llm(
        self,
        prompt: str,
        system_prompt: str = SYSTEM_PROMPT,
        max_tokens: int = 2000,
    ) -> str | None:
        """
        Call the LLM with a prompt.
        
        Args:
            prompt: The user prompt.
            system_prompt: The system prompt.
            max_tokens: Maximum tokens in response.
            
        Returns:
            LLM response text or None on failure.
        """
        client = self._get_llm_client()
        if client is None:
            logger.warning("llm_not_available", provider=self.llm_provider)
            return None
        
        self._llm_calls += 1
        
        try:
            if self.llm_provider == "openai":
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=max_tokens,
                    temperature=0.3,
                )
                self._total_tokens += response.usage.total_tokens if response.usage else 0
                return response.choices[0].message.content
            else:
                response = client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=max_tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": prompt}],
                )
                self._total_tokens += response.usage.input_tokens + response.usage.output_tokens
                return response.content[0].text
                
        except Exception as e:
            logger.exception("llm_call_failed", error=str(e))
            return None
    
    def process(
        self,
        mode: str = "plan",
        node_ids: list[str] | None = None,
        **kwargs: Any,
    ) -> AgentResult[ArchitectOutput]:
        """
        Execute the Architect agent.
        
        Args:
            mode: Operation mode:
                - 'plan': Generate migration plan only
                - 'analyze': Analyze specific nodes with LLM
                - 'propose': Generate migration proposals
                - 'full': Complete analysis and proposal generation
            node_ids: Specific nodes to process (for analyze/propose).
            **kwargs: Additional arguments.
            
        Returns:
            AgentResult containing ArchitectOutput.
        """
        self.logger.info("architect_started", mode=mode)
        
        output = ArchitectOutput()
        
        if mode in ("plan", "full"):
            output.plan = self.planner.generate_plan()
        
        if mode in ("analyze", "full"):
            target_nodes = self._get_target_nodes(node_ids)
            for node in target_nodes[:20]:  # Limit for cost control
                analysis = self._analyze_node(node)
                if analysis:
                    output.analysis_results.append(analysis)
        
        if mode in ("propose", "full"):
            target_nodes = self._get_target_nodes(node_ids)
            for node in target_nodes[:10]:  # Limit for cost control
                proposal = self._generate_proposal(node)
                if proposal:
                    output.proposals.append(proposal)
        
        output.llm_calls = self._llm_calls
        output.total_tokens = self._total_tokens
        
        self.logger.info(
            "architect_complete",
            mode=mode,
            plan_steps=len(output.plan.steps) if output.plan else 0,
            analyses=len(output.analysis_results),
            proposals=len(output.proposals),
            llm_calls=output.llm_calls,
            total_tokens=output.total_tokens,
        )
        
        return AgentResult(
            success=True,
            data=output,
            tokens_used=output.total_tokens,
        )
    
    def _get_target_nodes(self, node_ids: list[str] | None) -> list[Any]:
        """Get nodes to process based on IDs or default to deprecated."""
        if node_ids:
            return [self.tmg.get_node(nid) for nid in node_ids if self.tmg.has_node(nid)]
        
        # Default: nodes in ANALYZED or DEPRECATED state
        nodes = self.tmg.get_nodes_by_state(NodeState.ANALYZED)
        nodes.extend(self.tmg.get_nodes_by_state(NodeState.DEPRECATED))
        
        # Prioritize deprecated APIs
        nodes.sort(key=lambda n: (not n.metadata.get("deprecated", False), n.id))
        
        return nodes
    
    def _analyze_node(self, node: Any) -> dict[str, Any] | None:
        """Analyze a single node using LLM."""
        # Get source code if available
        source_code = self._get_source_code(node)
        
        # Get dependencies
        deps = self.tmg.get_dependencies(node.id)
        dep_info = [f"- {d.id} ({d.node_type.name})" for d in deps[:10]]
        
        # Get deprecated APIs
        deprecated = []
        if node.metadata.get("deprecated"):
            deprecated.append({
                "api": node.id,
                "replacement": node.metadata.get("replacement", "unknown"),
            })
        
        prompt = ANALYSIS_PROMPT.format(
            node_id=node.id,
            node_type=node.node_type.name,
            file_path=node.file_path,
            dependencies="\n".join(dep_info) if dep_info else "None",
            source_code=source_code or "Source code not available",
            deprecated_apis=json.dumps(deprecated, indent=2) if deprecated else "None",
        )
        
        response = self._call_llm(prompt)
        if not response:
            return None
        
        try:
            # Try to parse JSON response
            # Find JSON block in response
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except json.JSONDecodeError:
            logger.warning("json_parse_failed", node_id=node.id)
        
        return {"raw_response": response, "node_id": node.id}
    
    def _generate_proposal(self, node: Any) -> MigrationProposal | None:
        """Generate a migration proposal for a node."""
        source_code = self._get_source_code(node)
        if not source_code:
            return None
        
        # Get context from migrated dependencies
        migrated_deps = [
            self.tmg.get_node(d.id)
            for d in self.tmg.get_dependencies(node.id)
            if self.tmg.get_node(d.id).state == NodeState.MIGRATED
        ]
        migrated_info = "\n".join(
            f"- {d.id}: Already migrated"
            for d in migrated_deps[:5]
        )
        
        # Build requirements from metadata
        requirements = []
        if node.metadata.get("deprecated"):
            requirements.append(
                f"Replace deprecated API with: {node.metadata.get('replacement', 'modern equivalent')}"
            )
        
        prompt = MIGRATION_PROMPT.format(
            node_id=node.id,
            original_code=source_code,
            migration_requirements="\n".join(requirements) or "Standard Java 8 to 17 migration",
            migrated_dependencies=migrated_info or "None",
        )
        
        response = self._call_llm(prompt, max_tokens=3000)
        if not response:
            return None
        
        # Parse response to extract code and confidence
        proposed_code, rationale, confidence = self._parse_migration_response(response)
        
        return MigrationProposal(
            node_id=node.id,
            original_code=source_code,
            proposed_code=proposed_code,
            confidence=confidence,
            rationale=rationale,
            deprecation_apis=node.metadata.get("deprecated_apis", []),
        )
    
    def _get_source_code(self, node: Any) -> str | None:
        """Get source code for a node from file."""
        if not node.file_path or not Path(node.file_path).exists():
            return None
        
        try:
            with open(node.file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            # If we have line numbers, extract just that portion
            if node.line_start > 0:
                # Get some context around the node
                start = max(0, node.line_start - 1)
                end = node.line_end if node.line_end > 0 else min(len(lines), start + 50)
                return "".join(lines[start:end])
            
            # Otherwise return full file (limited)
            return "".join(lines[:200])
            
        except Exception as e:
            logger.warning("source_read_failed", file=node.file_path, error=str(e))
            return None
    
    def _parse_migration_response(self, response: str) -> tuple[str, str, float]:
        """Parse LLM migration response to extract components."""
        proposed_code = ""
        rationale = ""
        confidence = 0.5
        
        # Extract code block
        import re
        code_match = re.search(r"```java\n(.*?)```", response, re.DOTALL)
        if code_match:
            proposed_code = code_match.group(1).strip()
        
        # Extract rationale
        rationale_match = re.search(r"\*\*Rationale\*\*:?\s*(.*?)(?=\*\*|$)", response, re.DOTALL)
        if rationale_match:
            rationale = rationale_match.group(1).strip()
        
        # Extract confidence
        confidence_match = re.search(r"\*\*Confidence\*\*:?\s*([\d.]+)", response)
        if confidence_match:
            try:
                confidence = float(confidence_match.group(1))
            except ValueError:
                pass
        
        return proposed_code, rationale, max(0.0, min(1.0, confidence))
    
    def transition_to_deprecated(self, node_ids: list[str]) -> int:
        """
        Transition analyzed nodes to DEPRECATED state.
        
        Args:
            node_ids: List of node IDs to transition.
            
        Returns:
            Number of nodes successfully transitioned.
        """
        count = 0
        for node_id in node_ids:
            try:
                node = self.tmg.get_node(node_id)
                if node.state == NodeState.ANALYZED:
                    self.tmg.transition_state(node_id, NodeState.DEPRECATED)
                    count += 1
            except Exception as e:
                self.logger.warning(
                    "transition_failed",
                    node_id=node_id,
                    error=str(e),
                )
        
        self.logger.info("nodes_deprecated", count=count)
        return count
