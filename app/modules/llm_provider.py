"""Structured LLM provider boundary and offline contract validation.

This module deliberately has no external provider adapter and performs no I/O.
The orchestrator does not call it yet; it is a safe foundation for later, approved
F1-F4 integration.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from enum import Enum
from typing import Any, Mapping, Protocol, Type

from pydantic import BaseModel, StrictBool, StrictStr, ValidationError, confloat

try:  # Support both the installed Pydantic 2 and the repository's unpinned v1 range.
    from pydantic import ConfigDict, field_validator as _field_validator
    _PYDANTIC_V2 = True
except ImportError:  # pragma: no cover - exercised only in Pydantic 1 environments
    from pydantic import validator as _field_validator
    _PYDANTIC_V2 = False

from ..contracts.vocabularies import IntentCode


class LLMFunction(str, Enum):
    F1 = "F1"
    F2 = "F2"
    F3 = "F3"
    F4 = "F4"


class ProviderErrorCode(str, Enum):
    EMPTY_RESPONSE = "EMPTY_RESPONSE"
    OUTPUT_INVALID = "OUTPUT_INVALID"
    NO_FIXTURE = "NO_FIXTURE"
    TIMEOUT = "TIMEOUT"
    RATE_LIMITED = "RATE_LIMITED"
    UNAVAILABLE = "UNAVAILABLE"
    CONFIGURATION = "CONFIGURATION"
    AUTHENTICATION = "AUTHENTICATION"
    ACCESS_DENIED = "ACCESS_DENIED"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    CONNECTION_ERROR = "CONNECTION_ERROR"
    PROVIDER_ERROR = "PROVIDER_ERROR"


class ProviderError(Exception):
    """Safe provider failure; deliberately excludes upstream messages/payloads."""

    def __init__(self, code: ProviderErrorCode):
        self.code = code
        super().__init__(code.value)


if _PYDANTIC_V2:
    class StrictModel(BaseModel):
        model_config = ConfigDict(extra="forbid", validate_assignment=True)
else:  # pragma: no cover - installed Pydantic 2 is the verified runtime
    class StrictModel(BaseModel):
        class Config:
            extra = "forbid"
            validate_assignment = True


class F1Input(StrictModel):
    message: StrictStr
    short_context: StrictStr = ""


class IntentEntities(StrictModel):
    # These are the entity keys currently extracted by app.modules.intent._slots.
    card_last4: StrictStr | None = None
    reference: StrictStr | None = None
    date_hint: StrictStr | None = None

    @_field_validator("card_last4")
    def valid_card_last4(cls, value):
        if value is not None and not re.fullmatch(r"\d{4}", value):
            raise ValueError("invalid entity")
        return value

    @_field_validator("reference")
    def valid_reference(cls, value):
        if value is not None and not (1 <= len(value) <= 80):
            raise ValueError("invalid entity")
        return value

    @_field_validator("date_hint")
    def valid_date_hint(cls, value):
        if value is not None and not (1 <= len(value) <= 40):
            raise ValueError("invalid entity")
        return value


class F1Output(StrictModel):
    intent_code: IntentCode
    confidence_hint: confloat(strict=True, ge=0.0, le=1.0, allow_inf_nan=False)
    entities: IntentEntities
    is_multi: StrictBool


class F2Input(StrictModel):
    candidate_intent: IntentCode


class F2Output(StrictModel):
    question: StrictStr
    options: list[StrictStr]

    @_field_validator("question")
    def nonempty_question(cls, value):
        if not value.strip():
            raise ValueError("invalid clarification")
        return value

    @_field_validator("options")
    def bounded_options_without_internal_codes(cls, value):
        if len(value) > 3 or any(not option.strip() for option in value):
            raise ValueError("invalid clarification")
        enum_codes = [item.value for item in IntentCode]
        for option in value:
            if any(re.search(rf"(?<![A-Z0-9_]){re.escape(code)}(?![A-Z0-9_])", option, re.I)
                   for code in enum_codes):
                raise ValueError("invalid clarification")
        return value

    @_field_validator("question")
    def question_has_no_internal_code(cls, value):
        enum_codes = [item.value for item in IntentCode]
        if any(re.search(rf"(?<![A-Z0-9_]){re.escape(code)}(?![A-Z0-9_])", value, re.I)
               for code in enum_codes):
            raise ValueError("invalid clarification")
        return value


class F3Input(StrictModel):
    permitted_tools: list[StrictStr]
    tool_schemas: dict[StrictStr, dict[str, Any]]
    context: dict[str, Any]

    @_field_validator("permitted_tools")
    def unique_permitted_tools(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("invalid permitted tool set")
        return value

class F3Output(StrictModel):
    tool_name: StrictStr
    arguments: dict[str, Any]


class ClaimMapItem(StrictModel):
    claim: StrictStr
    source_ids: list[StrictStr]

    @_field_validator("claim")
    def nonempty_claim(cls, value):
        if not value.strip():
            raise ValueError("invalid claim")
        return value

    @_field_validator("source_ids")
    def requires_unique_sources(cls, value):
        if not value or len(value) != len(set(value)):
            raise ValueError("invalid claim sources")
        return value


class F4Source(StrictModel):
    source_id: StrictStr
    source_type: StrictStr  # caller-controlled enum is checked below
    text: StrictStr

    @_field_validator("source_id", "text")
    def nonempty_source_fields(cls, value):
        if not value.strip():
            raise ValueError("invalid source")
        return value

    @_field_validator("source_type")
    def allowed_source_type(cls, value):
        if value not in {"KNOWLEDGE_CITATION", "TOOL_RESULT"}:
            raise ValueError("invalid source")
        return value


class F4Input(StrictModel):
    question: StrictStr = ""
    sources: list[F4Source]

    @_field_validator("sources")
    def unique_source_ids(cls, value):
        ids = [item.source_id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("invalid sources")
        return value


class F4Output(StrictModel):
    text: StrictStr
    claim_map: list[ClaimMapItem]

    @_field_validator("text")
    def nonempty_text(cls, value):
        if not value.strip():
            raise ValueError("empty answer")
        return value


INPUT_MODELS: dict[LLMFunction, Type[StrictModel]] = {
    LLMFunction.F1: F1Input,
    LLMFunction.F2: F2Input,
    LLMFunction.F3: F3Input,
    LLMFunction.F4: F4Input,
}
OUTPUT_MODELS: dict[LLMFunction, Type[StrictModel]] = {
    LLMFunction.F1: F1Output,
    LLMFunction.F2: F2Output,
    LLMFunction.F3: F3Output,
    LLMFunction.F4: F4Output,
}


class StructuredGenerationProvider(Protocol):
    """Generate untrusted structured data; this interface cannot invoke tools."""

    def generate(self, function: LLMFunction, payload: StrictModel,
                 *, timeout_ms: int | None = None) -> object:
        """Return raw structured data for mandatory local schema validation."""
        ...


def _model_validate(model: Type[BaseModel], value: object) -> BaseModel:
    try:
        if isinstance(value, model):
            return value
        if value is None or value == "":
            raise ProviderError(ProviderErrorCode.EMPTY_RESPONSE)
        if isinstance(value, str):
            if not value.strip():
                raise ProviderError(ProviderErrorCode.EMPTY_RESPONSE)
            if hasattr(model, "model_validate_json"):
                return model.model_validate_json(value)
            return model.parse_raw(value)
        if hasattr(model, "model_validate"):
            return model.model_validate(value)
        return model.parse_obj(value)
    except ProviderError:
        raise
    except (ValidationError, ValueError, TypeError):
        # Do not chain Pydantic's error: it can include sensitive input values.
        raise ProviderError(ProviderErrorCode.OUTPUT_INVALID) from None


def _canonical_payload(payload: BaseModel) -> str:
    dumped = (payload.model_dump(exclude_none=True) if hasattr(payload, "model_dump")
              else payload.dict(exclude_none=True))
    return json.dumps(dumped, sort_keys=True, separators=(",", ":"), default=str)


def _model_json_schema(model: Type[BaseModel]) -> dict[str, Any]:
    if hasattr(model, "model_json_schema"):
        return model.model_json_schema()
    return model.schema()


def fixture_key(function: LLMFunction, payload: BaseModel) -> str:
    """Stable task+input key, so a fixture cannot answer unrelated requests."""
    digest = hashlib.sha256(_canonical_payload(payload).encode("utf-8")).hexdigest()
    return f"{function.value}:{digest}"


def _validate_timeout_ms(timeout_ms: int | None) -> None:
    if timeout_ms is not None and (type(timeout_ms) is not int or timeout_ms <= 0):
        raise ProviderError(ProviderErrorCode.CONFIGURATION)


class DeterministicStubProvider:
    """Offline fixture provider. Missing fixtures fail closed; no guessing/I/O."""

    def __init__(self, fixtures: Mapping[str, object] | None = None):
        self._fixtures = dict(fixtures or {})

    def generate(self, function: LLMFunction, payload: StrictModel,
                 *, timeout_ms: int | None = None) -> object:
        _validate_timeout_ms(timeout_ms)
        key = fixture_key(function, payload)
        if key not in self._fixtures:
            raise ProviderError(ProviderErrorCode.NO_FIXTURE)
        # Return a fresh copy and never let callers mutate a shared fixture.
        return json.loads(json.dumps(self._fixtures[key]))


def build_provider(provider_name: str | None = None,
                   fixtures: Mapping[str, object] | None = None) -> StructuredGenerationProvider:
    """Choose a provider explicitly; an API key alone never changes the stub default."""
    selected = provider_name if provider_name is not None else os.getenv("LLM_PROVIDER", "stub")
    if selected == "stub":
        return DeterministicStubProvider(fixtures)
    if selected == "gemini":
        from .gemini_provider import GeminiStructuredGenerationProvider

        api_key = os.getenv("LLM_API_KEY", "")
        model_name = os.getenv("LLM_MODEL", "")
        timeout_value = os.getenv("LLM_TIMEOUT_MS", "10000")
        try:
            timeout_ms = int(timeout_value)
        except (TypeError, ValueError):
            raise ProviderError(ProviderErrorCode.CONFIGURATION) from None
        return GeminiStructuredGenerationProvider(
            api_key=api_key,
            model_name=model_name,
            timeout_ms=timeout_ms,
        )
    else:
        raise ProviderError(ProviderErrorCode.CONFIGURATION)


def generate_validated(provider: StructuredGenerationProvider, function: LLMFunction,
                       payload: object, *, timeout_ms: int | None = None,
                       tool_models: Mapping[str, Type[BaseModel]] | None = None) -> StrictModel:
    """Validate request, provider output and F3/F4 references before returning."""
    request = _model_validate(INPUT_MODELS[function], payload)
    if isinstance(request, F3Input) and set(request.tool_schemas) != set(request.permitted_tools):
        raise ProviderError(ProviderErrorCode.OUTPUT_INVALID)
    _validate_timeout_ms(timeout_ms)
    try:
        raw = provider.generate(function, request, timeout_ms=timeout_ms)
    except ProviderError:
        raise
    except TimeoutError:
        raise ProviderError(ProviderErrorCode.TIMEOUT) from None
    except Exception:
        # Upstream exception text may contain request headers or payloads.
        raise ProviderError(ProviderErrorCode.UNAVAILABLE) from None

    result = _model_validate(OUTPUT_MODELS[function], raw)
    if isinstance(result, F3Output):
        permitted_models = dict(tool_models or {})
        if result.tool_name not in request.permitted_tools or result.tool_name not in permitted_models:
            raise ProviderError(ProviderErrorCode.OUTPUT_INVALID)
        expected_schema = _model_json_schema(permitted_models[result.tool_name])
        if json.dumps(request.tool_schemas[result.tool_name], sort_keys=True, separators=(",", ":")) != json.dumps(
                expected_schema, sort_keys=True, separators=(",", ":")):
            raise ProviderError(ProviderErrorCode.OUTPUT_INVALID)
        parsed_args = _model_validate(permitted_models[result.tool_name], result.arguments)
        result = F3Output(tool_name=result.tool_name,
                          arguments=(parsed_args.model_dump(exclude_none=True)
                                     if hasattr(parsed_args, "model_dump")
                                     else parsed_args.dict(exclude_none=True)))
    elif isinstance(result, F4Output):
        source_ids = {item.source_id for item in request.sources}
        normalized_text = " ".join(result.text.split()).casefold()
        normalized_claims = []
        for item in result.claim_map:
            if not set(item.source_ids).issubset(source_ids):
                raise ProviderError(ProviderErrorCode.OUTPUT_INVALID)
            # A mapped claim must actually occur in answer text. Source grounding
            # remains the responsibility of the caller's guardrail.
            normalized_claim = " ".join(item.claim.split()).casefold()
            if normalized_claim not in normalized_text:
                raise ProviderError(ProviderErrorCode.OUTPUT_INVALID)
            normalized_claims.append(normalized_claim)
        if result.text.strip() and not result.claim_map:
            raise ProviderError(ProviderErrorCode.OUTPUT_INVALID)
        # Every answer sentence must be represented in the source-mapped claims;
        # otherwise an uncited add-on could ride alongside a valid claim.
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", normalized_text) if part.strip()]
        if any(not any(sentence in claim or claim in sentence for claim in normalized_claims)
               for sentence in sentences):
            raise ProviderError(ProviderErrorCode.OUTPUT_INVALID)
    return result  # type: ignore[return-value]
