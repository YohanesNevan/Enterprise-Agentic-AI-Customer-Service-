"""Single-request Gemini smoke test; excluded unless explicitly opted in."""
from __future__ import annotations

import os

import pytest

from app.modules.llm_provider import (
    F1Output,
    LLMFunction,
    ProviderError,
    generate_validated,
    build_provider,
)


pytestmark = pytest.mark.skipif(
    os.getenv("EAICS_RUN_GEMINI_LIVE") != "1",
    reason="set EAICS_RUN_GEMINI_LIVE=1 to permit one real Gemini F1 request",
)


def test_gemini_f1_live_smoke_once():
    """Send one synthetic F1 request and expose only safe validation status."""
    try:
        provider = build_provider("gemini")
        result = generate_validated(
            provider,
            LLMFunction.F1,
            {"message": "Saya ingin mengetahui jam operasional layanan."},
        )
    except ProviderError as exc:
        pytest.fail(f"Gemini F1 smoke failed: {exc.code.value}", pytrace=False)

    if not isinstance(result, F1Output):
        pytest.fail("Gemini F1 smoke failed: OUTPUT_INVALID", pytrace=False)
