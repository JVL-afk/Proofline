from __future__ import annotations

from scripts.run_m67_bounded_controlled_egress import (
    BoundedEcsExecutionConfiguration,
    execute_once,
)


def _config() -> BoundedEcsExecutionConfiguration:
    return BoundedEcsExecutionConfiguration(
        schema_version="m67.phase1.controlled-egress-execution@2",
        aws_account_id="785072247535",
        aws_region="us-east-2",
        cluster="m67-phase1-research",
        controlled_egress_service="m67-phase1-controlled-egress",
        sampled_slot_task_definition=(
            "arn:aws:ecs:us-east-2:785072247535:task-definition/m67-phase1-sampled-slot-activator:5"
        ),
        sampled_slot_container_name="sampled-slot-activator",
        exact_image_digest="sha256:" + "a" * 64,
        task_execution_role_arn="arn:aws:iam::785072247535:role/m67-phase1-ecs-execution",
        task_role_arn="arn:aws:iam::785072247535:role/m67-phase1-sampled-slot-executor",
        subnet_id="subnet-synthetic",
        security_group_id="sg-synthetic",
        assign_public_ip="DISABLED",
        task_definition_readiness_timeout_seconds=6,
        startup_timeout_seconds=10,
        execution_timeout_seconds=30,
        shutdown_timeout_seconds=10,
    )


class _Clock:
    value = 0.0

    def now(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


class _Ecs:
    def __init__(
        self,
        *,
        task_exit: int = 0,
        startup_stalls: bool = False,
        inactive_describes: int = 0,
    ) -> None:
        self.counts = (0, 0, 0)
        self.task_exit = task_exit
        self.startup_stalls = startup_stalls
        self.update_calls: list[int] = []
        self.run_calls: list[dict[str, object]] = []
        self.inactive_describes = inactive_describes

    def describe_task_definition(self, **kwargs: object) -> dict[str, object]:
        assert kwargs["taskDefinition"] == _config().sampled_slot_task_definition
        status = "INACTIVE" if self.inactive_describes > 0 else "ACTIVE"
        self.inactive_describes = max(0, self.inactive_describes - 1)
        return {
            "taskDefinition": {
                "taskDefinitionArn": _config().sampled_slot_task_definition,
                "family": "m67-phase1-sampled-slot-activator",
                "revision": 5,
                "status": status,
                "executionRoleArn": _config().task_execution_role_arn,
                "taskRoleArn": _config().task_role_arn,
                "compatibilities": ["EC2", "FARGATE"],
                "runtimePlatform": {
                    "cpuArchitecture": "X86_64",
                    "operatingSystemFamily": "LINUX",
                },
                "containerDefinitions": [
                    {
                        "name": "sampled-slot-activator",
                        "image": "repo@sha256:" + "a" * 64,
                    }
                ],
            }
        }

    def describe_services(self, **kwargs: object) -> dict[str, object]:
        del kwargs
        return {
            "services": [
                {
                    "desiredCount": self.counts[0],
                    "runningCount": self.counts[1],
                    "pendingCount": self.counts[2],
                }
            ]
        }

    def update_service(self, **kwargs: object) -> dict[str, object]:
        desired = int(kwargs["desiredCount"])
        self.update_calls.append(desired)
        if desired == 0:
            self.counts = (0, 0, 0)
        elif self.startup_stalls:
            self.counts = (1, 0, 1)
        else:
            self.counts = (1, 1, 0)
        return {}

    def run_task(self, **kwargs: object) -> dict[str, object]:
        self.run_calls.append(kwargs)
        return {"tasks": [{"taskArn": "arn:synthetic:task/one"}], "failures": []}

    def describe_tasks(self, **kwargs: object) -> dict[str, object]:
        del kwargs
        return {
            "tasks": [
                {
                    "lastStatus": "STOPPED",
                    "containers": [{"name": "sampled-slot-activator", "exitCode": self.task_exit}],
                }
            ]
        }


def test_exact_existing_service_starts_before_task_and_returns_to_zero() -> None:
    client = _Ecs()
    clock = _Clock()
    receipt = execute_once(client, _config(), now=clock.now, sleep=clock.sleep)
    assert receipt["sampled_slot_task_exit_code"] == 0
    assert client.update_calls == [1, 0]
    assert client.counts == (0, 0, 0)
    assert len(client.run_calls) == 1
    network = client.run_calls[0]["networkConfiguration"]
    assert network == {
        "awsvpcConfiguration": {
            "subnets": ["subnet-synthetic"],
            "securityGroups": ["sg-synthetic"],
            "assignPublicIp": "DISABLED",
        }
    }


def test_startup_timeout_launches_no_task_and_restores_dormancy() -> None:
    client = _Ecs(startup_stalls=True)
    clock = _Clock()
    try:
        execute_once(client, _config(), now=clock.now, sleep=clock.sleep)
    except RuntimeError as error:
        assert "readiness transition timed out" in str(error)
    else:
        raise AssertionError("startup timeout must fail closed")
    assert client.run_calls == []
    assert client.update_calls == [1, 0]
    assert client.counts == (0, 0, 0)


def test_task_failure_still_restores_dormancy_without_retry() -> None:
    client = _Ecs(task_exit=1)
    clock = _Clock()
    try:
        execute_once(client, _config(), now=clock.now, sleep=clock.sleep)
    except RuntimeError as error:
        assert "terminated unsuccessfully" in str(error)
    else:
        raise AssertionError("nonzero activator exit must be terminal")
    assert len(client.run_calls) == 1
    assert client.update_calls == [1, 0]
    assert client.counts == (0, 0, 0)


def test_inactive_revision_waits_before_service_or_task_activity() -> None:
    client = _Ecs(inactive_describes=2)
    clock = _Clock()
    receipt = execute_once(client, _config(), now=clock.now, sleep=clock.sleep)
    assert receipt["sampled_slot_task_exit_code"] == 0
    assert clock.value >= 4
    assert client.update_calls == [1, 0]


def test_task_definition_readiness_timeout_is_pre_activity() -> None:
    client = _Ecs(inactive_describes=10)
    clock = _Clock()
    try:
        execute_once(client, _config(), now=clock.now, sleep=clock.sleep)
    except RuntimeError as error:
        assert "ACTIVE readiness timed out" in str(error)
    else:
        raise AssertionError("inactive task definition must fail closed")
    assert client.update_calls == []
    assert client.run_calls == []


def test_task_definition_identity_mismatch_is_pre_activity() -> None:
    client = _Ecs()
    original = client.describe_task_definition

    def mismatched(**kwargs: object) -> dict[str, object]:
        response = original(**kwargs)
        response["taskDefinition"]["taskDefinitionArn"] = (  # type: ignore[index]
            "arn:aws:ecs:us-east-2:785072247535:task-definition/m67-phase1-sampled-slot-activator:6"
        )
        return response

    client.describe_task_definition = mismatched  # type: ignore[method-assign]
    try:
        execute_once(client, _config())
    except RuntimeError as error:
        assert "immutable identity mismatch" in str(error)
    else:
        raise AssertionError("mismatched task definition must fail closed")
    assert client.update_calls == []
    assert client.run_calls == []
