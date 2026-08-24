import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_m67_post_dns_connectivity_preflight.py"
CONFIG = (
    ROOT / "docs/readiness/m6.7-authorization/"
    "post-dns-remediation-connectivity-preflight-configuration-2026-08-24.json"
)


def test_preconditions_precede_network_and_scope_is_frozen() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert text.index("readiness = pre_network_checks") < text.index("resolve_public(host)")
    assert "C:\\Python313\\python.exe" in text
    assert 'HOSTS = ("data.texas.gov", "nominatim.openstreetmap.org")' in text
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert config["pre_consumption"]["failure_consumes_grant"] is False
    assert config["network"]["http_requests"] == 0
    assert config["network"]["source_content_bytes"] == 0
    assert config["network"]["retries"] == 0
    assert config["network"]["alternate_resolvers"] == 0
