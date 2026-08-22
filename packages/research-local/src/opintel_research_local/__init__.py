"""Local M1 adapter exports."""

from opintel_research_local.browser import DisabledBrowserFallback, IsolatedBrowserFallback
from opintel_research_local.egress import ControlledEgressTransport
from opintel_research_local.http import SafeHttpFetcher, StdlibPinnedTransport
from opintel_research_local.persistence import SqlAlchemyResearchRepository
from opintel_research_local.runtime import SystemClock, SystemSleeper, UuidFactory
from opintel_research_local.settings import ResearchWorkerSettings, get_research_worker_settings

__all__ = [
    "ControlledEgressTransport",
    "DisabledBrowserFallback",
    "IsolatedBrowserFallback",
    "ResearchWorkerSettings",
    "SafeHttpFetcher",
    "SqlAlchemyResearchRepository",
    "StdlibPinnedTransport",
    "SystemClock",
    "SystemSleeper",
    "UuidFactory",
    "get_research_worker_settings",
]
