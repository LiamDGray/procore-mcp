#!/usr/bin/env python3
"""Automated Demo Recording CLI Script.

Executes the headless Procore-MCP demo scenario and generates .cast and .svg visual assets.
Usage:
    python3 scripts/record_demo.py [--out-dir docs/demo]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure repo root is on sys.path when script is executed directly
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from procore_mcp.recorder import (  # noqa: E402
    generate_asciinema_cast,
    generate_svg_animation,
    run_demo_scenario,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Record automated headless demo scenario")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("docs/demo"),
        help="Directory to save demo assets (default: docs/demo)",
    )
    args = parser.parse_args()

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=== Procore-MCP Headless Demo Recorder ===")
    print(f"Target directory: {out_dir.resolve()}")
    print("Running scripted scenario...")

    result = run_demo_scenario(output_dir=out_dir)
    print(f"  [OK] Scenario completed in {result.total_duration:.2f}s ({len(result.steps)} steps)")
    print(f"  [OK] Cryptographic audit chain verified: {result.verified_integrity}")

    cast_path = out_dir / "procore_mcp_demo.cast"
    generate_asciinema_cast(result, cast_path)
    print(f"  [OK] Asciinema recording saved: {cast_path}")

    svg_path = out_dir / "procore_mcp_demo.svg"
    generate_svg_animation(result, svg_path)
    print(f"  [OK] High-resolution SVG graphic saved: {svg_path}")

    print("\nAll demo assets generated successfully without requiring a Procore subscription!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
