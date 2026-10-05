# ADR-007: Hashing and canonical JSON for reproducibility

Status: accepted

Context: "Reproducibility of a scenario result" is a named success metric (`docs/plan/PLAN.md` section 16). Floating-point reductions differ across BLAS implementations and CPUs (confirmed as a Windows-dev-machine vs Linux-CI/container risk during planning), so naive float hashing would make the determinism tests flaky rather than meaningful.

Options considered:
- A. Hash the raw float outputs directly.
- B. Hash canonical JSON (sorted keys, compact separators, `allow_nan=False`) over **quantized integer** outputs (money in cents, percentages to 1e-4 pp, litres to 0.01), golden files generated inside the Linux container with `OPENBLAS_NUM_THREADS=1`.

Decision: B. `scenario_id` hashes the expanded, quantized levers; `result_hash` additionally covers engine/model/data/registry hashes, K and seed, status/reasons and the quantized outputs. The scenario's display `name` is excluded from both hashes.

Consequences: A value that sits exactly on a quantization boundary is a known residual risk (stated in `docs/HONESTY.md`). NumPy is pinned in `uv.lock` since `Generator` stream behaviour is not guaranteed stable across versions; a pin-version bump requires regenerating golden files deliberately, not silently.

Owner / date: B (engine owner) / 2026-10-05
