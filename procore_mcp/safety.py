"""Safety guardrails and state-transition invariants engine for Procore MCP."""

import re
import unicodedata
from typing import Any

FORBIDDEN_MUTATION_STATUSES: frozenset[str] = frozenset(
    {"issued", "approved", "executed", "closed"}
)

SAFE_MUTATION_STATUSES: frozenset[str] = frozenset({"draft", "open", "pending", "ready_for_review"})

_INVISIBLE_CHARS_RE: re.Pattern[str] = re.compile(
    r"[\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]"
)


def normalize_status_string(val: str) -> str:
    """Normalize a status key or value using NFKC unicode normalization,
    stripping invisible characters and whitespace, and converting to lowercase.
    """
    normalized = unicodedata.normalize("NFKC", val)
    normalized = _INVISIBLE_CHARS_RE.sub("", normalized)
    return normalized.strip().lower()


class SafetyInvariantViolation(Exception):
    """Raised when an operation violates state-transition invariants or safety guardrails."""


def _check_forbidden_status(value: Any, tool_name: str) -> None:
    """Recursively inspect an object for forbidden terminal/authoritative statuses."""
    if isinstance(value, dict):
        for k, v in value.items():
            if isinstance(k, str) and normalize_status_string(k) == "status":
                if isinstance(v, str) and normalize_status_string(v) in FORBIDDEN_MUTATION_STATUSES:
                    statuses_str = ", ".join(sorted(FORBIDDEN_MUTATION_STATUSES))
                    raise SafetyInvariantViolation(
                        f"Tool '{tool_name}' attempted to set forbidden status '{v.strip()}'. "
                        f"Mutations to terminal/authoritative statuses ({statuses_str}) "
                        "are blocked by safety guardrails."
                    )
            _check_forbidden_status(v, tool_name)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            _check_forbidden_status(item, tool_name)


def assert_write_permitted(tool_name: str, payload: dict[str, Any], allow_writes: bool) -> None:
    """Assert that a write operation is permitted by safety guardrails and state invariants.

    Args:
        tool_name: The name of the tool attempting the write.
        payload: The request payload/parameters to be inspected.
        allow_writes: Whether write operations are enabled globally on the server.

    Raises:
        PermissionError: If allow_writes is False (read-only mode).
        SafetyInvariantViolation: If payload attempts transition to a forbidden status.
    """
    if not allow_writes:
        raise PermissionError(
            f"Tool '{tool_name}' cannot perform writes: server is running in read-only mode."
        )

    _check_forbidden_status(payload, tool_name)
