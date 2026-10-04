"""Tests for Automated Cryptographic Verification CLI (procore-mcp verify)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from rich.console import Console

from procore_mcp.audit import AuditLogManager
from procore_mcp.server import main
from procore_mcp.verifier_cli import (
    VerificationReport,
    run_verification,
)


def test_run_verification_quick_success() -> None:
    """run_verification(quick=True) returns a successful report with all theorems proven."""
    report = run_verification(quick=True)

    assert isinstance(report, VerificationReport)
    assert report.success is True
    assert report.is_valid is True

    # Stage 1: Z3 SMT Solver Model Checking
    stage1 = report.stage1_smt
    assert stage1["passed"] is True
    assert stage1["proven_theorems"] == 4
    for entity in ("rfi", "commitment", "change_event", "submittal"):
        assert entity in stage1["theorems"]
        assert stage1["theorems"][entity]["proven"] is True
        assert str(stage1["theorems"][entity]["solver_status"]).lower() == "unsat"

    # Stage 2: Adversarial FSM Lifecycle & Homoglyph Immunity
    stage2 = report.stage2_fsm
    assert stage2["passed"] is True
    assert stage2["homoglyph_immunity"]["passed"] is True
    for entity in ("rfi", "commitment", "change_event", "submittal"):
        assert stage2["lifecycles"][entity] is True

    # Stage 3: HMAC-SHA256 Cryptographic Audit Ledger
    stage3 = report.stage3_audit
    assert stage3["passed"] is True
    assert stage3["genesis_signature_valid"] is True
    assert stage3["chain_valid"] is True
    assert stage3["timestamps_monotonic"] is True


def test_cli_execution_json_output(capsys: pytest.CaptureFixture[str]) -> None:
    """CLI execution main with --output json exits with code 0 and prints valid JSON."""
    with pytest.raises(SystemExit) as exc_info:
        main(["verify", "--quick", "--output", "json"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    data: dict[str, Any] = json.loads(captured.out)

    assert data["success"] is True
    assert data["status"] == "PASSED"
    assert "stages" in data
    assert "stage1_smt_z3" in data["stages"]
    assert "stage2_fsm_adversarial" in data["stages"]
    assert "stage3_audit_ledger" in data["stages"]
    assert data["stages"]["stage1_smt_z3"]["passed"] is True
    assert data["stages"]["stage2_fsm_adversarial"]["passed"] is True
    assert data["stages"]["stage3_audit_ledger"]["passed"] is True


def test_tampered_audit_log_strict_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Tampered audit log detection: corrupted log exits with code 1 under --strict."""
    log_path = tmp_path / "tampered_audit.jsonl"
    secret_key = b"test-secret-key-1234"

    # Create a valid audit log first
    mgr = AuditLogManager(log_path=log_path, secret_key=secret_key)
    mgr.log_event("procore_list_rfis", "ALLOWED", {"project_id": 101})
    mgr.log_event("procore_create_rfi_draft", "ALLOWED", {"rfi_id": 1, "status": "draft"})

    # Tamper with the log by corrupting line 2's payload_digest
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    entry2 = json.loads(lines[1])
    entry2["payload_digest"] = "f" * 64
    lines[1] = json.dumps(entry2)
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Programmatic verification should fail
    report = run_verification(
        quick=True,
        audit_log_path=log_path,
        audit_key=secret_key,
        strict=True,
    )
    assert report.success is False
    assert report.is_valid is False
    assert report.stage3_audit["passed"] is False
    is_compromised = (
        report.stage3_audit["chain_valid"] is False
        or report.stage3_audit["payload_digests_valid"] is False
    )
    assert is_compromised is True
    assert len(report.errors) > 0

    # CLI verify under --strict must exit with code 1
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "verify",
                "--quick",
                "--audit-log",
                str(log_path),
                "--audit-key",
                secret_key.decode("utf-8"),
                "--strict",
                "--output",
                "json",
            ]
        )
    assert exc_info.value.code == 1

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["success"] is False
    assert data["status"] == "FAILED"


def test_markdown_output_formatting(capsys: pytest.CaptureFixture[str]) -> None:
    """Markdown output formatting renders headers, tables, and formal attestation."""
    report = run_verification(quick=True)
    md = report.to_markdown()

    assert "# Procore MCP Formal Verification Certificate" in md
    assert "Stage 1: Z3 SMT Solver Model Checking" in md
    assert "Stage 2: Adversarial FSM Lifecycle & Homoglyph Immunity" in md
    assert "Stage 3: HMAC-SHA256 Cryptographic Audit Ledger" in md
    assert "UNSAT" in md
    assert "PROVEN" in md
    assert "| Entity |" in md or "| **Entity** |" in md

    with pytest.raises(SystemExit) as exc_info:
        main(["verify", "--quick", "--output", "markdown"])
    assert exc_info.value.code == 0

    captured = capsys.readouterr()
    assert "# Procore MCP Formal Verification Certificate" in captured.out


def test_terminal_output_formatting() -> None:
    """Terminal output renders Rich console dashboard with tables and panels."""
    report = run_verification(quick=True)
    console = Console(record=True, width=120)
    report.render_terminal(console=console)
    output = console.export_text()

    assert "Z3 SMT Solver" in output
    assert "Adversarial FSM" in output
    assert "HMAC-SHA256" in output
    assert "PROVEN" in output


