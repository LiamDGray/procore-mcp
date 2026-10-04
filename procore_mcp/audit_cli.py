"""Cryptographic Audit Flight Recorder CLI with Rich Visual Dashboard."""

from __future__ import annotations

import hmac
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from procore_mcp.audit import (
    GENESIS_PREV_SIGNATURE,
    AuditEntry,
    compute_entry_signature,
    compute_payload_digest,
)


def _get_console(console: Console | None = None) -> Console:
    """Return provided console or create an appropriately sized default."""
    if console is not None:
        return console
    if sys.stdout.isatty():
        return Console()
    return Console(width=160, height=100)


def run_audit_verify(
    log_path: Path | str,
    secret_key: bytes,
    console: Console | None = None,
) -> int:
    """Verify cryptographic integrity of an HMAC-chained audit log and display status dashboard.

    Returns:
        0 if chain integrity is completely valid, 1 if tampering or violation is detected.
    """
    con = _get_console(console)
    path = Path(log_path)

    if not path.exists():
        panel = Panel(
            f"[bold red]AUDIT CHAIN VERIFICATION ERROR[/bold red]\n\n"
            f"Audit log file not found: [yellow]{path}[/yellow]",
            title="Flight Recorder Integrity Violation",
            border_style="red",
        )
        con.print(panel)
        return 1

    if path.stat().st_size == 0:
        panel = Panel(
            "[bold green]AUDIT CHAIN INTEGRITY VERIFIED (EMPTY LOG)[/bold green]\n\n"
            f"Log Path: {path}\n"
            "Block Height: 0\n"
            "Total Verified Entries: 0\n"
            "Status: Valid empty audit log",
            title="Flight Recorder Integrity",
            border_style="green",
        )
        con.print(panel)
        return 0

    expected_entry_id = 1
    expected_prev_signature = GENESIS_PREV_SIGNATURE
    verified_entries = 0
    block_height = 0

    with path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line_str = line.strip()
            if not line_str:
                continue

            try:
                entry = json.loads(line_str)
            except json.JSONDecodeError as exc:
                panel = Panel(
                    f"[bold red]INTEGRITY VIOLATION DETECTED[/bold red]\n\n"
                    f"Log Path: {path}\n"
                    f"Failed at Block #{expected_entry_id} (line {line_num}): "
                    f"Malformed JSON: {exc}\n"
                    f"Verified Blocks Before Failure: {verified_entries}",
                    title="Flight Recorder Integrity Violation",
                    border_style="red",
                )
                con.print(panel)
                return 1

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
                entry_id_val = entry.get("entry_id", expected_entry_id)
                sorted_missing = sorted(missing)
                panel = Panel(
                    f"[bold red]INTEGRITY VIOLATION DETECTED[/bold red]\n\n"
                    f"Log Path: {path}\n"
                    f"Failed at Block #{entry_id_val}: Missing required audit fields: "
                    f"{sorted_missing}\n"
                    f"Verified Blocks Before Failure: {verified_entries}",
                    title="Flight Recorder Integrity Violation",
                    border_style="red",
                )
                con.print(panel)
                return 1

            entry_id = int(entry["entry_id"])
            if entry_id != expected_entry_id:
                panel = Panel(
                    f"[bold red]INTEGRITY VIOLATION DETECTED[/bold red]\n\n"
                    f"Log Path: {path}\n"
                    f"Failed at Block #{expected_entry_id}: Sequence gap detected "
                    f"(expected block #{expected_entry_id}, found block #{entry_id})\n"
                    f"Verified Blocks Before Failure: {verified_entries}",
                    title="Flight Recorder Integrity Violation",
                    border_style="red",
                )
                con.print(panel)
                return 1

            prev_sig = str(entry["prev_signature"])
            if prev_sig != expected_prev_signature:
                panel = Panel(
                    f"[bold red]INTEGRITY VIOLATION DETECTED[/bold red]\n\n"
                    f"Log Path: {path}\n"
                    f"Failed at Block #{entry_id}: Cryptographic chaining break "
                    f"(expected prev_signature {expected_prev_signature[:16]}..., "
                    f"got {prev_sig[:16]}...)\n"
                    f"Verified Blocks Before Failure: {verified_entries}",
                    title="Flight Recorder Integrity Violation",
                    border_style="red",
                )
                con.print(panel)
                return 1

            if "payload" in entry and entry["payload"] is not None:
                computed_digest = compute_payload_digest(entry["payload"])
                if computed_digest != entry["payload_digest"]:
                    panel = Panel(
                        f"[bold red]INTEGRITY VIOLATION DETECTED[/bold red]\n\n"
                        f"Log Path: {path}\n"
                        f"Failed at Block #{entry_id}: "
                        f"Payload digest mismatch (tampered payload data)\n"
                        f"Verified Blocks Before Failure: {verified_entries}",
                        title="Flight Recorder Integrity Violation",
                        border_style="red",
                    )
                    con.print(panel)
                    return 1

            expected_sig = compute_entry_signature(
                secret_key=secret_key,
                entry_id=entry_id,
                timestamp=str(entry["timestamp"]),
                tool_name=str(entry["tool_name"]),
                action_status=str(entry["action_status"]),
                caller=str(entry["caller"]),
                payload_digest=str(entry["payload_digest"]),
                prev_signature=prev_sig,
            )

            if not hmac.compare_digest(expected_sig, str(entry["signature"])):
                panel = Panel(
                    f"[bold red]INTEGRITY VIOLATION DETECTED[/bold red]\n\n"
                    f"Log Path: {path}\n"
                    f"Failed at Block #{entry_id}: HMAC signature mismatch "
                    f"(unauthorized tampering or invalid key)\n"
                    f"Verified Blocks Before Failure: {verified_entries}",
                    title="Flight Recorder Integrity Violation",
                    border_style="red",
                )
                con.print(panel)
                return 1

            verified_entries += 1
            block_height = entry_id
            expected_entry_id += 1
            expected_prev_signature = str(entry["signature"])

    panel = Panel(
        "[bold green]AUDIT CHAIN INTEGRITY VERIFIED[/bold green]\n\n"
        f"Log Path: [cyan]{path}[/cyan]\n"
        f"Block Height: [bold white]{block_height}[/bold white]\n"
        f"Total Verified Entries: [bold white]{verified_entries}[/bold white]\n"
        f"Chain Integrity: [green]Valid HMAC-SHA256 Chain "
        f"(Genesis -> Block #{block_height})[/green]",
        title="Flight Recorder Integrity",
        border_style="green",
    )
    con.print(panel)
    return 0


