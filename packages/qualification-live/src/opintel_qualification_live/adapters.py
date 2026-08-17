"""Provider-native adapters implementing the provider-neutral M2.5 contract."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from opintel_qualification.domain import (
    IntelligenceRequest,
    ProviderKind,
    ProviderResponse,
)

from opintel_qualification_live.config import REQUEST_TIMEOUT_SECONDS
from opintel_qualification_live.contracts import (
    AdapterInvocation,
    DeploymentSpec,
    JsonTransport,
    ProviderReceipt,
)
from opintel_qualification_live.schema import OUTPUT_SCHEMA, build_prompt, decode_output


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _integer(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _json(body: bytes) -> Mapping[str, Any]:
    value = json.loads(body.decode("utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError("provider_response_not_object")
    return value


def _gemini_schema(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: _gemini_schema(item)
            for key, item in value.items()
            if key != "additionalProperties"
        }
    if isinstance(value, list):
        return [_gemini_schema(item) for item in value]
    return value


class NativeAdapter:
    provider_kind = ProviderKind.LIVE

    def __init__(self, spec: DeploymentSpec, credential: str, transport: JsonTransport) -> None:
        if not credential:
            raise ValueError("credential unavailable")
        self.spec = spec
        self.deployment_id = spec.id
        self._credential = credential
        self._transport = transport
        self.receipts: list[ProviderReceipt] = []

    def invoke(self, request: IntelligenceRequest, attempt: int) -> ProviderResponse:
        invocation = self.invoke_with_receipt(request, attempt)
        self.receipts.append(invocation.receipt)
        return invocation.response

    def invoke_with_receipt(self, request: IntelligenceRequest, attempt: int) -> AdapterInvocation:
        del attempt
        http = self._transport.post(
            self._url(), self._headers(), self._payload(request), REQUEST_TIMEOUT_SECONDS
        )
        if http.status != 200:
            failure = (
                "authentication_failed"
                if http.status in {401, 403}
                else "rate_limited"
                if http.status == 429
                else "transient_failure"
                if http.status >= 500
                else "provider_rejected"
            )
            if failure == "provider_rejected":
                failure = self._safe_rejection_code(http.body)
            retry_after = self._retry_after(http.headers.get("retry-after"))
            return self._failure(request, http.latency_ms, failure, retry_after)
        try:
            native = _json(http.body)
            output_text, metadata = self._extract(native)
            output = decode_output(output_text)
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            return self._failure(request, http.latency_ms, "malformed_response", None)
        input_tokens = metadata["input_tokens"]
        output_tokens = metadata["output_tokens"]
        cached_tokens = metadata["cached_tokens"]
        cost = self.spec.pricing.cost_micros(input_tokens, output_tokens, cached_tokens)
        response = ProviderResponse(
            output,
            True,
            None,
            input_tokens,
            output_tokens,
            cached_tokens,
            http.latency_ms,
            cost,
            self.spec.pricing.version,
        )
        receipt = ProviderReceipt(
            self.spec.provider,
            self.spec.id,
            request.task_contract.task_class,
            metadata["request_id"],
            self.spec.model_id,
            metadata["model"],
            self.spec.config_hash,
            self.spec.pricing.version,
            input_tokens,
            output_tokens,
            metadata["reasoning_tokens"],
            cached_tokens,
            http.latency_ms,
            None,
            cost,
            "schema_valid",
            None,
        )
        return AdapterInvocation(response, receipt)

    def _failure(
        self,
        request: IntelligenceRequest,
        latency_ms: int,
        code: str,
        retry_after_ms: int | None,
    ) -> AdapterInvocation:
        response = ProviderResponse(
            None, False, code, 0, 0, 0, latency_ms, 0, self.spec.pricing.version
        )
        receipt = ProviderReceipt(
            self.spec.provider,
            self.spec.id,
            request.task_contract.task_class,
            None,
            self.spec.model_id,
            None,
            self.spec.config_hash,
            self.spec.pricing.version,
            0,
            0,
            0,
            0,
            latency_ms,
            retry_after_ms,
            0,
            "failed",
            code,
        )
        return AdapterInvocation(response, receipt)

    @staticmethod
    def _retry_after(value: str | None) -> int | None:
        try:
            return round(float(value) * 1000) if value is not None else None
        except ValueError:
            return None

    @staticmethod
    def _safe_rejection_code(body: bytes) -> str:
        try:
            native = _json(body)
            error = _mapping(native.get("error"))
            candidate = error.get("status") or error.get("type") or error.get("code")
            if isinstance(candidate, str):
                safe = re.sub(r"[^A-Za-z0-9_.-]", "_", candidate)[:64]
                message = error.get("message")
                allowed_fields = (
                    "responseFormat",
                    "responseMimeType",
                    "responseSchema",
                    "thinkingConfig",
                    "thinkingLevel",
                    "includeThoughts",
                    "maxOutputTokens",
                    "additionalProperties",
                )
                field = next(
                    (
                        item
                        for item in allowed_fields
                        if isinstance(message, str) and item.lower() in message.lower()
                    ),
                    None,
                )
                if field:
                    safe = f"{safe}:{field}"
                return f"provider_rejected:{safe}"
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            pass
        return "provider_rejected"

    def _url(self) -> str:
        raise NotImplementedError

    def _headers(self) -> Mapping[str, str]:
        raise NotImplementedError

    def _payload(self, request: IntelligenceRequest) -> Mapping[str, object]:
        raise NotImplementedError

    def _extract(self, native: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
        raise NotImplementedError


class OpenAIAdapter(NativeAdapter):
    def _url(self) -> str:
        return "https://api.openai.com/v1/responses"

    def _headers(self) -> Mapping[str, str]:
        return {"Authorization": f"Bearer {self._credential}", "Content-Type": "application/json"}

    def _payload(self, request: IntelligenceRequest) -> Mapping[str, object]:
        return {
            "model": self.spec.model_id,
            "input": build_prompt(request),
            "reasoning": {"effort": "high"},
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "m26_qualification_output",
                    "strict": True,
                    "schema": OUTPUT_SCHEMA,
                }
            },
            "max_output_tokens": request.max_output_tokens,
            "store": False,
        }

    def _extract(self, native: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
        texts: list[str] = []
        for item in native.get("output", []):
            if not isinstance(item, Mapping) or item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if isinstance(content, Mapping) and content.get("type") == "output_text":
                    text = _string(content.get("text"))
                    if text:
                        texts.append(text)
        usage = _mapping(native.get("usage"))
        input_details = _mapping(usage.get("input_tokens_details"))
        output_details = _mapping(usage.get("output_tokens_details"))
        if not texts:
            raise ValueError("missing_output_text")
        return "".join(texts), {
            "request_id": _string(native.get("id")),
            "model": _string(native.get("model")),
            "input_tokens": _integer(usage.get("input_tokens")),
            "output_tokens": _integer(usage.get("output_tokens")),
            "reasoning_tokens": _integer(output_details.get("reasoning_tokens")),
            "cached_tokens": _integer(input_details.get("cached_tokens")),
        }


class AnthropicAdapter(NativeAdapter):
    def _url(self) -> str:
        return "https://api.anthropic.com/v1/messages"

    def _headers(self) -> Mapping[str, str]:
        return {
            "x-api-key": self._credential,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

    def _payload(self, request: IntelligenceRequest) -> Mapping[str, object]:
        return {
            "model": self.spec.model_id,
            "max_tokens": request.max_output_tokens,
            "system": build_prompt(request).split("\n\nQUALIFICATION_INPUT=", 1)[0],
            "messages": [
                {
                    "role": "user",
                    "content": build_prompt(request).split("\n\nQUALIFICATION_INPUT=", 1)[1],
                }
            ],
            "thinking": {"type": "adaptive", "display": "omitted"},
            "output_config": {
                "effort": "high",
                "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA},
            },
        }

    def _extract(self, native: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
        texts = [
            str(item["text"])
            for item in native.get("content", [])
            if isinstance(item, Mapping) and item.get("type") == "text" and "text" in item
        ]
        usage = _mapping(native.get("usage"))
        output_details = _mapping(usage.get("output_tokens_details"))
        if not texts:
            raise ValueError("missing_text")
        return "".join(texts), {
            "request_id": _string(native.get("id")),
            "model": _string(native.get("model")),
            "input_tokens": _integer(usage.get("input_tokens")),
            "output_tokens": _integer(usage.get("output_tokens")),
            "reasoning_tokens": _integer(output_details.get("thinking_tokens")),
            "cached_tokens": _integer(usage.get("cache_read_input_tokens")),
        }


class GeminiAdapter(NativeAdapter):
    def _url(self) -> str:
        return (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.spec.model_id}:generateContent"
        )

    def _headers(self) -> Mapping[str, str]:
        return {"x-goog-api-key": self._credential, "Content-Type": "application/json"}

    def _payload(self, request: IntelligenceRequest) -> Mapping[str, object]:
        prompt = build_prompt(request)
        system, qualification_input = prompt.split("\n\nQUALIFICATION_INPUT=", 1)
        return {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": qualification_input}]}],
            "generationConfig": {
                "maxOutputTokens": request.max_output_tokens,
                "thinkingConfig": {"thinkingLevel": "MEDIUM", "includeThoughts": False},
                "responseMimeType": "application/json",
                "responseSchema": _gemini_schema(OUTPUT_SCHEMA),
            },
        }

    def _extract(self, native: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
        candidates = native.get("candidates", [])
        if not isinstance(candidates, list) or not candidates:
            raise ValueError("missing_candidate")
        content = _mapping(_mapping(candidates[0]).get("content"))
        texts = [
            str(part["text"])
            for part in content.get("parts", [])
            if isinstance(part, Mapping) and "text" in part and not part.get("thought", False)
        ]
        usage = _mapping(native.get("usageMetadata"))
        reasoning = _integer(usage.get("thoughtsTokenCount"))
        visible_output = _integer(usage.get("candidatesTokenCount"))
        if not texts:
            raise ValueError("missing_text")
        return "".join(texts), {
            "request_id": _string(native.get("responseId")),
            "model": _string(native.get("modelVersion")),
            "input_tokens": _integer(usage.get("promptTokenCount")),
            "output_tokens": visible_output + reasoning,
            "reasoning_tokens": reasoning,
            "cached_tokens": _integer(usage.get("cachedContentTokenCount")),
        }
