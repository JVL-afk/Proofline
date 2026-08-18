"""Validate the dependency-free repository foundation through M6.5.

This script intentionally uses only the Python standard library so a clean
checkout can validate governance and structure before application dependencies
exist.
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = (
    ".editorconfig",
    ".env.example",
    ".gitattributes",
    ".gitignore",
    ".nvmrc",
    ".python-version",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "GREENFIELD_ARCHITECTURE.md",
    "README.md",
    "SECURITY.md",
    "package-lock.json",
    "package.json",
    "pyproject.toml",
    "uv.lock",
    "apps/README.md",
    "services/README.md",
    "workers/README.md",
    "packages/README.md",
    "infra/README.md",
    "infra/local/README.md",
    "infra/terraform/README.md",
    "docs/adr/0000-template.md",
    "docs/adr/0001-modular-monolith-monorepo.md",
    "docs/adr/0002-runtime-and-workspace-baseline.md",
    "docs/adr/0003-python-workspace-and-locking.md",
    "docs/adr/0004-m0-local-walking-skeleton-adapters.md",
    "docs/adr/0005-m1-bounded-local-research.md",
    "docs/adr/0006-m2-semantic-lineage-and-review.md",
    "docs/adr/0007-commercial-hvac-lead-response-definition.md",
    "docs/adr/0008-m2-deterministic-economics-and-hypotheticals.md",
    "docs/adr/0009-m2-uncalibrated-factor-bands.md",
    "docs/adr/0010-m2-rule-based-reasoning.md",
    "docs/adr/0011-provider-neutral-intelligence-contracts.md",
    "docs/adr/0012-fixture-model-qualification-gates.md",
    "docs/adr/0013-deterministic-baseline-ai-routing.md",
    "docs/adr/0014-live-evaluation-isolation-and-budgets.md",
    "docs/adr/0015-controlled-live-model-tournament.md",
    "docs/adr/0016-structured-audit-claims-and-manifests.md",
    "docs/adr/0017-audit-lineage-and-qc.md",
    "docs/adr/0018-deterministic-audit-composition.md",
    "docs/adr/0019-audit-review-and-invalidation.md",
    "docs/adr/0020-audit-eligibility-and-publication-boundary.md",
    "docs/adr/0021-declarative-demo-specification.md",
    "docs/adr/0022-deterministic-demo-state-machine.md",
    "docs/adr/0023-demo-personalization-and-disclosure.md",
    "docs/adr/0024-demo-runtime-isolation.md",
    "docs/adr/0025-demo-eligibility-review-and-revocation.md",
    "docs/adr/0026-authenticated-demo-access.md",
    "docs/adr/0027-outreach-packages-and-exact-manifests.md",
    "docs/adr/0028-outreach-claim-projection-and-economics.md",
    "docs/adr/0029-deterministic-outreach-templates.md",
    "docs/adr/0030-outreach-artifact-separation-and-qc.md",
    "docs/adr/0031-outreach-content-review-no-delivery.md",
    "docs/adr/0032-functional-role-targeting.md",
    "docs/adr/0033-independent-contact-and-send-stages.md",
    "docs/adr/0034-proof-scoped-contact-verification.md",
    "docs/adr/0035-fixture-eligibility-and-a17-live-gate.md",
    "docs/adr/0036-suppression-cadence-and-time-precedence.md",
    "docs/adr/0037-typed-m5-delivery-slots.md",
    "docs/adr/0038-exact-manifest-and-one-send-authorization.md",
    "docs/adr/0039-mock-only-single-message-delivery.md",
    "docs/adr/0040-receipts-replies-and-first-party-assertions.md",
    "docs/adr/0041-referrals-and-controlled-reanalysis.md",
    "docs/adr/0042-isolated-mock-delivery-security.md",
    "docs/adr/0043-narrow-first-production-launch-envelope.md",
    "docs/adr/0044-deterministic-live-activation-readiness.md",
    "docs/adr/0045-versioned-production-outreach-policy.md",
    "docs/adr/0046-contact-source-and-proof-governance.md",
    "docs/adr/0047-sender-and-external-presence-lifecycle.md",
    "docs/adr/0048-version-specific-provider-certification.md",
    "docs/adr/0049-production-separation-of-duties.md",
    "docs/adr/0050-contact-data-lifecycle-and-tombstones.md",
    "docs/adr/0051-isolated-production-delivery-boundary.md",
    "docs/adr/0052-operational-readiness-and-suspension.md",
    "docs/adr/0053-m67-shadow-ready-boundary.md",
    "docs/adr/README.md",
    "docs/decisions/README.md",
    "docs/engineering/dependencies.md",
    "docs/engineering/module-boundaries.md",
    "docs/engineering/standards.md",
    "docs/milestones/M0.md",
    "docs/milestones/M1.md",
    "docs/milestones/M2.md",
    "docs/milestones/M2.5.md",
    "docs/milestones/M2.6.md",
    "docs/milestones/M3.md",
    "docs/milestones/M4.md",
    "docs/milestones/M5.md",
    "docs/milestones/M6.md",
    "docs/milestones/M6.5.md",
    "docs/policies/environment-and-data.md",
    "docs/policies/secrets.md",
    "packages/m0-core/README.md",
    "packages/m0-core/pyproject.toml",
    "packages/m0-local/README.md",
    "packages/m0-local/pyproject.toml",
    "packages/research-core/README.md",
    "packages/research-core/pyproject.toml",
    "packages/research-local/README.md",
    "packages/research-local/pyproject.toml",
    "packages/opportunity-core/README.md",
    "packages/opportunity-core/pyproject.toml",
    "packages/opportunity-local/README.md",
    "packages/opportunity-local/pyproject.toml",
    "packages/audit-core/README.md",
    "packages/audit-core/pyproject.toml",
    "packages/audit-local/README.md",
    "packages/audit-local/pyproject.toml",
    "packages/demo-core/README.md",
    "packages/demo-core/pyproject.toml",
    "packages/demo-local/README.md",
    "packages/demo-local/pyproject.toml",
    "packages/outreach-core/README.md",
    "packages/outreach-core/pyproject.toml",
    "packages/outreach-local/README.md",
    "packages/outreach-local/pyproject.toml",
    "packages/contact-core/README.md",
    "packages/contact-core/pyproject.toml",
    "packages/contact-local/README.md",
    "packages/contact-local/pyproject.toml",
    "packages/activation-core/README.md",
    "packages/activation-core/pyproject.toml",
    "packages/activation-local/README.md",
    "packages/activation-local/pyproject.toml",
    "packages/qualification-core/README.md",
    "packages/qualification-core/pyproject.toml",
    "packages/qualification-local/README.md",
    "packages/qualification-local/pyproject.toml",
    "packages/qualification-live/README.md",
    "packages/qualification-live/pyproject.toml",
    "services/api/README.md",
    "services/api/pyproject.toml",
    "services/demo-runtime/README.md",
    "services/demo-runtime/pyproject.toml",
    "workers/core/README.md",
    "workers/core/pyproject.toml",
    "workers/research/README.md",
    "workers/research/pyproject.toml",
    "workers/browser/README.md",
    "workers/browser/pyproject.toml",
    "workers/intelligence/README.md",
    "workers/intelligence/pyproject.toml",
    "apps/web/README.md",
    "fixtures/public-web/acme-success.html",
    "fixtures/public-web/transient-once.html",
)

ADR_HEADINGS = (
    "## Context",
    "## Decision drivers",
    "## Considered options",
    "## Decision",
    "## Consequences",
    "## Validation",
    "## Revisit triggers",
)

SENSITIVE_ENV_NAMES = re.compile(
    r"(?:SECRET|TOKEN|PASSWORD|PRIVATE_KEY|CLIENT_SECRET|DATABASE_URL)$"
)

LOCAL_SECRET_FILES = (".env.local", "apikeys.txt")


def load_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def validate_required_files(errors: list[str]) -> None:
    for relative_path in REQUIRED_FILES:
        path = ROOT / relative_path
        if not path.is_file():
            errors.append(f"missing required file: {relative_path}")


def validate_workspace(errors: list[str]) -> None:
    package = json.loads(load_text("package.json"))
    expected_workspaces = ["apps/*", "services/*", "workers/*", "packages/*"]
    if package.get("private") is not True:
        errors.append("package.json must set private=true")
    if package.get("workspaces") != expected_workspaces:
        errors.append("package.json workspaces do not match the accepted monorepo boundaries")
    if package.get("engines", {}).get("node") != ">=24 <25":
        errors.append("package.json must enforce the ADR-0002 Node.js 24 baseline")
    if package.get("engines", {}).get("npm") != ">=11 <12":
        errors.append("package.json must enforce the ADR-0002 npm 11 baseline")

    lock = json.loads(load_text("package-lock.json"))
    if lock.get("name") != package.get("name") or lock.get("version") != package.get("version"):
        errors.append("package-lock.json identity must match package.json")
    if lock.get("lockfileVersion") != 3:
        errors.append("package-lock.json must use lockfileVersion 3")

    pyproject = tomllib.loads(load_text("pyproject.toml"))
    if pyproject.get("project", {}).get("requires-python") != ">=3.13,<3.14":
        errors.append("pyproject.toml must enforce the ADR-0002 Python 3.13 baseline")
    if load_text(".nvmrc").strip() != "24":
        errors.append(".nvmrc must select Node.js 24")
    if load_text(".python-version").strip() != "3.13":
        errors.append(".python-version must select Python 3.13")
    members = pyproject.get("tool", {}).get("uv", {}).get("workspace", {}).get("members")
    expected_members = [
        "packages/m0-core",
        "packages/m0-local",
        "packages/research-core",
        "packages/research-local",
        "packages/opportunity-core",
        "packages/opportunity-local",
        "packages/audit-core",
        "packages/audit-local",
        "packages/demo-core",
        "packages/demo-local",
        "packages/outreach-core",
        "packages/outreach-local",
        "packages/contact-core",
        "packages/contact-local",
        "packages/activation-core",
        "packages/activation-local",
        "packages/qualification-core",
        "packages/qualification-local",
        "packages/qualification-live",
        "services/api",
        "services/demo-runtime",
        "workers/core",
        "workers/research",
        "workers/browser",
        "workers/intelligence",
    ]
    if members != expected_members:
        errors.append("Python workspace members do not match the accepted M6.5 boundaries")


def validate_decision_register(errors: list[str]) -> None:
    register = load_text("docs/decisions/README.md")
    found = re.findall(r"^\| (A-\d{2}) \|", register, flags=re.MULTILINE)
    expected = [f"A-{number:02d}" for number in range(1, 21)]
    if found != expected:
        errors.append(
            f"decision register rows must contain A-01 through A-20 in order; found {found}"
        )


def validate_adrs(errors: list[str]) -> None:
    adr_dir = ROOT / "docs" / "adr"
    for path in sorted(adr_dir.glob("[0-9][0-9][0-9][0-9]-*.md")):
        if path.name == "0000-template.md":
            continue
        text = path.read_text(encoding="utf-8")
        if "- **Status:** Accepted" not in text:
            errors.append(f"{path.relative_to(ROOT)} must have an explicit accepted status")
        for heading in ADR_HEADINGS:
            if heading not in text:
                errors.append(f"{path.relative_to(ROOT)} is missing heading: {heading}")


def validate_example_environment(errors: list[str]) -> None:
    for number, line in enumerate(load_text(".env.example").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", maxsplit=1)
        if SENSITIVE_ENV_NAMES.search(name) and value:
            errors.append(
                f".env.example:{number} must not contain a value for sensitive field {name}"
            )


def validate_local_secret_exclusions(errors: list[str]) -> None:
    ignore_lines = {
        line.strip()
        for line in load_text(".gitignore").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    for relative_path in LOCAL_SECRET_FILES:
        if relative_path == ".env.local":
            if ".env.*" not in ignore_lines and relative_path not in ignore_lines:
                errors.append(f"{relative_path} must be excluded by .gitignore")
            continue
        if relative_path not in ignore_lines:
            errors.append(f"{relative_path} must be explicitly excluded by .gitignore")


def validate_markdown_fences(errors: list[str]) -> None:
    ignored_parts = {".git", "node_modules"}
    for path in ROOT.rglob("*.md"):
        if ignored_parts.intersection(path.parts):
            continue
        fence_count = sum(
            1 for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("```")
        )
        if fence_count % 2:
            errors.append(f"{path.relative_to(ROOT)} has an unbalanced fenced code block")


def main() -> int:
    errors: list[str] = []
    validate_required_files(errors)
    if not errors:
        validate_workspace(errors)
        validate_decision_register(errors)
        validate_adrs(errors)
        validate_example_environment(errors)
        validate_local_secret_exclusions(errors)
        validate_markdown_fences(errors)

    if errors:
        print("Repository foundation validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("Repository foundation validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
