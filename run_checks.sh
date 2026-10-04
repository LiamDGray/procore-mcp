#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

echo "=== [1/3] Ruff Lint & Formatting ==="
ruff check .

echo "=== [2/3] Mypy Strict Type Check ==="
python3 -m mypy --strict procore_mcp tests

echo "=== [3/3] Pytest Test Suite ==="
python3 -m pytest -q

echo "=== ALL CHECKS PASSED (Green & Clean) ==="
