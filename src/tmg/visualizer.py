"""
TMG Visualization utilities.

Provides visual representations of the Typed Migration Graph for
debugging, documentation, and progress tracking.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import networkx as nx

from src.shared.logger import get_logger
from src.tmg.graph import TypedMigrationGraph
from src.tmg.models import NodeState, NodeType

logger = get_logger(__name__, component="tmg_visualizer")


# Color schemes for visualization
STATE_COLORS: dict[NodeState, str] = {
    NodeState.UNPROCESSED: "#9E9E9E",   # Gray
    NodeState.ANALYZED: "#2196F3",       # Blue
    NodeState.DEPRECATED: "#FF9800",     # Orange
    NodeState.MIGRATED: "#4CAF50",       # Green
    NodeState.FAILED: "#F44336",         # Red
}

TYPE_SHAPES: dict[NodeType, str] = {
    NodeType.CLASS: "o",        # Circle
    NodeType.INTERFACE: "s",    # Square
    NodeType.METHOD: "d",       # Diamond
    NodeType.FIELD: "^",        # Triangle up
    NodeType.IMPORT: "v",       # Triangle down
    NodeType.PACKAGE: "p",      # Pentagon
    NodeType.CONFIG: "h",       # Hexagon
    NodeType.ANNOTATION: "*",   # Star
}


def visualize_graph(
    tmg: TypedMigrationGraph,
    output_path: str | Path | None = None,
    figsize: tuple[int, int] = (16, 12),
    show_labels: bool = True,
    highlight_cycles: bool = True,
    title: str | None = None,
) -> plt.Figure:
    """
    Create a visualization of the TMG.
    
    Nodes are colored by state and shaped by type. Edges are drawn
    with arrows indicating dependency direction.
    
    Args:
        tmg: The TypedMigrationGraph to visualize.
        output_path: Optional path to save the figure.
        figsize: Figure size in inches (width, height).
        show_labels: Whether to show node labels.
        highlight_cycles: Whether to highlight cyclic nodes.
        title: Custom title for the plot.
        
    Returns:
        The matplotlib Figure object.
    """
    fig, ax = plt.subplots(1, 1, figsize=figsize)
    
    if len(tmg) == 0:
        ax.text(0.5, 0.5, "Empty Graph", ha="center", va="center", fontsize=20)
        ax.set_title(title or f"TMG: {tmg.name}")
        return fig
    
    # Get layout
    try:
        pos = nx.spring_layout(tmg.graph, k=2, iterations=50, seed=42)
    except Exception:
        pos = nx.circular_layout(tmg.graph)
    
    # Find cycles for highlighting
    cycle_nodes: set[str] = set()
    if highlight_cycles:
        for cycle in tmg.find_cycles():
            cycle_nodes.update(cycle)
    
    # Draw nodes by state
    for state in NodeState:
        nodes = [n.id for n in tmg.get_nodes_by_state(state)]
        if nodes:
            node_colors = [
                "#FF1744" if n in cycle_nodes else STATE_COLORS[state]
                for n in nodes
            ]
            nx.draw_networkx_nodes(
                tmg.graph,
                pos,
                nodelist=nodes,
                node_color=node_colors,
                node_size=500,
                ax=ax,
                alpha=0.9,
            )
    
    # Draw edges
    nx.draw_networkx_edges(
        tmg.graph,
        pos,
        ax=ax,
        arrows=True,
        arrowsize=15,
        edge_color="#666666",
        alpha=0.6,
        connectionstyle="arc3,rad=0.1",
    )
    
    # Draw labels
    if show_labels:
        # Truncate long labels
        labels = {
            node_id: (node_id.split(".")[-1][:15] if "." in node_id else node_id[:15])
            for node_id in tmg.graph.nodes()
        }
        nx.draw_networkx_labels(
            tmg.graph,
            pos,
            labels=labels,
            font_size=8,
            ax=ax,
        )
    
    # Title and legend
    ax.set_title(title or f"TMG: {tmg.name} ({len(tmg)} nodes)", fontsize=14)
    ax.axis("off")
    
    # Add legend for states
    legend_elements = [
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=color, 
                   markersize=10, label=state.name)
        for state, color in STATE_COLORS.items()
    ]
    ax.legend(handles=legend_elements, loc="upper left", title="Node States")
    
    plt.tight_layout()
    
    # Save if path provided
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        logger.info("visualization_saved", path=str(output_path))
    
    return fig


def generate_stats_report(tmg: TypedMigrationGraph) -> str:
    """
    Generate a text report of TMG statistics.
    
    Args:
        tmg: The TypedMigrationGraph to report on.
        
    Returns:
        Formatted string report.
    """
    stats = tmg.get_stats()
    
    lines = [
        f"TMG Statistics Report: {stats['name']}",
        "=" * 50,
        "",
        f"Migration: Java {stats['source_version']} → Java {stats['target_version']}",
        f"Total Nodes: {stats['node_count']}",
        f"Total Edges: {stats['edge_count']}",
        f"Is DAG: {'Yes' if stats['is_dag'] else 'No (cycles detected!)'}",
        f"Cycle Count: {stats['cycle_count']}",
        "",
        "State Distribution:",
    ]
    
    for state, count in stats["state_distribution"].items():
        pct = (count / stats["node_count"] * 100) if stats["node_count"] > 0 else 0
        lines.append(f"  {state}: {count} ({pct:.1f}%)")
    
    lines.append("")
    lines.append("Type Distribution:")
    for node_type, count in stats["type_distribution"].items():
        lines.append(f"  {node_type}: {count}")
    
    return "\n".join(lines)
