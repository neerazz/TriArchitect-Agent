"""
TriArchitect Demo - Run a complete migration workflow.

This demo shows the full TriArchitect pipeline in action,
demonstrating the three agents working together with the
Typed Migration Graph and Consensus Protocol.
"""

import json
import tempfile
from pathlib import Path
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Initialize logging first
# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.shared.logger import setup_logging
setup_logging(log_level="INFO", log_format="console")

from src.orchestrator import MigrationEngine
from src.tmg import TypedMigrationGraph
from src.tmg.visualizer import generate_stats_report

console = Console()


def create_demo_project(base_dir: Path) -> Path:
    """
    Create a sample Java 8 project for demonstration.
    
    Returns the path to the created project.
    """
    project_dir = base_dir / "demo_java_project"
    project_dir.mkdir(parents=True, exist_ok=True)
    
    # Create pom.xml
    pom_content = '''<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example.demo</groupId>
    <artifactId>legacy-service</artifactId>
    <version>1.0.0</version>
    
    <properties>
        <maven.compiler.source>8</maven.compiler.source>
        <maven.compiler.target>8</maven.compiler.target>
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
    (project_dir / "pom.xml").write_text(pom_content)
    
    # Create source directory structure
    src_dir = project_dir / "src" / "main" / "java" / "com" / "example" / "demo"
    src_dir.mkdir(parents=True, exist_ok=True)
    
    # Main service class (with deprecated API usage)
    service_content = '''package com.example.demo;

import java.util.ArrayList;
import java.util.List;

/**
 * Legacy user service from Java 8 era.
 * Contains patterns that should be migrated to Java 17.
 */
public class UserService {
    
    private List<User> users = new ArrayList<>();
    
    public void addUser(User user) {
        if (user != null) {
            users.add(user);
        }
    }
    
    public User findById(String id) {
        for (User user : users) {
            if (user.getId().equals(id)) {
                return user;
            }
        }
        return null;
    }
    
    public List<User> getActiveUsers() {
        List<User> active = new ArrayList<>();
        for (User user : users) {
            if (user.isActive()) {
                active.add(user);
            }
        }
        return active;
    }
    
    @Deprecated
    protected void finalize() throws Throwable {
        // Deprecated cleanup - should use try-with-resources
        users.clear();
        super.finalize();
    }
}
'''
    (src_dir / "UserService.java").write_text(service_content)
    
    # User model class
    user_content = '''package com.example.demo;

/**
 * User domain model.
 */
public class User {
    
    private String id;
    private String name;
    private String email;
    private boolean active;
    
    public User(String id, String name, String email) {
        this.id = id;
        this.name = name;
        this.email = email;
        this.active = true;
    }
    
    public String getId() { return id; }
    public String getName() { return name; }
    public String getEmail() { return email; }
    public boolean isActive() { return active; }
    public void setActive(boolean active) { this.active = active; }
    
    @Override
    public String toString() {
        return "User{id='" + id + "', name='" + name + "'}";
    }
}
'''
    (src_dir / "User.java").write_text(user_content)
    
    # Data processor with more complexity
    processor_content = '''package com.example.demo;

import java.util.List;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.Collections;

/**
 * Data processor for batch operations.
 */
public class DataProcessor {
    
    private UserService userService;
    
    public DataProcessor(UserService userService) {
        this.userService = userService;
    }
    
    public List<User> processAndSort(Comparator<User> comparator) {
        List<User> users = userService.getActiveUsers();
        Collections.sort(users, comparator);
        return users;
    }
    
    public void bulkAdd(List<User> newUsers) {
        for (User user : newUsers) {
            userService.addUser(user);
        }
    }
}
'''
    (src_dir / "DataProcessor.java").write_text(processor_content)
    
    # Create test directory
    test_dir = project_dir / "src" / "test" / "java" / "com" / "example" / "demo"
    test_dir.mkdir(parents=True, exist_ok=True)
    
    # Unit test
    test_content = '''package com.example.demo;

import org.junit.Test;
import org.junit.Before;
import static org.junit.Assert.*;

public class UserServiceTest {
    
    private UserService service;
    
    @Before
    public void setUp() {
        service = new UserService();
    }
    
