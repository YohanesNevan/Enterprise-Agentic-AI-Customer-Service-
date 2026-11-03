from __future__ import annotations

import json

import httpx
import pytest
from google.genai.errors import APIError, ClientError, ServerError
from pydantic import StrictInt, StrictStr

from app.contracts.vocabularies import IntentCode
from app.modules import gemini_provider as GeminiModule
from app.modules.gemini_provider import GeminiStructuredGenerationProvider
from app.modules.llm_provider import (
    F1Input,
    F1Output,
    F2Input,
    F2Output,
    F3Input,
    F3Output,
    F4Input,
    F4Output,
    F4Source,
    LLMFunction,
    ProviderError,
    ProviderErrorCode,
    StrictModel,
    build_provider,
    generate_validated,
)


class FakeModels:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, response=None, error=None):
        self.models = FakeModels(response=response, error=error)


class FakeResponse:
    def __init__(self, text=None, parsed=None):
        self.text = text
        self.parsed = parsed


class CaseLookupArgs(StrictModel):
    reference: StrictStr
    limit: StrictInt


def _adapter(response=None, error=None):
    client = FakeClient(response=response, error=error)
    provider = GeminiStructuredGenerationProvider(
        api_key="synthetic-test-key",
        model_name="test-model",
        timeout_ms=7000,
        client=client,
    )
    return provider, client


def test_adapter_matches_provider_generate_interface_and_sends_structured_request():
    expected = {
        "intent_code": IntentCode.INFO_PRODUCT_POLICY.value,
        "confidence_hint": 0.8,
        "entities": {},
        "is_multi": False,
    }
    provider, client = _adapter(FakeResponse(text=json.dumps(expected)))
    assert callable(provider.generate)

    result = generate_validated(
        provider, LLMFunction.F1, F1Input(message="cek biaya"))

    assert isinstance(result, F1Output)
    call = client.models.calls[0]
    assert call["model"] == "test-model"
    assert call["config"]["response_mime_type"] == "application/json"
    assert call["config"]["response_json_schema"] == F1Output.model_json_schema()
    assert call["config"]["http_options"]["timeout"] == 7000
    assert call["config"]["http_options"]["retry_options"]["attempts"] == 1
    assert "tools" not in call["config"]


def test_adapter_honors_per_call_timeout_override():
    expected = {
        "intent_code": IntentCode.INFO_PRODUCT_POLICY.value,
        "confidence_hint": 0.8,
        "entities": {},
        "is_multi": False,
    }
    provider, client = _adapter(FakeResponse(text=json.dumps(expected)))

    provider.generate(LLMFunction.F1, F1Input(message="cek biaya"), timeout_ms=1250)

    assert client.models.calls[0]["config"]["http_options"]["timeout"] == 1250


@pytest.mark.parametrize("function,payload,output", [
    (LLMFunction.F1, F1Input(message="hi"), {
        "intent_code": "GEN_SMALL_TALK_OTHER", "confidence_hint": 0.8,
        "entities": {}, "is_multi": False,
    }),
    (LLMFunction.F2, F2Input(candidate_intent=IntentCode.INFO_PRODUCT_POLICY), {
        "question": "Apakah yang ingin Anda ketahui?", "options": ["Biaya", "Syarat"],
    }),
    (LLMFunction.F3, F3Input(permitted_tools=["case_lookup"],
        tool_schemas={"case_lookup": CaseLookupArgs.model_json_schema()}, context={
            "reference": "CASE-123",
        }), {
        "tool_name": "case_lookup", "arguments": {"reference": "CASE-123", "limit": 1},
    }),
    (LLMFunction.F4, F4Input(sources=[F4Source(source_id="src-1",
        source_type="KNOWLEDGE_CITATION", text="Biaya layanan Rp 25.000.")]), {
        "text": "Biaya layanan Rp 25.000.",
        "claim_map": [{"claim": "Biaya layanan Rp 25.000.", "source_ids": ["src-1"]}],
    }),
])
def test_adapter_validates_all_function_schemas(function, payload, output):
    provider, _ = _adapter(FakeResponse(text=json.dumps(output)))
    tool_models = {"case_lookup": CaseLookupArgs} if function == LLMFunction.F3 else None

    result = generate_validated(provider, function, payload, tool_models=tool_models)

    assert isinstance(result, {
        LLMFunction.F1: F1Output,
        LLMFunction.F2: F2Output,
        LLMFunction.F3: F3Output,
        LLMFunction.F4: F4Output,
    }[function])


