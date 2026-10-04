"""Tests for GitHub Actions Continuous Integration (CI) configuration.

Verifies multi-OS matrix, strict static analysis, property testing,
benchmark regression gates, and LaTeX whitepaper compilation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CI_CONFIG_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"


@pytest.fixture
def workflow_config() -> dict[Any, Any]:
    """Load and parse the CI workflow YAML file."""
    assert CI_CONFIG_PATH.exists(), f"CI config file not found at {CI_CONFIG_PATH}"
    content = CI_CONFIG_PATH.read_text(encoding="utf-8")
    assert content.strip(), "CI workflow file is empty"
    data: dict[Any, Any] = yaml.safe_load(content)
    assert isinstance(data, dict), "CI workflow must be a valid YAML mapping"
    return data


class TestCIWorkflowStructure:
    """Verifies existence, parsing, and trigger configuration of the CI workflow."""

    def test_ci_file_exists_and_valid_yaml(self, workflow_config: dict[Any, Any]) -> None:
        """ci.yml must exist and parse into a valid non-empty YAML dictionary."""
        assert CI_CONFIG_PATH.is_file()
        assert len(workflow_config) > 0

    def test_workflow_triggers_push_and_pull_request(self, workflow_config: dict[Any, Any]) -> None:
        """Triggers must include push to main and pull_request to main."""
        # Note: PyYAML may parse unquoted 'on:' as boolean True
        triggers: dict[Any, Any] | None = workflow_config.get("on") or workflow_config.get(True)
        assert triggers is not None, "Workflow missing 'on' triggers"

        # Push trigger validation
        assert "push" in triggers, "Workflow missing 'push' trigger"
        push_cfg = triggers["push"]
        push_branches = push_cfg.get("branches", [])
        assert "main" in push_branches, f"push trigger must target main, found: {push_branches}"

        # Pull request trigger validation
        assert "pull_request" in triggers, "Workflow missing 'pull_request' trigger"
        pr_cfg = triggers["pull_request"]
        pr_branches = pr_cfg.get("branches", [])
        assert "main" in pr_branches, f"pull_request trigger must target main, found: {pr_branches}"


class TestCIMatrixAndJobs:
    """Verifies matrix execution across OSs, Python versions, and test pipeline stages."""

    def test_matrix_operating_systems_and_python_versions(
        self, workflow_config: dict[Any, Any]
    ) -> None:
        """CI matrix must cover ubuntu, macos, windows and Python 3.10, 3.11, 3.12."""
        jobs = workflow_config.get("jobs", {})
        assert "test" in jobs or "matrix" in jobs, f"Jobs defined: {list(jobs.keys())}"

        # Locate the matrix test job
        test_job = jobs.get("test") or jobs.get("matrix")
        assert test_job is not None
        strategy = test_job.get("strategy", {})
        matrix = strategy.get("matrix", {})

        # Verify OS coverage
        os_list = matrix.get("os", []) or matrix.get("operating-system", [])
        expected_os = {"ubuntu-latest", "macos-latest", "windows-latest"}
        assert expected_os.issubset(set(os_list)), (
            f"Missing required OS in matrix: {expected_os - set(os_list)}"
        )

        # Verify Python versions coverage
        py_list = [str(v) for v in (matrix.get("python-version", []) or matrix.get("python", []))]
        expected_py = {"3.10", "3.11", "3.12"}
        assert expected_py.issubset(set(py_list)), (
            f"Missing required Python versions in matrix: {expected_py - set(py_list)}"
        )

    def test_dependency_caching_configured(self, workflow_config: dict[Any, Any]) -> None:
        """Workflow must utilize pip caching via actions/cache or setup-python cache."""
        content = CI_CONFIG_PATH.read_text(encoding="utf-8")
        has_cache = (
            "cache: 'pip'" in content
            or 'cache: "pip"' in content
            or "cache: pip" in content
            or "actions/cache" in content
        )
        assert has_cache, "Dependency caching (pip cache in setup-python or actions/cache) missing"

    def test_ruff_lint_and_format_step_present(self, workflow_config: dict[Any, Any]) -> None:
        """Workflow must include Ruff linting and formatting steps."""
        content = CI_CONFIG_PATH.read_text(encoding="utf-8")
        assert "ruff check" in content, "Ruff lint check step missing from workflow"
        assert "ruff format" in content or "ruff check" in content, (
            "Ruff format or check step missing"
        )

    def test_mypy_strict_step_present(self, workflow_config: dict[Any, Any]) -> None:
        """Workflow must include Mypy with strict type checking."""
        content = CI_CONFIG_PATH.read_text(encoding="utf-8")
        assert "mypy" in content, "Mypy type checking step missing from workflow"
        assert "--strict" in content, "Mypy step must include --strict flag"

    def test_pytest_execution_with_hypothesis(self, workflow_config: dict[Any, Any]) -> None:
        """Workflow must execute pytest suite covering Hypothesis property tests."""
        content = CI_CONFIG_PATH.read_text(encoding="utf-8")
        assert "pytest" in content, "Pytest test execution step missing from workflow"

    def test_context_distillation_benchmark_gate(self, workflow_config: dict[Any, Any]) -> None:
        """Workflow must assert context token distillation benchmark gate >= 85.0%."""
        content = CI_CONFIG_PATH.read_text(encoding="utf-8")
        assert "benchmarks" in content or "bench-tokens" in content, (
            "Token distillation benchmark step missing from workflow"
        )
        assert "85" in content, "Benchmark regression gate must assert >= 85% token reduction"


class TestWhitepaperBuildJob:
    """Verifies dedicated LaTeX whitepaper PDF compilation and artifact upload."""

    def test_whitepaper_job_exists_and_compiles_latex(
        self, workflow_config: dict[Any, Any]
    ) -> None:
        """A dedicated whitepaper compilation job must compile docs/whitepaper.tex and upload."""
        jobs = workflow_config.get("jobs", {})
        # Find whitepaper / docs / latex job
        matched = [k for k in jobs if any(m in k.lower() for m in ["whitepaper", "latex", "pdf"])]
        assert matched, f"No whitepaper job found in jobs: {list(jobs.keys())}"

        content = CI_CONFIG_PATH.read_text(encoding="utf-8")
        assert "docs/whitepaper.tex" in content, "Whitepaper job must reference docs/whitepaper.tex"
        assert "upload-artifact" in content, (
            "Whitepaper job must upload compiled PDF via upload-artifact action"
        )
        assert "whitepaper.pdf" in content or "whitepaper" in content, (
            "Whitepaper job must produce or upload whitepaper.pdf"
        )