def test_timestamp_monotonicity_violation(tmp_path: Path) -> None:
    """Detects timestamp non-monotonicity in audit log."""
    log_path = tmp_path / "monotonicity_audit.jsonl"
    secret_key = b"test-key-mono"

    mgr = AuditLogManager(log_path=log_path, secret_key=secret_key)
    mgr.log_event("tool1", "ALLOWED", {"a": 1}, timestamp="2026-10-04T12:00:00+00:00")
    mgr.log_event("tool2", "ALLOWED", {"b": 2}, timestamp="2026-10-04T11:00:00+00:00")

    report = run_verification(
        quick=True,
        audit_log_path=log_path,
        audit_key=secret_key,
        strict=True,
    )
    assert report.success is False
    assert report.stage3_audit["timestamps_monotonic"] is False
    assert any("monotonic" in err.lower() for err in report.errors)


def test_homoglyph_immunity_verification() -> None:
    """Verifies that Stage 2 adversarial checks detect fullwidth and zero-width homoglyphs."""
    report = run_verification(quick=True)
    imm = report.stage2_fsm["homoglyph_immunity"]
    assert imm["passed"] is True
    assert imm["vectors_tested"] > 0


def test_run_verification_full_depth() -> None:
    """Full depth verification (quick=False) tests depth 10 reachability theorems."""
    report = run_verification(quick=False)
    assert report.success is True
    stage1 = report.stage1_smt
    for entity in ("rfi", "commitment", "change_event", "submittal"):
        assert stage1["theorems"][entity]["max_depth"] == 10
        assert stage1["theorems"][entity]["proven"] is True


def test_cli_terminal_output_default(capsys: pytest.CaptureFixture[str]) -> None:
    """CLI execution main(["verify", "--quick"]) defaults to terminal output and exits 0."""
    with pytest.raises(SystemExit) as exc_info:
        main(["verify", "--quick"])
    assert exc_info.value.code == 0


def test_empty_audit_log_verification(tmp_path: Path) -> None:
    """Empty audit log is valid and does not cause verification failure."""
    empty_log = tmp_path / "empty_audit.jsonl"
    empty_log.touch()

    report = run_verification(
        quick=True,
        audit_log_path=empty_log,
        audit_key=b"any-key",
        strict=True,
    )
    assert report.success is True
    assert report.stage3_audit["passed"] is True
    assert report.stage3_audit["block_height"] == 0


def test_missing_audit_log_strict_vs_non_strict(tmp_path: Path) -> None:
    """Missing audit log fails under strict mode and passes with warning under non-strict mode."""
    missing_log = tmp_path / "does_not_exist.jsonl"

    report_strict = run_verification(
        quick=True,
        audit_log_path=missing_log,
        strict=True,
    )
    assert report_strict.success is False
    assert report_strict.stage3_audit["passed"] is False

    report_lenient = run_verification(
        quick=True,
        audit_log_path=missing_log,
        strict=False,
    )
    assert report_lenient.stage3_audit["passed"] is False


def test_sequence_gap_detection(tmp_path: Path) -> None:
    """Audit log with sequence gap (entry_id jump) is detected."""
    log_path = tmp_path / "gap_audit.jsonl"
    secret_key = b"secret-key-gap"

    mgr = AuditLogManager(log_path=log_path, secret_key=secret_key)
    mgr.log_event("tool1", "ALLOWED", {})
    mgr.log_event("tool2", "ALLOWED", {})

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    entry2 = json.loads(lines[1])
    entry2["entry_id"] = 5
    lines[1] = json.dumps(entry2)
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    report = run_verification(
        quick=True,
        audit_log_path=log_path,
        audit_key=secret_key,
        strict=True,
    )
    assert report.success is False
    assert report.stage3_audit["passed"] is False
    assert "sequence gap" in str(report.stage3_audit.get("error")).lower()


def test_malformed_json_detection(tmp_path: Path) -> None:
    """Malformed JSON line in audit log is detected."""
    log_path = tmp_path / "malformed_audit.jsonl"
    log_path.write_text("{not valid json\n", encoding="utf-8")

    report = run_verification(
        quick=True,
        audit_log_path=log_path,
        audit_key=b"secret",
        strict=True,
    )
    assert report.success is False
    assert "malformed" in str(report.stage3_audit.get("error")).lower()


def test_wrong_audit_key_detection(tmp_path: Path) -> None:
    """Providing wrong audit key causes signature mismatch failure."""
    log_path = tmp_path / "keyed_audit.jsonl"
    secret_key = b"correct-secret-key-1234"

    mgr = AuditLogManager(log_path=log_path, secret_key=secret_key)
    mgr.log_event("tool1", "ALLOWED", {"val": 1})

    report = run_verification(
        quick=True,
        audit_log_path=log_path,
        audit_key=b"wrong-secret-key-5678",
        strict=True,
    )
    assert report.success is False
    assert report.stage3_audit["passed"] is False
    assert "signature" in str(report.stage3_audit.get("error")).lower()
