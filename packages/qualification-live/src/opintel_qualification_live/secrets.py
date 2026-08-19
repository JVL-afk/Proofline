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


@dataclass(frozen=True, slots=True)
class AvailableSecretBundle:
    openai: str | None = field(repr=False)
    anthropic: str | None = field(repr=False)
    gemini: str | None = field(repr=False)

    def for_provider(self, provider: str) -> str | None:
        if provider == "openai":
            return self.openai
        if provider == "anthropic":
            return self.anthropic
        if provider == "gemini":
            return self.gemini
        raise SecretConfigurationError(provider)


def _read_secret_values(path: Path) -> dict[str, str]:
    raw = path.read_bytes()
    text = _decode_secret_text(raw)
    values: dict[str, str] = {}
    for line in text.splitlines():
        label, value = _secret_line(line)
        if label is not None and value is not None:
            values[label] = value
    return values


def _decode_secret_text(raw: bytes) -> str:
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
    return text


def _secret_line(line: str) -> tuple[str | None, str | None]:
    stripped = line.strip()
    if not stripped:
        return None, None
    label, separator, raw_value = stripped.partition(":")
    if not separator:
        return None, None
    value = raw_value.strip()
    quote_chars = {'"', "\u201c", "\u201d"}
    if len(value) >= 2 and value[0] in quote_chars and value[-1] in quote_chars:
        value = value[1:-1]
    return label.strip().upper(), value


def load_single_provider_secret(path: Path, provider: str) -> str:
    """Load only one provider value without retaining unrelated credentials."""
    wanted = {"openai": "OPENAI", "anthropic": "ANTHROPIC", "gemini": "GEMINI"}.get(provider)
    if wanted is None:
        raise SecretConfigurationError(provider)
    text = _decode_secret_text(path.read_bytes())
    for line in text.splitlines():
        label, value = _secret_line(line)
        if label == wanted and value:
            return value
    raise SecretConfigurationError(provider)


def load_available_secret_bundle(path: Path) -> AvailableSecretBundle:
    values = _read_secret_values(path)
    return AvailableSecretBundle(
        values.get("OPENAI"), values.get("ANTHROPIC"), values.get("GEMINI")
    )


def load_secret_bundle(path: Path) -> SecretBundle:
    values = _read_secret_values(path)
    for label in ("OPENAI", "ANTHROPIC", "GEMINI"):
        if not values.get(label):
            raise SecretConfigurationError(label)
    return SecretBundle(values["OPENAI"], values["ANTHROPIC"], values["GEMINI"])
