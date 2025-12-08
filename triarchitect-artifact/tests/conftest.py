"""
Pytest configuration and shared fixtures.
"""

import tempfile
from pathlib import Path
from typing import Generator

import pytest

from src.shared.tmg import TypedMigrationGraph
from src.shared.tmg.models import EdgeType, NodeState, NodeType, TMGEdge, TMGNode


@pytest.fixture
def tmg() -> TypedMigrationGraph:
    """Create a fresh TMG for testing."""
    return TypedMigrationGraph(
        name="test_graph",
        source_version="8",
        target_version="17",
    )


@pytest.fixture
def sample_node() -> TMGNode:
    """Create a sample TMG node."""
    return TMGNode(
        id="com.example.TestClass",
        name="TestClass",
        node_type=NodeType.CLASS,
        state=NodeState.UNPROCESSED,
        file_path="/path/to/TestClass.java",
        line_start=1,
        line_end=50,
    )


@pytest.fixture
def sample_class_node() -> TMGNode:
    """Create a sample class node."""
    return TMGNode(
        id="com.example.Service",
        name="Service",
        node_type=NodeType.CLASS,
        state=NodeState.UNPROCESSED,
        file_path="/path/to/Service.java",
        metadata={"deprecated": True, "replacement": "com.example.v2.Service"},
    )


@pytest.fixture
def sample_method_node() -> TMGNode:
    """Create a sample method node."""
    return TMGNode(
        id="com.example.Service.doWork",
        name="doWork",
        node_type=NodeType.METHOD,
        state=NodeState.UNPROCESSED,
        file_path="/path/to/Service.java",
        line_start=10,
        line_end=25,
    )


@pytest.fixture
def populated_tmg(
    tmg: TypedMigrationGraph,
    sample_class_node: TMGNode,
    sample_method_node: TMGNode,
) -> TypedMigrationGraph:
    """Create a TMG with some nodes and edges."""
    tmg.add_node(sample_class_node)
    tmg.add_node(sample_method_node)
    
    edge = TMGEdge(
        source=sample_class_node.id,
        target=sample_method_node.id,
        edge_type=EdgeType.SYNTACTIC,
    )
    tmg.add_edge(edge)
    
    return tmg


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_java_file(temp_dir: Path) -> Path:
    """Create a sample Java file for testing."""
    java_content = '''package com.example;

import java.util.List;
import java.util.ArrayList;

/**
 * A sample service class for testing.
 */
public class SampleService {
    
    private List<String> items = new ArrayList<>();
    
    public void addItem(String item) {
        items.add(item);
    }
    
    public List<String> getItems() {
        return items;
    }
    
    @Deprecated
    protected void finalize() throws Throwable {
        // Deprecated in Java 9+
        super.finalize();
    }
}
'''
    
    # Create package structure
    pkg_dir = temp_dir / "src" / "main" / "java" / "com" / "example"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    
    java_file = pkg_dir / "SampleService.java"
    java_file.write_text(java_content)
    
    return java_file


@pytest.fixture
def sample_maven_project(temp_dir: Path, sample_java_file: Path) -> Path:
    """Create a sample Maven project structure."""
    # Create pom.xml
    pom_content = '''<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    
    <groupId>com.example</groupId>
    <artifactId>sample-project</artifactId>
    <version>1.0.0</version>
    <packaging>jar</packaging>
    
    <properties>
        <maven.compiler.source>8</maven.compiler.source>
        <maven.compiler.target>8</maven.compiler.target>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    </properties>
    
    <dependencies>
        <dependency>
            <groupId>junit</groupId>
            <artifactId>junit</artifactId>
            <version>4.13.2</version>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>
'''
    pom_file = temp_dir / "pom.xml"
    pom_file.write_text(pom_content)
    
    # Create test directory
    test_dir = temp_dir / "src" / "test" / "java" / "com" / "example"
    test_dir.mkdir(parents=True, exist_ok=True)
    
    test_content = '''package com.example;

import org.junit.Test;
import static org.junit.Assert.*;

public class SampleServiceTest {
    
    @Test
    public void testAddItem() {
        SampleService service = new SampleService();
        service.addItem("test");
        assertEquals(1, service.getItems().size());
    }
}
'''
    test_file = test_dir / "SampleServiceTest.java"
    test_file.write_text(test_content)
    
    return temp_dir
