"""
Migration planning utilities for the Architect agent.

Provides algorithms for determining migration order and
generating migration plans based on TMG analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.shared.logger import get_logger
from src.tmg import TypedMigrationGraph
from src.tmg.models import NodeState, NodeType

logger = get_logger(__name__, component="planner")


@dataclass
class MigrationStep:
    """
    A single step in the migration plan.
    
    Attributes:
        order: Execution order (1-based).
        node_id: ID of the node to migrate.
        node_type: Type of the artifact.
        dependencies: IDs of nodes this depends on.
        priority: Priority level (higher = more urgent).
        estimated_complexity: Estimated migration complexity (1-10).
        notes: Additional notes or warnings.
    """
    order: int
    node_id: str
    node_type: NodeType
    dependencies: list[str] = field(default_factory=list)
    priority: int = 5
    estimated_complexity: int = 5
    notes: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "order": self.order,
            "node_id": self.node_id,
            "node_type": self.node_type.name,
            "dependencies": self.dependencies,
            "priority": self.priority,
            "estimated_complexity": self.estimated_complexity,
            "notes": self.notes,
        }


@dataclass
class MigrationPlan:
    """
    Complete migration plan for a codebase.
    
    Attributes:
        name: Plan name/identifier.
        source_version: Source Java version.
        target_version: Target Java version.
        steps: Ordered list of migration steps.
        total_nodes: Total nodes to migrate.
        estimated_effort_hours: Rough effort estimate.
        warnings: Any warnings or concerns.
    """
    name: str
    source_version: str
    target_version: str
    steps: list[MigrationStep] = field(default_factory=list)
    total_nodes: int = 0
    estimated_effort_hours: float = 0.0
    warnings: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "source_version": self.source_version,
            "target_version": self.target_version,
            "steps": [s.to_dict() for s in self.steps],
            "total_nodes": self.total_nodes,
            "estimated_effort_hours": self.estimated_effort_hours,
            "warnings": self.warnings,
        }


class MigrationPlanner:
    """
    Generates migration plans based on TMG analysis.
    
    Uses topological sorting and priority analysis to determine
    the optimal order for migrating code artifacts.
    
    Attributes:
        tmg: The Typed Migration Graph to analyze.
    
    Example:
        >>> planner = MigrationPlanner(tmg)
        >>> plan = planner.generate_plan()
        >>> for step in plan.steps[:5]:
        ...     print(f"{step.order}. {step.node_id}")
    """
    
    # Complexity estimates by node type
    COMPLEXITY_WEIGHTS: dict[NodeType, int] = {
        NodeType.CLASS: 7,
        NodeType.INTERFACE: 5,
        NodeType.METHOD: 4,
        NodeType.FIELD: 2,
        NodeType.IMPORT: 1,
        NodeType.PACKAGE: 1,
        NodeType.CONFIG: 6,
        NodeType.ANNOTATION: 3,
    }
    
    def __init__(self, tmg: TypedMigrationGraph) -> None:
        """
        Initialize the planner.
        
        Args:
            tmg: The TMG to analyze.
        """
        self.tmg = tmg
    
    def generate_plan(
        self,
        include_states: list[NodeState] | None = None,
    ) -> MigrationPlan:
        """
        Generate a migration plan based on TMG analysis.
        
        Args:
            include_states: Only include nodes in these states.
                           Defaults to [ANALYZED, DEPRECATED].
        
        Returns:
            A complete MigrationPlan.
        """
        if include_states is None:
            include_states = [NodeState.ANALYZED, NodeState.DEPRECATED]
        
        plan = MigrationPlan(
            name=f"Migration Plan: {self.tmg.name}",
            source_version=self.tmg.source_version,
            target_version=self.tmg.target_version,
        )
        
        # Check for cycles first
        cycles = self.tmg.find_cycles()
        if cycles:
            plan.warnings.append(
                f"WARNING: {len(cycles)} dependency cycles detected. "
                "These may cause migration issues."
            )
            for cycle in cycles[:3]:
                plan.warnings.append(f"  Cycle: {' -> '.join(cycle)}")
        
        # Get nodes to migrate
        nodes_to_migrate = []
        for state in include_states:
            nodes_to_migrate.extend(self.tmg.get_nodes_by_state(state))
        
        plan.total_nodes = len(nodes_to_migrate)
        
        if plan.total_nodes == 0:
            logger.info("no_nodes_to_migrate")
            return plan
        
        # Get topological order
        try:
            topo_order = self.tmg.get_migration_order()
        except Exception as e:
            logger.warning("topological_sort_failed", error=str(e))
            # Fallback to simple ordering
            topo_order = [n.id for n in nodes_to_migrate]
            plan.warnings.append(
                "Could not determine optimal order due to cycles. "
                "Using discovery order instead."
            )
        
        # Build steps based on topological order
        order = 1
        node_ids_to_migrate = {n.id for n in nodes_to_migrate}
        
        for node_id in topo_order:
            if node_id not in node_ids_to_migrate:
                continue
            
            node = self.tmg.get_node(node_id)
            
            # Get dependencies that need to be migrated first
            deps = self.tmg.get_dependencies(node_id)
            dep_ids = [
                d.id for d in deps 
                if d.id in node_ids_to_migrate and d.state in include_states
            ]
            
            # Calculate priority
            priority = self._calculate_priority(node)
            
            # Estimate complexity
            complexity = self._estimate_complexity(node)
            
            # Generate notes
            notes = self._generate_notes(node)
            
            step = MigrationStep(
                order=order,
                node_id=node_id,
                node_type=node.node_type,
                dependencies=dep_ids,
                priority=priority,
                estimated_complexity=complexity,
                notes=notes,
            )
            plan.steps.append(step)
            order += 1
        
        # Estimate total effort
        plan.estimated_effort_hours = self._estimate_effort(plan.steps)
        
        logger.info(
            "plan_generated",
            total_steps=len(plan.steps),
            estimated_hours=plan.estimated_effort_hours,
            warnings=len(plan.warnings),
        )
        
        return plan
    
    def _calculate_priority(self, node: Any) -> int:
        """
        Calculate migration priority for a node.
        
        Higher priority = should be migrated earlier (within constraints).
        """
        priority = 5  # Default
        
        # Deprecated APIs get higher priority
        if node.metadata.get("deprecated"):
            priority += 3
        
        # More dependents = higher priority (blocking others)
        dependents = self.tmg.get_dependents(node.id)
        priority += min(len(dependents), 3)
        
        return min(priority, 10)
    
    def _estimate_complexity(self, node: Any) -> int:
        """
        Estimate migration complexity for a node.
        """
        base = self.COMPLEXITY_WEIGHTS.get(node.node_type, 5)
        
        # Adjust based on metadata
        if node.metadata.get("deprecated"):
            base += 2
        
        if node.metadata.get("calls"):
            base += len(node.metadata["calls"]) // 5
        
        return min(base, 10)
    
    def _generate_notes(self, node: Any) -> str:
        """
        Generate migration notes for a node.
        """
        notes = []
        
        if node.metadata.get("deprecated"):
            replacement = node.metadata.get("replacement", "unknown")
            notes.append(f"Uses deprecated API. Replacement: {replacement}")
        
        if node.metadata.get("extends"):
            notes.append(f"Extends: {node.metadata['extends']}")
        
        if node.metadata.get("implements"):
            notes.append(f"Implements: {', '.join(node.metadata['implements'])}")
        
        return "; ".join(notes) if notes else ""
    
    def _estimate_effort(self, steps: list[MigrationStep]) -> float:
        """
        Estimate total effort in hours.
        
        Rough heuristic: complexity * factor, summed across all steps.
        """
        total = 0.0
        for step in steps:
            # Base: 0.1 hours per complexity point
            total += step.estimated_complexity * 0.1
        
        return round(total, 1)
