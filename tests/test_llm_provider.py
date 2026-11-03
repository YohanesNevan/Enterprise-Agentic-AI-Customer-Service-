import ast
from pathlib import Path

import pytest
from pydantic import StrictInt, StrictStr

from app.contracts.vocabularies import IntentCode
from app.modules.llm_provider import (
    DeterministicStubProvider,
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
    fixture_key,
    generate_validated,
)


class FakeProvider:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def generate(self, function, payload, *, timeout_ms=None):
        self.calls.append((function, payload, timeout_ms))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class CaseLookupArgs(StrictModel):
    reference: StrictStr
    limit: StrictInt


def _f3_input(context=None):
    return F3Input(
        permitted_tools=["case_lookup"],
        tool_schemas={"case_lookup": CaseLookupArgs.model_json_schema()},
        context=context or {},
    )


def test_default_provider_is_fixture_stub_and_repeats_without_network():
    payload = F1Input(message="cek biaya", short_context="")
    fixture = {
        "intent_code": IntentCode.INFO_PRODUCT_POLICY.value,
        "confidence_hint": 0.9,
        "entities": {},
        "is_multi": False,
    }
    provider = build_provider(fixtures={fixture_key(LLMFunction.F1, payload): fixture})
    assert isinstance(provider, DeterministicStubProvider)
    first = generate_validated(provider, LLMFunction.F1, payload)
    second = generate_validated(provider, LLMFunction.F1, payload)
    assert first == second
    assert isinstance(first, F1Output)
    assert first.intent_code == IntentCode.INFO_PRODUCT_POLICY


def test_stub_without_matching_fixture_fails_closed():
    with pytest.raises(ProviderError) as exc:
        generate_validated(build_provider(), LLMFunction.F1,
                           F1Input(message="unmatched", short_context=""))
    assert exc.value.code == ProviderErrorCode.NO_FIXTURE


@pytest.mark.parametrize("timeout_ms", [0, -1, True, 1.5, "500"])
def test_timeout_argument_rejects_unbounded_or_wrong_type_values(timeout_ms):
    with pytest.raises(ProviderError) as exc:
        generate_validated(build_provider(), LLMFunction.F1,
                           F1Input(message="x"), timeout_ms=timeout_ms)
    assert exc.value.code == ProviderErrorCode.CONFIGURATION


def test_f1_rejects_intent_outside_vocabulary():
    with pytest.raises(ProviderError) as exc:
        generate_validated(FakeProvider({
            "intent_code": "NOT_AN_INTENT",
            "confidence_hint": 0.8,
            "entities": {},
            "is_multi": False,
        }), LLMFunction.F1, F1Input(message="x"))
    assert exc.value.code == ProviderErrorCode.OUTPUT_INVALID


def test_f1_rejects_nonfinite_or_out_of_range_confidence_hint():
    for hint in (float("nan"), 1.1, -0.1):
        with pytest.raises(ProviderError) as exc:
            generate_validated(FakeProvider({
                "intent_code": "INFO_PRODUCT_POLICY",
                "confidence_hint": hint,
                "entities": {},
                "is_multi": False,
            }), LLMFunction.F1, F1Input(message="x"))
        assert exc.value.code == ProviderErrorCode.OUTPUT_INVALID


def test_f2_accepts_three_options_and_rejects_four():
    valid = generate_validated(FakeProvider({
        "question": "Informasi yang Anda maksud?",
        "options": ["Biaya", "Syarat", "Waktu proses"],
    }), LLMFunction.F2, F2Input(candidate_intent=IntentCode.INFO_PRODUCT_POLICY))
    assert isinstance(valid, F2Output) and len(valid.options) == 3
    with pytest.raises(ProviderError) as exc:
        generate_validated(FakeProvider({
            "question": "Pilih satu",
            "options": ["A", "B", "C", "D"],
        }), LLMFunction.F2, F2Input(candidate_intent=IntentCode.INFO_PRODUCT_POLICY))
    assert exc.value.code == ProviderErrorCode.OUTPUT_INVALID


def test_f2_rejects_internal_intent_code_in_customer_text():
    with pytest.raises(ProviderError) as exc:
        generate_validated(FakeProvider({
            "question": "Pilih INFO_PRODUCT_POLICY",
            "options": ["Informasi produk"],
        }), LLMFunction.F2, F2Input(candidate_intent=IntentCode.INFO_PRODUCT_POLICY))
    assert exc.value.code == ProviderErrorCode.OUTPUT_INVALID


def test_f3_validates_allowlist_and_tool_argument_schema():
    payload = _f3_input({"reference": "T-123"})
    result = generate_validated(FakeProvider({
        "tool_name": "case_lookup",
        "arguments": {"reference": "T-123", "limit": 1},
    }), LLMFunction.F3, payload, tool_models={"case_lookup": CaseLookupArgs})
    assert isinstance(result, F3Output)
    assert result.arguments == {"reference": "T-123", "limit": 1}


def test_f3_rejects_tool_outside_policy_allowlist_without_execution():
    fake = FakeProvider({"tool_name": "transfer_funds", "arguments": {}})
    with pytest.raises(ProviderError) as exc:
        generate_validated(fake, LLMFunction.F3, _f3_input(),
                           tool_models={"case_lookup": CaseLookupArgs})
    assert exc.value.code == ProviderErrorCode.OUTPUT_INVALID
    assert len(fake.calls) == 1  # proposal only; this layer has no tool executor


