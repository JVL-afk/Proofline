"""Exact M2.6 deployment/configuration/pricing identities."""

from __future__ import annotations

import hashlib
import json
from uuid import NAMESPACE_URL, uuid5

from opintel_qualification_live.contracts import DeploymentSpec, Pricing


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _spec(
    provider: str,
    model: str,
    configuration: dict[str, object],
    pricing: Pricing,
) -> DeploymentSpec:
    identity = {"provider": provider, "model": model, "configuration": configuration}
    return DeploymentSpec(
        uuid5(NAMESPACE_URL, f"opintel:m2.6:{provider}:{model}:{_hash(configuration)}"),
        provider,
        model,
        f"{provider}.{model}.m2_6@1",
        configuration,
        _hash(identity),
        pricing,
        10_000_000,
    )


DEPLOYMENTS = (
    _spec(
        "openai",
        "gpt-5.6-terra",
        {"api": "responses", "reasoning_effort": "high", "tools": False, "store": False},
        Pricing("openai-2026-08-17-terra", 2_000_000, 12_000_000, 200_000),
    ),
    _spec(
        "openai",
        "gpt-5.6-sol",
        {"api": "responses", "reasoning_effort": "high", "tools": False, "store": False},
        Pricing("openai-2026-08-17-sol", 5_000_000, 30_000_000, 500_000),
    ),
    _spec(
        "anthropic",
        "claude-sonnet-5",
        {"api": "messages", "thinking": "adaptive", "effort": "high", "tools": False},
        Pricing("anthropic-2026-08-17-sonnet5", 2_000_000, 10_000_000),
    ),
    _spec(
        "anthropic",
        "claude-opus-5",
        {"api": "messages", "thinking": "adaptive", "effort": "high", "tools": False},
        Pricing("anthropic-2026-08-17-opus5", 5_000_000, 25_000_000),
    ),
    _spec(
        "gemini",
        "gemini-3.6-flash",
        {"api": "generateContent", "thinking_level": "medium", "tools": False},
        Pricing("gemini-2026-08-17-3.6-flash", 1_500_000, 7_500_000, 150_000),
    ),
)

TOURNAMENT_BUDGET_MICROS = 50_000_000
MAX_OUTPUT_TOKENS = 1_536
REQUEST_TIMEOUT_SECONDS = 90.0
