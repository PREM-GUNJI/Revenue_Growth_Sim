# Defect log

Every defect that review or CI caught, honestly recorded: what it was, how it was caught, and what rule/hook/test was added to prevent recurrence. A log with zero entries by submission time is not credible (`docs/plan/CAPSTONE_COMPLIANCE.md` section 6.4) — do not let this stay empty.

| # | Phase | Defect | How caught | Prevention added |
|---|---|---|---|---|
| 1 | Frontend scaffold (post-Phase 0) | The `block_destructive_bash.py` hook's `rm -rf` regex captured everything to the end of the whole command string, not just the current shell segment. `cd frontend && rm -rf dist && cat /tmp/vite-dev.log` (a safe in-repo cleanup) was blocked because the unrelated `/tmp/vite-dev.log` later in the same line was swept into the "targets" list and flagged as outside the repo. | Hit live while starting the Vite dev server for a real verification check; confirmed by re-running the five hook pipe-tests, one of which regressed | Hook now splits the command on `&&`/`\|\|`/`;`/newline before matching `rm -rf`, so later unrelated segments can't be captured. Regression case added to the hook's standard test set (see commit). Known residual limitation: it's regex-based, not a real shell parser — quoting and subshells can still fool it either way; it is a safety net, not a security boundary. |