def test_f3_rejects_arguments_that_do_not_match_allowed_tool_schema():
    with pytest.raises(ProviderError) as exc:
        generate_validated(FakeProvider({
            "tool_name": "case_lookup",
            "arguments": {"reference": "T-123", "limit": 1, "admin": True},
        }), LLMFunction.F3, _f3_input(),
            tool_models={"case_lookup": CaseLookupArgs})
    assert exc.value.code == ProviderErrorCode.OUTPUT_INVALID


def test_f3_rejects_schema_that_does_not_match_policy_schema():
    fake = FakeProvider({"tool_name": "case_lookup",
                         "arguments": {"reference": "T-123", "limit": 1}})
    payload = F3Input(permitted_tools=["case_lookup"],
                      tool_schemas={"case_lookup": {"type": "object"}}, context={})
    with pytest.raises(ProviderError) as exc:
        generate_validated(fake, LLMFunction.F3, payload,
                           tool_models={"case_lookup": CaseLookupArgs})
    assert exc.value.code == ProviderErrorCode.OUTPUT_INVALID


def _f4_input():
    return F4Input(sources=[F4Source(
        source_id="knowledge:article-1:version-1:body",
        source_type="KNOWLEDGE_CITATION",
        text="Biaya layanan sebesar Rp 25.000.",
    )])


def test_f4_accepts_claim_mapped_to_a_supplied_source():
    result = generate_validated(FakeProvider({
        "text": "Biaya layanan sebesar Rp 25.000.",
        "claim_map": [{
            "claim": "Biaya layanan sebesar Rp 25.000.",
            "source_ids": ["knowledge:article-1:version-1:body"],
        }],
    }), LLMFunction.F4, _f4_input())
    assert isinstance(result, F4Output)


@pytest.mark.parametrize("claim_map", [
    [{"claim": "Klaim tanpa sumber", "source_ids": []}],
    [{"claim": "Klaim dengan sumber palsu", "source_ids": ["fake-source"]}],
    [{"claim": "Teks yang tidak ada di jawaban", "source_ids": ["knowledge:article-1:version-1:body"]}],
    [],
])
def test_f4_rejects_claims_without_a_valid_source_and_answer_span(claim_map):
    with pytest.raises(ProviderError) as exc:
        generate_validated(FakeProvider({
            "text": "Jawaban yang memiliki klaim.",
            "claim_map": claim_map,
        }), LLMFunction.F4, _f4_input())
    assert exc.value.code == ProviderErrorCode.OUTPUT_INVALID


@pytest.mark.parametrize("response,code", [
    (None, ProviderErrorCode.EMPTY_RESPONSE),
    ("   ", ProviderErrorCode.EMPTY_RESPONSE),
    ("not-json", ProviderErrorCode.OUTPUT_INVALID),
    ({"wrong": "shape"}, ProviderErrorCode.OUTPUT_INVALID),
])
def test_empty_and_invalid_provider_outputs_are_controlled(response, code):
    with pytest.raises(ProviderError) as exc:
        generate_validated(FakeProvider(response), LLMFunction.F1,
                           F1Input(message="x"))
    assert exc.value.code == code


def test_invalid_response_and_provider_exception_do_not_leak_secrets_to_logs(caplog):
    message = "customer email alice.private@example.test bearer secret-canary"
    with pytest.raises(ProviderError):
        generate_validated(FakeProvider({"raw": message}), LLMFunction.F1,
                           F1Input(message=message))
    assert "alice.private@example.test" not in caplog.text
    assert "secret-canary" not in caplog.text


@pytest.mark.parametrize("exception,code", [
    (TimeoutError("sensitive upstream detail"), ProviderErrorCode.TIMEOUT),
    (RuntimeError("Authorization: secret-canary"), ProviderErrorCode.UNAVAILABLE),
])
def test_provider_failures_are_mapped_without_upstream_exception_text(exception, code):
    with pytest.raises(ProviderError) as exc:
        generate_validated(FakeProvider(exception), LLMFunction.F1,
                           F1Input(message="x"))
    assert exc.value.code == code
    assert "secret-canary" not in str(exc.value)
    assert exc.value.__cause__ is None


def test_rate_limit_is_a_safe_typed_provider_error():
    class RateLimitedProvider(FakeProvider):
        def generate(self, function, payload, *, timeout_ms=None):
            raise ProviderError(ProviderErrorCode.RATE_LIMITED)

    with pytest.raises(ProviderError) as exc:
        generate_validated(RateLimitedProvider(None), LLMFunction.F1,
                           F1Input(message="x"))
    assert exc.value.code == ProviderErrorCode.RATE_LIMITED


def test_default_factory_stays_stub_even_when_key_exists_and_orchestrator_calls_provider_at_runtime(monkeypatch):
    assert len(LLMFunction) == 4
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("LLM_API_KEY", "synthetic-test-key")
    assert isinstance(build_provider(), DeterministicStubProvider)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(ProviderError) as exc:
        build_provider("gemini")
    assert exc.value.code == ProviderErrorCode.CONFIGURATION
    source = Path("app/modules/orchestrator.py").read_text(encoding="utf-8")
    assert "generate_validated" in source
    assert "LLMFunction.F4" in source
    tree = ast.parse(source)
    budget = next(node.value.elts[1] for node in ast.walk(tree)
                  if isinstance(node, ast.Assign)
                  and any(isinstance(target, ast.Tuple)
                          and any(isinstance(name, ast.Name) and name.id == "BUDGET_LLM"
                                  for name in target.elts)
                          for target in node.targets))
    assert ast.literal_eval(budget) == 4
    assert not any(isinstance(node, ast.Call) and "generate" in ast.unparse(node.func).lower()
                   and "llm" in ast.unparse(node.func).lower() for node in ast.walk(tree))
