"""Cryptographic Tamper-Evident HMAC Audit Trail for Enterprise Governance."""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

GENESIS_PREV_SIGNATURE: str = "0" * 64


class ActionStatus(str, Enum):
    """Action outcome status for audited operations."""

    ALLOWED = "ALLOWED"
    BLOCKED = "BLOCKED"
    ERROR = "ERROR"


@dataclass
class AuditEntry:
    """Structured audit log entry containing cryptographic HMAC chaining metadata."""

    entry_id: int
    timestamp: str
    tool_name: str
    action_status: str
    caller: str
    payload_digest: str
    prev_signature: str
    signature: str
    payload: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert entry to a dictionary matching JSONL schema."""
        data: dict[str, Any] = {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "tool_name": self.tool_name,
            "action_status": self.action_status,
            "caller": self.caller,
            "payload_digest": self.payload_digest,
            "prev_signature": self.prev_signature,
            "signature": self.signature,
        }
        if self.payload is not None:
            data["payload"] = self.payload
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuditEntry:
        """Create an AuditEntry from parsed dictionary data."""
        return cls(
            entry_id=int(data["entry_id"]),
            timestamp=str(data["timestamp"]),
            tool_name=str(data["tool_name"]),
            action_status=str(data["action_status"]),
            caller=str(data["caller"]),
            payload_digest=str(data["payload_digest"]),
            prev_signature=str(data["prev_signature"]),
            signature=str(data["signature"]),
            payload=data.get("payload"),
        )

    def signable_bytes(self) -> bytes:
        """Generate canonical bytes for HMAC-SHA256 calculation."""
        data = {
            "action_status": self.action_status,
            "caller": self.caller,
            "entry_id": self.entry_id,
            "payload_digest": self.payload_digest,
            "prev_signature": self.prev_signature,
            "timestamp": self.timestamp,
            "tool_name": self.tool_name,
        }
        return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_payload_digest(payload: Any) -> str:
    """Compute deterministic SHA-256 digest of payload data."""
    if payload is None:
        raw = b"{}"
    elif isinstance(payload, bytes):
        raw = payload
    elif isinstance(payload, str):
        raw = payload.encode("utf-8")
    else:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
            "utf-8"
        )
    return hashlib.sha256(raw).hexdigest()


def compute_entry_signature(
    secret_key: bytes,
    entry_id: int,
    timestamp: str,
    tool_name: str,
    action_status: str,
    caller: str,
    payload_digest: str,
    prev_signature: str,
) -> str:
    """Compute HMAC-SHA256 signature for canonical audit entry data."""
    data = {
        "action_status": action_status,
        "caller": caller,
        "entry_id": entry_id,
        "payload_digest": payload_digest,
        "prev_signature": prev_signature,
        "timestamp": timestamp,
        "tool_name": tool_name,
    }
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(secret_key, canonical, hashlib.sha256).hexdigest()


class AuditLogManager:
    """Thread-safe append-only manager for tamper-evident HMAC chained audit logs."""

    def __init__(self, log_path: Path | str, secret_key: bytes) -> None:
        self.log_path = Path(log_path)
        self.secret_key = secret_key
        self._lock = threading.Lock()
        self._last_entry_id = 0
        self._last_signature = GENESIS_PREV_SIGNATURE

        self._initialize_chain()

    def _initialize_chain(self) -> None:
        """Scan existing log file to determine current chain state."""
        if not self.log_path.exists() or self.log_path.stat().st_size == 0:
            return

        with self.log_path.open("r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    entry_dict = json.loads(stripped)
                    self._last_entry_id = int(entry_dict["entry_id"])
                    self._last_signature = str(entry_dict["signature"])
                except Exception:
                    pass

    def log_event(
        self,
        tool_name: str,
        action_status: str | ActionStatus,
        payload: Any = None,
        caller: str = "mcp_client",
        payload_digest: str | None = None,
        timestamp: str | None = None,
    ) -> AuditEntry:
        """Log an event, append it to the chain, and flush to disk."""
        status_str = (
            action_status.value if isinstance(action_status, ActionStatus) else str(action_status)
        )
        ts = timestamp if timestamp is not None else datetime.now(timezone.utc).isoformat()
        digest = payload_digest if payload_digest is not None else compute_payload_digest(payload)

        with self._lock:
            entry_id = self._last_entry_id + 1
            prev_sig = self._last_signature

            sig = compute_entry_signature(
                secret_key=self.secret_key,
                entry_id=entry_id,
                timestamp=ts,
                tool_name=tool_name,
                action_status=status_str,
                caller=caller,
                payload_digest=digest,
                prev_signature=prev_sig,
            )

            entry = AuditEntry(
                entry_id=entry_id,
                timestamp=ts,
                tool_name=tool_name,
                action_status=status_str,
                caller=caller,
                payload_digest=digest,
                prev_signature=prev_sig,
                signature=sig,
                payload=payload if isinstance(payload, dict) else None,
            )

            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")
                f.flush()

            self._last_entry_id = entry_id
            self._last_signature = sig

            return entry

    log = log_event

    def get_entries(self) -> list[AuditEntry]:
        """Read and parse all entries currently in the log file."""
        if not self.log_path.exists():
            return []
        entries: list[AuditEntry] = []
        with self.log_path.open("r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if line_str:
                    entries.append(AuditEntry.from_dict(json.loads(line_str)))
        return entries


def verify_audit_log(log_path: Path | str, secret_key: bytes) -> tuple[bool, str | None]:
    """Verify cryptographic integrity and sequence of an HMAC chained audit log."""
    path = Path(log_path)
    if not path.exists():
        return False, f"Audit log file not found: {path}"

    if path.stat().st_size == 0:
        return True, None

    expected_entry_id = 1
    expected_prev_signature = GENESIS_PREV_SIGNATURE

    with path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line_str = line.strip()
            if not line_str:
                continue

            try:
                entry = json.loads(line_str)
            except json.JSONDecodeError as exc:
                return False, f"Malformed JSON on line {line_num}: {exc}"

            required_fields = {
                "entry_id",
                "timestamp",
                "tool_name",
                "action_status",
                "caller",
                "payload_digest",
                "prev_signature",
                "signature",
            }
            missing = required_fields - set(entry.keys())
            if missing:
                return (
                    False,
                    f"Missing required audit fields on line {line_num}: {sorted(missing)}",
                )

            entry_id = entry["entry_id"]
            if entry_id != expected_entry_id:
                return (
                    False,
                    f"Sequence gap at line {line_num}: "
                    f"expected entry_id {expected_entry_id}, got {entry_id}",
                )

            prev_sig = entry["prev_signature"]
            if prev_sig != expected_prev_signature:
                return (
                    False,
                    f"Chain break at entry_id {entry_id}: expected prev_signature "
                    f"{expected_prev_signature}, got {prev_sig}",
                )

            # Check if payload is stored and if it matches payload_digest
            if "payload" in entry and entry["payload"] is not None:
                computed_digest = compute_payload_digest(entry["payload"])
                if computed_digest != entry["payload_digest"]:
                    return (
                        False,
                        f"Payload digest mismatch at entry_id {entry_id}: payload data tampered",
                    )

            expected_sig = compute_entry_signature(
                secret_key=secret_key,
                entry_id=entry_id,
                timestamp=entry["timestamp"],
                tool_name=entry["tool_name"],
                action_status=entry["action_status"],
                caller=entry["caller"],
                payload_digest=entry["payload_digest"],
                prev_signature=prev_sig,
            )

            if not hmac.compare_digest(expected_sig, entry["signature"]):
                return (
                    False,
                    f"HMAC signature mismatch at entry_id {entry_id}: "
                    "signature verification failed",
                )

            expected_entry_id += 1
            expected_prev_signature = entry["signature"]

    return True, None
