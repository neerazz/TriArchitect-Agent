"""
Data models for the Typed Migration Graph (TMG).

This module defines the core data structures used to represent code artifacts
and their relationships in the migration graph. The TMG is the shared state
mechanism that enables coordination between the three agents.

Mathematical Definition:
    G = (V, E, τ, σ) where:
    - V = set of vertices (code artifacts)
    - E = set of edges (dependencies)
    - τ = type function (NodeType)
    - σ = state function (NodeState)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any


class NodeType(Enum):
    """
    Classification of code artifact nodes in the TMG.
    
    Each node in the graph represents a distinct code element with
    a specific type that determines how it should be processed.
    
    Attributes:
        CLASS: A Java class declaration.
        INTERFACE: A Java interface declaration.
        METHOD: A method within a class/interface.
        FIELD: A field/member variable.
        IMPORT: An import statement.
        PACKAGE: A package declaration.
        CONFIG: Configuration file (pom.xml, properties).
        ANNOTATION: Annotation type definition.
    """
    CLASS = auto()
    INTERFACE = auto()
    METHOD = auto()
    FIELD = auto()
    IMPORT = auto()
    PACKAGE = auto()
    CONFIG = auto()
    ANNOTATION = auto()


class EdgeType(Enum):
    """
    Classification of relationships between code artifacts.
    
    Edges represent dependencies and relationships in the codebase.
    These are crucial for determining migration order and detecting
    circular dependencies that could cause hallucination issues.
    
    Attributes:
        SYNTACTIC: Import/include relationships.
        SEMANTIC: Method calls, field access.
        INHERITANCE: Extends/implements relationships.
        ANNOTATION: Annotation usage.
        CONFIGURATION: Build/config references.
    """
    SYNTACTIC = auto()       # E_syntactic: imports, includes
    SEMANTIC = auto()        # E_semantic: method calls, field access
    INHERITANCE = auto()     # extends/implements
    ANNOTATION = auto()      # annotation usage
    CONFIGURATION = auto()   # pom.xml references, properties


class NodeState(Enum):
    """
    Migration state machine for code artifacts.
    
    Each node transitions through states as the migration progresses.
    Valid transitions: UNPROCESSED → ANALYZED → DEPRECATED → MIGRATED
    
    State Transition Diagram:
        UNPROCESSED ──────► ANALYZED ──────► DEPRECATED ──────► MIGRATED
             │                                    │                 │
             └────────────────────────────────────┴─────► FAILED ◄──┘
    
    Attributes:
        UNPROCESSED: Initial state, not yet analyzed.
        ANALYZED: Analyzed by Archeologist, dependencies mapped.
        DEPRECATED: Marked for migration, old API identified.
        MIGRATED: Successfully migrated and verified.
        FAILED: Migration failed, requires manual intervention.
    """
    UNPROCESSED = auto()
    ANALYZED = auto()
    DEPRECATED = auto()
    MIGRATED = auto()
    FAILED = auto()


# Valid state transitions
VALID_TRANSITIONS: dict[NodeState, set[NodeState]] = {
    NodeState.UNPROCESSED: {NodeState.ANALYZED, NodeState.FAILED},
    NodeState.ANALYZED: {NodeState.DEPRECATED, NodeState.FAILED},
    NodeState.DEPRECATED: {NodeState.MIGRATED, NodeState.FAILED},
    NodeState.MIGRATED: set(),  # Terminal state
    NodeState.FAILED: {NodeState.UNPROCESSED},  # Can retry
}


@dataclass
class TMGNode:
    """
    A vertex in the Typed Migration Graph representing a code artifact.
    
    Nodes are the fundamental units of the TMG, each representing a
    distinct code element (class, method, etc.) with its migration state.
    
    Attributes:
        id: Unique identifier for the node (typically fully-qualified name).
        name: Human-readable name of the artifact.
        node_type: The type classification of this artifact.
        state: Current migration state.
        file_path: Absolute path to the source file.
        line_start: Starting line number in the file.
        line_end: Ending line number in the file.
        source_version: Original Java version (e.g., "8").
        target_version: Target Java version (e.g., "17").
        metadata: Additional context-specific data.
        created_at: Timestamp when the node was created.
        updated_at: Timestamp of last state change.
    
    Example:
        >>> node = TMGNode(
        ...     id="com.example.MyClass",
        ...     name="MyClass",
        ...     node_type=NodeType.CLASS,
        ...     state=NodeState.UNPROCESSED,
        ...     file_path="/path/to/MyClass.java"
        ... )
    """
    id: str
    name: str
    node_type: NodeType
    state: NodeState = NodeState.UNPROCESSED
    file_path: str = ""
    line_start: int = 0
    line_end: int = 0
    source_version: str = "8"
    target_version: str = "17"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def can_transition_to(self, new_state: NodeState) -> bool:
        """
        Check if a state transition is valid.
        
        Args:
            new_state: The proposed new state.
            
        Returns:
            True if the transition is valid, False otherwise.
        """
        return new_state in VALID_TRANSITIONS.get(self.state, set())
    
    def to_dict(self) -> dict[str, Any]:
        """
        Serialize node to dictionary for JSON export.
        
        Returns:
            Dictionary representation of the node.
        """
        return {
            "id": self.id,
            "name": self.name,
            "node_type": self.node_type.name,
            "state": self.state.name,
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "source_version": self.source_version,
            "target_version": self.target_version,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TMGNode":
        """
        Deserialize node from dictionary.
        
        Args:
            data: Dictionary representation of a node.
            
        Returns:
            Reconstructed TMGNode instance.
        """
        return cls(
            id=data["id"],
            name=data["name"],
            node_type=NodeType[data["node_type"]],
            state=NodeState[data["state"]],
            file_path=data.get("file_path", ""),
            line_start=data.get("line_start", 0),
            line_end=data.get("line_end", 0),
            source_version=data.get("source_version", "8"),
            target_version=data.get("target_version", "17"),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )


@dataclass
class TMGEdge:
    """
    An edge in the Typed Migration Graph representing a dependency.
    
    Edges connect nodes to represent various types of relationships,
    from syntactic (imports) to semantic (method calls).
    
    Attributes:
        source: ID of the source node.
        target: ID of the target node.
        edge_type: Classification of the relationship.
        weight: Importance/strength of the dependency (0.0-1.0).
        metadata: Additional context-specific data.
    
    Example:
        >>> edge = TMGEdge(
        ...     source="com.example.ServiceA",
        ...     target="com.example.ServiceB",
        ...     edge_type=EdgeType.SEMANTIC,
        ...     metadata={"method": "callService"}
        ... )
    """
    source: str
    target: str
    edge_type: EdgeType
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """
        Serialize edge to dictionary for JSON export.
        
        Returns:
            Dictionary representation of the edge.
        """
        return {
            "source": self.source,
            "target": self.target,
            "edge_type": self.edge_type.name,
            "weight": self.weight,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TMGEdge":
        """
        Deserialize edge from dictionary.
        
        Args:
            data: Dictionary representation of an edge.
            
        Returns:
            Reconstructed TMGEdge instance.
        """
        return cls(
            source=data["source"],
            target=data["target"],
            edge_type=EdgeType[data["edge_type"]],
            weight=data.get("weight", 1.0),
            metadata=data.get("metadata", {}),
        )


@dataclass
class MigrationProposal:
    """
    A proposed code migration generated by the Architect agent.
    
    Represents a specific change to be made to a code artifact,
    including the original and proposed new code.
    
    Attributes:
        node_id: ID of the node being modified.
        original_code: The original code snippet.
        proposed_code: The proposed migrated code.
        confidence: Agent's confidence in the proposal (0.0-1.0).
        rationale: Explanation for the proposed change.
        deprecation_apis: List of deprecated APIs being replaced.
        new_apis: List of new APIs being used.
    """
    node_id: str
    original_code: str
    proposed_code: str
    confidence: float
    rationale: str
    deprecation_apis: list[str] = field(default_factory=list)
    new_apis: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize proposal to dictionary."""
        return {
            "node_id": self.node_id,
            "original_code": self.original_code,
            "proposed_code": self.proposed_code,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "deprecation_apis": self.deprecation_apis,
            "new_apis": self.new_apis,
        }