@pytest.mark.parametrize("response,code", [
    (FakeResponse(text=None), ProviderErrorCode.EMPTY_RESPONSE),
    (FakeResponse(text="  "), ProviderErrorCode.EMPTY_RESPONSE),
    (FakeResponse(text="not-json"), ProviderErrorCode.OUTPUT_INVALID),
    (FakeResponse(text='{"intent_code":"UNKNOWN"}'), ProviderErrorCode.OUTPUT_INVALID),
])
def test_empty_or_invalid_gemini_output_is_rejected_safely(response, code):
    provider, _ = _adapter(response)

    with pytest.raises(ProviderError) as exc:
        generate_validated(provider, LLMFunction.F1, F1Input(message="x"))

    assert exc.value.code == code
    assert "not-json" not in str(exc.value)


@pytest.mark.parametrize("error,code", [
    (TimeoutError("upstream secret text"), ProviderErrorCode.TIMEOUT),
    (httpx.ReadTimeout("api-key-canary", request=httpx.Request("POST", "https://example.invalid")),
     ProviderErrorCode.TIMEOUT),
    (httpx.ConnectError("authorization-header-canary",
                        request=httpx.Request("POST", "https://example.invalid")),
     ProviderErrorCode.CONNECTION_ERROR),
    (ClientError(401, {"status": "UNAUTHENTICATED", "message": "api-key-canary"}),
     ProviderErrorCode.AUTHENTICATION),
    (ClientError(403, {"status": "PERMISSION_DENIED", "message": "bearer-header-canary"}),
     ProviderErrorCode.ACCESS_DENIED),
    (ClientError(404, {"status": "NOT_FOUND", "message": "private-model-name"}),
     ProviderErrorCode.RESOURCE_NOT_FOUND),
    (ClientError(429, {"status": "RESOURCE_EXHAUSTED", "message": "private-quota-detail"}),
     ProviderErrorCode.RATE_LIMITED),
    (ClientError(403, {"status": "RESOURCE_EXHAUSTED", "message": "private-quota-detail"}),
     ProviderErrorCode.RATE_LIMITED),
    (ClientError(408, {"status": "DEADLINE_EXCEEDED", "message": "private-timeout-detail"}),
     ProviderErrorCode.TIMEOUT),
    (ClientError(400, {"status": "INVALID_ARGUMENT", "message": "private-request-detail"}),
     ProviderErrorCode.CONFIGURATION),
    (ServerError(503, {"status": "UNAVAILABLE", "message": "private-provider-detail"}),
     ProviderErrorCode.PROVIDER_ERROR),
    (APIError(418, {"status": "UNKNOWN_STATUS", "message": "raw-response-canary"}),
     ProviderErrorCode.UNAVAILABLE),
])
def test_provider_failures_map_to_safe_internal_error(error, code, caplog):
    provider, client = _adapter(error=error)

    with pytest.raises(ProviderError) as exc:
        provider.generate(LLMFunction.F1, F1Input(message="synthetic"))

    assert exc.value.code == code
    assert str(exc.value) == code.value
    assert exc.value.__cause__ is None
    assert all(secret not in str(exc.value) for secret in (
        "api-key-canary", "authorization-header-canary", "bearer-header-canary",
        "private-model-name", "private-quota-detail", "private-timeout-detail",
        "private-request-detail", "private-provider-detail", "raw-response-canary",
    ))
    assert all(secret not in caplog.text for secret in (
        "api-key-canary", "authorization-header-canary", "bearer-header-canary",
        "private-provider-detail", "raw-response-canary",
    ))
    assert len(client.models.calls) == 1


@pytest.mark.parametrize(("status_code", "rpc_status", "reason"), [
    (404, "NOT_FOUND", "MODEL_OR_ENDPOINT_NOT_FOUND"),
    (403, "PERMISSION_DENIED", "ACCESS_DENIED"),
    (401, "UNAUTHENTICATED", "CREDENTIAL_REJECTED"),
    (429, "RESOURCE_EXHAUSTED", "RATE_LIMITED"),
])
def test_provider_failure_diagnostic_uses_allowlisted_status_only(status_code, rpc_status, reason):
    error = APIError(status_code, {"status": rpc_status, "message": "private-canary-detail"})
    assert GeminiStructuredGenerationProvider._safe_error_reason(error) == reason
    assert "private-canary-detail" not in reason


