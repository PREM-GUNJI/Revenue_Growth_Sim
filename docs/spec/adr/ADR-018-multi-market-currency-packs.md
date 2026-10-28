# ADR-018: Multi-market currency packs (INR / USD / EUR)

## Status
Accepted

## Context
ADR-016 fixed the money scale as INR so the engine, research layer and UI agreed. The product now needs to support other markets without inventing live FX conversions or mixing currencies inside one case. Elasticities and absolute prices also differ by market in real CPG work, so display-only conversion of one India dataset would be dishonest.

## Decision
- Each **market pack** (YAML under `backend/markets/packs/`) defines a currency, money assumption overlays (costs and shelf prices), optional demand overlays, and generator volume/list-price seeds.
- Shipping packs: `in` (India, INR — base registry), `us` (USD), `eu` (EUR). Adding a market is a pack file plus `python -m backend.markets.generate_all`, not an engine rewrite.
- A **case locks `market_id` at create**; it cannot be patched later. Evaluation, situation, export and the agent resolve that market and install it via a contextvar overlay on `registry.get`.
- Synthetic history is stored per market under `data/markets/{id}/`. Root `data/` remains the India pack for older tooling.
- UI formats money with the case currency. Copy states the data is synthetic for that market, not live FX.

## Consequences
- Absolute gross-profit figures differ by market; percentage moves and refusal logic stay coverage-driven.
- India (`in`) keeps empty overlays so base assumption values are unchanged; regenerating data may still bump the data hash when the generator version advances.
- Amends ADR-016: INR remains the India market's currency, not the only currency in the product.
