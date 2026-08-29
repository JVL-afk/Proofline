"""One-shot entry point that materializes and writes the exact Window 2 approval.

This runs under the bounded ``m67-phase1-operator`` identity (which the accepted Window 2
authorization already scopes to the sampled-slot lifecycle). It reads the exact current
predecessor research-release, kill switch and stored approval from SSM, the exact deployed
activator task-definition environment from ECS, and the accepted owner authorization
artifacts from the repository, then delegates to
:func:`opintel_research_worker.authority_materialization.materialize`.

It performs exactly one authority write: the validated envelope onto
``/m67-phase1/sampled-slot-execution-approval``. The ``restore`` mode writes the exact
``{"state":"NOT_AUTHORIZED"}`` sentinel back after the bounded run, mirroring the historical
authorized-envelope -> restored-sentinel lifecycle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from opintel_research_worker.activation import FrozenA09DecisionRegistry
from opintel_research_worker.authority_materialization import (
    AuthorityMaterializationError,
    MaterializationInputs,
    RepairImageSuccessor,
    materialize,
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


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repair_image_successor_chain() -> tuple[RepairImageSuccessor, ...]:
    """Build the sealed bounded-repair image successor chain from committed evidence.

    ``OPINTEL_REPAIR_SUCCESSOR_REGISTRY_EVIDENCE_PATHS`` and
    ``OPINTEL_REPAIR_SUCCESSOR_DEPLOYMENT_EVIDENCE_PATHS`` are parallel,
    comma-separated, repair-ordered lists of the sealed registry-evidence and
    deployment-evidence JSON files. Every field of every link is read out of
    those immutable records - nothing is passed in directly.
    """

    registry_env = "OPINTEL_REPAIR_SUCCESSOR_REGISTRY_EVIDENCE_PATHS"
    deployment_env = "OPINTEL_REPAIR_SUCCESSOR_DEPLOYMENT_EVIDENCE_PATHS"
    registry_raw = os.environ.get(registry_env, "").strip()
    deployment_raw = os.environ.get(deployment_env, "").strip()
    if not registry_raw and not deployment_raw:
        return ()
    registry_paths = [Path(p.strip()) for p in registry_raw.split(",") if p.strip()]
    deployment_paths = [Path(p.strip()) for p in deployment_raw.split(",") if p.strip()]
    if len(registry_paths) != len(deployment_paths) or not registry_paths:
        raise SystemExit(
            "repair successor registry/deployment evidence path lists "
            "must be equal-length and non-empty"
        )

    chain: list[RepairImageSuccessor] = []
    for index, (registry_path, deployment_path) in enumerate(
        zip(registry_paths, deployment_paths, strict=True), start=1
    ):
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        deployment_text = deployment_path.read_text(encoding="utf-8")
        json.loads(deployment_text)  # must be well-formed sealed JSON
        identity = registry.get("registry_identity", {})
        scan = registry.get("ecr_scan", {})
        source = registry.get("source_image", {})
        successor_digest = str(identity.get("registry_digest", ""))
        if successor_digest and successor_digest not in deployment_text:
            raise SystemExit(
                f"repair {index} deployment evidence does not reference its sealed "
                f"registry successor digest"
            )
        chain.append(
            RepairImageSuccessor(
                repair_number=index,
                predecessor_image_digest=str(source.get("base_registry_digest", "")),
                successor_image_digest=successor_digest,
                registry_evidence_sha256=_sha256_file(registry_path),
                deployment_evidence_sha256=_sha256_file(deployment_path),
                representation_equivalent_proven=(
                    identity.get("classification") == "REPRESENTATION_EQUIVALENT_PROVEN"
                    and identity.get("archive_manifest_byte_equal_to_registry") is True
                ),
                ecr_scan_critical=int(scan.get("critical", 1)),
                ecr_scan_high=int(scan.get("high", 1)),
                ecr_scan_blocking=int(scan.get("blocking", 1)),
            )
        )
    return tuple(chain)


def _activator_environment(client: object, task_definition: str) -> dict[str, str]:
    response = client.describe_task_definition(taskDefinition=task_definition)  # type: ignore[attr-defined]
    definition = response["taskDefinition"]
    if definition.get("status") != "ACTIVE":
        raise SystemExit("deployed activator task definition is not ACTIVE")
    containers = definition.get("containerDefinitions") or []
    if len(containers) != 1:
        raise SystemExit("deployed activator task definition has an unexpected container shape")
    return {item["name"]: item["value"] for item in containers[0].get("environment", [])}


def _materialize(args: argparse.Namespace) -> int:
    region = os.environ.get("OPINTEL_AWS_REGION", "us-east-2").strip() or "us-east-2"
    statement_path = Path(_env("OPINTEL_OWNER_AUTHORIZATION_STATEMENT_PATH"))
    record_path = Path(_env("OPINTEL_OWNER_AUTHORIZATION_RECORD_PATH"))
    slot_registry_path = _env("OPINTEL_PHASE1_SLOT_REGISTRY_PATH")
    a09_registry_path = _env("OPINTEL_PHASE1_A09_DECISION_REGISTRY_PATH")
    activator_task_definition = _env("OPINTEL_ACTIVATOR_TASK_DEFINITION")

    ready_record = json.loads(record_path.read_text(encoding="utf-8"))
    statement_source = json.loads(statement_path.read_text(encoding="utf-8"))
    if "exact_owner_approval_statement" in statement_source:
        statement = str(statement_source["exact_owner_approval_statement"])
    else:
        statement = statement_path.read_text(encoding="utf-8")

    ssm = _client("ssm", region)
    ecs = _client("ecs", region)

    inputs = MaterializationInputs(
        owner_authorization_statement=statement,
        owner_authorization_record=ready_record,
        sample_registry=FrozenPhaseOneSampleRegistry(slot_registry_path),
        a09_registry=FrozenA09DecisionRegistry(a09_registry_path),
        current_research_release_raw=_read_parameter(ssm, RESEARCH_RELEASE_PARAMETER),
        kill_switch_state=_read_parameter(ssm, KILL_SWITCH_PARAMETER),
        stored_sampled_slot_approval_raw=_read_parameter(ssm, APPROVAL_PARAMETER),
        deployed_activator_environment=_activator_environment(ecs, activator_task_definition),
        now=datetime.now(UTC),
        repair_image_successor_chain=_repair_image_successor_chain(),
    )

    try:
        result = materialize(inputs)
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

    print(
        json.dumps(
            {
                "materialized": True,
                "wrote_parameter": wrote,
                "already_present": result.already_present,
                "dry_run": bool(args.dry_run),
                "approval_artifact_sha256": result.approval_artifact_sha256,
                "authorized_release_id": str(result.authorized_release_id),
                "predecessor_release_id": str(result.predecessor_release_id),
                "diagnostics": dict(result.diagnostics),
            },
            sort_keys=True,
        )
    )
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
            Name=APPROVAL_PARAMETER,
            Value=SAMPLED_APPROVAL_LOCK_SENTINEL,
            Type="String",
            Overwrite=True,
        )
    print(json.dumps({"restored": not args.dry_run, "dry_run": bool(args.dry_run)}))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Materialize the exact Window 2 approval envelope."
    )
    parser.add_argument(
        "mode",
        choices=("materialize", "restore"),
        help="materialize the envelope or restore the sentinel",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="compute and validate without writing"
    )
    args = parser.parse_args()
    raise SystemExit(
        _materialize(args) if args.mode == "materialize" else _restore(args)
    )


if __name__ == "__main__":
    main()
