"""Per-model token rates and the cost of one agent run.

Rates are USD per 1,000,000 tokens, Standard tier, copied from the provider's pricing page on
`FETCHED_ON`. They are data, not logic: change `RATES` and bump `RATE_VERSION` when the provider
changes prices, and older `ai_usage` rows keep the version they were priced with. A model that
has no entry is stored with cost NULL ("rate not set"), never a guessed figure.
"""

from __future__ import annotations

from dataclasses import dataclass

SOURCE_URL = "https://developers.openai.com/api/docs/pricing"
FETCHED_ON = "2026-10-07"
RATE_VERSION = "openai-standard-2026-10-07"
TOKENS_PER_RATE_UNIT = 1_000_000


@dataclass(frozen=True)
class Rate:
    input: float
    cached_input: float
    output: float


RATES: dict[str, Rate] = {
    # Listed for contexts up to 272K input tokens; every agent call here is far below that.
    "gpt-5.5": Rate(input=5.00, cached_input=0.50, output=30.00),
    # No context-length restriction listed for this model on the same page.
    "gpt-5.1": Rate(input=1.25, cached_input=0.125, output=10.00),
}


def cost_usd(model: str, input_tokens: int, cached_input_tokens: int, output_tokens: int) -> float | None:
    """Cost of one run, or None when the model has no rate.

    `input_tokens` is the provider's total input count, which already includes the cached part,
    so only the uncached remainder is charged at the full input rate.
    """
    rate = RATES.get(model.strip())
    if rate is None:
        return None
    cached = min(max(cached_input_tokens, 0), max(input_tokens, 0))
    uncached = max(input_tokens, 0) - cached
    total = uncached * rate.input + cached * rate.cached_input + max(output_tokens, 0) * rate.output
    return round(total / TOKENS_PER_RATE_UNIT, 6)


def rate_table() -> dict[str, object]:
    """What the audit page shows next to the figures, so a reviewer can check them."""
    return {"version": RATE_VERSION, "source": SOURCE_URL, "fetched_on": FETCHED_ON, "unit": "USD per 1M tokens",
            "models": {name: {"input": r.input, "cached_input": r.cached_input, "output": r.output} for name, r in RATES.items()}}
