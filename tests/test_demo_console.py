"""Tests for the interactive HTML demo console (docs/demo/index.html)."""

import re
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parent.parent / "docs" / "demo"
DEMO_HTML = DEMO_DIR / "index.html"


def test_demo_html_exists_and_size() -> None:
    """Verify docs/demo/index.html exists and is non-empty (>5000 bytes)."""
    assert DEMO_HTML.exists(), "docs/demo/index.html must exist"
    content = DEMO_HTML.read_text(encoding="utf-8")
    content_bytes = len(content.encode("utf-8"))
    assert content_bytes > 5000, f"docs/demo/index.html should be >5000 bytes, got {content_bytes}"


def test_demo_html_no_external_cdn_scripts() -> None:
    """Verify index.html is 100% offline and hermetic (no external CDN scripts or CSS)."""
    assert DEMO_HTML.exists()
    content = DEMO_HTML.read_text(encoding="utf-8")

    # Check for <script src="http...">
    script_pattern = r'<script[^>]+src=["\'](https?://[^"\']+)["\']'
    external_scripts = re.findall(script_pattern, content, re.IGNORECASE)
    assert not external_scripts, f"Found external CDN script tags: {external_scripts}"

    # Also check for external stylesheets from CDNs
    style_pattern = r'<link[^>]+href=["\'](https?://[^"\']+)["\']'
    external_styles = re.findall(style_pattern, content, re.IGNORECASE)
    assert not external_styles, f"Found external CDN stylesheets: {external_styles}"


def test_demo_html_contains_token_diet_simulator() -> None:
    """Verify Token Diet Simulator module and tiers (raw, compact, standard, executive)."""
    assert DEMO_HTML.exists()
    content = DEMO_HTML.read_text(encoding="utf-8")

    assert 'id="token-diet-simulator"' in content or 'class="token-diet-simulator"' in content
    # Verify tiers present in simulator
    assert "raw" in content.lower()
    assert "compact" in content.lower()
    assert "standard" in content.lower()
    assert "executive" in content.lower()
    # Verify token savings metrics mentioned
    assert "248" in content  # Raw 248KB
    assert "14" in content  # Compact 14KB
    assert "25" in content  # Standard 25KB
    assert "21" in content  # Executive 21KB


def test_demo_html_contains_safety_gate_simulator() -> None:
    """Verify Live Safety Gate Interceptor module with allowed draft vs blocked terminal states."""
    assert DEMO_HTML.exists()
    content = DEMO_HTML.read_text(encoding="utf-8")

    assert 'id="safety-gate-simulator"' in content or 'class="safety-gate-simulator"' in content
    assert "draft" in content.lower()
    assert "issued" in content.lower() or "rogue" in content.lower()
    assert "SafetyInvariantViolation" in content or "safety" in content.lower()
    assert "hmac" in content.lower()


def test_demo_html_contains_multi_agent_config_exporter() -> None:
    """Verify Multi-Agent Config Exporter containing all 7 clients."""
    assert DEMO_HTML.exists()
    content = DEMO_HTML.read_text(encoding="utf-8")

    assert 'id="config-exporter"' in content or 'class="config-exporter"' in content

    clients = [
        "claude-desktop",
        "claude-code",
        "cursor",
        "windsurf",
        "pi-agent",
        "hermes-agent",
        "codex-cli",
    ]
    for client in clients:
        assert client in content, f"Client {client} missing from config exporter in index.html"


def test_demo_html_contains_formal_verification_explorer() -> None:
    """Verify Formal Verification Proof Explorer with Z3 SMT solver and Lean 4 references."""
    assert DEMO_HTML.exists()
    content = DEMO_HTML.read_text(encoding="utf-8")

    assert 'id="verification-explorer"' in content or 'class="verification-explorer"' in content
    assert "Z3" in content or "z3" in content
    assert "SMT" in content or "smt" in content
    assert "Lean 4" in content or "lean" in content.lower()
    assert "unsat" in content.lower()


def test_demo_html_preserves_svg_and_cast_assets() -> None:
    """Verify index.html preserves existing SVG demo animation and asciinema cast links."""
    assert DEMO_HTML.exists()
    content = DEMO_HTML.read_text(encoding="utf-8")

    assert "procore_mcp_demo.svg" in content
    assert "procore_mcp_demo.cast" in content
