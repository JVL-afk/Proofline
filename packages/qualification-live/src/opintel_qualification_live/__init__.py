"""Explicit synthetic-only M2.6 live qualification boundary."""

from opintel_qualification_live.adapters import AnthropicAdapter, GeminiAdapter, OpenAIAdapter
from opintel_qualification_live.config import DEPLOYMENTS
from opintel_qualification_live.tournament import TournamentRunner

__all__ = ["DEPLOYMENTS", "AnthropicAdapter", "GeminiAdapter", "OpenAIAdapter", "TournamentRunner"]
