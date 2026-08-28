"""Bounded ECS lifecycle for one already-approved sampled-slot execution.

This command never accepts business, host, slot, URL, or release fields. Those identities are
derived and enforced inside the sampled-slot activator and controlled-egress lease. The command
only makes the existing dormant ECS dependency available, launches one exact activator task, and
returns the dependency to zero in a finally block.
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class BoundedEcsExecutionConfiguration:
    schema_version: str
    aws_account_id: str
    aws_region: str
    cluster: str
    controlled_egress_service: str
    sampled_slot_task_definition: str
    sampled_slot_container_name: str
    exact_image_digest: str
    subnet_id: str
    security_group_id: str
    assign_public_ip: str
    startup_timeout_seconds: int
    execution_timeout_seconds: int
    shutdown_timeout_seconds: int

    @classmethod
    def load(cls, path: Path) -> BoundedEcsExecutionConfiguration:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or set(value) != set(cls.__annotations__):
            raise ValueError("bounded ECS configuration has unexpected or missing fields")
        config = cls(**value)
        if (
            config.schema_version != "m67.phase1.controlled-egress-execution@1"
            or config.aws_account_id != "785072247535"
            or config.aws_region != "us-east-2"
            or config.assign_public_ip != "DISABLED"
            or not config.exact_image_digest.startswith("sha256:")
            or not 1 <= config.startup_timeout_seconds <= 60
            or not 1 <= config.execution_timeout_seconds <= 900
            or not 1 <= config.shutdown_timeout_seconds <= 60
        ):
            raise ValueError("bounded ECS configuration is outside accepted Phase 1 constraints")
        return config


class EcsClient(Protocol):
    def describe_services(self, **kwargs: object) -> dict[str, object]: ...
    def describe_task_definition(self, **kwargs: object) -> dict[str, object]: ...
    def describe_tasks(self, **kwargs: object) -> dict[str, object]: ...
    def update_service(self, **kwargs: object) -> dict[str, object]: ...
    def run_task(self, **kwargs: object) -> dict[str, object]: ...


def execute_once(
    client: EcsClient,
    config: BoundedEcsExecutionConfiguration,
    *,
    now: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, object]:
    """Scale one existing gateway, run one activator, and always restore service dormancy."""
    _verify_task_definition(client, config)
    service = _service(client, config)
    if _counts(service) != (0, 0, 0):
        raise RuntimeError("controlled-egress service is not initially dormant")
    task_arn: str | None = None
    started = False
    try:
        client.update_service(
            cluster=config.cluster,
            service=config.controlled_egress_service,
            desiredCount=1,
        )
        started = True
        _wait_service(client, config, (1, 1, 0), config.startup_timeout_seconds, now, sleep)
        response = client.run_task(
            cluster=config.cluster,
            taskDefinition=config.sampled_slot_task_definition,
            launchType="FARGATE",
            count=1,
            platformVersion="1.4.0",
            networkConfiguration={
                "awsvpcConfiguration": {
                    "subnets": [config.subnet_id],
                    "securityGroups": [config.security_group_id],
                    "assignPublicIp": config.assign_public_ip,
                }
            },
        )
        failures = response.get("failures", [])
        tasks = response.get("tasks", [])
        if failures or not isinstance(tasks, list) or len(tasks) != 1:
            raise RuntimeError("exact sampled-slot task was not launched")
        task_arn = str(tasks[0]["taskArn"])
        stopped = _wait_task(client, config, task_arn, config.execution_timeout_seconds, now, sleep)
        containers = stopped.get("containers", [])
        if not isinstance(containers, list) or len(containers) != 1:
            raise RuntimeError("sampled-slot task terminal shape is invalid")
        container = containers[0]
        if container.get("name") != config.sampled_slot_container_name:
            raise RuntimeError("sampled-slot terminal container identity mismatch")
        if int(container.get("exitCode", -1)) != 0:
            raise RuntimeError("sampled-slot task terminated unsuccessfully")
        return {
            "controlled_egress_started": True,
            "sampled_slot_task_arn": task_arn,
            "sampled_slot_task_exit_code": 0,
        }
    finally:
        if started:
            client.update_service(
                cluster=config.cluster,
                service=config.controlled_egress_service,
                desiredCount=0,
            )
            _wait_service(client, config, (0, 0, 0), config.shutdown_timeout_seconds, now, sleep)


def _verify_task_definition(client: EcsClient, config: BoundedEcsExecutionConfiguration) -> None:
    response = client.describe_task_definition(taskDefinition=config.sampled_slot_task_definition)
    task = response.get("taskDefinition", {})
    definitions = task.get("containerDefinitions", []) if isinstance(task, dict) else []
    if not isinstance(definitions, list) or len(definitions) != 1:
        raise RuntimeError("sampled-slot task definition shape is invalid")
    container = definitions[0]
    image = str(container.get("image", ""))
    if container.get("name") != config.sampled_slot_container_name or not image.endswith(
        "@" + config.exact_image_digest
    ):
        raise RuntimeError("sampled-slot task definition image identity mismatch")


def _service(client: EcsClient, config: BoundedEcsExecutionConfiguration) -> dict[str, object]:
    response = client.describe_services(
        cluster=config.cluster, services=[config.controlled_egress_service]
    )
    services = response.get("services", [])
    if not isinstance(services, list) or len(services) != 1:
        raise RuntimeError("controlled-egress service is unavailable")
    return services[0]


def _counts(service: dict[str, object]) -> tuple[int, int, int]:
    return (
        int(service.get("desiredCount", -1)),
        int(service.get("runningCount", -1)),
        int(service.get("pendingCount", -1)),
    )


def _wait_service(
    client: EcsClient,
    config: BoundedEcsExecutionConfiguration,
    expected: tuple[int, int, int],
    timeout: int,
    now: Callable[[], float],
    sleep: Callable[[float], None],
) -> None:
    deadline = now() + timeout
    while _counts(_service(client, config)) != expected:
        if now() >= deadline:
            raise RuntimeError("controlled-egress service readiness transition timed out")
        sleep(min(2.0, max(0.0, deadline - now())))


def _wait_task(
    client: EcsClient,
    config: BoundedEcsExecutionConfiguration,
    task_arn: str,
    timeout: int,
    now: Callable[[], float],
    sleep: Callable[[float], None],
) -> dict[str, object]:
    deadline = now() + timeout
    while True:
        response = client.describe_tasks(cluster=config.cluster, tasks=[task_arn])
        tasks = response.get("tasks", [])
        if not isinstance(tasks, list) or len(tasks) != 1:
            raise RuntimeError("sampled-slot task state is unavailable")
        task = tasks[0]
        if task.get("lastStatus") == "STOPPED":
            return task
        if now() >= deadline:
            raise RuntimeError("sampled-slot task execution timed out")
        sleep(min(2.0, max(0.0, deadline - now())))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("configuration", type=Path)
    args = parser.parse_args()
    config = BoundedEcsExecutionConfiguration.load(args.configuration)
    import boto3  # type: ignore[import-untyped]

    client = boto3.client("ecs", region_name=config.aws_region)
    print(json.dumps(execute_once(client, config), sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
