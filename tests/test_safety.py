"""Tests for safety guardrails and state-transition invariants."""

from typing import Any

import pytest

from procore_mcp.safety import (
    FORBIDDEN_MUTATION_STATUSES,
    SafetyInvariantViolation,
    assert_write_permitted,
)


def test_forbidden_statuses_constant() -> None:
    """Verify standard forbidden terminal/authoritative statuses."""
    expected = {"issued", "approved", "executed", "closed"}
    assert expected.issubset({s.lower() for s in FORBIDDEN_MUTATION_STATUSES})


def test_read_only_mode_blocks_writes() -> None:
    """Read-only default: allow_writes=False must raise PermissionError."""
    with pytest.raises(PermissionError, match=r"read-only mode"):
        assert_write_permitted("create_rfi", {"title": "RFI 1"}, allow_writes=False)

    with pytest.raises(PermissionError, match=r"read-only mode"):
        assert_write_permitted("update_budget", {}, allow_writes=False)


def test_read_only_mode_blocks_even_with_forbidden_payload() -> None:
    """PermissionError takes precedence when allow_writes=False."""
    with pytest.raises(PermissionError, match=r"read-only mode"):
        assert_write_permitted("close_rfi", {"status": "closed"}, allow_writes=False)


@pytest.mark.parametrize(
    "status",
    [
        "issued",
        "Issued",
        "ISSUED",
        " approved",
        "APPROVED ",
        "executed",
        "EXECUTED",
        "closed",
        "Closed",
        "  closed  ",
    ],
)
def test_hard_invariant_forbids_terminal_statuses(status: str) -> None:
    """Terminal or authoritative statuses must raise SafetyInvariantViolation."""
    payload: dict[str, Any] = {"title": "Test Item", "status": status}
    with pytest.raises(SafetyInvariantViolation) as exc_info:
        assert_write_permitted("update_rfi", payload, allow_writes=True)

    assert "forbidden" in str(exc_info.value).lower()


@pytest.mark.parametrize(
    "nested_payload",
    [
        {"rfi": {"status": "Issued"}},
        {"item": {"details": {"status": "approved"}}},
        {"batch": [{"status": "draft"}, {"status": "Executed"}]},
        {"data": {"nested_list": [[{"status": "closed"}]]}},
        {"submittals": [{"actions": [{"status": " closed "}]}]},
    ],
)
def test_hard_invariant_scans_nested_structures(nested_payload: dict[str, Any]) -> None:
    """Nested dicts and lists must be recursively inspected for forbidden statuses."""
    with pytest.raises(SafetyInvariantViolation) as exc_info:
        assert_write_permitted("patch_record", nested_payload, allow_writes=True)

    assert "forbidden" in str(exc_info.value).lower()


@pytest.mark.parametrize(
    "safe_status",
    [
        "draft",
        "Draft",
        "DRAFT",
        "open",
        "Open",
        "pending",
        "ready_for_review",
        "READY_FOR_REVIEW",
    ],
)
def test_safe_statuses_allowed(safe_status: str) -> None:
    """Safe draft/in-progress statuses are permitted when allow_writes=True."""
    payload: dict[str, Any] = {
        "title": "Valid Draft",
        "status": safe_status,
        "details": {"status": "draft"},
    }
    # Should not raise any exception
    assert_write_permitted("create_rfi", payload, allow_writes=True)


def test_omitted_status_and_arbitrary_payload_allowed() -> None:
    """Payloads without status fields or with empty data are allowed."""
    assert_write_permitted("create_item", {}, allow_writes=True)
    assert_write_permitted(
        "update_spec",
        {
            "description": "Updated spec description",
            "quantity": 10,
            "is_active": True,
            "cost": 125.50,
            "tags": ["structural", "foundation"],
            "metadata": {"reviewer_id": 42, "notes": None},
        },
        allow_writes=True,
    )


def test_non_string_status_values_handled_gracefully() -> None:
    """Non-string status values (e.g. numbers, booleans, None) do not crash scanner."""
    assert_write_permitted("test_tool", {"status": 100}, allow_writes=True)
    assert_write_permitted("test_tool", {"status": None}, allow_writes=True)
    assert_write_permitted("test_tool", {"status": True}, allow_writes=True)
    assert_write_permitted("test_tool", {"status": {"code": 1}}, allow_writes=True)


def test_package_exports() -> None:
    """Verify safety symbols are exported at package root."""
    import procore_mcp
    from procore_mcp.safety import SAFE_MUTATION_STATUSES, normalize_status_string

    assert hasattr(procore_mcp, "SafetyInvariantViolation")
    assert hasattr(procore_mcp, "assert_write_permitted")
    assert hasattr(procore_mcp, "FORBIDDEN_MUTATION_STATUSES")
    assert hasattr(procore_mcp, "SAFE_MUTATION_STATUSES")
    assert hasattr(procore_mcp, "normalize_status_string")
    assert procore_mcp.SafetyInvariantViolation is SafetyInvariantViolation
    assert procore_mcp.assert_write_permitted is assert_write_permitted
    assert procore_mcp.FORBIDDEN_MUTATION_STATUSES is FORBIDDEN_MUTATION_STATUSES
    assert procore_mcp.SAFE_MUTATION_STATUSES is SAFE_MUTATION_STATUSES
    assert procore_mcp.normalize_status_string is normalize_status_string
