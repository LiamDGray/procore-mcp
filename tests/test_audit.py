"""Tests for Cryptographic Tamper-Evident HMAC Audit Trail for Enterprise Governance."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from procore_mcp.audit import (
    GENESIS_PREV_SIGNATURE,
    ActionStatus,
    AuditEntry,
    AuditLogManager,
    compute_payload_digest,
    verify_audit_log,
)
from procore_mcp.client import ProcoreClient
from procore_mcp.server import create_server


@pytest.fixture
def secret_key() -> bytes:
    return b"test-secret-audit-key-32bytes!!"


@pytest.fixture
def audit_log_path(tmp_path: Path) -> Path:
    return tmp_path / "procore_audit.jsonl"


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock(spec=ProcoreClient)
    client.list_companies.return_value = [{"id": 1, "name": "Acme Builders"}]
    client.create_rfi.return_value = {"id": 101, "subject": "Draft RFI", "status": "draft"}
    return client


# --- 1. AuditLogManager Unit & Structure Tests ---


def test_audit_entry_genesis_fields(audit_log_path: Path, secret_key: bytes) -> None:
    manager = AuditLogManager(log_path=audit_log_path, secret_key=secret_key)
    payload = {"company_id": 42, "query": "all"}

    entry = manager.log_event(
        tool_name="procore_list_projects",
        action_status="ALLOWED",
        payload=payload,
        caller="claude-enterprise",
    )

    assert isinstance(entry, AuditEntry)
    assert entry.entry_id == 1
    assert entry.tool_name == "procore_list_projects"
    assert entry.action_status == "ALLOWED"
    assert entry.caller == "claude-enterprise"
    assert entry.prev_signature == GENESIS_PREV_SIGNATURE
    assert entry.prev_signature == "0" * 64
    assert entry.payload_digest == compute_payload_digest(payload)
    assert len(entry.signature) == 64  # SHA-256 hex string

    # Verify written to .jsonl
    assert audit_log_path.exists()
    lines = audit_log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["entry_id"] == 1
    assert data["prev_signature"] == "0" * 64
    assert data["signature"] == entry.signature
    assert data["payload_digest"] == entry.payload_digest


def test_audit_log_chaining_and_incremental_ids(audit_log_path: Path, secret_key: bytes) -> None:
    manager = AuditLogManager(log_path=audit_log_path, secret_key=secret_key)

    e1 = manager.log_event("tool_1", "ALLOWED", {"step": 1})
    e2 = manager.log_event("tool_2", "BLOCKED", {"step": 2})
    e3 = manager.log_event("tool_3", "ERROR", {"step": 3})

    assert e1.entry_id == 1
    assert e1.prev_signature == "0" * 64

    assert e2.entry_id == 2
    assert e2.prev_signature == e1.signature

    assert e3.entry_id == 3
    assert e3.prev_signature == e2.signature

    # Reconnect a new manager instance to the same log path (e.g. process restart)
    manager_reconnected = AuditLogManager(log_path=audit_log_path, secret_key=secret_key)
    e4 = manager_reconnected.log_event("tool_4", "ALLOWED", {"step": 4})

    assert e4.entry_id == 4
    assert e4.prev_signature == e3.signature


# --- 2. Verification & Cryptographic Tamper Detection Tests ---


def test_verify_audit_log_uncompromised(audit_log_path: Path, secret_key: bytes) -> None:
    manager = AuditLogManager(log_path=audit_log_path, secret_key=secret_key)
    manager.log_event("tool_a", "ALLOWED", {"a": 1})
    manager.log_event("tool_b", "BLOCKED", {"b": 2})
    manager.log_event("tool_c", "ALLOWED", {"c": 3})

    is_valid, reason = verify_audit_log(audit_log_path, secret_key)
    assert is_valid is True
    assert reason is None


def test_verify_empty_audit_log(tmp_path: Path, secret_key: bytes) -> None:
    empty_log = tmp_path / "empty.jsonl"
    empty_log.touch()
    is_valid, reason = verify_audit_log(empty_log, secret_key)
    assert is_valid is True
    assert reason is None


def test_verify_missing_file(tmp_path: Path, secret_key: bytes) -> None:
    missing_log = tmp_path / "nonexistent.jsonl"
    is_valid, reason = verify_audit_log(missing_log, secret_key)
    assert is_valid is False
    assert reason is not None
    assert "not found" in reason.lower() or "does not exist" in reason.lower()


def test_tampering_altered_timestamp(audit_log_path: Path, secret_key: bytes) -> None:
    manager = AuditLogManager(log_path=audit_log_path, secret_key=secret_key)
    manager.log_event("tool_a", "ALLOWED", {"step": 1})
    manager.log_event("tool_b", "ALLOWED", {"step": 2})

    lines = audit_log_path.read_text(encoding="utf-8").strip().splitlines()
    entry1 = json.loads(lines[0])
    entry1["timestamp"] = "1999-01-01T00:00:00Z"
    lines[0] = json.dumps(entry1)
    audit_log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    is_valid, reason = verify_audit_log(audit_log_path, secret_key)
    assert is_valid is False
    assert reason is not None
    assert "signature mismatch" in reason.lower() or "hmac" in reason.lower()


def test_tampering_altered_status(audit_log_path: Path, secret_key: bytes) -> None:
    manager = AuditLogManager(log_path=audit_log_path, secret_key=secret_key)
    manager.log_event("tool_a", "BLOCKED", {"step": 1})

    lines = audit_log_path.read_text(encoding="utf-8").strip().splitlines()
    entry0 = json.loads(lines[0])
    entry0["action_status"] = "ALLOWED"  # Attacker attempts to change BLOCKED to ALLOWED
    lines[0] = json.dumps(entry0)
    audit_log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    is_valid, reason = verify_audit_log(audit_log_path, secret_key)
    assert is_valid is False
    assert reason is not None
    assert "signature mismatch" in reason.lower() or "hmac" in reason.lower()


def test_tampering_altered_payload_digest_or_data(audit_log_path: Path, secret_key: bytes) -> None:
    manager = AuditLogManager(log_path=audit_log_path, secret_key=secret_key)
    manager.log_event("tool_a", "ALLOWED", {"authorized_transfer": False})

    lines = audit_log_path.read_text(encoding="utf-8").strip().splitlines()
    entry0 = json.loads(lines[0])
    # Attacker changes payload digest or tampered payload
    entry0["payload_digest"] = hashlib.sha256(b"tampered data").hexdigest()
    lines[0] = json.dumps(entry0)
    audit_log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    is_valid, reason = verify_audit_log(audit_log_path, secret_key)
    assert is_valid is False
    assert reason is not None


def test_tampering_deleted_entry_in_middle(audit_log_path: Path, secret_key: bytes) -> None:
    manager = AuditLogManager(log_path=audit_log_path, secret_key=secret_key)
    manager.log_event("tool_1", "ALLOWED", {"step": 1})
    manager.log_event("tool_2", "BLOCKED", {"step": 2})  # Attacker deletes this evidence
    manager.log_event("tool_3", "ALLOWED", {"step": 3})

    lines = audit_log_path.read_text(encoding="utf-8").strip().splitlines()
    # Remove entry 2 (index 1)
    del lines[1]
    audit_log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    is_valid, reason = verify_audit_log(audit_log_path, secret_key)
    assert is_valid is False
    assert reason is not None
    assert (
        "gap" in reason.lower() or "chain" in reason.lower() or "prev_signature" in reason.lower()
    )


def test_tampering_modified_or_truncated_hmac_signature(
    audit_log_path: Path, secret_key: bytes
) -> None:
    manager = AuditLogManager(log_path=audit_log_path, secret_key=secret_key)
    manager.log_event("tool_1", "ALLOWED", {"step": 1})

    lines = audit_log_path.read_text(encoding="utf-8").strip().splitlines()
    entry0 = json.loads(lines[0])
    entry0["signature"] = entry0["signature"][:-8] + "deadbeef"
    lines[0] = json.dumps(entry0)
    audit_log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    is_valid, reason = verify_audit_log(audit_log_path, secret_key)
    assert is_valid is False
    assert reason is not None
    assert "signature mismatch" in reason.lower() or "hmac" in reason.lower()


def test_tampering_incorrect_secret_key(audit_log_path: Path, secret_key: bytes) -> None:
    manager = AuditLogManager(log_path=audit_log_path, secret_key=secret_key)
    manager.log_event("tool_1", "ALLOWED", {"step": 1})

    wrong_key = b"wrong-audit-secret-key-00000000"
    is_valid, reason = verify_audit_log(audit_log_path, wrong_key)
    assert is_valid is False
    assert reason is not None
    assert "signature mismatch" in reason.lower() or "hmac" in reason.lower()


# --- 3. Server & Safety Gate Integration Tests ---


def test_server_calling_tool_generates_allowed_audit_entry(
    audit_log_path: Path, secret_key: bytes, mock_client: MagicMock
) -> None:
    manager = AuditLogManager(log_path=audit_log_path, secret_key=secret_key)
    server = create_server(client=mock_client, audit_manager=manager)

    # Call a read tool
    asyncio.run(server.call_tool("procore_list_companies", {"page": 1, "per_page": 10}))

    # Verify audit log recorded an ALLOWED event
    assert audit_log_path.exists()
    entries = manager.get_entries()
    assert len(entries) == 1
    assert entries[0].tool_name == "procore_list_companies"
    assert entries[0].action_status == ActionStatus.ALLOWED or entries[0].action_status == "ALLOWED"
    assert entries[0].prev_signature == "0" * 64

    # Verify cryptographic integrity of the generated log
    is_valid, reason = verify_audit_log(audit_log_path, secret_key)
    assert is_valid is True
    assert reason is None


def test_server_blocked_write_attempt_generates_blocked_audit_entry(
    audit_log_path: Path, secret_key: bytes, mock_client: MagicMock
) -> None:
    manager = AuditLogManager(log_path=audit_log_path, secret_key=secret_key)
    server = create_server(allow_writes=False, client=mock_client, audit_manager=manager)

    offending_payload = {"project_id": 10, "subject": "Unauthorized Draft RFI"}
    offending_digest = compute_payload_digest(offending_payload)

    with pytest.raises(Exception) as exc_info:
        asyncio.run(server.call_tool("procore_create_rfi_draft", offending_payload))
    assert "read-only mode" in str(exc_info.value)
    mock_client.create_rfi.assert_not_called()

    # Verify audit log recorded a BLOCKED event with offending payload digest
    entries = manager.get_entries()
    assert len(entries) == 1
    assert entries[0].tool_name == "procore_create_rfi_draft"
    assert entries[0].action_status == "BLOCKED"
    assert entries[0].payload_digest == offending_digest

    # Verify the audit log itself remains cryptographically uncorrupted and verifiable
    is_valid, reason = verify_audit_log(audit_log_path, secret_key)
    assert is_valid is True
    assert reason is None


def test_server_blocked_forbidden_status_generates_blocked_audit_entry(
    audit_log_path: Path, secret_key: bytes, mock_client: MagicMock
) -> None:
    manager = AuditLogManager(log_path=audit_log_path, secret_key=secret_key)
    server = create_server(allow_writes=True, client=mock_client, audit_manager=manager)

    forbidden_payload = {
        "project_id": 10,
        "subject": "Forbidden Status RFI",
        "status": "approved",
    }
    forbidden_digest = compute_payload_digest(forbidden_payload)

    with pytest.raises(Exception) as exc_info:
        asyncio.run(server.call_tool("procore_create_rfi_draft", forbidden_payload))
    assert "forbidden status" in str(exc_info.value).lower()
    mock_client.create_rfi.assert_not_called()

    entries = manager.get_entries()
    assert len(entries) == 1
    assert entries[0].tool_name == "procore_create_rfi_draft"
    assert entries[0].action_status == "BLOCKED"
    assert entries[0].payload_digest == forbidden_digest

    is_valid, reason = verify_audit_log(audit_log_path, secret_key)
    assert is_valid is True
    assert reason is None


def test_server_env_instantiates_audit_log_manager(
    monkeypatch: pytest.MonkeyPatch,
    audit_log_path: Path,
    mock_client: MagicMock,
) -> None:
    key_hex = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    monkeypatch.setenv("PROCORE_AUDIT_LOG_PATH", str(audit_log_path))
    monkeypatch.setenv("PROCORE_AUDIT_KEY", key_hex)

    server = create_server(client=mock_client)
    asyncio.run(server.call_tool("procore_list_companies", {"page": 1, "per_page": 5}))

    assert audit_log_path.exists()
    is_valid, reason = verify_audit_log(audit_log_path, key_hex.encode("utf-8"))
    assert is_valid is True
    assert reason is None
