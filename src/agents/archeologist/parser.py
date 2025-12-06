"""
Java source code parser for the Archeologist agent.

Uses the javalang library to parse Java source files and extract
structural information including classes, methods, imports, and
their relationships.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import javalang
from javalang.tree import (
    ClassCreator,
    ClassDeclaration,
    CompilationUnit,
    FieldDeclaration,
    Import,
    InterfaceDeclaration,
    MethodDeclaration,
    MethodInvocation,
    PackageDeclaration,
    ReferenceType,
)

from src.shared.logger import get_logger
from src.shared.tmg.models import EdgeType, NodeType, TMGEdge, TMGNode

logger = get_logger(__name__, component="java_parser")


@dataclass
class ParseResult:
    """
    Result of parsing a single Java file.
    
    Attributes:
        file_path: Path to the parsed file.
        package_name: Package declaration if present.
        nodes: List of TMG nodes discovered.
        edges: List of TMG edges discovered.
        errors: Any parsing errors encountered.
        metrics: Parsing statistics.
    """
    file_path: str
    package_name: str = ""
    nodes: list[TMGNode] = field(default_factory=list)
    edges: list[TMGEdge] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metrics: dict[str, int] = field(default_factory=dict)


class JavaParser:
    """
    Parser for Java source files using javalang.
    
    Extracts structural information from Java files and converts
    them to TMG nodes and edges.
    
    Attributes:
        source_version: The Java version of the source code.
        target_version: The Java version to migrate to.
    
    Example:
        >>> parser = JavaParser()
        >>> result = parser.parse_file("/path/to/MyClass.java")
        >>> print(f"Found {len(result.nodes)} nodes")
    """
    
    # Deprecated Java 8 APIs that should be flagged
    DEPRECATED_APIS: dict[str, str] = {
        "javax.xml.bind": "jakarta.xml.bind",
        "javax.activation": "jakarta.activation",
        "java.security.acl": "Removed in Java 17",
        "sun.misc.Unsafe": "Use VarHandle instead",
        "finalize": "Deprecated cleanup method",
    }
    
    def __init__(
        self,
        source_version: str = "8",
        target_version: str = "17",
    ) -> None:
        """
        Initialize the Java parser.
        
        Args:
            source_version: Source Java version.
            target_version: Target Java version.
        """
        self.source_version = source_version
        self.target_version = target_version
        self._current_package = ""
        self._current_file = ""
    
    def parse_file(self, file_path: str | Path) -> ParseResult:
        """
        Parse a single Java source file.
        
        Args:
            file_path: Path to the Java file.
            
        Returns:
            ParseResult containing discovered nodes and edges.
        """
        file_path = Path(file_path)
        self._current_file = str(file_path)
        
        result = ParseResult(file_path=str(file_path))
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()
            
            tree = javalang.parse.parse(source)
            result = self._process_compilation_unit(tree, result)
            
            logger.debug(
                "file_parsed",
                file=str(file_path),
                node_count=len(result.nodes),
                edge_count=len(result.edges),
            )
            
        except javalang.parser.JavaSyntaxError as e:
            error_msg = f"Syntax error in {file_path}: {e}"
            result.errors.append(error_msg)
            logger.warning("parse_error", file=str(file_path), error=str(e))
            
        except Exception as e:
            error_msg = f"Failed to parse {file_path}: {e}"
            result.errors.append(error_msg)
            logger.exception("parse_exception", file=str(file_path))
        
        return result
    
    def _process_compilation_unit(
        self,
        tree: CompilationUnit,
        result: ParseResult,
    ) -> ParseResult:
        """Process a complete Java compilation unit."""
        # Extract package
        if tree.package:
            self._current_package = tree.package.name
            result.package_name = tree.package.name
            
            pkg_node = TMGNode(
                id=tree.package.name,
                name=tree.package.name,
                node_type=NodeType.PACKAGE,
                file_path=self._current_file,
            )
            result.nodes.append(pkg_node)
        
        # Process imports
        for imp in tree.imports or []:
            result = self._process_import(imp, result)
        
        # Process types (classes, interfaces)
        for type_decl in tree.types or []:
            if isinstance(type_decl, ClassDeclaration):
                result = self._process_class(type_decl, result)
            elif isinstance(type_decl, InterfaceDeclaration):
                result = self._process_interface(type_decl, result)
        
        # Update metrics
        result.metrics = {
            "imports": len([n for n in result.nodes if n.node_type == NodeType.IMPORT]),
            "classes": len([n for n in result.nodes if n.node_type == NodeType.CLASS]),
            "interfaces": len([n for n in result.nodes if n.node_type == NodeType.INTERFACE]),
            "methods": len([n for n in result.nodes if n.node_type == NodeType.METHOD]),
            "fields": len([n for n in result.nodes if n.node_type == NodeType.FIELD]),
        }
        
        return result
    
    def _process_import(self, imp: Import, result: ParseResult) -> ParseResult:
        """Process an import statement."""
        import_path = imp.path
        
        # Create import node
        node_id = f"{self._current_package}.imports.{import_path}"
        import_node = TMGNode(
            id=node_id,
            name=import_path,
            node_type=NodeType.IMPORT,
            file_path=self._current_file,
            metadata={
                "static": imp.static,
                "wildcard": imp.wildcard,
            },
        )
        
        # Check for deprecated APIs
        for deprecated, replacement in self.DEPRECATED_APIS.items():
            if deprecated in import_path:
                import_node.metadata["deprecated"] = True
                import_node.metadata["replacement"] = replacement
                logger.debug(
                    "deprecated_api_found",
                    api=import_path,
                    replacement=replacement,
                )
        
        result.nodes.append(import_node)
        
        # Create edge from package to import
        if self._current_package:
            edge = TMGEdge(
                source=self._current_package,
                target=node_id,
                edge_type=EdgeType.SYNTACTIC,
                metadata={"import_path": import_path},
            )
            result.edges.append(edge)
        
        return result
    
    def _process_class(
        self,
        cls: ClassDeclaration,
        result: ParseResult,
        parent_id: str = "",
    ) -> ParseResult:
        """Process a class declaration."""
        class_id = f"{self._current_package}.{cls.name}" if self._current_package else cls.name
        if parent_id:
            class_id = f"{parent_id}.{cls.name}"
        
        # Get position info if available
        position = getattr(cls, "position", None)
        line_start = position.line if position else 0
        
        class_node = TMGNode(
            id=class_id,
            name=cls.name,
            node_type=NodeType.CLASS,
            file_path=self._current_file,
            line_start=line_start,
            metadata={
                "modifiers": list(cls.modifiers) if cls.modifiers else [],
                "extends": cls.extends.name if cls.extends else None,
                "implements": [i.name for i in (cls.implements or [])],
                "annotations": [a.name for a in (cls.annotations or [])],
            },
        )
        result.nodes.append(class_node)
        
        # Edge from package
        if self._current_package:
            edge = TMGEdge(
                source=self._current_package,
                target=class_id,
                edge_type=EdgeType.SYNTACTIC,
            )
            result.edges.append(edge)
        
        # Process inheritance
        if cls.extends:
            # Will create edge to parent class (may be external)
            extends_id = cls.extends.name
            class_node.metadata["extends_id"] = extends_id
        
        # Process implements
        for impl in cls.implements or []:
            class_node.metadata.setdefault("implements_ids", []).append(impl.name)
        
        # Process class body
        for item in cls.body or []:
            if isinstance(item, MethodDeclaration):
                result = self._process_method(item, class_id, result)
            elif isinstance(item, FieldDeclaration):
                result = self._process_field(item, class_id, result)
            elif isinstance(item, ClassDeclaration):
                # Inner class
                result = self._process_class(item, result, parent_id=class_id)
        
        return result
    
    def _process_interface(
        self,
        iface: InterfaceDeclaration,
        result: ParseResult,
    ) -> ParseResult:
        """Process an interface declaration."""
        iface_id = f"{self._current_package}.{iface.name}" if self._current_package else iface.name
        
        position = getattr(iface, "position", None)
        line_start = position.line if position else 0
        
        iface_node = TMGNode(
            id=iface_id,
            name=iface.name,
            node_type=NodeType.INTERFACE,
            file_path=self._current_file,
            line_start=line_start,
            metadata={
                "modifiers": list(iface.modifiers) if iface.modifiers else [],
                "extends": [e.name for e in (iface.extends or [])],
            },
        )
        result.nodes.append(iface_node)
        
        # Edge from package
        if self._current_package:
            edge = TMGEdge(
                source=self._current_package,
                target=iface_id,
                edge_type=EdgeType.SYNTACTIC,
            )
            result.edges.append(edge)
        
        # Process interface body (methods are abstract by default)
        for item in iface.body or []:
            if isinstance(item, MethodDeclaration):
                result = self._process_method(item, iface_id, result)
        
        return result
    
    def _process_method(
        self,
        method: MethodDeclaration,
        parent_id: str,
        result: ParseResult,
    ) -> ParseResult:
        """Process a method declaration."""
        method_id = f"{parent_id}.{method.name}"
        
        position = getattr(method, "position", None)
        line_start = position.line if position else 0
        
        # Extract parameter types
        params = []
        for param in method.parameters or []:
            param_type = param.type.name if hasattr(param.type, "name") else str(param.type)
            params.append({"name": param.name, "type": param_type})
        
        # Extract return type
        return_type = None
        if method.return_type:
            return_type = method.return_type.name if hasattr(method.return_type, "name") else "void"
        
        method_node = TMGNode(
            id=method_id,
            name=method.name,
            node_type=NodeType.METHOD,
            file_path=self._current_file,
            line_start=line_start,
            metadata={
                "modifiers": list(method.modifiers) if method.modifiers else [],
                "parameters": params,
                "return_type": return_type,
                "throws": [t.name for t in (method.throws or [])],
                "annotations": [a.name for a in (method.annotations or [])],
            },
        )
        
        # Check for deprecated finalize method
        if method.name == "finalize":
            method_node.metadata["deprecated"] = True
            method_node.metadata["deprecation_reason"] = "finalize() is deprecated in Java 9+"
        
        result.nodes.append(method_node)
        
        # Edge from class to method
        edge = TMGEdge(
            source=parent_id,
            target=method_id,
            edge_type=EdgeType.SYNTACTIC,
        )
        result.edges.append(edge)
        
        # Analyze method body for semantic edges (method calls)
        result = self._process_method_body(method, method_id, result)
        
        return result
    
    def _process_method_body(
        self,
        method: MethodDeclaration,
        method_id: str,
        result: ParseResult,
    ) -> ParseResult:
        """Analyze method body for semantic dependencies."""
        if not method.body:
            return result
        
        # Walk the AST looking for method invocations and type references
        for path, node in method:
            if isinstance(node, MethodInvocation):
                # Record method call as semantic edge
                qualifier = node.qualifier if node.qualifier else "this"
                call_target = f"{qualifier}.{node.member}"
                
                # Store as metadata since target might not be in graph
                result.nodes[-1].metadata.setdefault("calls", []).append({
                    "target": call_target,
                    "member": node.member,
                    "qualifier": qualifier,
                })
            
            elif isinstance(node, ClassCreator):
                # Record class instantiation
                if hasattr(node.type, "name"):
                    result.nodes[-1].metadata.setdefault("instantiates", []).append(
                        node.type.name
                    )
        
        return result
    
    def _process_field(
        self,
        field: FieldDeclaration,
        parent_id: str,
        result: ParseResult,
    ) -> ParseResult:
        """Process a field declaration."""
        for declarator in field.declarators:
            field_id = f"{parent_id}.{declarator.name}"
            
            position = getattr(field, "position", None)
            line_start = position.line if position else 0
            
            # Get field type
            field_type = None
            if field.type:
                field_type = field.type.name if hasattr(field.type, "name") else str(field.type)
            
            field_node = TMGNode(
                id=field_id,
                name=declarator.name,
                node_type=NodeType.FIELD,
                file_path=self._current_file,
                line_start=line_start,
                metadata={
                    "modifiers": list(field.modifiers) if field.modifiers else [],
                    "type": field_type,
                    "annotations": [a.name for a in (field.annotations or [])],
                },
            )
            result.nodes.append(field_node)
            
            # Edge from class to field
            edge = TMGEdge(
                source=parent_id,
                target=field_id,
                edge_type=EdgeType.SYNTACTIC,
            )
            result.edges.append(edge)
        
        return result
    
    def parse_directory(
        self,
        directory: str | Path,
        recursive: bool = True,
    ) -> list[ParseResult]:
        """
        Parse all Java files in a directory.
        
        Args:
            directory: Path to the directory.
            recursive: Whether to search subdirectories.
            
        Returns:
            List of ParseResult for each file.
        """
        directory = Path(directory)
        pattern = "**/*.java" if recursive else "*.java"
        
        results = []
        java_files = list(directory.glob(pattern))
        
        logger.info(
            "parsing_directory",
            directory=str(directory),
            file_count=len(java_files),
            recursive=recursive,
        )
        
        for java_file in java_files:
            result = self.parse_file(java_file)
            results.append(result)
        
        total_nodes = sum(len(r.nodes) for r in results)
        total_edges = sum(len(r.edges) for r in results)
        total_errors = sum(len(r.errors) for r in results)
        
        logger.info(
            "directory_parsing_complete",
            files_parsed=len(results),
            total_nodes=total_nodes,
            total_edges=total_edges,
            total_errors=total_errors,
        )
        
        return results
