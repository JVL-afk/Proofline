"""One-shot entry point that materialises and writes one v2 (@4) sampled-slot approval.

Mirrors :mod:`authority_materialization_main` but for
AUTHORIZE_SLOTS02_06_PHASE1_M1_V2_EXECUTION: the owner authority is the immutable
package (sha256 d28e42594c943debf0144b3f5ecce57589760881e579ebbf52f6984d8150677a)
plus the sealed execution-ceiling envelope and deployment evidence, not a
regex-parseable statement. It performs exactly one authority write: the validated
envelope onto ``/m67-phase1/sampled-slot-execution-approval``. ``restore`` writes
the ``{"state":"NOT_AUTHORIZED"}`` sentinel back.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from opintel_research_worker.activation import FrozenA09DecisionRegistry
from opintel_research_worker.authority_materialization import AuthorityMaterializationError
from opintel_research_worker.authority_materialization_v2 import (
    BatchConsumed,
    BatchHeadroomExhausted,
    MaterializationInputsV2,
    materialize_v2,
)
from opintel_research_worker.release_application import SAMPLED_APPROVAL_LOCK_SENTINEL
from opintel_research_worker.sample_registry import FrozenPhaseOneSampleRegistry

APPROVAL_PARAMETER = "/m67-phase1/sampled-slot-execution-approval"
RESEARCH_RELEASE_PARAMETER = "/m67-phase1/research-release"
KILL_SWITCH_PARAMETER = "/m67-phase1/kill-switch"


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"required setting is absent: {name}")
    return value


def _client(service: str, region: str) -> object:
    import boto3  # type: ignore[import-untyped]

    return boto3.client(service, region_name=region)


def _read_parameter(client: object, name: str) -> str:
    response = client.get_parameter(Name=name, WithDecryption=False)  # type: ignore[attr-defined]
    return str(response["Parameter"]["Value"])


def _activator_environment(client: object, task_definition: str) -> dict[str, str]:
    response = client.describe_task_definition(taskDefinition=task_definition)  # type: ignore[attr-defined]
    definition = response["taskDefinition"]
    if definition.get("status") != "ACTIVE":
        raise SystemExit("deployed activator task definition is not ACTIVE")
    containers = definition.get("containerDefinitions") or []
    if len(containers) != 1:
        raise SystemExit("deployed activator task definition has an unexpected container shape")
    return {item["name"]: item["value"] for item in containers[0].get("environment", [])}


def _batch_consumed() -> BatchConsumed:
    path = os.environ.get("OPINTEL_BATCH_CONSUMED_PATH", "").strip()
    if not path:
        return BatchConsumed()
    record = json.loads(Path(path).read_text(encoding="utf-8"))
    counters = record.get("batch_cumulative", record)
    return BatchConsumed(
        useful_page_fetches=int(counters.get("useful_page_fetches", 0)),
        total_http_requests=int(counters.get("total_http_requests", 0)),
        total_bytes=int(counters.get("total_bytes", 0)),
        m1_duration_seconds=int(counters.get("m1_duration_seconds", 0)),
    )


def _materialize(args: argparse.Namespace) -> int:
    region = os.environ.get("OPINTEL_AWS_REGION", "us-east-2").strip() or "us-east-2"
    slot_number = int(_env("OPINTEL_SLOT_NUMBER"))
    ssm = _client("ssm", region)
    ecs = _client("ecs", region)

    inputs = MaterializationInputsV2(
        slot_number=slot_number,
        authorization_package_raw=Path(
            _env("OPINTEL_AUTHORIZATION_PACKAGE_PATH")
        ).read_text(encoding="utf-8"),
        owner_decision_raw=Path(_env("OPINTEL_OWNER_DECISION_PATH")).read_text(encoding="utf-8"),
        execution_ceiling_envelope_raw=Path(
            _env("OPINTEL_EXECUTION_CEILING_ENVELOPE_PATH")
        ).read_text(encoding="utf-8"),
        deployment_evidence_raw=Path(
            _env("OPINTEL_DEPLOYMENT_EVIDENCE_PATH")
        ).read_text(encoding="utf-8"),
        sample_registry=FrozenPhaseOneSampleRegistry(_env("OPINTEL_PHASE1_SLOT_REGISTRY_PATH")),
        a09_registry=FrozenA09DecisionRegistry(_env("OPINTEL_PHASE1_A09_DECISION_REGISTRY_PATH")),
        current_research_release_raw=_read_parameter(ssm, RESEARCH_RELEASE_PARAMETER),
        kill_switch_state=_read_parameter(ssm, KILL_SWITCH_PARAMETER),
        stored_sampled_slot_approval_raw=_read_parameter(ssm, APPROVAL_PARAMETER),
        deployed_activator_environment=_activator_environment(
            ecs, _env("OPINTEL_ACTIVATOR_TASK_DEFINITION")
        ),
        batch_consumed=_batch_consumed(),
        now=datetime.now(UTC),
    )

    try:
        result = materialize_v2(inputs)
    except BatchHeadroomExhausted as error:
        print(json.dumps(
            {"materialized": False, "batch_headroom_exhausted": True, "slot": slot_number,
             "reason": str(error)},
            sort_keys=True,
        ))
        return 2
    except AuthorityMaterializationError as error:
        print(json.dumps({"materialized": False, "error": str(error)}, sort_keys=True))
        return 1

    payload = result.envelope.model_dump_json()
    wrote = False
    if not result.already_present and not args.dry_run:
        ssm.put_parameter(  # type: ignore[attr-defined]
            Name=APPROVAL_PARAMETER, Value=payload, Type="String", Overwrite=True
        )
        wrote = True
    print(json.dumps(
        {
            "materialized": True,
            "wrote_parameter": wrote,
            "already_present": result.already_present,
            "dry_run": bool(args.dry_run),
            "slot": slot_number,
            "approval_artifact_sha256": result.approval_artifact_sha256,
            "authorized_release_id": str(result.authorized_release_id),
            "predecessor_release_id": str(result.predecessor_release_id),
            "diagnostics": dict(result.diagnostics),
        },
        sort_keys=True,
    ))
    return 0


def _restore(args: argparse.Namespace) -> int:
    region = os.environ.get("OPINTEL_AWS_REGION", "us-east-2").strip() or "us-east-2"
    ssm = _client("ssm", region)
    current = _read_parameter(ssm, APPROVAL_PARAMETER)
    if current == SAMPLED_APPROVAL_LOCK_SENTINEL:
        print(json.dumps({"restored": False, "reason": "already the NOT_AUTHORIZED sentinel"}))
        return 0
    if not args.dry_run:
        ssm.put_parameter(  # type: ignore[attr-defined]
            Name=APPROVAL_PARAMETER, Value=SAMPLED_APPROVAL_LOCK_SENTINEL,
            Type="String", Overwrite=True,
        )
    print(json.dumps({"restored": not args.dry_run, "dry_run": bool(args.dry_run)}))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialise one v2 sampled-slot approval.")
    parser.add_argument("mode", choices=("materialize", "restore"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    raise SystemExit(_materialize(args) if args.mode == "materialize" else _restore(args))


if __name__ == "__main__":
    main()
