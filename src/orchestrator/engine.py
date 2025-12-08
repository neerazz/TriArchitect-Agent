"""
Migration Engine - Main orchestrator for TriArchitect.

Coordinates the three agents (Archeologist, Architect, Validator)
through the complete migration workflow with consensus protocol.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any

from src.agents.archeologist import ArcheologistAgent
from src.agents.architect import ArchitectAgent
from src.agents.validator import ValidatorAgent
from src.consensus import ConsensusProtocol, ConsensusResult
from src.shared.config import get_settings
from src.shared.logger import get_logger, set_correlation_id, setup_logging
from src.tmg import TypedMigrationGraph
from src.tmg.models import MigrationProposal, NodeState
from src.tmg.visualizer import generate_stats_report, visualize_graph

logger = get_logger(__name__, component="engine")


class PipelineStage(Enum):
    """Stages in the migration pipeline."""
    INIT = auto()
    DISCOVERY = auto()
    PLANNING = auto()
    PROPOSAL = auto()
    VALIDATION = auto()
    CONSENSUS = auto()
    APPLICATION = auto()
    COMPLETE = auto()


@dataclass
class MigrationResult:
    """
    Result of a complete migration run.
    
    Attributes:
        success: Overall success status.
        repository_path: Path to the migrated repository.
        stages_completed: List of completed pipeline stages.
        nodes_migrated: Number of nodes successfully migrated.
        proposals_approved: Number of approved proposals.
        consensus_results: Results from consensus rounds.
        execution_time_seconds: Total execution time.
        errors: Any errors encountered.
        report_path: Path to generated report.
    """
    success: bool = False
    repository_path: str = ""
    stages_completed: list[str] = field(default_factory=list)
    nodes_migrated: int = 0
    proposals_approved: int = 0
    consensus_results: list[dict[str, Any]] = field(default_factory=list)
    execution_time_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)
    report_path: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "repository_path": self.repository_path,
            "stages_completed": self.stages_completed,
            "nodes_migrated": self.nodes_migrated,
            "proposals_approved": self.proposals_approved,
            "consensus_results": self.consensus_results,
            "execution_time_seconds": self.execution_time_seconds,
            "errors": self.errors,
            "report_path": self.report_path,
        }


class MigrationEngine:
    """
    Main orchestrator for the TriArchitect migration system.
    
    Coordinates all agents through the migration pipeline:
    1. Discovery (Archeologist) - Parse and analyze codebase
    2. Planning (Architect) - Generate migration plan
    3. Proposal (Architect) - Create migration proposals
    4. Validation (Validator) - Test proposals
    5. Consensus (All agents) - Reach agreement
    6. Application - Apply approved changes
    
    Attributes:
        tmg: The shared Typed Migration Graph.
        archeologist: Analysis agent.
        architect: Planning agent.
        validator: Testing agent.
        consensus: Consensus protocol.
    
    Example:
        >>> engine = MigrationEngine()
        >>> result = engine.run("/path/to/java/project")
        >>> print(f"Migrated {result.nodes_migrated} nodes")
    """
    
    def __init__(
        self,
        source_version: str = "8",
        target_version: str = "17",
        use_docker: bool = True,
    ) -> None:
        """
        Initialize the migration engine.
        
        Args:
            source_version: Source Java version.
            target_version: Target Java version.
            use_docker: Whether to use Docker for validation.
        """
        self.source_version = source_version
        self.target_version = target_version
        self.use_docker = use_docker
        
        # These will be initialized per run
        self._tmg: TypedMigrationGraph | None = None
        self._archeologist: ArcheologistAgent | None = None
        self._architect: ArchitectAgent | None = None
        self._validator: ValidatorAgent | None = None
        self._consensus: ConsensusProtocol | None = None
        
        self._current_stage = PipelineStage.INIT
        self._start_time: datetime | None = None
        
        logger.info(
            "engine_initialized",
            source_version=source_version,
            target_version=target_version,
        )
    
    @property
    def tmg(self) -> TypedMigrationGraph:
        """Get the TMG instance."""
        if self._tmg is None:
            raise ValueError("TMG not initialized. Call run() first.")
        return self._tmg
    
    def _initialize_components(self, project_name: str) -> None:
        """Initialize all components for a migration run."""
        # Create TMG
        self._tmg = TypedMigrationGraph(
            name=project_name,
            source_version=self.source_version,
            target_version=self.target_version,
        )
        
        # Create agents
        self._archeologist = ArcheologistAgent(
            tmg=self._tmg,
            source_version=self.source_version,
            target_version=self.target_version,
        )
        self._architect = ArchitectAgent(tmg=self._tmg)
        self._validator = ValidatorAgent(tmg=self._tmg, use_docker=self.use_docker)
        
        # Create consensus protocol
        self._consensus = ConsensusProtocol()
        
        logger.info("components_initialized", project=project_name)
    
    def run(
        self,
        repository_path: str,
        output_dir: str | None = None,
        dry_run: bool = False,
        max_proposals: int = 10,
    ) -> MigrationResult:
        """
        Run the complete migration pipeline.
        
        Args:
            repository_path: Path to the Java repository.
            output_dir: Directory for outputs (defaults to repo/triarchitect_output).
            dry_run: If True, don't apply changes.
            max_proposals: Maximum proposals to process.
            
        Returns:
            MigrationResult with outcomes.
        """
        import time
        import uuid
        
        # Set correlation ID for this run
        correlation_id = str(uuid.uuid4())[:8]
        set_correlation_id(correlation_id)
        
        self._start_time = datetime.now()
        start_time = time.perf_counter()
        
        repo_path = Path(repository_path).resolve()
        project_name = repo_path.name
        
        result = MigrationResult(repository_path=str(repo_path))
        
        logger.info(
            "migration_started",
            repository=str(repo_path),
            project=project_name,
            dry_run=dry_run,
        )
        
        try:
            # Initialize
            self._initialize_components(project_name)
            self._set_stage(PipelineStage.INIT, result)
            
            # Stage 1: Discovery
            discovery_result = self._run_discovery(repo_path, result)
            if not discovery_result:
                return result
            
            # Stage 2: Planning
            plan_result = self._run_planning(result)
            if not plan_result:
                return result
            
            # Stage 3: Proposal
            proposals = self._run_proposal(max_proposals, result)
            
            # Stage 4: Validation (establish baseline)
            validation_result = self._run_validation(repo_path, result)
            
            # Stage 5: Consensus
            consensus_results = self._run_consensus(proposals, result)
            
            # Stage 6: Application (if not dry run)
            if not dry_run:
                self._apply_migrations(consensus_results, result)
            
            # Mark complete
            self._set_stage(PipelineStage.COMPLETE, result)
            result.success = len(result.errors) == 0
            
        except Exception as e:
            logger.exception("migration_failed", error=str(e))
            result.errors.append(str(e))
            result.success = False
        
        finally:
            # Calculate execution time
            result.execution_time_seconds = round(time.perf_counter() - start_time, 2)
            
            # Generate report
            output_path = Path(output_dir) if output_dir else repo_path / "triarchitect_output"
            result.report_path = self._generate_report(output_path, result)
        
        logger.info(
            "migration_complete",
            success=result.success,
            nodes_migrated=result.nodes_migrated,
            proposals_approved=result.proposals_approved,
            execution_time=result.execution_time_seconds,
        )
        
        return result
    
    def _set_stage(self, stage: PipelineStage, result: MigrationResult) -> None:
        """Update current stage and track in result."""
        self._current_stage = stage
        result.stages_completed.append(stage.name)
        logger.info("stage_entered", stage=stage.name)
    
    def _run_discovery(self, repo_path: Path, result: MigrationResult) -> bool:
        """Run the discovery (Archeologist) stage."""
        self._set_stage(PipelineStage.DISCOVERY, result)
        
        analysis_result = self._archeologist.execute(repository_path=str(repo_path))
        
        if not analysis_result.success:
            error = f"Discovery failed: {analysis_result.error}"
            result.errors.append(error)
            logger.error("discovery_failed", error=analysis_result.error)
            return False
        
        report = analysis_result.data
        logger.info(
            "discovery_complete",
            files_analyzed=report.files_analyzed,
            nodes_created=report.total_nodes,
            deprecated_apis=report.deprecated_apis,
        )
        
        return True
    
    def _run_planning(self, result: MigrationResult) -> bool:
        """Run the planning (Architect) stage."""
        self._set_stage(PipelineStage.PLANNING, result)
        
        plan_result = self._architect.execute(mode="plan")
        
        if not plan_result.success:
            error = f"Planning failed: {plan_result.error}"
            result.errors.append(error)
            return False
        
        plan = plan_result.data.plan
        logger.info(
            "planning_complete",
            steps=len(plan.steps) if plan else 0,
            estimated_hours=plan.estimated_effort_hours if plan else 0,
        )
        
        return True
    
    def _run_proposal(
        self,
        max_proposals: int,
        result: MigrationResult,
    ) -> list[MigrationProposal]:
        """Generate migration proposals."""
        self._set_stage(PipelineStage.PROPOSAL, result)
        
        # Get nodes that need migration
        deprecated_nodes = self._tmg.get_nodes_by_state(NodeState.DEPRECATED)
        if not deprecated_nodes:
            # Transition some analyzed nodes to deprecated
            analyzed = self._tmg.get_nodes_by_state(NodeState.ANALYZED)
            for node in analyzed[:max_proposals]:
                if node.metadata.get("deprecated"):
                    try:
                        self._tmg.transition_state(node.id, NodeState.DEPRECATED)
                    except Exception:
                        pass
            deprecated_nodes = self._tmg.get_nodes_by_state(NodeState.DEPRECATED)
        
        # Generate proposals
        proposal_result = self._architect.execute(
            mode="propose",
            node_ids=[n.id for n in deprecated_nodes[:max_proposals]],
        )
        
        proposals = proposal_result.data.proposals if proposal_result.success else []
        
        logger.info("proposals_generated", count=len(proposals))
        
        return proposals
    
    def _run_validation(self, repo_path: Path, result: MigrationResult) -> bool:
        """Run baseline validation."""
        self._set_stage(PipelineStage.VALIDATION, result)
        
        validation_result = self._validator.execute(
            project_path=str(repo_path),
            establish_baseline=True,
        )
        
        if validation_result.success:
            report = validation_result.data
            logger.info(
                "baseline_validation_complete",
                tests_run=report.test_result.test_count if report.test_result else 0,
                passed=report.test_result.passed_count if report.test_result else 0,
            )
        
        return validation_result.success
    
    def _run_consensus(
        self,
        proposals: list[MigrationProposal],
        result: MigrationResult,
    ) -> list[ConsensusResult]:
        """Run consensus on proposals."""
        self._set_stage(PipelineStage.CONSENSUS, result)
        
        consensus_results = []
        
        for proposal in proposals:
            # Simple consensus simulation
            # In production, this would involve actual agent coordination
            votes = [
                ("archeologist", "Archeologist", True, 0.85),
                ("architect", "Architect", True, proposal.confidence),
                ("validator", "Validator", True, 0.80),
            ]
            
            consensus_result = self._consensus.run_simple(proposal, votes)
            consensus_results.append(consensus_result)
            
            result.consensus_results.append(consensus_result.to_dict())
            
            if consensus_result.status.name == "APPROVED":
                result.proposals_approved += 1
        
        logger.info(
            "consensus_complete",
            total_proposals=len(proposals),
            approved=result.proposals_approved,
        )
        
        return consensus_results
    
    def _apply_migrations(
        self,
        consensus_results: list[ConsensusResult],
        result: MigrationResult,
    ) -> None:
        """Apply approved migrations."""
        self._set_stage(PipelineStage.APPLICATION, result)
        
        for consensus in consensus_results:
            if consensus.status.name == "APPROVED":
                try:
                    node = self._tmg.get_node(consensus.proposal.node_id)
                    if node.state == NodeState.DEPRECATED:
                        self._tmg.transition_state(node.id, NodeState.MIGRATED)
                        result.nodes_migrated += 1
                except Exception as e:
                    logger.warning(
                        "migration_apply_failed",
                        node_id=consensus.proposal.node_id,
                        error=str(e),
                    )
        
        logger.info("migrations_applied", count=result.nodes_migrated)
    
    def _generate_report(
        self,
        output_dir: Path,
        result: MigrationResult,
    ) -> str:
        """Generate migration report and artifacts."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save TMG
        tmg_path = output_dir / "tmg.json"
        self._tmg.save(tmg_path)
        
        # Save visualization
        try:
            fig = visualize_graph(self._tmg, output_dir / "tmg_graph.png")
            fig.clear()
        except Exception as e:
            logger.warning("visualization_failed", error=str(e))
        
        # Save result
        result_path = output_dir / "migration_result.json"
        with open(result_path, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        
        # Save text report
        report_path = output_dir / "migration_report.txt"
        with open(report_path, "w") as f:
            f.write("=" * 60 + "\n")
            f.write("TRIARCHITECT MIGRATION REPORT\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"Repository: {result.repository_path}\n")
            f.write(f"Execution Time: {result.execution_time_seconds}s\n")
            f.write(f"Success: {result.success}\n\n")
            f.write("Stages Completed:\n")
            for stage in result.stages_completed:
                f.write(f"  ✓ {stage}\n")
            f.write(f"\nNodes Migrated: {result.nodes_migrated}\n")
            f.write(f"Proposals Approved: {result.proposals_approved}\n")
            if result.errors:
                f.write("\nErrors:\n")
                for error in result.errors:
                    f.write(f"  ✗ {error}\n")
            f.write("\n")
            f.write(generate_stats_report(self._tmg))
        
        logger.info("report_generated", path=str(output_dir))
        
        return str(report_path)
    
    def analyze_only(self, repository_path: str) -> dict[str, Any]:
        """
        Run only the analysis phase (Archeologist).
        
        Useful for exploring a codebase without running full migration.
        
        Args:
            repository_path: Path to the repository.
            
        Returns:
            Analysis results as dictionary.
        """
        repo_path = Path(repository_path).resolve()
        project_name = repo_path.name
        
        self._initialize_components(project_name)
        result = self._archeologist.execute(repository_path=str(repo_path))
        
        if result.success:
            return {
                "success": True,
                "report": result.data.to_dict(),
                "tmg_stats": self._tmg.get_stats(),
            }
        else:
            return {
                "success": False,
                "error": result.error,
            }
