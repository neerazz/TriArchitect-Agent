"""
Docker runner for isolated test execution.

Provides utilities for running Maven builds and tests in
Docker containers to ensure isolation and consistency.
"""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.shared.config import get_settings
from src.shared.logger import get_logger

logger = get_logger(__name__, component="docker_runner")


@dataclass
class TestResult:
    """
    Result from running tests in Docker.
    
    Attributes:
        success: Whether the build/test passed.
        exit_code: Process exit code.
        stdout: Standard output.
        stderr: Standard error.
        test_count: Number of tests run.
        passed_count: Number of tests passed.
        failed_count: Number of tests failed.
        skipped_count: Number of tests skipped.
        duration_seconds: Total execution time.
        error_message: Error message if failed.
    """
    success: bool
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    test_count: int = 0
    passed_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    duration_seconds: float = 0.0
    error_message: str = ""
    test_reports: list[dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "exit_code": self.exit_code,
            "test_count": self.test_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "skipped_count": self.skipped_count,
            "duration_seconds": self.duration_seconds,
            "error_message": self.error_message,
        }


class DockerRunner:
    """
    Runs Maven builds and tests in Docker containers.
    
    Provides isolated execution environment for validating
    migrated Java code.
    
    Attributes:
        docker_image: Docker image to use.
        timeout: Timeout in seconds.
    
    Example:
        >>> runner = DockerRunner()
        >>> if runner.is_docker_available():
        ...     result = runner.run_maven_verify("/path/to/project")
        ...     print(f"Tests passed: {result.passed_count}")
    """
    
    def __init__(
        self,
        docker_image: str | None = None,
        timeout: int | None = None,
    ) -> None:
        """
        Initialize the Docker runner.
        
        Args:
            docker_image: Docker image to use for Maven builds.
            timeout: Timeout in seconds for Docker operations.
        """
        settings = get_settings()
        self.docker_image = docker_image or settings.docker_image
        self.timeout = timeout or settings.docker_timeout
        self._docker_available: bool | None = None
    
    def is_docker_available(self) -> bool:
        """
        Check if Docker is available and running.
        
        Returns:
            True if Docker is available, False otherwise.
        """
        if self._docker_available is not None:
            return self._docker_available
        
        try:
            result = subprocess.run(
                ["docker", "version"],
                capture_output=True,
                timeout=10,
            )
            self._docker_available = result.returncode == 0
            if self._docker_available:
                logger.info("docker_available")
            else:
                logger.warning("docker_not_available", stderr=result.stderr.decode())
        except Exception as e:
            logger.warning("docker_check_failed", error=str(e))
            self._docker_available = False
        
        return self._docker_available
    
    def pull_image(self) -> bool:
        """
        Pull the Docker image if not present.
        
        Returns:
            True if image is available, False on failure.
        """
        try:
            logger.info("pulling_docker_image", image=self.docker_image)
            result = subprocess.run(
                ["docker", "pull", self.docker_image],
                capture_output=True,
                timeout=300,  # 5 minutes for pull
            )
            if result.returncode == 0:
                logger.info("docker_image_pulled", image=self.docker_image)
                return True
            else:
                logger.error(
                    "docker_pull_failed",
                    image=self.docker_image,
                    stderr=result.stderr.decode(),
                )
                return False
        except Exception as e:
            logger.exception("docker_pull_exception", error=str(e))
            return False
    
    def run_maven_verify(
        self,
        project_path: str | Path,
        java_version: str = "17",
    ) -> TestResult:
        """
        Run Maven verify in a Docker container.
        
        Args:
            project_path: Path to the Maven project.
            java_version: Target Java version.
            
        Returns:
            TestResult with build and test outcomes.
        """
        project_path = Path(project_path).resolve()
        
        if not project_path.exists():
            return TestResult(
                success=False,
                error_message=f"Project path does not exist: {project_path}",
            )
        
        if not (project_path / "pom.xml").exists():
            return TestResult(
                success=False,
                error_message=f"No pom.xml found in: {project_path}",
            )
        
        if not self.is_docker_available():
            return TestResult(
                success=False,
                error_message="Docker is not available",
            )
        
        logger.info(
            "running_maven_verify",
            project=str(project_path),
            java_version=java_version,
        )
        
        # Docker run command
        cmd = [
            "docker", "run",
            "--rm",
            "-v", f"{project_path}:/project",
            "-w", "/project",
            self.docker_image,
            "mvn", "clean", "verify",
            "-DskipTests=false",
            f"-Dmaven.compiler.source={java_version}",
            f"-Dmaven.compiler.target={java_version}",
        ]
        
        try:
            import time
            start_time = time.perf_counter()
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=self.timeout,
            )
            
            duration = time.perf_counter() - start_time
            
            test_result = TestResult(
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=result.stdout.decode("utf-8", errors="replace"),
                stderr=result.stderr.decode("utf-8", errors="replace"),
                duration_seconds=round(duration, 2),
            )
            
            # Parse test results from output
            self._parse_maven_output(test_result)
            
            # Try to parse JUnit XML reports
            self._parse_junit_reports(project_path, test_result)
            
            logger.info(
                "maven_verify_complete",
                success=test_result.success,
                tests_run=test_result.test_count,
                passed=test_result.passed_count,
                failed=test_result.failed_count,
                duration=test_result.duration_seconds,
            )
            
            return test_result
            
        except subprocess.TimeoutExpired:
            return TestResult(
                success=False,
                error_message=f"Maven verify timed out after {self.timeout} seconds",
            )
        except Exception as e:
            logger.exception("maven_verify_failed", error=str(e))
            return TestResult(
                success=False,
                error_message=str(e),
            )
    
    def run_maven_compile(self, project_path: str | Path) -> TestResult:
        """
        Run Maven compile only (faster than verify).
        
        Args:
            project_path: Path to the Maven project.
            
        Returns:
            TestResult with compilation outcome.
        """
        project_path = Path(project_path).resolve()
        
        if not self.is_docker_available():
            return TestResult(
                success=False,
                error_message="Docker is not available",
            )
        
        cmd = [
            "docker", "run",
            "--rm",
            "-v", f"{project_path}:/project",
            "-w", "/project",
            self.docker_image,
            "mvn", "clean", "compile",
        ]
        
        try:
            import time
            start_time = time.perf_counter()
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=self.timeout,
            )
            
            duration = time.perf_counter() - start_time
            
            return TestResult(
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=result.stdout.decode("utf-8", errors="replace"),
                stderr=result.stderr.decode("utf-8", errors="replace"),
                duration_seconds=round(duration, 2),
            )
            
        except subprocess.TimeoutExpired:
            return TestResult(
                success=False,
                error_message=f"Maven compile timed out after {self.timeout} seconds",
            )
        except Exception as e:
            return TestResult(
                success=False,
                error_message=str(e),
            )
    
    def _parse_maven_output(self, result: TestResult) -> None:
        """Parse Maven output to extract test counts."""
        import re
        
        # Look for surefire test summary
        # Example: "Tests run: 5, Failures: 1, Errors: 0, Skipped: 0"
        pattern = r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+),\s*Skipped:\s*(\d+)"
        matches = re.findall(pattern, result.stdout)
        
        for match in matches:
            result.test_count += int(match[0])
            result.failed_count += int(match[1]) + int(match[2])  # Failures + Errors
            result.skipped_count += int(match[3])
        
        result.passed_count = result.test_count - result.failed_count - result.skipped_count
        
        # Check for compilation errors
        if "COMPILATION ERROR" in result.stdout or "COMPILATION ERROR" in result.stderr:
            result.error_message = "Compilation failed"
    
    def _parse_junit_reports(
        self,
        project_path: Path,
        result: TestResult,
    ) -> None:
        """Parse JUnit XML reports if available."""
        import xml.etree.ElementTree as ET
        
        reports_dir = project_path / "target" / "surefire-reports"
        if not reports_dir.exists():
            return
        
        for xml_file in reports_dir.glob("TEST-*.xml"):
            try:
                tree = ET.parse(xml_file)
                root = tree.getroot()
                
                report = {
                    "name": root.get("name", "unknown"),
                    "tests": int(root.get("tests", 0)),
                    "failures": int(root.get("failures", 0)),
                    "errors": int(root.get("errors", 0)),
                    "skipped": int(root.get("skipped", 0)),
                    "time": float(root.get("time", 0)),
                }
                result.test_reports.append(report)
                
            except Exception as e:
                logger.debug("junit_parse_error", file=str(xml_file), error=str(e))


class LocalRunner:
    """
    Fallback runner that executes Maven locally without Docker.
    
    Used when Docker is not available.
    """
    
    def __init__(self, timeout: int = 300) -> None:
        """Initialize with timeout."""
        self.timeout = timeout
    
    def is_maven_available(self) -> bool:
        """Check if Maven is available locally."""
        try:
            result = subprocess.run(
                ["mvn", "--version"],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def run_maven_verify(self, project_path: str | Path) -> TestResult:
        """Run Maven verify locally."""
        project_path = Path(project_path).resolve()
        
        if not self.is_maven_available():
            return TestResult(
                success=False,
                error_message="Maven is not available locally",
            )
        
        try:
            import time
            start_time = time.perf_counter()
            
            result = subprocess.run(
                ["mvn", "clean", "verify"],
                cwd=project_path,
                capture_output=True,
                timeout=self.timeout,
            )
            
            duration = time.perf_counter() - start_time
            
            return TestResult(
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=result.stdout.decode("utf-8", errors="replace"),
                stderr=result.stderr.decode("utf-8", errors="replace"),
                duration_seconds=round(duration, 2),
            )
            
        except Exception as e:
            return TestResult(
                success=False,
                error_message=str(e),
            )
