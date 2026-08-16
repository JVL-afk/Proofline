"""Credential-free clock, identifier, and timing adapters."""

import time
from datetime import UTC, datetime
from uuid import UUID, uuid4


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class UuidFactory:
    def new(self) -> UUID:
        return uuid4()


class SystemSleeper:
    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)
