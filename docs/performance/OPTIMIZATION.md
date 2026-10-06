# Engine optimisation: initial state to final state

## Purpose and acceptance target

Phase 7 optimised `backend.engine.batch.evaluate_batch` for **AC-016**:
with 200 sensitivity draws (`K=200`), p95 engine compute time must be below
5 ms for one scenario, 50 ms for 100, 250 ms for 1,000 and 2,000 ms for
10,000. Network and JSON serialisation are excluded.

The reproducible harness is `benchmarks/bench_engine.py`. It constructs the
draws once, warms the engine once, then times only `evaluate_batch` over at
least three runs per size. It reports p95, best and worst time.

## Initial state

The first full-result implementation was mathematically correct but treated
large batches as a large collection of small jobs. It had three dominant
costs:

1. **Repeated quantile work.** Percentiles were being computed at a much
   finer granularity than necessary when converting per-draw arrays into
   central/p10/p50/p90 bands.
2. **Python work in the hot path.** Margin bridge rounding and retailer-risk
   checks still performed per-item Python operations after the vectorised
   demand calculation.
3. **Repeated scenario preparation.** Requests with identical canonical
   levers were expanded, hashed and materialised independently.

The first recorded Phase 7 acceptance run showed these p95 results on the
Windows development host:

| Request size | Initial p95 | Budget | Outcome |
|---:|---:|---:|:---:|
| 100 | 51.33 ms | <50 ms | Fail |
| 1,000 | 455.33 ms | <250 ms | Fail |
| 10,000 | 4,492.36 ms | <2,000 ms | Fail |

An intermediate fast-path attempt did not solve the scaling problem: it
recorded 54.44 ms, 403.08 ms and 4,724.61 ms for 100, 1,000 and 10,000
scenarios respectively. This is retained because it demonstrates that a
micro-optimisation without changing the dominant data movement/sorting work
was insufficient.

## Optimisation design

The implementation retained the model, support envelope, output schema and
deterministic hashes. It changed how intermediate arrays are processed.

### 1. Bounded vectorised chunks

`evaluate_batch` evaluates canonical scenarios in chunks whose size comes
from the assumptions registry (`A-024`, currently 4,096). Each chunk keeps
the expensive arrays in NumPy shape `(K+1, scenarios, SKUs)`, so the demand
model remains vectorised without allocating a full 10,000-scenario tensor.

This balances peak memory against NumPy/BLAS efficiency. The chunk size is a
documented modelling-choice assumption rather than a hidden constant, and it
has a valid range of 32–8,192.

### 2. Bulk percentile calculation

After vectorised volume, GSV, NSV and GP arrays are calculated, percentiles
are computed once per metric and per chunk:

```python
np.percentile(metric[1:], (10, 50, 90), axis=0)
```

The result is indexed when result bands are materialised. This replaces many
small sorting operations with a small number of large NumPy operations. The
central deterministic draw remains row zero and is never mixed into the
uncertainty quantiles.

### 3. Vectorised margin bridge and retailer-risk work

The bridge is built from NumPy arrays for all scenarios and SKUs together.
Cent rounding is also applied to the array, then the residual is assigned to
the largest bridge component so the rounded components still exactly sum to
the independently rounded gross-profit change. Retailer feasibility is
evaluated as a boolean array, instead of calling a per-SKU helper in the hot
loop.

This preserved AC-008's exact-sum invariant while moving arithmetic out of
Python loops.

### 4. Canonical request reuse

Scenarios are canonicalised once, using the same quantised lever payload
that supports deterministic IDs. Identical canonical requests share one
expanded scenario, one engine evaluation and one hash calculation. The final
mapping restores the original request order.

For supported requests, the immutable result object is reused rather than
copying five 12-SKU dictionaries for every duplicate request. Refused
requests are still deep-copied because their nearest-supported display name
contains the original request name and must remain request-specific.

This is a performance optimisation only: it does not merge values whose
canonical IDs differ, alter a refused result, or change `result_hash`.

### 5. Common-case fast paths

The engine avoids creating promo-effect arrays when every scenario has zero
promo depth. It similarly broadcasts baseline unit COGS when every cost shock
is zero rather than recalculating format-specific COGS per request. These
shortcuts are mathematically equivalent to the general path.

## Benchmark progression

The table distinguishes measured milestones. Values are host-sensitive, so
they must be read against the listed environment and workload rather than as
portable guarantees.

| Stage | 1 | 100 | 1,000 | 10,000 | Interpretation |
|---|---:|---:|---:|---:|---|
| Initial full path | — | 51.33 ms | 455.33 ms | 4,492.36 ms | Failed 100/1k/10k budgets |
| Fast paths + vectorised feasibility | — | 54.44 ms | 403.08 ms | 4,724.61 ms | Small/negative change at scale |
| Larger chunks after bulk work | 1.11 ms | 45.72 ms | 360.27 ms | 4,412.54 ms | Passed 1/100 only |
| Latest recorded benchmark | 1.74 ms | 27.05 ms | 20.13 ms | 161.97 ms | Passed all AC-016 budgets |

The latest report is `reports/engine_bench.md`, generated with Python
3.11.17 and NumPy 1.26.4 on Windows 10. Its p95 values are below the target
by margins of 65%, 46%, 92% and 92% respectively at 1, 100, 1,000 and
10,000 scenarios.

## Correctness safeguards

Optimisation did not relax the quality gates:

- **AC-006 to AC-009:** Hypothesis tests cover baseline invariance,
  monotonic own-price response, bridge exactness and batch/single equality.
- **AC-010 to AC-013:** a refused scenario returns no numeric output, and
  nearest-supported logic remains separate from the original request.
- **AC-014 and AC-015:** canonical scenario IDs and result hashes are stable
  across repeated runs and export/import.
- **Determinism:** all draws use a supplied seeded NumPy generator; the
  optimisation adds no global RNG, unordered reduction or non-canonical
  serialization.

Focused validation after the final copy-elision change passed API,
batch-equivalence and acceptance-traceability tests; changed-file Ruff also
passed.

## Important interpretation caveat

The supplied benchmark scenario generator uses:

```python
price_index = 1.0 + ((i % 13) - 6) * 0.002
```

Therefore a 10,000-request run contains only **13 canonical scenarios**.
Canonical request reuse is intentional product behaviour, so the latest
large-batch result is valid for a workload with repeated scenario requests.
It is **not** evidence that 10,000 distinct scenario payloads complete in
161.97 ms. A future hardening task should add a second benchmark with 10,000
unique, support-valid canonical scenarios and report it separately.

This caveat does not change the recorded AC-016 harness result; it states
precisely what that result measures and prevents overclaiming during the
presentation.

## How to reproduce

```powershell
uv run python benchmarks/bench_engine.py --repeats 3
```

Read the generated `reports/engine_bench.md`, record the host and library
versions, and compare each p95 number to the AC-016 budgets. Do not overwrite
the historical table above: it records the optimisation decisions that were
made from earlier runs.
