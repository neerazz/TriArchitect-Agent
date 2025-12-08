"""
TriArchitect Pipeline Runner for J8-to-J17-Bench.
"""
from __future__ import annotations
import json, shutil, time
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict

from src.orchestrator import MigrationEngine
from src.shared.logger import get_logger, setup_logging
from src.shared.tmg.models import NodeState

logger = get_logger(__name__)

@dataclass
class Result:
    repo_name: str
    pass_at_1: float
    hallucination_rate: float
    semantic_preservation: float
    time_seconds: float
    consensus_rounds: int
    error: str | None = None

def run_triarchitect(repo: Path, test_repo: Path, use_docker: bool = True) -> Result:
    start = time.perf_counter()
    try:
        engine = MigrationEngine(source_version="8", target_version="17", use_docker=use_docker)
        result = engine.migrate(str(repo), str(test_repo), dry_run=False)
        elapsed = time.perf_counter() - start
        
        if result["success"]:
            report = result.get("report", {})
            return Result(
                repo_name=repo.name,
                pass_at_1=report.get("test_pass_rate", 0.0),
                hallucination_rate=report.get("hallucination_rate", 0.0),
                semantic_preservation=report.get("semantic_preservation", 0.0),
                time_seconds=elapsed,
                consensus_rounds=result.get("consensus_stats", {}).get("total_rounds", 1),
            )
        return Result(repo.name, 0.0, 1.0, 0.0, elapsed, 0, result.get("error"))
    except Exception as e:
        return Result(repo.name, 0.0, 1.0, 0.0, time.perf_counter()-start, 0, str(e))

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_dir", required=True)
    parser.add_argument("--num_repos", type=int, default=300)
    parser.add_argument("--output_file", required=True)
    parser.add_argument("--no_docker", action="store_true")
    args = parser.parse_args()
    
    setup_logging(log_level="INFO", log_format="console")
    repos = [d for d in Path(args.input_dir).iterdir() if d.is_dir()][:args.num_repos]
    
    results = []
    for i, repo in enumerate(repos):
        print(f"[{i+1}/{len(repos)}] {repo.name}")
        test_repo = Path(f"/tmp/tri_test_{repo.name}")
        if test_repo.exists(): shutil.rmtree(test_repo)
        shutil.copytree(repo, test_repo)
        results.append(asdict(run_triarchitect(repo, test_repo, not args.no_docker)))
        if test_repo.exists(): shutil.rmtree(test_repo)
    
    Path(args.output_file).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output_file, "w") as f:
        json.dump({"baseline": "triarchitect", "timestamp": datetime.now().isoformat(), "results": results}, f, indent=2)
    
    ok = [r for r in results if not r["error"]]
    if ok:
        print(f"\nTriArchitect: Pass@1={sum(r['pass_at_1'] for r in ok)/len(ok):.2%}, Halluc={sum(r['hallucination_rate'] for r in ok)/len(ok):.2%}")

if __name__ == "__main__":
    main()