def run_audit_inspect(
    log_path: Path | str,
    limit: int = 50,
    blocked_only: bool = False,
    console: Console | None = None,
) -> int:
    """Inspect and render audit log records in a formatted visual Rich table.

    Returns:
        0 on successful inspection, 1 on file error.
    """
    con = _get_console(console)
    path = Path(log_path)

    if not path.exists():
        panel = Panel(
            f"[bold red]INSPECTION ERROR[/bold red]\n\n"
            f"Audit log file not found: [yellow]{path}[/yellow]",
            title="Flight Recorder Inspection",
            border_style="red",
        )
        con.print(panel)
        return 1

    entries: list[AuditEntry] = []
    if path.stat().st_size > 0:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    data = json.loads(line_str)
                    entries.append(AuditEntry.from_dict(data))
                except Exception:
                    continue

    if blocked_only:
        entries = [e for e in entries if e.action_status == "BLOCKED"]

    if limit > 0:
        entries = entries[:limit]

    filter_desc = "BLOCKED Only" if blocked_only else "All Actions"
    table = Table(
        title=f"Flight Recorder Audit Entries ({filter_desc})",
        header_style="bold cyan",
    )
    table.add_column("Block #", justify="right", style="cyan", no_wrap=True)
    table.add_column("Timestamp", style="white")
    table.add_column("Tool Name", style="bold magenta", no_wrap=True)
    table.add_column("Action Status", justify="center", no_wrap=True)
    table.add_column("Caller", style="blue", no_wrap=True)
    table.add_column("Payload Digest", style="dim")
    table.add_column("HMAC Prefix", style="dim")

    for entry in entries:
        if entry.action_status == "ALLOWED":
            status_display = "[bold green]ALLOWED[/bold green]"
        elif entry.action_status == "BLOCKED":
            status_display = "[bold red]BLOCKED[/bold red]"
        else:
            status_display = f"[bold yellow]{entry.action_status}[/bold yellow]"

        table.add_row(
            str(entry.entry_id),
            entry.timestamp,
            entry.tool_name,
            status_display,
            entry.caller,
            f"{entry.payload_digest[:16]}..."
            if len(entry.payload_digest) > 16
            else entry.payload_digest,
            f"{entry.signature[:16]}..." if len(entry.signature) > 16 else entry.signature,
        )

    con.print(table)
    return 0
