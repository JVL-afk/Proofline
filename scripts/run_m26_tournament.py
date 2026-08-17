"""Explicit, synthetic-only M2.6 live tournament. Never used by normal CI."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from opintel_qualification_live.adapters import AnthropicAdapter, GeminiAdapter, OpenAIAdapter
from opintel_qualification_live.certification import certify
from opintel_qualification_live.config import DEPLOYMENTS, TOURNAMENT_BUDGET_MICROS
from opintel_qualification_live.secrets import SecretConfigurationError, load_secret_bundle
from opintel_qualification_live.tournament import (
    TournamentRunner,
    estimated_maximum_cost,
    safe_report,
)
from opintel_qualification_live.transport import UrllibJsonTransport


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Run synthetic-only M2.6 live qualification")
    value.add_argument("--execute-live", action="store_true")
    value.add_argument("--confirm-synthetic-only", action="store_true")
    value.add_argument("--kill-switch-open", action="store_true")
    value.add_argument("--credentials", type=Path, default=Path("apikeys.txt"))
    value.add_argument("--budget-usd", type=int, default=50)
    value.add_argument(
        "--stage", choices=("certification", "critical", "tournament"), required=True
    )
    value.add_argument("--deployment", action="append", default=[])
    value.add_argument("--output", type=Path, default=Path("local-data/m2.6/tournament.json"))
    value.add_argument(
        "--certification-output",
        type=Path,
        default=Path("local-data/m2.6/certification.json"),
    )
    value.add_argument(
        "--critical-output",
        type=Path,
        default=Path("local-data/m2.6/critical.json"),
    )
    return value


def main() -> int:
    args = parser().parse_args()
    prior_certification_costs: dict[str, int] = {}
    if args.stage in {"critical", "tournament"} and args.certification_output.is_file():
        prior = json.loads(args.certification_output.read_text(encoding="utf-8"))
        if prior.get("synthetic_only") is not True:
            print("Live tournament denied: prior certification artifact is not synthetic-only.")
            return 2
        costs = prior.get("deployment_costs_micros", {})
        if isinstance(costs, dict):
            prior_certification_costs = {
                str(key): int(value)
                for key, value in costs.items()
                if isinstance(value, int) and value >= 0
            }
    if not (args.execute_live and args.confirm_synthetic_only and args.kill_switch_open):
        print(
            "Live tournament denied: explicit execution, synthetic-only, "
            "and kill-switch flags required."
        )
        return 2
    if args.budget_usd != 50:
        print("Live tournament denied: the authorized hard budget is exactly USD 50.")
        return 2
    estimate, per_deployment = estimated_maximum_cost(DEPLOYMENTS)
    print(f"Preflight maximum estimate: USD {estimate / 1_000_000:.6f}")
    if estimate > TOURNAMENT_BUDGET_MICROS or any(
        value > item.sub_budget_micros
        for item, value in zip(DEPLOYMENTS, per_deployment.values(), strict=True)
    ):
        print("Live tournament denied: preflight or deployment sub-budget exceeded.")
        return 2
    try:
        secrets = load_secret_bundle(args.credentials)
    except (OSError, SecretConfigurationError) as exc:
        provider = exc.provider if isinstance(exc, SecretConfigurationError) else "credential_file"
        print(f"Live tournament denied: credential unavailable for {provider}.")
        return 2
    transport = UrllibJsonTransport()
    selected = tuple(
        spec for spec in DEPLOYMENTS if not args.deployment or spec.model_id in args.deployment
    )
    if not selected or any(
        name not in {spec.model_id for spec in DEPLOYMENTS} for name in args.deployment
    ):
        print("Live tournament denied: deployment allowlist contains an unknown model ID.")
        return 2
    if args.stage in {"critical", "tournament"} and selected != DEPLOYMENTS:
        print(
            "Live tournament denied: tournament stage requires the complete deployment allowlist."
        )
        return 2
    adapters: dict[object, object] = {}
    for spec in selected:
        credential = secrets.for_provider(spec.provider)
        adapter_type = {
            "openai": OpenAIAdapter,
            "anthropic": AnthropicAdapter,
            "gemini": GeminiAdapter,
        }[spec.provider]
        adapters[spec.id] = adapter_type(spec, credential, transport)
    certifications = [certify(spec, adapters[spec.id]) for spec in selected]
    for item in certifications:
        print(
            f"Certification {item.provider}/{item.model_id}: {'PASS' if item.admitted else 'FAIL'}"
        )
    previous_results: list[dict[str, object]] = []
    previous_costs: dict[str, int] = {}
    if args.stage == "certification" and args.certification_output.is_file():
        previous = json.loads(args.certification_output.read_text(encoding="utf-8"))
        if previous.get("synthetic_only") is True:
            previous_results = [
                item for item in previous.get("results", []) if isinstance(item, dict)
            ]
            previous_costs = {
                str(key): int(value)
                for key, value in previous.get("deployment_costs_micros", {}).items()
                if isinstance(value, int) and value >= 0
            }
    replaced = {str(item.deployment_id) for item in certifications}
    merged_results = [
        item for item in previous_results if str(item.get("deployment_id")) not in replaced
    ] + [asdict(item) for item in certifications]
    merged_costs = dict(previous_costs)
    for item in certifications:
        key = str(item.deployment_id)
        merged_costs[key] = merged_costs.get(key, 0) + item.actual_cost_micros
    certification_payload = {
        "schema_version": "m2_6.adapter_certification@1",
        "synthetic_only": True,
        "results": merged_results,
        "actual_cost_micros": sum(merged_costs.values()),
        "deployment_costs_micros": merged_costs,
    }
    args.certification_output.parent.mkdir(parents=True, exist_ok=True)
    args.certification_output.write_text(
        json.dumps(certification_payload, indent=2, default=str), encoding="utf-8"
    )
    if args.stage == "certification":
        print(f"Certification review artifact written to: {args.certification_output}")
        return 0 if any(item.admitted for item in certifications) else 3
    admitted = tuple(
        spec for spec in DEPLOYMENTS if certifications[DEPLOYMENTS.index(spec)].admitted
    )
    if not admitted:
        print("No deployment passed adapter certification; tournament stopped.")
        return 3
    runner = TournamentRunner(admitted, {item.id: adapters[item.id] for item in admitted})
    prior_stage_costs = prior_certification_costs
    if args.stage == "tournament" and args.critical_output.is_file():
        prior_critical = json.loads(args.critical_output.read_text(encoding="utf-8"))
        if prior_critical.get("synthetic_only") is not True:
            print("Live tournament denied: prior critical artifact is not synthetic-only.")
            return 2
        prior_stage_costs = {
            str(key): int(value)
            for key, value in prior_critical.get("deployment_costs_micros", {}).items()
            if isinstance(value, int) and value >= 0
        }
    for spec in admitted:
        runner.budget.record(spec, prior_stage_costs.get(str(spec.id), 0))
    for item in certifications:
        matching = next((spec for spec in admitted if spec.id == item.deployment_id), None)
        if matching is not None:
            runner.budget.record(matching, item.actual_cost_micros)
    if args.stage == "critical":
        runner.run_critical()
        summaries = runner.summaries()
        report = safe_report(runner, summaries)
        report["preflight_estimate_micros"] = estimate
        report["certifications"] = [asdict(item) for item in certifications]
        args.critical_output.parent.mkdir(parents=True, exist_ok=True)
        args.critical_output.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(
            "Critical gauntlet completed with cumulative calculated spend USD "
            f"{runner.budget.total_spent / 1_000_000:.6f}."
        )
        print(f"Critical review artifact written to: {args.critical_output}")
        return 0
    summaries = runner.run()
    report = safe_report(runner, summaries)
    report["preflight_estimate_micros"] = estimate
    report["certifications"] = [asdict(item) for item in certifications]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(
        "Tournament completed with actual calculated spend USD "
        f"{runner.budget.total_spent / 1_000_000:.6f}."
    )
    print(f"Review artifact written to ignored local path: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
