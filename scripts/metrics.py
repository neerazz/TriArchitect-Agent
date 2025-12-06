"""
Evaluation Metrics for J8-to-J17-Bench.

Implements the three core metrics:
1. Pass@1: Does migrated code compile and pass tests?
2. Hallucination Rate: What % of dependencies don't exist?
3. Semantic Preservation: Are test method counts preserved?
"""

from __future__ import annotations

import os
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import requests

from src.shared.logger import get_logger

logger = get_logger(__name__, component="metrics")


# =============================================================================
# METRIC 1: Pass@1
# =============================================================================

def evaluate_pass_at_1(repo_path: Path) -> float:
    """
    Does the migrated code compile and pass tests?
    
    Returns:
        1.0 if all tests pass, 0.0 otherwise
    """
    try:
        # Step 1: Compile
        compile_result = subprocess.run(
            ["mvn", "clean", "compile", "-q"],
            cwd=repo_path,
            capture_output=True,
            timeout=300,
        )
        
        if compile_result.returncode != 0:
            logger.warning(
                "compilation_failed",
                repo=repo_path.name,
                stderr=compile_result.stderr.decode()[:500],
            )
            return 0.0
        
        # Step 2: Run tests
        test_result = subprocess.run(
            ["mvn", "test", "-q"],
            cwd=repo_path,
            capture_output=True,
            timeout=600,
        )
        
        if test_result.returncode != 0:
            logger.warning(
                "tests_failed",
                repo=repo_path.name,
                stderr=test_result.stderr.decode()[:500],
            )
            return 0.0
        
        # Step 3: Verify Java version in compiled classes
        major_version = check_class_major_version(repo_path)
        if major_version and major_version < 61:  # Java 17 = major version 61
            logger.warning(
                "wrong_java_version",
                repo=repo_path.name,
                major_version=major_version,
            )
            return 0.5  # Partial credit
        
        return 1.0
        
    except subprocess.TimeoutExpired:
        logger.warning("timeout", repo=repo_path.name)
        return 0.0
    except Exception as e:
        logger.exception("pass_at_1_error", error=str(e))
        return 0.0


def check_class_major_version(repo_path: Path) -> int | None:
    """Check major version in compiled .class files."""
    target_dir = repo_path / "target" / "classes"
    
    if not target_dir.exists():
        return None
    
    for class_file in target_dir.glob("**/*.class"):
        try:
            with open(class_file, "rb") as f:
                magic = f.read(4)
                if magic != b'\xca\xfe\xba\xbe':
                    continue
                minor = int.from_bytes(f.read(2), "big")
                major = int.from_bytes(f.read(2), "big")
                return major
        except:
            continue
    
    return None


# =============================================================================
# METRIC 2: Hallucination Rate
# =============================================================================

# Cache for Maven Central checks
_maven_cache: dict[str, bool] = {}


def detect_hallucinations(repo_path: Path) -> float:
    """
    What percentage of dependencies don't actually exist in Maven Central?
    
    Returns:
        Hallucination rate (0.0 = no hallucinations, 1.0 = all hallucinated)
    """
    pom_path = repo_path / "pom.xml"
    
    if not pom_path.exists():
        return 0.0
    
    try:
        tree = ET.parse(pom_path)
        root = tree.getroot()
        
        # Handle Maven namespace
        ns = {"m": "http://maven.apache.org/POM/4.0.0"}
        
        # Find all dependencies
        dependencies = root.findall(".//m:dependency", ns)
        
        if not dependencies:
            # Try without namespace
            dependencies = root.findall(".//dependency")
        
        if not dependencies:
            return 0.0
        
        hallucinated = 0
        checked = 0
        
        for dep in dependencies:
            try:
                if ns:
                    group_id = dep.find("m:groupId", ns)
                    artifact_id = dep.find("m:artifactId", ns)
                    version = dep.find("m:version", ns)
                else:
                    group_id = dep.find("groupId")
                    artifact_id = dep.find("artifactId")
                    version = dep.find("version")
                
                if group_id is None or artifact_id is None:
                    continue
                
                g = group_id.text
                a = artifact_id.text
                v = version.text if version is not None else "LATEST"
                
                checked += 1
                
                if not check_maven_central(g, a, v):
                    hallucinated += 1
                    logger.debug(
                        "hallucinated_dependency",
                        group_id=g,
                        artifact_id=a,
                        version=v,
                    )
                    
            except Exception as e:
                logger.warning("dependency_parse_error", error=str(e))
        
        if checked == 0:
            return 0.0
        
        rate = hallucinated / checked
        logger.info(
            "hallucination_check",
            repo=repo_path.name,
            checked=checked,
            hallucinated=hallucinated,
            rate=f"{rate:.2%}",
        )
        
        return rate
        
    except ET.ParseError as e:
        logger.warning("pom_parse_error", error=str(e))
        return 0.0


