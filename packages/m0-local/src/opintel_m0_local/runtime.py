"""Clock and identifier adapters."""

from datetime import UTC, datetime
from uuid import UUID, uuid4


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class UuidFactory:
    def new(self) -> UUID:
        return uuid4()
