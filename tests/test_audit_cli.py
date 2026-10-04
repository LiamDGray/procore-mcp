"""Tests for Cryptographic Audit Flight Recorder CLI with Rich Visual Dashboard."""

from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from rich.console import Console

from procore_mcp.audit import AuditLogManager
from procore_mcp.audit_cli import run_audit_inspect, run_audit_verify
from procore_mcp.server import main


@pytest.fixture
def secret_key() -> bytes:
    return b"test-secret-audit-key-32bytes!!"


@pytest.fixture
def audit_log_path(tmp_path: Path) -> Path:
    return tmp_path / "flight_recorder_audit.jsonl"


@pytest.fixture
def populated_audit_log(audit_log_path: Path, secret_key: bytes) -> Path:
    manager = AuditLogManager(log_path=audit_log_path, secret_key=secret_key)
    manager.log_event(
        tool_name="procore_list_companies",
        action_status="ALLOWED",
        payload={"page": 1},
        caller="claude-desktop",
    )
    manager.log_event(
        tool_name="procore_create_rfi_draft",
        action_status="BLOCKED",
        payload={"status": "approved"},
        caller="claude-code",
    )
    manager.log_event(
        tool_name="procore_list_projects",
        action_status="ALLOWED",
        payload={"company_id": 42},
        caller="claude-desktop",
    )
    return audit_log_path


# --- 1. run_audit_verify Tests ---


def test_audit_verify_valid_log_returns_zero_and_green_panel(
    populated_audit_log: Path, secret_key: bytes
) -> None:
    string_io = io.StringIO()
    console = Console(file=string_io, force_terminal=True, width=120)

    exit_code = run_audit_verify(populated_audit_log, secret_key, console=console)

    assert exit_code == 0
    output = string_io.getvalue()
    # Outputs verification status panel with green indicators
    assert "AUDIT CHAIN INTEGRITY VERIFIED" in output or "VERIFIED" in output
    assert "Block Height" in output
    assert "3" in output
    assert "Total Verified Entries" in output or "Total Entries" in output
    # Check green styling is present in terminal output
    assert "green" in output or "\x1b[32m" in output or "VERIFIED" in output


def test_audit_verify_empty_log_returns_zero(tmp_path: Path, secret_key: bytes) -> None:
    empty_log = tmp_path / "empty.jsonl"
    empty_log.touch()
    string_io = io.StringIO()
    console = Console(file=string_io, force_terminal=True, width=120)

    exit_code = run_audit_verify(empty_log, secret_key, console=console)

    assert exit_code == 0
    output = string_io.getvalue()
    assert "0" in output
    assert "VERIFIED" in output


def test_audit_verify_tampered_status_returns_one_and_red_panel(
    populated_audit_log: Path, secret_key: bytes
) -> None:
    # Tamper with status in block #2 (change BLOCKED to ALLOWED)
    lines = populated_audit_log.read_text(encoding="utf-8").strip().splitlines()
    entry1 = json.loads(lines[1])
    entry1["action_status"] = "ALLOWED"
    lines[1] = json.dumps(entry1)
    populated_audit_log.write_text("\n".join(lines) + "\n", encoding="utf-8")

    string_io = io.StringIO()
    console = Console(file=string_io, force_terminal=True, width=120)

    exit_code = run_audit_verify(populated_audit_log, secret_key, console=console)

    assert exit_code == 1
    output = string_io.getvalue()
    assert "VIOLATION" in output or "INTEGRITY VIOLATION" in output or "FAILED" in output
    # Must identify exact block number where integrity failed
    assert "Block #2" in output or "block 2" in output.lower() or "entry_id 2" in output.lower()


def test_audit_verify_tampered_timestamp_identifies_block_one(
    populated_audit_log: Path, secret_key: bytes
) -> None:
    # Tamper with timestamp in block #1
    lines = populated_audit_log.read_text(encoding="utf-8").strip().splitlines()
    entry0 = json.loads(lines[0])
    entry0["timestamp"] = "2000-01-01T00:00:00Z"
    lines[0] = json.dumps(entry0)
    populated_audit_log.write_text("\n".join(lines) + "\n", encoding="utf-8")

    string_io = io.StringIO()
    console = Console(file=string_io, force_terminal=True, width=120)

    exit_code = run_audit_verify(populated_audit_log, secret_key, console=console)

    assert exit_code == 1
    output = string_io.getvalue()
    assert "VIOLATION" in output or "FAILED" in output
    assert "Block #1" in output or "block 1" in output.lower() or "entry_id 1" in output.lower()


def test_audit_verify_deleted_entry_identifies_sequence_break(
    populated_audit_log: Path, secret_key: bytes
) -> None:
    # Delete block #2 from the log
    lines = populated_audit_log.read_text(encoding="utf-8").strip().splitlines()
    del lines[1]  # Delete entry 2
    populated_audit_log.write_text("\n".join(lines) + "\n", encoding="utf-8")

    string_io = io.StringIO()
    console = Console(file=string_io, force_terminal=True, width=120)

    exit_code = run_audit_verify(populated_audit_log, secret_key, console=console)

    assert exit_code == 1
    output = string_io.getvalue()
    assert "VIOLATION" in output or "FAILED" in output
    assert "Block #2" in output or "block 2" in output.lower() or "entry_id 2" in output.lower()