    @Test
    public void testAddUser() {
        User user = new User("1", "Alice", "alice@example.com");
        service.addUser(user);
        
        User found = service.findById("1");
        assertNotNull(found);
        assertEquals("Alice", found.getName());
    }
    
    @Test
    public void testFindByIdNotFound() {
        User found = service.findById("nonexistent");
        assertNull(found);
    }
    
    @Test
    public void testGetActiveUsers() {
        User active = new User("1", "Active", "active@example.com");
        User inactive = new User("2", "Inactive", "inactive@example.com");
        inactive.setActive(false);
        
        service.addUser(active);
        service.addUser(inactive);
        
        assertEquals(1, service.getActiveUsers().size());
    }
}
'''
    (test_dir / "UserServiceTest.java").write_text(test_content)
    
    return project_dir


def run_demo():
    """Run the complete TriArchitect demo."""
    console.print(Panel.fit(
        "[bold blue]TriArchitect Demo[/bold blue]\n"
        "[dim]Shared-State Multi-Agent Framework for Safe Legacy Migration[/dim]",
        border_style="blue",
    ))
    
    # Create temporary demo project
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        
        console.print("\n[bold]1. Creating demo Java 8 project...[/bold]")
        project_dir = create_demo_project(base_dir)
        console.print(f"   Created project at: {project_dir}")
        
        # Initialize engine
        console.print("\n[bold]2. Initializing TriArchitect engine...[/bold]")
        engine = MigrationEngine(
            source_version="8",
            target_version="17",
            use_docker=False,  # Use local runner for demo
        )
        
        # Run analysis only (full migration requires LLM keys)
        console.print("\n[bold]3. Running Archeologist analysis...[/bold]")
        result = engine.analyze_only(str(project_dir))
        
        if result["success"]:
            report = result["report"]
            stats = result["tmg_stats"]
            
            # Display results
            table = Table(title="Analysis Results")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            
            table.add_row("Files Analyzed", str(report["files_analyzed"]))
            table.add_row("Total Nodes", str(report["total_nodes"]))
            table.add_row("Total Edges", str(report["total_edges"]))
            table.add_row("Deprecated APIs", str(report["deprecated_apis"]))
            table.add_row("Parse Errors", str(len(report["parse_errors"])))
            
            console.print(table)
            
            # State distribution
            if stats.get("state_distribution"):
                console.print("\n[bold]Node State Distribution:[/bold]")
                for state, count in stats["state_distribution"].items():
                    console.print(f"   {state}: {count}")
            
            # Type distribution
            if stats.get("type_distribution"):
                console.print("\n[bold]Node Type Distribution:[/bold]")
                for node_type, count in stats["type_distribution"].items():
                    console.print(f"   {node_type}: {count}")
            
            # Show TMG stats report
            console.print("\n[bold]4. TMG Statistics Report:[/bold]")
            tmg = engine._tmg
            console.print(generate_stats_report(tmg))
            
            # Demonstrate consensus protocol
            console.print("\n[bold]5. Demonstrating Consensus Protocol...[/bold]")
            from src.consensus import ConsensusProtocol
            from src.tmg.models import MigrationProposal
            
            protocol = ConsensusProtocol(threshold=0.8)
            
            # Create a sample proposal
            proposal = MigrationProposal(
                node_id="com.example.demo.UserService.finalize",
                original_code="protected void finalize() throws Throwable { ... }",
                proposed_code="// Removed deprecated finalize() - use try-with-resources",
                confidence=0.85,
                rationale="The finalize() method was deprecated in Java 9",
                deprecation_apis=["finalize"],
            )
            
            # Simulate agent votes
            votes = [
                ("archeologist", "Archeologist", True, 0.90),
                ("architect", "Architect", True, 0.85),
                ("validator", "Validator", True, 0.80),
            ]
            
            consensus_result = protocol.run_simple(proposal, votes)
            
            console.print(f"   Proposal: {proposal.node_id}")
            console.print(f"   Status: [green]{consensus_result.status.name}[/green]")
            console.print(f"   Score: {consensus_result.final_score:.2f}")
            console.print(f"   Signatures: {consensus_result.signatures.get_approval_count()}/3 approved")
            
            console.print("\n[bold green]✓ Demo complete![/bold green]")
            
        else:
            console.print(f"[red]Analysis failed: {result['error']}[/red]")
    
    return 0


if __name__ == "__main__":
    run_demo()