def test_adapter_rejects_missing_api_key_invalid_timeout_and_empty_f3_allowlist():
    with pytest.raises(ProviderError) as missing:
        GeminiStructuredGenerationProvider(api_key="", model_name="test-model", client=FakeClient())
    assert missing.value.code == ProviderErrorCode.CONFIGURATION
    assert str(missing.value) == ProviderErrorCode.CONFIGURATION.value

    with pytest.raises(ProviderError) as timeout:
        GeminiStructuredGenerationProvider(api_key="synthetic-test-key", model_name="test-model",
                                            timeout_ms=20_001, client=FakeClient())
    assert timeout.value.code == ProviderErrorCode.CONFIGURATION

    provider, client = _adapter(FakeResponse(text='{"tool_name":"x","arguments":{}}'))
    with pytest.raises(ProviderError) as empty_allowlist:
        provider.generate(LLMFunction.F3, F3Input(permitted_tools=[], tool_schemas={}, context={}))
    assert empty_allowlist.value.code == ProviderErrorCode.OUTPUT_INVALID
    assert client.models.calls == []


def test_factory_requires_explicit_gemini_and_rejects_missing_key(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("LLM_API_KEY", "synthetic-test-key")
    assert build_provider().__class__.__name__ == "DeterministicStubProvider"

    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(ProviderError) as missing:
        build_provider()
    assert missing.value.code == ProviderErrorCode.CONFIGURATION


def test_factory_selects_gemini_only_when_provider_setting_is_explicit(monkeypatch):
    captured = {}

    class FactoryFake:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(GeminiModule, "GeminiStructuredGenerationProvider", FactoryFake)
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("LLM_API_KEY", "synthetic-test-key")
    monkeypatch.setenv("LLM_MODEL", "gemini-test-model")
    monkeypatch.setenv("LLM_TIMEOUT_MS", "9000")

    selected = build_provider()

    assert isinstance(selected, FactoryFake)
    assert captured == {
        "api_key": "synthetic-test-key",
        "model_name": "gemini-test-model",
        "timeout_ms": 9000,
    }


def test_f3_output_schema_narrows_tool_names_without_providing_executor():
    schema = GeminiStructuredGenerationProvider._request_schema(
        LLMFunction.F3,
        F3Input(permitted_tools=["case_lookup"], tool_schemas={"case_lookup": {}}, context={}),
    )
    assert schema["properties"]["tool_name"]["enum"] == ["case_lookup"]
    assert "tools" not in schema


def test_f4_prompt_requires_claim_text_to_match_validated_claim_map():
    from app.modules.gemini_provider import GeminiStructuredGenerationProvider
    prompt = GeminiStructuredGenerationProvider._prompt(
        LLMFunction.F4,
        F4Input(question="Apa itu NPB?", sources=[F4Source(
            source_id="synthetic-npb", source_type="KNOWLEDGE_CITATION",
            text="NPB means Nusantara Prima Bank.")]),
    )
    assert "copy every claim_map.claim verbatim into text" in prompt
    assert "do not add text that is absent from claim_map" in prompt


def test_f3_rejects_tool_outside_policy_set_and_schema_mismatch_offline():
    payload = F3Input(permitted_tools=["case_lookup"],
        tool_schemas={"case_lookup": CaseLookupArgs.model_json_schema()}, context={})
    outside, outside_client = _adapter(FakeResponse(text=json.dumps({
        "tool_name": "transfer_funds", "arguments": {},
    })))
    with pytest.raises(ProviderError) as denied:
        outside.generate(LLMFunction.F3, payload)
    assert denied.value.code == ProviderErrorCode.OUTPUT_INVALID
    assert "tools" not in outside_client.models.calls[0]["config"]

    mismatch, mismatch_client = _adapter(FakeResponse(text=json.dumps({
        "tool_name": "case_lookup", "arguments": {"reference": "CASE-1", "limit": 1},
    })))
    bad_payload = F3Input(permitted_tools=["case_lookup"], tool_schemas={}, context={})
    with pytest.raises(ProviderError) as invalid_request:
        mismatch.generate(LLMFunction.F3, bad_payload)
    assert invalid_request.value.code == ProviderErrorCode.OUTPUT_INVALID
    assert mismatch_client.models.calls == []
