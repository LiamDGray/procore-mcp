"""Tests for Context Token-Distillation Benchmark Suite.

Proves 85%+ context token reduction across Procore API modules.
"""

from typing import Any

import pytest

from procore_mcp.benchmarks import (
    RAW_FIXTURES,
    DistillationMetric,
    estimate_token_count,
    run_all_benchmarks,
)

REQUIRED_MODULES = {
    "RFIs",
    "Submittals",
    "Daily Logs",
    "Change Events",
    "Commitments",
    "Budget",
    "Directory",
    "Companies",
    "Projects",
    "Cost Codes",
}


class TestTokenEstimator:
    """Tests for estimate_token_count."""

    def test_estimate_token_count_json_string(self) -> None:
        raw_json_str = '{"id": 1, "name": "Test Company", "active": true}'
        tokens = estimate_token_count(raw_json_str)
        assert isinstance(tokens, int)
        assert tokens > 0

    def test_estimate_token_count_dict(self) -> None:
        data: dict[str, Any] = {
            "id": 101,
            "title": "Submittal for Structural Steel Shop Drawings",
            "nested": {"key": "value", "count": 42},
        }
        tokens = estimate_token_count(data)
        assert isinstance(tokens, int)
        assert tokens >= 10

    def test_estimate_token_count_list(self) -> None:
        data: list[dict[str, Any]] = [
            {"id": i, "name": f"Item {i}", "desc": "Detailed description"} for i in range(10)
        ]
        tokens = estimate_token_count(data)
        assert isinstance(tokens, int)
        assert tokens > 50

    def test_estimate_token_count_empty(self) -> None:
        assert estimate_token_count("") == 0
        assert estimate_token_count({}) == 0
        assert estimate_token_count([]) == 0

    def test_estimate_token_count_proportionality(self) -> None:
        small_payload = {"id": 1, "status": "Open"}
        large_payload = {
            "id": 1,
            "status": "Open",
            "hypermedia_links": {f"rel_{i}": f"https://api.procore.com/v1/{i}" for i in range(50)},
            "deep_user_tree": {
                "user": {
                    "first_name": "Alexander",
                    "last_name": "Hamilton",
                    "avatar_url": "https://storage.procore.com/avatars/user_12345_original.png",
                    "permissions": {f"perm_{i}": True for i in range(30)},
                }
            },
        }
        tokens_small = estimate_token_count(small_payload)
        tokens_large = estimate_token_count(large_payload)
        assert tokens_large > tokens_small * 5


class TestBenchmarkFixturesBloat:
    """Verify raw fixtures accurately simulate realistic Procore API response bloat."""

    def test_fixtures_cover_all_ten_modules(self) -> None:
        assert set(RAW_FIXTURES.keys()) == REQUIRED_MODULES

    @pytest.mark.parametrize("module_name", list(REQUIRED_MODULES))
    def test_fixture_contains_realistic_bloat(self, module_name: str) -> None:
        raw_data = RAW_FIXTURES[module_name]
        raw_str = str(raw_data)

        # Realistic Procore payloads contain hypermedia links, avatars/storage URLs,
        # deep user hashes, or nested permission/system metadata
        has_bloat = any(
            marker in raw_str
            for marker in [
                "avatar",
                "links",
                "permissions",
                "created_by",
                "https://",
                "updated_at",
            ]
        )
        assert has_bloat, f"Module fixture '{module_name}' lacks realistic Procore API bloat"


class TestDistillationInvariants:
    """Strict invariant tests proving token reduction efficiency."""

    def test_run_all_benchmarks_returns_metrics(self) -> None:
        metrics = run_all_benchmarks()
        assert len(metrics) == 10

        modules_reported = {m.module for m in metrics}
        assert modules_reported == REQUIRED_MODULES

        for metric in metrics:
            assert isinstance(metric, DistillationMetric)
            assert metric.raw_bytes > 0
            assert metric.distilled_bytes > 0
            assert metric.distilled_bytes < metric.raw_bytes
            assert metric.raw_tokens > 0
            assert metric.distilled_tokens > 0
            assert metric.distilled_tokens < metric.raw_tokens
            assert 0.0 < metric.reduction_pct < 100.0

    def test_single_module_reduction_invariant(self) -> None:
        """Every single module MUST achieve >= 70% token reduction."""
        metrics = run_all_benchmarks()
        failed_modules: list[str] = []

        for metric in metrics:
            if metric.reduction_pct < 70.0:
                failed_modules.append(
                    f"{metric.module}: {metric.reduction_pct:.2f}% "
                    f"(raw: {metric.raw_tokens}, distilled: {metric.distilled_tokens})"
                )

        assert not failed_modules, "Modules failing the >= 70% reduction threshold:\n" + "\n".join(
            failed_modules
        )

    def test_aggregate_reduction_invariant(self) -> None:
        """The aggregate reduction across all modules MUST achieve >= 80% (targeting 85%+)."""
        metrics = run_all_benchmarks()

        total_raw_tokens = sum(m.raw_tokens for m in metrics)
        total_distilled_tokens = sum(m.distilled_tokens for m in metrics)
        aggregate_reduction = (1.0 - (total_distilled_tokens / total_raw_tokens)) * 100.0

        average_module_reduction = sum(m.reduction_pct for m in metrics) / len(metrics)

        assert aggregate_reduction >= 80.0, (
            f"Aggregate token reduction {aggregate_reduction:.2f}% "
            "is below required 80.0% threshold"
        )
        assert average_module_reduction >= 80.0, (
            f"Average module reduction {average_module_reduction:.2f}% "
            "is below required 80.0% threshold"
        )
        # Verify efficiency approaches or exceeds 85%
        assert aggregate_reduction >= 85.0, (
            f"Aggregate token reduction {aggregate_reduction:.2f}% did not achieve the 85%+ target"
        )
