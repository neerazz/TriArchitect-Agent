"""
Typed Migration Graph (TMG) implementation.

The TMG is the central shared state mechanism that enables coordination
between the three agents (Archeologist, Architect, Validator). It provides:
- Persistent semantic state for code artifacts
- State machine transitions with validation
- Atomic batch updates with rollback support
- Serialization for persistence

Mathematical Definition:
    G = (V, E, τ, σ) where:
    - V = set of vertices (code artifacts)
    - E = set of edges (dependencies)  
    - τ : V → NodeType (type function)
    - σ : V → NodeState (state function)
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

import networkx as nx

from src.shared.logger import get_logger
from src.tmg.models import (
    VALID_TRANSITIONS,
    EdgeType,
    NodeState,
    NodeType,
    TMGEdge,
    TMGNode,
)

logger = get_logger(__name__, component="tmg")


class TMGError(Exception):
    """Base exception for TMG operations."""
    pass


class InvalidTransitionError(TMGError):
    """Raised when an invalid state transition is attempted."""
    pass


class NodeNotFoundError(TMGError):
    """Raised when a referenced node doesn't exist."""
    pass


class TypedMigrationGraph:
    """
    A directed graph representing code artifacts and their dependencies.
    
    The TMG wraps a NetworkX DiGraph with typed nodes and edges,
    providing state machine semantics and atomic batch operations.
    
    Attributes:
        graph: The underlying NetworkX directed graph.
        name: Human-readable name for this graph instance.
        source_version: Source Java version (e.g., "8").
        target_version: Target Java version (e.g., "17").
        created_at: Timestamp when the graph was created.
    
    Example:
        >>> tmg = TypedMigrationGraph(name="MyProject")
        >>> node = TMGNode(id="com.example.MyClass", name="MyClass", 
        ...                node_type=NodeType.CLASS)
        >>> tmg.add_node(node)
        >>> tmg.transition_state("com.example.MyClass", NodeState.ANALYZED)
    """
    
    def __init__(
        self,
        name: str = "migration_graph",
        source_version: str = "8",
        target_version: str = "17",
    ) -> None:
        """
        Initialize a new Typed Migration Graph.
        
        Args:
            name: Human-readable name for the graph.
            source_version: Source Java version.
            target_version: Target Java version.
        """
        self.graph: nx.DiGraph = nx.DiGraph()
        self.name = name
        self.source_version = source_version
        self.target_version = target_version
        self.created_at = datetime.now()
        self._nodes: dict[str, TMGNode] = {}
        self._edges: dict[tuple[str, str], TMGEdge] = {}
        self._rollback_stack: list[dict[str, Any]] = []
        
        logger.info(
            "initialized_tmg",
            name=name,
            source_version=source_version,
            target_version=target_version,
        )
    
    # =========================================================================
    # Node Operations
    # =========================================================================
    
    def add_node(self, node: TMGNode) -> None:
        """
        Add a node to the graph.
        
        Args:
            node: The TMGNode to add.
            
        Raises:
            ValueError: If a node with the same ID already exists.
        """
        if node.id in self._nodes:
            raise ValueError(f"Node {node.id} already exists")
        
        self._nodes[node.id] = node
        self.graph.add_node(
            node.id,
            node_type=node.node_type,
            state=node.state,
            data=node,
        )
        
        logger.debug(
            "added_node",
            node_id=node.id,
            node_type=node.node_type.name,
            state=node.state.name,
        )
    
    def get_node(self, node_id: str) -> TMGNode:
        """
        Retrieve a node by ID.
        
        Args:
            node_id: The unique identifier of the node.
            
        Returns:
            The requested TMGNode.
            
        Raises:
            NodeNotFoundError: If the node doesn't exist.
        """
        if node_id not in self._nodes:
            raise NodeNotFoundError(f"Node {node_id} not found")
        return self._nodes[node_id]
    
    def has_node(self, node_id: str) -> bool:
        """Check if a node exists in the graph."""
        return node_id in self._nodes
    
    def remove_node(self, node_id: str) -> None:
        """
        Remove a node and all its edges from the graph.
        
        Args:
            node_id: The ID of the node to remove.
        """
        if node_id in self._nodes:
            del self._nodes[node_id]
            # Remove associated edges
            edges_to_remove = [
                key for key in self._edges 
                if key[0] == node_id or key[1] == node_id
            ]
            for key in edges_to_remove:
                del self._edges[key]
            self.graph.remove_node(node_id)
            logger.debug("removed_node", node_id=node_id)
    
    def get_nodes_by_state(self, state: NodeState) -> list[TMGNode]:
        """
        Get all nodes in a specific state.
        
        Args:
            state: The NodeState to filter by.
            
        Returns:
            List of nodes in the specified state.
        """
        return [n for n in self._nodes.values() if n.state == state]
    
    def get_nodes_by_type(self, node_type: NodeType) -> list[TMGNode]:
        """
        Get all nodes of a specific type.
        
        Args:
            node_type: The NodeType to filter by.
            
        Returns:
            List of nodes of the specified type.
        """
        return [n for n in self._nodes.values() if n.node_type == node_type]
    
    # =========================================================================
    # Edge Operations
    # =========================================================================
    
    def add_edge(self, edge: TMGEdge) -> None:
        """
        Add an edge between two nodes.
        
        Args:
            edge: The TMGEdge to add.
            
        Raises:
            NodeNotFoundError: If source or target node doesn't exist.
        """
        if edge.source not in self._nodes:
            raise NodeNotFoundError(f"Source node {edge.source} not found")
        if edge.target not in self._nodes:
            raise NodeNotFoundError(f"Target node {edge.target} not found")
        
        key = (edge.source, edge.target)
        self._edges[key] = edge
        self.graph.add_edge(
            edge.source,
            edge.target,
            edge_type=edge.edge_type,
            weight=edge.weight,
            data=edge,
        )
        
        logger.debug(
            "added_edge",
            source=edge.source,
            target=edge.target,
            edge_type=edge.edge_type.name,
        )
    
    def get_edge(self, source: str, target: str) -> TMGEdge | None:
        """Get an edge between two nodes, or None if not found."""
        return self._edges.get((source, target))
    
    def get_dependencies(self, node_id: str) -> list[TMGNode]:
        """
        Get all nodes that the specified node depends on.
        
        Args:
            node_id: The ID of the node to query.
            
        Returns:
            List of nodes that are dependencies (outgoing edges).
        """
        if node_id not in self._nodes:
            return []
        return [self._nodes[n] for n in self.graph.successors(node_id)]
    
    def get_dependents(self, node_id: str) -> list[TMGNode]:
        """
        Get all nodes that depend on the specified node.
        
        Args:
            node_id: The ID of the node to query.
            
        Returns:
            List of nodes that are dependents (incoming edges).
        """
        if node_id not in self._nodes:
            return []
        return [self._nodes[n] for n in self.graph.predecessors(node_id)]
    
    # =========================================================================
    # State Transitions
    # =========================================================================
    
    def transition_state(
        self,
        node_id: str,
        new_state: NodeState,
        metadata_update: dict[str, Any] | None = None,
    ) -> None:
        """
        Transition a node to a new state.
        
        Validates that the transition is legal according to the
        state machine rules before applying.
        
        Args:
            node_id: The ID of the node to transition.
            new_state: The target state.
            metadata_update: Optional metadata to merge.
            
        Raises:
            NodeNotFoundError: If the node doesn't exist.
            InvalidTransitionError: If the transition is not valid.
        """
        node = self.get_node(node_id)
        old_state = node.state
        
        if not node.can_transition_to(new_state):
            raise InvalidTransitionError(
                f"Cannot transition {node_id} from {old_state.name} to {new_state.name}. "
                f"Valid transitions: {[s.name for s in VALID_TRANSITIONS.get(old_state, set())]}"
            )
        
        # Apply transition
        node.state = new_state
        node.updated_at = datetime.now()
        if metadata_update:
            node.metadata.update(metadata_update)
        
        # Update graph data
        self.graph.nodes[node_id]["state"] = new_state
        self.graph.nodes[node_id]["data"] = node
        
        logger.info(
            "state_transition",
            node_id=node_id,
            old_state=old_state.name,
            new_state=new_state.name,
        )
    
    def batch_transition(
        self,
        node_ids: list[str],
        new_state: NodeState,
    ) -> dict[str, bool]:
        """
        Attempt to transition multiple nodes atomically.
        
        If any transition fails, all transitions are rolled back.
        
        Args:
            node_ids: List of node IDs to transition.
            new_state: The target state for all nodes.
            
        Returns:
            Dict mapping node_id to success (True) or failure (False).
        """
        results: dict[str, bool] = {}
        successful: list[tuple[str, NodeState]] = []
        
        for node_id in node_ids:
            try:
                node = self.get_node(node_id)
                old_state = node.state
                self.transition_state(node_id, new_state)
                successful.append((node_id, old_state))
                results[node_id] = True
            except (NodeNotFoundError, InvalidTransitionError) as e:
                results[node_id] = False
                logger.warning(
                    "batch_transition_failed",
                    node_id=node_id,
                    error=str(e),
                )
                # Rollback successful transitions
                for rolled_id, old_state in successful:
                    node = self._nodes[rolled_id]
                    node.state = old_state
                    node.updated_at = datetime.now()
                    self.graph.nodes[rolled_id]["state"] = old_state
                logger.info(
                    "batch_rollback",
                    rolled_back_count=len(successful),
                )
                break
        
        return results
    
    # =========================================================================
    # Graph Analysis
    # =========================================================================
    
    def get_migration_order(self) -> list[str]:
        """
        Get the topological order for migration.
        
        Returns nodes in dependency order (dependencies first),
        which is crucial for avoiding hallucination issues.
        
        Returns:
            List of node IDs in migration order.
            
        Raises:
            TMGError: If the graph has cycles.
        """
        try:
            return list(nx.topological_sort(self.graph))
        except nx.NetworkXUnfeasible as e:
            raise TMGError(f"Graph has cycles: {e}")
    
    def find_cycles(self) -> list[list[str]]:
        """
        Find all cycles in the dependency graph.
        
        Cycles are a major source of LLM hallucination as they
        cause context loss. This method identifies them for handling.
        
        Returns:
            List of cycles (each cycle is a list of node IDs).
        """
        try:
            cycles = list(nx.simple_cycles(self.graph))
            if cycles:
                logger.warning("cycles_detected", cycle_count=len(cycles))
            return cycles
        except Exception:
            return []
    
    def get_strongly_connected_components(self) -> list[set[str]]:
        """
        Get strongly connected components (potential problem areas).
        
        Returns:
            List of sets, each containing node IDs in a component.
        """
        return [set(c) for c in nx.strongly_connected_components(self.graph)]
    
    # =========================================================================
    # Statistics
    # =========================================================================
    
    def get_stats(self) -> dict[str, Any]:
        """
        Get statistics about the graph.
        
        Returns:
            Dictionary with various graph metrics.
        """
        state_counts = {}
        type_counts = {}
        
        for node in self._nodes.values():
            state_counts[node.state.name] = state_counts.get(node.state.name, 0) + 1
            type_counts[node.node_type.name] = type_counts.get(node.node_type.name, 0) + 1
        
        return {
            "name": self.name,
            "node_count": len(self._nodes),
            "edge_count": len(self._edges),
            "state_distribution": state_counts,
            "type_distribution": type_counts,
            "is_dag": nx.is_directed_acyclic_graph(self.graph),
            "cycle_count": len(self.find_cycles()),
            "source_version": self.source_version,
            "target_version": self.target_version,
        }
    
    # =========================================================================
    # Serialization
    # =========================================================================
    
    def to_dict(self) -> dict[str, Any]:
        """
        Serialize the entire graph to a dictionary.
        
        Returns:
            Dictionary representation of the graph.
        """
        return {
            "name": self.name,
            "source_version": self.source_version,
            "target_version": self.target_version,
            "created_at": self.created_at.isoformat(),
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "edges": [e.to_dict() for e in self._edges.values()],
        }
    
    def save(self, path: str | Path) -> None:
        """
        Save the graph to a JSON file.
        
        Args:
            path: File path to save to.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info("graph_saved", path=str(path))
    
    @classmethod
    def load(cls, path: str | Path) -> "TypedMigrationGraph":
        """
        Load a graph from a JSON file.
        
        Args:
            path: File path to load from.
            
        Returns:
            Reconstructed TypedMigrationGraph instance.
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        graph = cls(
            name=data["name"],
            source_version=data.get("source_version", "8"),
            target_version=data.get("target_version", "17"),
        )
        graph.created_at = datetime.fromisoformat(data["created_at"])
        
        # Restore nodes
        for node_data in data["nodes"]:
            node = TMGNode.from_dict(node_data)
            graph.add_node(node)
        
        # Restore edges
        for edge_data in data["edges"]:
            edge = TMGEdge.from_dict(edge_data)
            graph.add_edge(edge)
        
        logger.info("graph_loaded", path=str(path), node_count=len(graph._nodes))
        return graph
    
    # =========================================================================
    # Iteration
    # =========================================================================
    
    def __iter__(self) -> Iterator[TMGNode]:
        """Iterate over all nodes in the graph."""
        return iter(self._nodes.values())
    
    def __len__(self) -> int:
        """Return the number of nodes in the graph."""
        return len(self._nodes)
    
    def __repr__(self) -> str:
        return f"TypedMigrationGraph(name={self.name!r}, nodes={len(self._nodes)}, edges={len(self._edges)})"
