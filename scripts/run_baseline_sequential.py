"""
Sequential Agent Baseline for J8-to-J17-Bench Evaluation.

This baseline uses multiple LLM calls in sequence (Reader → Planner → Executor)
but WITHOUT shared state (TMG). This demonstrates the value of the TMG.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from src.shared.logger import get_logger, setup_logging

logger = get_logger(__name__, baseline="sequential")


@dataclass
class MigrationResult:
    """Result of a single migration attempt."""
    repo_name: str
    baseline: str
    pass_at_1: float
    hallucination_rate: float
    semantic_preservation: float
    time_seconds: float
    tokens_used: int
    error: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def call_llm(prompt: str, provider: str = "openai", max_tokens: int = 2048) -> tuple[str, int]:
    """Call LLM API and return response with token count."""
    if provider == "openai":
        try:
            import openai
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model="gpt-5.1",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.3,
            )
            tokens = response.usage.total_tokens if response.usage else 0
            return response.choices[0].message.content or "", tokens
        except Exception as e:
            logger.error("openai_error", error=str(e))
            return "", 0
    
    elif provider == "anthropic":
        try:
            import anthropic
            client = anthropic.Anthropic()
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            tokens = response.usage.input_tokens + response.usage.output_tokens
            return response.content[0].text, tokens
        except Exception as e:
            logger.error("anthropic_error", error=str(e))
            return "", 0
    
    return "", 0


def agent_reader(repo_path: Path, provider: str) -> tuple[dict, int]:
    """
    Agent 1: Reader - Analyzes build configuration and identifies migration needs.
    """
    pom_path = repo_path / "pom.xml"
    pom_content = pom_path.read_text() if pom_path.exists() else ""
    
    prompt = f"""You are a build configuration analyzer. Analyze this Java pom.xml and identify:
1. Current Java version
2. Dependencies that need migration for Java 17
3. Plugins that need updates
4. Deprecated APIs likely in use based on dependencies

pom.xml:
{pom_content[:3000]}

Output a JSON object with this structure:
{{
    "java_version": "current version",
    "dependencies_to_migrate": ["list", "of", "deps"],
    "plugins_to_update": ["list", "of", "plugins"],
    "likely_deprecated_apis": ["list", "of", "apis"]
}}
"""
    
    response, tokens = call_llm(prompt, provider, max_tokens=1024)
    
    try:
        # Extract JSON from response
        import re
        json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group()), tokens
    except json.JSONDecodeError:
        pass
    
    return {
        "java_version": "8",
        "dependencies_to_migrate": [],
        "plugins_to_update": [],
        "likely_deprecated_apis": [],
    }, tokens


def agent_planner(build_analysis: dict, repo_path: Path, provider: str) -> tuple[str, int]:
    """
    Agent 2: Planner - Creates step-by-step migration plan.
    """
    # Count Java files for context
    java_files = list(repo_path.glob("**/*.java"))
    
    prompt = f"""You are a migration planner. Given this build analysis, create a detailed migration plan.

Build Analysis:
{json.dumps(build_analysis, indent=2)}

Repository Info:
- Number of Java files: {len(java_files)}
- Has tests: {any('test' in str(f).lower() for f in java_files)}

Create a step-by-step plan to migrate from Java 8 to Java 17.
Include:
1. Build configuration changes
2. Dependency updates with specific versions
3. Code changes for deprecated APIs
4. Testing strategy

Output the plan as a numbered list.
"""
    
    return call_llm(prompt, provider, max_tokens=2048)


def agent_executor(plan: str, repo_path: Path, provider: str) -> tuple[str, int]:
    """
    Agent 3: Executor - Generates migrated code based on plan.
    """
    # Read source files
    java_files = []
    for java_file in repo_path.glob("**/*.java"):
        if "/test/" not in str(java_file):
            try:
                content = java_file.read_text(encoding="utf-8")
                relative = java_file.relative_to(repo_path)
                java_files.append(f"// File: {relative}\n{content}")
            except:
                pass
    
    source_code = "\n\n".join(java_files)[:12000]  # Truncate
    
    prompt = f"""You are a code migration executor. Execute this migration plan on the source code.

Migration Plan:
{plan}

Source Code:
{source_code}

Requirements:
1. Preserve all method signatures
2. Update deprecated Java 8 APIs to Java 17 equivalents
3. Update import statements
4. Do not remove any methods