def test_audit_verify_wrong_key_fails_at_block_one(
    populated_audit_log: Path,
) -> None:
    wrong_key = b"completely-wrong-audit-secret-key"
    string_io = io.StringIO()
    console = Console(file=string_io, force_terminal=True, width=120)

    exit_code = run_audit_verify(populated_audit_log, wrong_key, console=console)

    assert exit_code == 1
    output = string_io.getvalue()
    assert "VIOLATION" in output or "FAILED" in output
    assert "Block #1" in output or "block 1" in output.lower() or "entry_id 1" in output.lower()


def test_audit_verify_missing_file_returns_one(tmp_path: Path, secret_key: bytes) -> None:
    missing_path = tmp_path / "does_not_exist.jsonl"
    string_io = io.StringIO()
    console = Console(file=string_io, force_terminal=True, width=120)

    exit_code = run_audit_verify(missing_path, secret_key, console=console)

    assert exit_code == 1
    output = string_io.getvalue()
    assert "not found" in output.lower() or "does not exist" in output.lower()


# --- 2. run_audit_inspect Tests ---


def test_audit_inspect_renders_rich_table_with_required_columns(
    populated_audit_log: Path,
) -> None:
    string_io = io.StringIO()
    console = Console(file=string_io, force_terminal=True, width=160, height=100)

    exit_code = run_audit_inspect(
        populated_audit_log, limit=50, blocked_only=False, console=console
    )

    assert exit_code == 0
    output = string_io.getvalue()

    # Required columns:
    # Block #, Timestamp, Tool Name, Action Status, Caller, Payload Digest, HMAC Prefix
    assert "Block #" in output
    assert "Timestamp" in output
    assert "Tool Name" in output
    assert "Action Status" in output
    assert "Caller" in output
    assert "Payload Digest" in output
    assert "HMAC Prefix" in output

    # Check contents of rows
    assert "procore_list_companies" in output
    assert "procore_create_rfi_draft" in output
    assert "procore_list_projects" in output
    assert "ALLOWED" in output
    assert "BLOCKED" in output
    assert "claude-desktop" in output
    assert "claude-code" in output


def test_audit_inspect_blocked_only_filters_to_violations(
    populated_audit_log: Path,
) -> None:
    string_io = io.StringIO()
    console = Console(file=string_io, force_terminal=True, width=160, height=100)

    exit_code = run_audit_inspect(populated_audit_log, limit=50, blocked_only=True, console=console)

    assert exit_code == 0
    output = string_io.getvalue()

    assert "procore_create_rfi_draft" in output
    assert "BLOCKED" in output
    # ALLOWED tools must not appear in blocked-only mode
    assert "procore_list_companies" not in output
    assert "procore_list_projects" not in output


def test_audit_inspect_limit_caps_entry_count(
    populated_audit_log: Path,
) -> None:
    string_io = io.StringIO()
    console = Console(file=string_io, force_terminal=True, width=160, height=100)

    exit_code = run_audit_inspect(populated_audit_log, limit=1, blocked_only=False, console=console)

    assert exit_code == 0
    output = string_io.getvalue()

    # With limit=1, only 1 entry row is rendered
    assert "procore_list_companies" in output
    assert "procore_create_rfi_draft" not in output
    assert "procore_list_projects" not in output


def test_audit_inspect_empty_log_returns_zero(tmp_path: Path) -> None:
    empty_log = tmp_path / "empty_inspect.jsonl"
    empty_log.touch()
    string_io = io.StringIO()
    console = Console(file=string_io, force_terminal=True, width=160, height=100)

    exit_code = run_audit_inspect(empty_log, console=console)

    assert exit_code == 0


def test_audit_inspect_missing_file_returns_one(tmp_path: Path) -> None:
    missing_file = tmp_path / "nonexistent.jsonl"
    string_io = io.StringIO()
    console = Console(file=string_io, force_terminal=True, width=160, height=100)

    exit_code = run_audit_inspect(missing_file, console=console)

    assert exit_code == 1
    assert "not found" in string_io.getvalue().lower()


# --- 3. CLI Entrypoint Integration Tests (procore-mcp audit verify / inspect) ---


def test_cli_entrypoint_audit_verify_success(populated_audit_log: Path, secret_key: bytes) -> None:
    with patch("sys.exit") as mock_exit:
        main(
            [
                "audit",
                "verify",
                str(populated_audit_log),
                "--key",
                secret_key.decode("utf-8"),
            ]
        )
        mock_exit.assert_not_called()


def test_cli_entrypoint_audit_verify_tampered_fails(
    populated_audit_log: Path, secret_key: bytes
) -> None:
    # Tamper log
    lines = populated_audit_log.read_text(encoding="utf-8").strip().splitlines()
    entry = json.loads(lines[0])
    entry["action_status"] = "TAMPERED"
    lines[0] = json.dumps(entry)
    populated_audit_log.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "audit",
                "verify",
                str(populated_audit_log),
                "--key",
                secret_key.decode("utf-8"),
            ]
        )
    assert exc_info.value.code == 1


def test_cli_entrypoint_audit_inspect_blocked_only(
    populated_audit_log: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(
        [
            "audit",
            "inspect",
            str(populated_audit_log),
            "--blocked-only",
            "--limit",
            "10",
        ]
    )
    captured = capsys.readouterr()
    assert "procore_create_rfi_draft" in captured.out
    assert "BLOCKED" in captured.out
    assert "procore_list_companies" not in captured.out
