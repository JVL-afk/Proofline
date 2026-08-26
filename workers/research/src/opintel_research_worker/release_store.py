"""Exact-parameter SSM store for the bounded sampled-slot execution lifecycle."""

from __future__ import annotations

from typing import Protocol, cast


class SsmReadWriteClient(Protocol):
    def get_parameter(self, *, Name: str, WithDecryption: bool = False) -> object: ...
    def put_parameter(
        self, *, Name: str, Value: str, Type: str, Overwrite: bool
    ) -> object: ...


class AwsSsmReleaseControlStore:
    def __init__(
        self,
        *,
        approval_parameter: str,
        release_parameter: str,
        kill_switch_parameter: str,
        region: str,
        client: SsmReadWriteClient | None = None,
    ) -> None:
        names = (approval_parameter, release_parameter, kill_switch_parameter)
        if any(not value or not value.startswith("/m67-phase1/") for value in names):
            raise ValueError("bounded release store requires exact Phase 1 parameter names")
        if len(set(names)) != 3:
            raise ValueError("approval, release, and kill parameters must be distinct")
        if client is None:
            import boto3  # type: ignore[import-untyped]

            client = boto3.client("ssm", region_name=region)
        self._client = client
        self._approval = approval_parameter
        self._release = release_parameter
        self._kill = kill_switch_parameter

    def read_approval_envelope(self) -> str:
        return self._read(self._approval)

    def read_release(self) -> str:
        return self._read(self._release)

    def write_release(self, value: str) -> None:
        self._write(self._release, value)

    def read_kill_switch(self) -> str:
        return self._read(self._kill)

    def write_kill_switch(self, value: str) -> None:
        if value not in {"RUN", "TRIPPED"}:
            raise ValueError("kill switch accepts only RUN or TRIPPED")
        self._write(self._kill, value)

    def _read(self, name: str) -> str:
        response = self._client.get_parameter(Name=name, WithDecryption=False)
        if not isinstance(response, dict):
            raise ValueError("unexpected SSM response")
        parameter = response.get("Parameter")
        if not isinstance(parameter, dict) or not isinstance(parameter.get("Value"), str):
            raise ValueError("SSM parameter value is unavailable")
        return cast(str, parameter["Value"])

    def _write(self, name: str, value: str) -> None:
        self._client.put_parameter(
            Name=name, Value=value, Type="String", Overwrite=True
        )
