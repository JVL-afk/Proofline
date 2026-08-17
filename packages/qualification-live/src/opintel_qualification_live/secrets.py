"""Strict ignored-file credential loader with redacted representations."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


class SecretConfigurationError(ValueError):
    def __init__(self, provider: str) -> None:
        super().__init__(f"credential unavailable for provider: {provider}")
        self.provider = provider


@dataclass(frozen=True, slots=True)
class SecretBundle:
    openai: str = field(repr=False)
    anthropic: str = field(repr=False)
    gemini: str = field(repr=False)

    def for_provider(self, provider: str) -> str:
        if provider == "openai":
            return self.openai
        if provider == "anthropic":
            return self.anthropic
        if provider == "gemini":
            return self.gemini
        raise SecretConfigurationError(provider)


def load_secret_bundle(path: Path) -> SecretBundle:
    raw = path.read_bytes()
    text: str | None = None
    encodings = (
        ("utf-16",) if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else ("utf-8-sig", "cp1252")
    )
    for encoding in encodings:
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise SecretConfigurationError("credential_file")
    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        label, separator, raw_value = stripped.partition(":")
        if not separator:
            continue
        value = raw_value.strip()
        quote_chars = {'"', "\u201c", "\u201d"}
        if len(value) >= 2 and value[0] in quote_chars and value[-1] in quote_chars:
            value = value[1:-1]
        values[label.strip().upper()] = value
    for label in ("OPENAI", "ANTHROPIC", "GEMINI"):
        if not values.get(label):
            raise SecretConfigurationError(label)
    return SecretBundle(values["OPENAI"], values["ANTHROPIC"], values["GEMINI"])
