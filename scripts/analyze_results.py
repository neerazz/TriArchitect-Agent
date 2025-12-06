"""
Result Analysis and Figure Generation for MigrationBench Evaluation.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

def load_results(file_path: Path) -> list[dict]:
    with open(file_path) as f:
        data = json.load(f)
    return data.get("results", [])

def aggregate(results: list[dict], baseline: str) -> dict:
    ok = [r for r in results if not r.get("error")]
    if not ok:
        return {"baseline": baseline, "n": 0}
    return {
        "baseline": baseline,
        "n": len(ok),
        "pass_at_1": np.mean([r["pass_at_1"] for r in ok]),
        "pass_at_1_std": np.std([r["pass_at_1"] for r in ok]),
        "hallucination_rate": np.mean([r["hallucination_rate"] for r in ok]),
        "halluc_std": np.std([r["hallucination_rate"] for r in ok]),
        "semantic_preservation": np.mean([r["semantic_preservation"] for r in ok]),
        "semantic_std": np.std([r["semantic_preservation"] for r in ok]),
        "avg_time": np.mean([r["time_seconds"] for r in ok]),
    }

def create_bar_chart(df: pd.DataFrame, metric: str, title: str, output: Path, lower_better: bool = False):
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = ['#ff7f7f', '#ffb347', '#87ceeb', '#90ee90'][:len(df)]
    bars = ax.bar(df['baseline'], df[metric], color=colors, edgecolor='black')
    
    # Add error bars if available
    std_col = f"{metric}_std" if metric != "hallucination_rate" else "halluc_std"
    if std_col in df.columns:
        ax.errorbar(df['baseline'], df[metric], yerr=df[std_col]*1.96, fmt='none', color='black', capsize=5)
    
    ax.set_ylabel(metric.replace("_", " ").title())
    ax.set_title(title)
    ax.set_ylim(0, 1.0)
    
    for bar, val in zip(bars, df[metric]):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02, f'{val:.1%}', ha='center', fontsize=10)
    
    plt.tight_layout()
    plt.savefig(output, dpi=150, bbox_inches='tight')
    plt.close()

def create_grouped_bar(df: pd.DataFrame, metrics: list[str], output: Path):
    x = np.arange(len(df))
    width = 0.25
    fig, ax = plt.subplots(figsize=(12, 6))
    
    colors = ['#4c72b0', '#55a868', '#c44e52']
    for i, metric in enumerate(metrics):
        offset = (i - 1) * width
        ax.bar(x + offset, df[metric], width, label=metric.replace("_", " ").title(), color=colors[i])
    
    ax.set_xticks(x)
    ax.set_xticklabels(df['baseline'])
    ax.set_ylim(0, 1.0)
    ax.legend()
    ax.set_title('MigrationBench Evaluation Results')
    
    plt.tight_layout()
    plt.savefig(output, dpi=150, bbox_inches='tight')
    plt.close()

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--zero_shot", required=True)
    parser.add_argument("--sequential", required=True)
    parser.add_argument("--triarchitect", required=True)
    parser.add_argument("--output_file", required=True)
    parser.add_argument("--figures_dir", required=True)
    args = parser.parse_args()
    
    figs = Path(args.figures_dir)
    figs.mkdir(parents=True, exist_ok=True)
    
    # Load and aggregate
    summaries = [
        aggregate(load_results(Path(args.zero_shot)), "Zero-Shot"),
        aggregate(load_results(Path(args.sequential)), "Sequential"),
        aggregate(load_results(Path(args.triarchitect)), "TriArchitect"),
    ]
    
    df = pd.DataFrame(summaries)
    df.to_json(args.output_file, indent=2)
    df.to_csv(args.output_file.replace('.json', '.csv'), index=False)
    
    # Generate figures
    create_bar_chart(df, "pass_at_1", "Pass@1 Comparison", figs / "pass_at_1.png")
    create_bar_chart(df, "hallucination_rate", "Hallucination Rate (Lower is Better)", figs / "hallucination.png", True)
    create_bar_chart(df, "semantic_preservation", "Semantic Preservation", figs / "semantic.png")
    create_grouped_bar(df, ["pass_at_1", "semantic_preservation"], figs / "comparison.png")
    
    print(f"\n{'='*60}")
    print("FINAL RESULTS")
    print(f"{'='*60}")
    print(df[['baseline', 'n', 'pass_at_1', 'hallucination_rate', 'semantic_preservation']].to_string(index=False))
    print(f"\nFigures saved to {figs}/")

if __name__ == "__main__":
    main()