Output the fully migrated code. For each file, start with: // File: <path>
"""
    
    return call_llm(prompt, provider, max_tokens=4096)


def write_migrated_code(test_repo: Path, migrated_code: str) -> None:
    """Parse and write migrated code to test repository."""
    current_file = None
    current_content = []
    
    for line in migrated_code.split("\n"):
        if line.startswith("// File:"):
            if current_file and current_content:
                file_path = test_repo / current_file
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text("\n".join(current_content), encoding="utf-8")
            
            current_file = line.replace("// File:", "").strip()
            current_content = []
        else:
            current_content.append(line)
    
    if current_file and current_content:
        file_path = test_repo / current_file
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("\n".join(current_content), encoding="utf-8")


def evaluate_migration(repo_path: Path) -> dict[str, float]:
    """Evaluate migrated repository."""
    from scripts.metrics import (
        evaluate_pass_at_1,
        detect_hallucinations,
        check_semantic_preservation,
    )
    
    return {
        "pass_at_1": evaluate_pass_at_1(repo_path),
        "hallucination_rate": detect_hallucinations(repo_path),
        "semantic_preservation": check_semantic_preservation(repo_path),
    }


def run_sequential_migration(
    repo_path: Path,
    test_repo_path: Path,
    provider: str = "openai",
) -> MigrationResult:
    """
    Run sequential agent migration (no shared state).
    
    Pipeline: Reader → Planner → Executor
    Each agent passes output to next via text, no TMG.
    """
    logger.info("starting_sequential", repo=repo_path.name)
    start_time = time.perf_counter()
    total_tokens = 0
    
    try:
        # Agent 1: Reader
        logger.info("agent_reader_start")
        build_analysis, tokens1 = agent_reader(repo_path, provider)
        total_tokens += tokens1
        logger.info("agent_reader_complete", tokens=tokens1)
        
        # Agent 2: Planner
        logger.info("agent_planner_start")
        plan, tokens2 = agent_planner(build_analysis, repo_path, provider)
        total_tokens += tokens2
        logger.info("agent_planner_complete", tokens=tokens2)
        
        if not plan:
            return MigrationResult(
                repo_name=repo_path.name,
                baseline="sequential_agent",
                pass_at_1=0.0,
                hallucination_rate=1.0,
                semantic_preservation=0.0,
                time_seconds=time.perf_counter() - start_time,
                tokens_used=total_tokens,
                error="Planner returned empty response",
            )
        
        # Agent 3: Executor
        logger.info("agent_executor_start")
        migrated_code, tokens3 = agent_executor(plan, repo_path, provider)
        total_tokens += tokens3
        logger.info("agent_executor_complete", tokens=tokens3)
        
        if not migrated_code:
            return MigrationResult(
                repo_name=repo_path.name,
                baseline="sequential_agent",
                pass_at_1=0.0,
                hallucination_rate=1.0,
                semantic_preservation=0.0,
                time_seconds=time.perf_counter() - start_time,
                tokens_used=total_tokens,
                error="Executor returned empty response",
            )
        
        # Write and evaluate
        write_migrated_code(test_repo_path, migrated_code)
        metrics = evaluate_migration(test_repo_path)
        
        elapsed = time.perf_counter() - start_time
        
        return MigrationResult(
            repo_name=repo_path.name,
            baseline="sequential_agent",
            pass_at_1=metrics["pass_at_1"],
            hallucination_rate=metrics["hallucination_rate"],
            semantic_preservation=metrics["semantic_preservation"],
            time_seconds=elapsed,
            tokens_used=total_tokens,
        )
        
    except Exception as e:
        logger.exception("sequential_error", error=str(e))
        return MigrationResult(
            repo_name=repo_path.name,
            baseline="sequential_agent",
            pass_at_1=0.0,
            hallucination_rate=1.0,
            semantic_preservation=0.0,
            time_seconds=time.perf_counter() - start_time,
            tokens_used=total_tokens,
            error=str(e),
        )


def main():
    """Run sequential agent baseline on all repositories."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Sequential Agent Baseline")
    parser.add_argument("--input_dir", required=True)
    parser.add_argument("--num_repos", type=int, default=300)
    parser.add_argument("--output_file", required=True)
    parser.add_argument("--provider", default="openai")
    args = parser.parse_args()
    
    setup_logging(log_level="INFO", log_format="console")
    
    input_dir = Path(args.input_dir)
    output_file = Path(args.output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    repos = [d for d in input_dir.iterdir() if d.is_dir()][:args.num_repos]
    
    results = []
    for i, repo in enumerate(repos):
        logger.info("progress", current=i+1, total=len(repos), repo=repo.name)
        
        test_repo = Path(f"/tmp/sequential_test_{repo.name}")
        if test_repo.exists():
            shutil.rmtree(test_repo)
        shutil.copytree(repo, test_repo)
        
        result = run_sequential_migration(repo, test_repo, args.provider)
        results.append(result.to_dict())
        
        if test_repo.exists():
            shutil.rmtree(test_repo)
    
    with open(output_file, "w") as f:
        json.dump({
            "baseline": "sequential_agent",
            "timestamp": datetime.now().isoformat(),
            "provider": args.provider,
            "num_repos": len(results),
            "results": results,
        }, f, indent=2)
    
    successful = [r for r in results if r["error"] is None]
    if successful:
        print(f"\n{'='*50}")
        print(f"Sequential Agent Results (n={len(successful)})")
        print(f"{'='*50}")
        print(f"Pass@1:              {sum(r['pass_at_1'] for r in successful)/len(successful):.2%}")
        print(f"Hallucination Rate:  {sum(r['hallucination_rate'] for r in successful)/len(successful):.2%}")
        print(f"Semantic Pres.:      {sum(r['semantic_preservation'] for r in successful)/len(successful):.2%}")
        print(f"{'='*50}")


if __name__ == "__main__":
    main()
