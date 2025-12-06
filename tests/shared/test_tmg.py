"""
Unit tests for the Typed Migration Graph (TMG).
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.shared.tmg import TypedMigrationGraph
from src.shared.tmg.graph import InvalidTransitionError, NodeNotFoundError
from src.shared.tmg.models import (
    EdgeType,
    NodeState,
    NodeType,
    TMGEdge,
    TMGNode,
)


class TestTMGNode:
    """Tests for TMGNode dataclass."""
    
    def test_create_node(self):
        """Test basic node creation."""
        node = TMGNode(
            id="com.example.Test",
            name="Test",
            node_type=NodeType.CLASS,
        )
        assert node.id == "com.example.Test"
        assert node.name == "Test"
        assert node.node_type == NodeType.CLASS
        assert node.state == NodeState.UNPROCESSED
    
    def test_can_transition_to_valid(self):
        """Test valid state transitions."""
        node = TMGNode(
            id="test",
            name="test",
            node_type=NodeType.CLASS,
            state=NodeState.UNPROCESSED,
        )
        assert node.can_transition_to(NodeState.ANALYZED)
        assert not node.can_transition_to(NodeState.MIGRATED)
    
    def test_node_serialization(self):
        """Test node to/from dict."""
        node = TMGNode(
            id="com.example.Test",
            name="Test",
            node_type=NodeType.CLASS,
            state=NodeState.ANALYZED,
            metadata={"deprecated": True},
        )
        
        data = node.to_dict()
        assert data["id"] == "com.example.Test"
        assert data["node_type"] == "CLASS"
        assert data["state"] == "ANALYZED"
        
        restored = TMGNode.from_dict(data)
        assert restored.id == node.id
        assert restored.node_type == node.node_type
        assert restored.state == node.state


class TestTMGEdge:
    """Tests for TMGEdge dataclass."""
    
    def test_create_edge(self):
        """Test basic edge creation."""
        edge = TMGEdge(
            source="com.example.A",
            target="com.example.B",
            edge_type=EdgeType.SYNTACTIC,
        )
        assert edge.source == "com.example.A"
        assert edge.target == "com.example.B"
        assert edge.weight == 1.0
    
    def test_edge_serialization(self):
        """Test edge to/from dict."""
        edge = TMGEdge(
            source="A",
            target="B",
            edge_type=EdgeType.SEMANTIC,
            weight=0.8,
        )
        
        data = edge.to_dict()
        restored = TMGEdge.from_dict(data)
        
        assert restored.source == edge.source
        assert restored.edge_type == edge.edge_type


class TestTypedMigrationGraph:
    """Tests for TypedMigrationGraph class."""
    
    def test_create_empty_graph(self, tmg: TypedMigrationGraph):
        """Test creating empty graph."""
        assert len(tmg) == 0
        assert tmg.name == "test_graph"
        assert tmg.source_version == "8"
        assert tmg.target_version == "17"
    
    def test_add_node(self, tmg: TypedMigrationGraph, sample_node: TMGNode):
        """Test adding a node."""
        tmg.add_node(sample_node)
        assert len(tmg) == 1
        assert tmg.has_node(sample_node.id)
    
    def test_add_duplicate_node_fails(self, tmg: TypedMigrationGraph, sample_node: TMGNode):
        """Test that adding duplicate node raises error."""
        tmg.add_node(sample_node)
        with pytest.raises(ValueError):
            tmg.add_node(sample_node)
    
    def test_get_node(self, tmg: TypedMigrationGraph, sample_node: TMGNode):
        """Test retrieving a node."""
        tmg.add_node(sample_node)
        retrieved = tmg.get_node(sample_node.id)
        assert retrieved.id == sample_node.id
    
    def test_get_nonexistent_node_fails(self, tmg: TypedMigrationGraph):
        """Test that getting nonexistent node raises error."""
        with pytest.raises(NodeNotFoundError):
            tmg.get_node("nonexistent")
    
    def test_add_edge(self, populated_tmg: TypedMigrationGraph):
        """Test that edges are added correctly."""
        edge = populated_tmg.get_edge(
            "com.example.Service",
            "com.example.Service.doWork",
        )
        assert edge is not None
        assert edge.edge_type == EdgeType.SYNTACTIC
    
    def test_state_transition(self, tmg: TypedMigrationGraph, sample_node: TMGNode):
        """Test valid state transition."""
        tmg.add_node(sample_node)
        tmg.transition_state(sample_node.id, NodeState.ANALYZED)
        
        node = tmg.get_node(sample_node.id)
        assert node.state == NodeState.ANALYZED
    
    def test_invalid_state_transition(self, tmg: TypedMigrationGraph, sample_node: TMGNode):
        """Test that invalid transition raises error."""
        tmg.add_node(sample_node)
        with pytest.raises(InvalidTransitionError):
            tmg.transition_state(sample_node.id, NodeState.MIGRATED)
    
    def test_get_nodes_by_state(self, populated_tmg: TypedMigrationGraph):
        """Test filtering nodes by state."""
        nodes = populated_tmg.get_nodes_by_state(NodeState.UNPROCESSED)
        assert len(nodes) == 2
    
    def test_get_nodes_by_type(self, populated_tmg: TypedMigrationGraph):
        """Test filtering nodes by type."""
        classes = populated_tmg.get_nodes_by_type(NodeType.CLASS)
        methods = populated_tmg.get_nodes_by_type(NodeType.METHOD)
        
        assert len(classes) == 1
        assert len(methods) == 1
    
    def test_get_dependencies(self, populated_tmg: TypedMigrationGraph):
        """Test getting node dependencies."""
        deps = populated_tmg.get_dependencies("com.example.Service")
        assert len(deps) == 1
        assert deps[0].id == "com.example.Service.doWork"
    
    def test_get_dependents(self, populated_tmg: TypedMigrationGraph):
        """Test getting node dependents."""
        dependents = populated_tmg.get_dependents("com.example.Service.doWork")
        assert len(dependents) == 1
        assert dependents[0].id == "com.example.Service"
    
    def test_serialization(self, populated_tmg: TypedMigrationGraph, temp_dir: Path):
        """Test save and load."""
        save_path = temp_dir / "graph.json"
        populated_tmg.save(save_path)
        
        assert save_path.exists()
        
        loaded = TypedMigrationGraph.load(save_path)
        assert len(loaded) == len(populated_tmg)
        assert loaded.name == populated_tmg.name
    
    def test_get_stats(self, populated_tmg: TypedMigrationGraph):
        """Test graph statistics."""
        stats = populated_tmg.get_stats()
        
        assert stats["node_count"] == 2
        assert stats["edge_count"] == 1
        assert "UNPROCESSED" in stats["state_distribution"]
    
    def test_batch_transition(self, tmg: TypedMigrationGraph):
        """Test batch state transition."""
        # Add multiple nodes
        for i in range(3):
            node = TMGNode(
                id=f"node_{i}",
                name=f"Node{i}",
                node_type=NodeType.CLASS,
            )
            tmg.add_node(node)
        
        # Batch transition
        results = tmg.batch_transition(
            ["node_0", "node_1", "node_2"],
            NodeState.ANALYZED,
        )
        
        assert all(results.values())
        assert all(
            tmg.get_node(f"node_{i}").state == NodeState.ANALYZED
            for i in range(3)
        )
    
    def test_iteration(self, populated_tmg: TypedMigrationGraph):
        """Test iterating over graph nodes."""
        nodes = list(populated_tmg)
        assert len(nodes) == 2
