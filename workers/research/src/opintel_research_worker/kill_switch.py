"""Fail-closed Phase 1 SSM kill-switch adapter."""

from __future__ import annotations

import logging
from typing import Protocol


class SsmClient(Protocol):
    def get_parameter(self, *, Name: str) -> object: ...


class AwsSsmStopSignal:
    def __init__(self, parameter_name: str, region: str, client: SsmClient | None = None) -> None:
        if not parameter_name:
            raise ValueError("kill-switch parameter is required")
        if client is None:
            import boto3  # type: ignore[import-untyped]

            client = boto3.client("ssm", region_name=region)
        self._client = client
        self._name = parameter_name

    def is_active(self) -> bool:
        try:
            response = self._client.get_parameter(Name=self._name)
            if not isinstance(response, dict):
                raise TypeError("unexpected SSM response")
            parameter = response.get("Parameter")
            if not isinstance(parameter, dict):
                raise TypeError("missing SSM parameter")
            return str(parameter.get("Value", "")).strip().upper() != "RUN"
        except Exception:
            logging.exception("kill_switch.read_failed")
            return True


__all__ = ["AwsSsmStopSignal"]
