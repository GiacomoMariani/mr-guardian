import logging

import pytest

from mr_guardian.core.llm_pricing import GENERIC_FALLBACK, estimate_cost_usd


def test_estimates_cost_for_known_model() -> None:
    # gpt-4.1-mini: $0.40 / 1M input, $1.60 / 1M output.
    cost = estimate_cost_usd(
        provider="openai",
        model="gpt-4.1-mini",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )
    assert cost == pytest.approx(2.0)


def test_rounds_small_costs_to_six_places() -> None:
    cost = estimate_cost_usd(
        provider="openai",
        model="gpt-4.1-mini",
        input_tokens=1200,
        output_tokens=80,
    )
    # 1200/1e6 * 0.40 + 80/1e6 * 1.60 = 0.000608
    assert cost == pytest.approx(0.000608)


def test_provider_lookup_is_case_and_whitespace_insensitive() -> None:
    cost = estimate_cost_usd(
        provider="OpenAI",
        model=" gpt-4.1-mini",
        input_tokens=1_000_000,
        output_tokens=0,
    )
    assert cost == pytest.approx(0.40)


def test_unknown_model_uses_generic_fallback_and_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        cost = estimate_cost_usd(
            provider="openai",
            model="some-unlisted-model",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )
    expected = GENERIC_FALLBACK.input_per_million + GENERIC_FALLBACK.output_per_million
    assert cost == pytest.approx(expected)
    assert any("generic fallback" in message for message in caplog.messages)


def test_unknown_provider_uses_generic_fallback() -> None:
    cost = estimate_cost_usd(
        provider="anthropic",
        model="claude-x",
        input_tokens=0,
        output_tokens=1_000_000,
    )
    assert cost == pytest.approx(GENERIC_FALLBACK.output_per_million)


def test_returns_none_when_both_token_counts_missing() -> None:
    assert (
        estimate_cost_usd(
            provider="openai",
            model="gpt-4.1-mini",
            input_tokens=None,
            output_tokens=None,
        )
        is None
    )


def test_treats_single_missing_count_as_zero() -> None:
    cost = estimate_cost_usd(
        provider="openai",
        model="gpt-4.1-mini",
        input_tokens=1_000_000,
        output_tokens=None,
    )
    assert cost == pytest.approx(0.40)


def test_missing_tokens_does_not_warn_for_unknown_model(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Both counts missing -> None is returned BEFORE any pricing lookup, so a skipped or
    # disabled call never emits a fallback warning.
    with caplog.at_level(logging.WARNING):
        result = estimate_cost_usd(
            provider="disabled",
            model="none",
            input_tokens=None,
            output_tokens=None,
        )
    assert result is None
    assert caplog.messages == []
