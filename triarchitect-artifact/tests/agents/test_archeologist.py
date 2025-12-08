"""
Tests for the Archeologist agent.
"""

from pathlib import Path

import pytest

from src.agents.archeologist import ArcheologistAgent
from src.agents.archeologist.parser import JavaParser
from src.shared.tmg import TypedMigrationGraph
from src.shared.tmg.models import NodeState, NodeType


class TestJavaParser:
    """Tests for the Java parser."""
    
    def test_parse_single_file(self, sample_java_file: Path):
        """Test parsing a single Java file."""
        parser = JavaParser()
        result = parser.parse_file(sample_java_file)
        
        assert result.file_path == str(sample_java_file)
        assert len(result.errors) == 0
        assert result.package_name == "com.example"
        assert len(result.nodes) > 0
    
    def test_parse_extracts_class(self, sample_java_file: Path):
        """Test that parser extracts class declarations."""
        parser = JavaParser()
        result = parser.parse_file(sample_java_file)
        
        class_nodes = [n for n in result.nodes if n.node_type == NodeType.CLASS]
        assert len(class_nodes) >= 1
        assert any("SampleService" in n.name for n in class_nodes)
    
    def test_parse_extracts_methods(self, sample_java_file: Path):
        """Test that parser extracts method declarations."""
        parser = JavaParser()
        result = parser.parse_file(sample_java_file)
        
        method_nodes = [n for n in result.nodes if n.node_type == NodeType.METHOD]
        assert len(method_nodes) >= 1
    
    def test_parse_extracts_imports(self, sample_java_file: Path):
        """Test that parser extracts imports."""
        parser = JavaParser()
        result = parser.parse_file(sample_java_file)
        
        import_nodes = [n for n in result.nodes if n.node_type == NodeType.IMPORT]
        assert len(import_nodes) >= 1
    
    def test_parse_detects_deprecated_finalize(self, sample_java_file: Path):
        """Test that parser flags deprecated finalize method."""
        parser = JavaParser()
        result = parser.parse_file(sample_java_file)
        
        finalize_nodes = [
            n for n in result.nodes
            if n.node_type == NodeType.METHOD and n.name == "finalize"
        ]
        assert len(finalize_nodes) == 1
        assert finalize_nodes[0].metadata.get("deprecated", False)
    
    def test_parse_directory(self, sample_maven_project: Path):
        """Test parsing a directory of Java files."""
        parser = JavaParser()
        src_dir = sample_maven_project / "src"
        
        results = parser.parse_directory(src_dir, recursive=True)
        
        assert len(results) >= 1
        total_nodes = sum(len(r.nodes) for r in results)
        assert total_nodes > 0
    
    def test_parse_nonexistent_file(self, temp_dir: Path):
        """Test parsing a nonexistent file."""
        parser = JavaParser()
        result = parser.parse_file(temp_dir / "nonexistent.java")
        
        assert len(result.errors) > 0


class TestArcheologistAgent:
    """Tests for the Archeologist agent."""
    
    def test_analyze_repository(self, sample_maven_project: Path):
        """Test analyzing a repository."""
        tmg = TypedMigrationGraph(name="test_project")
        agent = ArcheologistAgent(tmg=tmg)
        
        result = agent.execute(repository_path=str(sample_maven_project))
        
        assert result.success
        assert result.data.files_analyzed > 0
        assert result.data.total_nodes > 0
    
    def test_tmg_populated(self, sample_maven_project: Path):
        """Test that TMG is populated after analysis."""
        tmg = TypedMigrationGraph(name="test_project")
        agent = ArcheologistAgent(tmg=tmg)
        
        agent.execute(repository_path=str(sample_maven_project))
        
        assert len(tmg) > 0
    
    def test_nodes_transitioned_to_analyzed(self, sample_maven_project: Path):
        """Test that nodes are transitioned to ANALYZED state."""
        tmg = TypedMigrationGraph(name="test_project")
        agent = ArcheologistAgent(tmg=tmg)
        
        agent.execute(repository_path=str(sample_maven_project))
        
        analyzed_nodes = tmg.get_nodes_by_state(NodeState.ANALYZED)
        assert len(analyzed_nodes) > 0
    
    def test_get_deprecated_nodes(self, sample_maven_project: Path):
        """Test retrieving deprecated nodes."""
        tmg = TypedMigrationGraph(name="test_project")
        agent = ArcheologistAgent(tmg=tmg)
        
        agent.execute(repository_path=str(sample_maven_project))
        
        deprecated = agent.get_deprecated_nodes()
        # Should find the finalize method
        assert any("finalize" in d["name"] for d in deprecated)
    
    def test_invalid_path_fails(self):
        """Test that invalid path returns failure."""
        tmg = TypedMigrationGraph(name="test")
        agent = ArcheologistAgent(tmg=tmg)
        
        result = agent.execute(repository_path="/nonexistent/path")
        
        assert not result.success
        assert result.error is not None
