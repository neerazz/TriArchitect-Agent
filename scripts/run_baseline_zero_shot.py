"""
Zero-Shot LLM Baseline for MigrationBench Evaluation.

This baseline represents the simplest approach: directly prompting
an LLM to migrate Java 8 code to Java 17 in a single pass.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from src.shared.logger import get_logger, setup_logging

logger = get_logger(__name__, baseline="zero_shot")


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


def read_java_files(repo_path: Path) -> str:
    """Read all Java source files from repository."""
    java_files = []
    
    for java_file in repo_path.glob("**/*.java"):
        # Skip test files for migration (but keep for validation)
        if "/test/" not in str(java_file):
            try:
                content = java_file.read_text(encoding="utf-8")
                relative_path = java_file.relative_to(repo_path)
                java_files.append(f"// File: {relative_path}\n{content}")
            except Exception as e:
                logger.warning("read_error", file=str(java_file), error=str(e))
    
    return "\n\n".join(java_files)


def read_pom_xml(repo_path: Path) -> str:
    """Read pom.xml for build configuration."""
    pom_path = repo_path / "pom.xml"
    if pom_path.exists():
        return pom_path.read_text(encoding="utf-8")
    return ""


def create_zero_shot_prompt(source_code: str, pom_content: str) -> str:
    """Create the zero-shot migration prompt."""
    return f"""You are an expert Java engineer. Migrate this Java 8 codebase to Java 17.

## Requirements
1. Preserve all method signatures (do not rename methods)
2. Do not delete any test methods
3. Update deprecated Java 8 APIs to Java 17 equivalents:
   - java.util.Date → java.time.LocalDate/LocalDateTime
   - javax.xml.bind.* → jakarta.xml.bind.*
   - sun.misc.BASE64* → java.util.Base64
   - finalize() → Cleaner API
4. Update language features where appropriate:
   - Use var keyword for local variables
   - Use text blocks for multi-line strings
   - Use records for data classes
5. Update dependencies to Java 17 compatible versions

## Build Configuration (pom.xml)
{pom_content[:2000] if pom_content else "Not provided"}

## Source Code
{source_code[:15000]}  # Truncate to fit context