def check_maven_central(group_id: str, artifact_id: str, version: str) -> bool:
    """
    Check if a dependency exists in Maven Central.
    
    Uses search.maven.org API with caching.
    """
    cache_key = f"{group_id}:{artifact_id}:{version}"
    
    if cache_key in _maven_cache:
        return _maven_cache[cache_key]
    
    try:
        # Use Maven Central search API
        url = f"https://search.maven.org/solrsearch/select"
        params = {
            "q": f'g:"{group_id}" AND a:"{artifact_id}"',
            "rows": 1,
            "wt": "json",
        }
        
        response = requests.get(url, params=params, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            exists = data.get("response", {}).get("numFound", 0) > 0
            _maven_cache[cache_key] = exists
            return exists
        
        # On API failure, assume exists (conservative)
        return True
        
    except requests.RequestException:
        # On network failure, assume exists
        return True


# =============================================================================
# METRIC 3: Semantic Preservation
# =============================================================================

def check_semantic_preservation(repo_path: Path, original_path: Path | None = None) -> float:
    """
    Are test method counts preserved?
    
    Compares @Test annotated methods before and after migration.
    
    Returns:
        Ratio of after/before test count (capped at 1.0)
    """
    # Count tests in current (migrated) repo
    after_count = count_test_methods(repo_path)
    
    # If original path provided, compare
    if original_path and original_path.exists():
        before_count = count_test_methods(original_path)
    else:
        # Use metadata file if available
        metadata_path = repo_path / ".triarchitect_original_test_count"
        if metadata_path.exists():
            before_count = int(metadata_path.read_text().strip())
        else:
            # Assume current count is after-migration state
            # This happens when we only have the migrated version
            before_count = after_count
    
    if before_count == 0:
        return 1.0 if after_count == 0 else 0.0
    
    ratio = after_count / before_count
    
    logger.info(
        "semantic_preservation",
        repo=repo_path.name,
        before=before_count,
        after=after_count,
        ratio=f"{ratio:.2%}",
    )
    
    return min(ratio, 1.0)


def count_test_methods(repo_path: Path) -> int:
    """Count methods annotated with @Test."""
    count = 0
    
    # Look in standard Maven test directories
    test_dirs = [
        repo_path / "src" / "test" / "java",
        repo_path / "src" / "test",
    ]
    
    for test_dir in test_dirs:
        if not test_dir.exists():
            continue
        
        for java_file in test_dir.glob("**/*.java"):
            try:
                content = java_file.read_text(encoding="utf-8")
                
                # Count @Test annotations
                count += len(re.findall(r"@Test\b", content))
                
                # Also count @ParameterizedTest for JUnit 5
                count += len(re.findall(r"@ParameterizedTest\b", content))
                
            except Exception:
                continue
    
    return count


# =============================================================================
# COMBINED EVALUATION
# =============================================================================

def evaluate_migration(
    repo_path: Path,
    original_path: Path | None = None,
) -> dict[str, float]:
    """
    Run all three metrics on a migrated repository.
    
    Args:
        repo_path: Path to migrated repository
        original_path: Optional path to original (pre-migration) for comparison
    
    Returns:
        Dictionary with all metrics
    """
    return {
        "pass_at_1": evaluate_pass_at_1(repo_path),
        "hallucination_rate": detect_hallucinations(repo_path),
        "semantic_preservation": check_semantic_preservation(repo_path, original_path),
    }


def compute_overall_score(metrics: dict[str, float]) -> float:
    """
    Compute weighted overall score from individual metrics.
    
    Weights:
    - Pass@1: 50% (most important - does it work?)
    - Semantic Preservation: 30% (behavior preserved?)
    - Hallucination: 20% (quality of dependencies?)
    """
    α, β, γ = 0.5, 0.3, 0.2
    
    return (
        α * metrics["pass_at_1"] +
        β * metrics["semantic_preservation"] +
        γ * (1 - metrics["hallucination_rate"])
    )
