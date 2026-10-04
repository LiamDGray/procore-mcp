"""Tests verifying the formal research whitepaper in Markdown and LaTeX formats."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
WHITEPAPER_MD = DOCS_DIR / "whitepaper.md"
WHITEPAPER_TEX = DOCS_DIR / "whitepaper.tex"

REQUIRED_THEOREMS = [
    "Theorem 1: Zero Terminal Reachability",
    "Theorem 2: Adversarial Invariant Robustness",
    "Theorem 3: Cryptographic Audit Hash Chaining",
]

REQUIRED_SYMBOLS = [
    "ReachableStates",
    "FORBIDDEN_MUTATION_STATUSES",
    "HMAC-SHA256",
]

REQUIRED_MODULES = [
    "Companies",
    "Projects",
    "Directory",
    "Cost Codes",
    "RFIs",
    "Submittals",
    "Daily Logs",
    "Change Events",
    "Commitments",
    "Budget",
]


class TestWhitepaperArtifacts:
    """Verifies that whitepaper documents exist, are non-empty, and contain all theorems."""

    def test_whitepaper_files_exist_and_non_empty(self) -> None:
        """docs/whitepaper.md and docs/whitepaper.tex must exist and have substantial content."""
        assert WHITEPAPER_MD.exists(), f"Missing {WHITEPAPER_MD}"
        assert WHITEPAPER_TEX.exists(), f"Missing {WHITEPAPER_TEX}"

        md_size = WHITEPAPER_MD.stat().st_size
        tex_size = WHITEPAPER_TEX.stat().st_size

        assert md_size > 5000, f"whitepaper.md is too small ({md_size} bytes)"
        assert tex_size > 5000, f"whitepaper.tex is too small ({tex_size} bytes)"

    def test_markdown_title_and_sections(self) -> None:
        """Markdown whitepaper must have exact title and essential academic sections."""
        content = WHITEPAPER_MD.read_text(encoding="utf-8")
        expected_title = (
            "Deterministic Safety Invariants and Cryptographic Auditability in "
            "Autonomous Construction AI: Proving Zero Terminal Reachability in "
            "Model Context Protocol Implementations"
        )
        assert expected_title in content

        required_sections = [
            "Abstract",
            "Introduction",
            "Construction Domain Liability Model",
            "System Architecture",
            "Formal State Machine Verification",
            "Adversarial Fuzzing Results",
            "Cryptographic HMAC Audit Chain",
            "Token Distillation Efficiency Benchmarks",
            "Conclusion",
        ]
        for section in required_sections:
            assert section.lower() in content.lower(), f"Missing section: {section}"

    def test_markdown_theorems_and_symbols(self) -> None:
        """Markdown whitepaper must contain all formal theorems and mathematical symbols."""
        content = WHITEPAPER_MD.read_text(encoding="utf-8")

        for theorem in REQUIRED_THEOREMS:
            assert theorem in content, f"Missing theorem in markdown: {theorem}"

        for symbol in REQUIRED_SYMBOLS:
            assert symbol in content, f"Missing symbol in markdown: {symbol}"

        assert "89.5%" in content or "89.53%" in content, (
            "Missing aggregate token reduction (89.5% or 89.53%) in markdown"
        )

        for module in REQUIRED_MODULES:
            assert module in content, f"Missing benchmark module in markdown: {module}"

    def test_latex_title_and_packages(self) -> None:
        """LaTeX whitepaper must conform to publication standards with required packages."""
        content = WHITEPAPER_TEX.read_text(encoding="utf-8")

        assert r"\documentclass" in content
        assert "amsmath" in content
        assert "amssymb" in content
        assert "hyperref" in content
        assert "booktabs" in content
        assert "tikz" in content
        assert r"\begin{document}" in content
        assert r"\end{document}" in content

        for theorem in REQUIRED_THEOREMS:
            assert theorem in content, f"Missing theorem in LaTeX: {theorem}"

        for symbol in REQUIRED_SYMBOLS:
            assert symbol in content, f"Missing symbol in LaTeX: {symbol}"

        assert "89.5%" in content or "89.53%" in content, (
            "Missing aggregate token reduction (89.5% or 89.53%) in LaTeX"
        )

        for module in REQUIRED_MODULES:
            assert module in content, f"Missing benchmark module in LaTeX: {module}"

    def test_latex_compilation(self, tmp_path: Path) -> None:
        """LaTeX whitepaper compiles cleanly with pdflatex if available on the system."""
        pdflatex_bin = shutil.which("pdflatex")
        if not pdflatex_bin:
            pytest.skip("pdflatex is not installed on this system")

        # Copy .tex file to tmp_path to avoid littering docs/ with auxiliary files (.aux, .log)
        temp_tex = tmp_path / "whitepaper.tex"
        shutil.copy(WHITEPAPER_TEX, temp_tex)

        result = subprocess.run(
            [pdflatex_bin, "-interaction=nonstopmode", "-halt-on-error", "whitepaper.tex"],
            cwd=str(tmp_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )

        assert result.returncode == 0, (
            f"pdflatex compilation failed with code {result.returncode}:\n{result.stdout[-2000:]}"
        )
        output_pdf = tmp_path / "whitepaper.pdf"
        assert output_pdf.exists(), "pdflatex succeeded but whitepaper.pdf was not generated"
        assert output_pdf.stat().st_size > 10000, "Generated PDF is unexpectedly small"
