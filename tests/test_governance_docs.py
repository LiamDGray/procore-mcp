"""Tests verifying enterprise governance, commercial licensing, and security documentation."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
COMMERCIAL_MD = DOCS_DIR / "COMMERCIAL.md"
SECURITY_MD = DOCS_DIR / "SECURITY.md"
README_MD = REPO_ROOT / "README.md"


class TestCommercialDocumentation:
    """Verifies docs/COMMERCIAL.md exists and contains enterprise terms, tiers, and indemnity."""

    def test_commercial_file_exists(self) -> None:
        """docs/COMMERCIAL.md must exist and have substantial content."""
        assert COMMERCIAL_MD.exists(), f"Missing {COMMERCIAL_MD}"
        assert COMMERCIAL_MD.stat().st_size > 1000, "COMMERCIAL.md is unexpectedly small"

    def test_bsl_vs_enterprise_terms(self) -> None:
        """COMMERCIAL.md must clearly define BSL 1.1 vs Enterprise Commercial License terms."""
        content = COMMERCIAL_MD.read_text(encoding="utf-8")
        assert "BSL 1.1" in content or "Business Source License 1.1" in content
        assert "Enterprise Commercial License" in content

    def test_commercial_pricing_tiers(self) -> None:
        """COMMERCIAL.md defines tiers without static consumer pricing."""
        content = COMMERCIAL_MD.read_text(encoding="utf-8")
        assert "Enterprise Commercial License" in content
        assert (
            "Turnkey Async Deployment Sprints" in content
            or "Turnkey Deployment Sprints" in content
        )
        assert "Enterprise Support Retainer" in content
        # Ensure no consumer sticker prices anchor enterprise procurement
        assert "$4,950" not in content
        assert "$12,500" not in content
        assert "$1,500" not in content
        assert "procurement@liamdgray.com" in content

    def test_legal_indemnity_and_dmsa(self) -> None:
        """COMMERCIAL.md must specify legal indemnity and multi-tenant DMSA credentials."""
        content = COMMERCIAL_MD.read_text(encoding="utf-8")
        assert "indemnity" in content.lower() or "indemnification" in content.lower()
        assert "multi-tenant" in content.lower()
        assert "DMSA" in content

    def test_procurement_contact(self) -> None:
        """COMMERCIAL.md must provide procurement contact details."""
        content = COMMERCIAL_MD.read_text(encoding="utf-8")
        assert "procurement" in content.lower() or "contact" in content.lower()
        assert "@" in content


class TestLicenseDocumentation:
    """Verifies LICENSE.md exists, conforms to BSL 1.1, and cross-references commercial terms."""

    def test_license_file_exists(self) -> None:
        """LICENSE.md must exist in repository root with substantive content."""
        license_md = REPO_ROOT / "LICENSE.md"
        assert license_md.exists(), f"Missing {license_md}"
        assert license_md.stat().st_size > 500, "LICENSE.md is unexpectedly small"

    def test_bsl_parameters(self) -> None:
        """LICENSE.md must declare BSL 1.1 parameters and Change Date."""
        license_md = REPO_ROOT / "LICENSE.md"
        content = license_md.read_text(encoding="utf-8")
        assert "Business Source License 1.1" in content
        assert "Liam D Gray Labs" in content
        assert "2028-10-04" in content
        assert "Apache License, Version 2.0" in content or "Apache 2.0" in content
        assert "docs/COMMERCIAL.md" in content or "COMMERCIAL.md" in content


class TestSecurityDocumentation:
    """Verifies docs/SECURITY.md contains security policies, proofs, and disclosure contact."""

    def test_security_file_exists(self) -> None:
        """docs/SECURITY.md must exist and have substantial content."""
        assert SECURITY_MD.exists(), f"Missing {SECURITY_MD}"
        assert SECURITY_MD.stat().st_size > 1000, "SECURITY.md is unexpectedly small"

    def test_zero_leak_credential_policy(self) -> None:
        """SECURITY.md must document zero-leak credential policy and secret masking."""
        content = SECURITY_MD.read_text(encoding="utf-8")
        assert "zero-leak" in content.lower() or "zero leak" in content.lower()
        assert "mask" in content.lower()
        assert "prompt" in content.lower()

    def test_structural_prompt_injection_immunity(self) -> None:
        """SECURITY.md must detail structural prompt injection immunity and safety gates."""
        content = SECURITY_MD.read_text(encoding="utf-8")
        assert "prompt injection" in content.lower()
        assert "safety gate" in content.lower() or "safety gates" in content.lower()

    def test_cryptographic_audit_log_specification(self) -> None:
        """SECURITY.md must define cryptographic HMAC-SHA256 audit log integrity."""
        content = SECURITY_MD.read_text(encoding="utf-8")
        assert "HMAC-SHA256" in content
        assert "audit log" in content.lower()

    def test_responsible_disclosure_and_contact(self) -> None:
        """SECURITY.md must include disclosure policy and security contact email."""
        content = SECURITY_MD.read_text(encoding="utf-8")
        assert "security@liamdgray.com" in content
        assert "disclosure" in content.lower() or "vulnerability" in content.lower()


class TestReadmePresentation:
    """Verifies README.md navigation links, guarantee callout, and badges."""

    def test_readme_links_to_key_docs(self) -> None:
        """README.md links to whitepaper, commercial, security, arch, deployment, license."""
        content = README_MD.read_text(encoding="utf-8")
        assert "docs/whitepaper.md" in content
        assert "docs/COMMERCIAL.md" in content
        assert "docs/SECURITY.md" in content
        assert "docs/ARCHITECTURE.md" in content
        assert "docs/DEPLOYMENT.md" in content
        assert "LICENSE.md" in content

    def test_zero_unauthorized_commitment_guarantee(self) -> None:
        """README.md must contain the 'Zero Unauthorized Commitment Guarantee' callout."""
        content = README_MD.read_text(encoding="utf-8")
        assert "Zero Unauthorized Commitment Guarantee" in content

    def test_github_status_badges(self) -> None:
        """README.md must contain badges for CI, Mypy Strict, Ruff, Context Diet, and License."""
        content = README_MD.read_text(encoding="utf-8")
        assert "CI" in content or "actions/workflows" in content or "checks" in content
        assert "mypy" in content.lower() and "strict" in content.lower()
        assert "ruff" in content.lower()
        assert (
            "context diet" in content.lower()
            or "token diet" in content.lower()
            or "-89.5%" in content
            or "89.5%" in content
        )
        assert "License" in content and "BSL" in content
