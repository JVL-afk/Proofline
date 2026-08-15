"""Local-only M0 adapters."""

from opintel_m0_local.auth import LocalTokenAuthenticator
from opintel_m0_local.fixture import FixtureHtmlExtractor, LocalFixtureFetcher
from opintel_m0_local.persistence import SqlAlchemyM0Repository
from opintel_m0_local.runtime import SystemClock, UuidFactory
from opintel_m0_local.settings import LocalSettings

__all__ = [
    "FixtureHtmlExtractor",
    "LocalFixtureFetcher",
    "LocalSettings",
    "LocalTokenAuthenticator",
    "SqlAlchemyM0Repository",
    "SystemClock",
    "UuidFactory",
]
