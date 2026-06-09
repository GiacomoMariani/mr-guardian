"""Estimated USD cost for LLM calls.

A small, typed pricing table mapping ``provider -> model -> rates`` plus a pure
``estimate_cost_usd`` helper. Rates are expressed **per 1,000,000 tokens**, matching how
providers publish their price sheets. Costs are computed at review time and persisted, so a
stored row keeps the price that was in effect when the call ran.

This is reference data, not a policy rule, so it lives in Python rather than YAML (the
"YAML is the only runtime source of truth" rule governs executable rules).
"""

import logging
from dataclasses import dataclass

__all__ = ["ModelPricing", "GENERIC_FALLBACK", "PRICING", "estimate_cost_usd"]

logger = logging.getLogger(__name__)

# Cost amounts are rounded to this many decimal places. Six is enough to keep sub-cent
# per-review costs meaningful without storing float noise.
_COST_PRECISION = 6
_TOKENS_PER_MILLION = 1_000_000


@dataclass(frozen=True)
class ModelPricing:
    """USD rates for one model, per 1,000,000 tokens."""

    input_per_million: float
    output_per_million: float


# Public list-price estimates (USD per 1M tokens). Update as provider pricing changes; the
# stored cost is a snapshot, so revising these only affects reviews run afterward.
PRICING: dict[str, dict[str, ModelPricing]] = {
    "openai": {
        "gpt-4.1": ModelPricing(input_per_million=2.00, output_per_million=8.00),
        "gpt-4.1-mini": ModelPricing(input_per_million=0.40, output_per_million=1.60),
        "gpt-4.1-nano": ModelPricing(input_per_million=0.10, output_per_million=0.40),
        "gpt-4o": ModelPricing(input_per_million=2.50, output_per_million=10.00),
        "gpt-4o-mini": ModelPricing(input_per_million=0.15, output_per_million=0.60),
    },
}

# Applied when a provider/model is not in ``PRICING`` so a review still gets a cost estimate
# rather than nothing. Deliberately mid-range; the fallback is logged server-side (see
# ``_lookup_pricing``) but never flagged to any frontend.
GENERIC_FALLBACK = ModelPricing(input_per_million=1.00, output_per_million=3.00)


def estimate_cost_usd(
    *,
    provider: str,
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
) -> float | None:
    """Estimate the USD cost of one LLM call from its token usage.

    Returns ``None`` when both token counts are missing — there is no quantity to price, so
    a number would be invented rather than estimated (distinct from an unknown *rate*, which
    falls back to :data:`GENERIC_FALLBACK`). A single missing count is treated as ``0``.
    """
    if input_tokens is None and output_tokens is None:
        return None
    pricing = _lookup_pricing(provider=provider, model=model)
    billable_input = input_tokens or 0
    billable_output = output_tokens or 0
    cost = (
        billable_input / _TOKENS_PER_MILLION * pricing.input_per_million
        + billable_output / _TOKENS_PER_MILLION * pricing.output_per_million
    )
    return round(cost, _COST_PRECISION)


def _lookup_pricing(*, provider: str, model: str) -> ModelPricing:
    pricing = PRICING.get(provider.strip().lower(), {}).get(model.strip())
    if pricing is not None:
        return pricing
    # Not silent: record the fallback so unpriced models are visible in server logs/telemetry.
    # Never surface this to a frontend — a fallback cost reads as a normal cost there.
    logger.warning(
        "No LLM pricing for provider=%r model=%r; using generic fallback rate.",
        provider,
        model,
    )
    return GENERIC_FALLBACK