## Output Format
Provide the migrated code for each file, prefixed with the file path.
Start each file with: // File: <path>
"""


def call_llm(prompt: str, provider: str = "openai") -> tuple[str, int]:
    """
    Call LLM API and return response with token count.
    
    Returns:
        Tuple of (response_text, tokens_used)
    """
    tokens_used = 0
    
    if provider == "openai":
        try:
            import openai
            client = openai.OpenAI()
            
            response = client.chat.completions.create(
                model="gpt-5.1",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4096,
                temperature=0.3,
            )
            
            tokens_used = response.usage.total_tokens if response.usage else 0
            return response.choices[0].message.content or "", tokens_used
            
        except Exception as e:
            logger.error("openai_error", error=str(e))
            return "", 0
    
    elif provider == "anthropic":
        try:
            import anthropic
            client = anthropic.Anthropic()
            
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            
            tokens_used = response.usage.input_tokens + response.usage.output_tokens
            return response.content[0].text, tokens_used
            
        except Exception as e:
            logger.error("anthropic_error", error=str(e))
            return "", 0
    
    return "", 0


def write_migrated_code(test_repo: Path, migrated_code: str) -> None:
    """Parse and write migrated code to test repository."""
    current_file = None
    current_content = []
    
    for line in migrated_code.split("\n"):
        if line.startswith("// File:"):
            # Save previous file
            if current_file and current_content:
                file_path = test_repo / current_file
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text("\n".join(current_content), encoding="utf-8")
            
            # Start new file
            current_file = line.replace("// File:", "").strip()
            current_content = []
        else:
            current_content.append(line)
    
    # Save last file
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


def run_zero_shot_migration(
    repo_path: Path,
    test_repo_path: Path,
    provider: str = "openai",
) -> MigrationResult:
    """
    Run zero-shot LLM migration on a single repository.
    
    Args:
        repo_path: Path to original Java 8 repository
        test_repo_path: Path for testing migrated code
        provider: LLM provider (openai or anthropic)
    
    Returns:
        MigrationResult with metrics
    """
    logger.info("starting_migration", repo=repo_path.name)
    start_time = time.perf_counter()
    
    try:
        # Read source code
        source_code = read_java_files(repo_path)
        pom_content = read_pom_xml(repo_path)
        
        if not source_code:
            return MigrationResult(
                repo_name=repo_path.name,
                baseline="zero_shot",
                pass_at_1=0.0,
                hallucination_rate=1.0,
                semantic_preservation=0.0,
                time_seconds=0.0,
                tokens_used=0,
                error="No Java files found",
            )
        
        # Create prompt and call LLM
        prompt = create_zero_shot_prompt(source_code, pom_content)
        migrated_code, tokens_used = call_llm(prompt, provider)
        
        if not migrated_code:
            return MigrationResult(
                repo_name=repo_path.name,
                baseline="zero_shot",
                pass_at_1=0.0,
                hallucination_rate=1.0,
                semantic_preservation=0.0,
                time_seconds=time.perf_counter() - start_time,
                tokens_used=tokens_used,
                error="LLM returned empty response",
            )
        
        # Write migrated code
        write_migrated_code(test_repo_path, migrated_code)
        
        # Evaluate
        metrics = evaluate_migration(test_repo_path)
        
        elapsed = time.perf_counter() - start_time
        
        return MigrationResult(
            repo_name=repo_path.name,
            baseline="zero_shot",
            pass_at_1=metrics["pass_at_1"],
            hallucination_rate=metrics["hallucination_rate"],
            semantic_preservation=metrics["semantic_preservation"],
            time_seconds=elapsed,
            tokens_used=tokens_used,
        )
        
    except Exception as e:
        logger.exception("migration_error", error=str(e))
        return MigrationResult(
            repo_name=repo_path.name,
            baseline="zero_shot",
            pass_at_1=0.0,
            hallucination_rate=1.0,
            semantic_preservation=0.0,
            time_seconds=time.perf_counter() - start_time,
            tokens_used=0,
            error=str(e),
        )


def main():
    """Run zero-shot baseline on all repositories."""
    import argparse
    import shutil
    
    parser = argparse.ArgumentParser(description="Zero-Shot LLM Baseline")
    parser.add_argument("--input_dir", required=True, help="Directory with repos")
    parser.add_argument("--num_repos", type=int, default=300, help="Number of repos")
    parser.add_argument("--output_file", required=True, help="Output JSON file")
    parser.add_argument("--provider", default="openai", help="LLM provider")
    args = parser.parse_args()
    
    setup_logging(log_level="INFO", log_format="console")
    
    input_dir = Path(args.input_dir)
    output_file = Path(args.output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Find repositories
    repos = [d for d in input_dir.iterdir() if d.is_dir()][:args.num_repos]
    
    results = []
    for i, repo in enumerate(repos):
        logger.info("progress", current=i+1, total=len(repos), repo=repo.name)
        
        # Create test directory
        test_repo = Path(f"/tmp/zero_shot_test_{repo.name}")
        if test_repo.exists():
            shutil.rmtree(test_repo)
        shutil.copytree(repo, test_repo)
        
        # Run migration
        result = run_zero_shot_migration(repo, test_repo, args.provider)
        results.append(result.to_dict())
        
        # Cleanup
        if test_repo.exists():
            shutil.rmtree(test_repo)
    
    # Save results
    with open(output_file, "w") as f:
        json.dump({
            "baseline": "zero_shot",
            "timestamp": datetime.now().isoformat(),
            "provider": args.provider,
            "num_repos": len(results),
            "results": results,
        }, f, indent=2)
    
    # Print summary
    successful = [r for r in results if r["error"] is None]
    if successful:
        avg_pass = sum(r["pass_at_1"] for r in successful) / len(successful)
        avg_halluc = sum(r["hallucination_rate"] for r in successful) / len(successful)
        avg_semantic = sum(r["semantic_preservation"] for r in successful) / len(successful)
        
        print(f"\n{'='*50}")
        print(f"Zero-Shot Baseline Results (n={len(successful)})")
        print(f"{'='*50}")
        print(f"Pass@1:              {avg_pass:.2%}")
        print(f"Hallucination Rate:  {avg_halluc:.2%}")
        print(f"Semantic Pres.:      {avg_semantic:.2%}")
        print(f"{'='*50}")


if __name__ == "__main__":
    main()
