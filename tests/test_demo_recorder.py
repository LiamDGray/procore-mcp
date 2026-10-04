import json
import tempfile
from pathlib import Path

from procore_mcp.recorder import (
    DemoScenarioResult,
    generate_asciinema_cast,
    generate_svg_animation,
    run_demo_scenario,
)


def test_run_demo_scenario_executes_all_steps() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)
        result = run_demo_scenario(output_dir=out_dir)

        assert isinstance(result, DemoScenarioResult)
        assert len(result.steps) >= 5
        assert result.verified_integrity is True
        assert result.audit_log_path.exists()

        # Step assertions
        step_names = [s.name for s in result.steps]
        assert "bootstrap_demo" in step_names
        assert "query_rfis" in step_names
        assert "create_rfi_draft" in step_names
        assert "blocked_mutation_attempt" in step_names
        assert "verify_audit_log" in step_names

        # Security step assertion
        blocked_step = next(s for s in result.steps if s.name == "blocked_mutation_attempt")
        assert blocked_step.is_security_alert is True
        assert "SafetyInvariantViolation" in blocked_step.output


def test_generate_asciinema_cast() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)
        result = run_demo_scenario(output_dir=out_dir)
        cast_file = out_dir / "demo.cast"

        saved_path = generate_asciinema_cast(result, cast_file)
        assert saved_path.exists()
        assert saved_path.stat().st_size > 0

        # Validate Asciinema v2 format
        lines = cast_file.read_text(encoding="utf-8").strip().split("\n")
        header = json.loads(lines[0])
        assert header["version"] == 2
        assert "width" in header
        assert "height" in header
        assert len(lines) > 1

        # Check frame structure: [timestamp, "o", text]
        frame = json.loads(lines[1])
        assert isinstance(frame, list)
        assert len(frame) == 3
        assert frame[1] == "o"


def test_generate_svg_animation() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)
        result = run_demo_scenario(output_dir=out_dir)
        svg_file = out_dir / "demo.svg"

        saved_path = generate_svg_animation(result, svg_file)
        assert saved_path.exists()
        assert saved_path.stat().st_size > 0

        content = svg_file.read_text(encoding="utf-8")
        assert "<svg" in content
        assert "</svg>" in content
        assert "Aegis Tower" in content
        assert "BLOCKED" in content
        assert "AUDIT CHAIN INTEGRITY VERIFIED" in content
