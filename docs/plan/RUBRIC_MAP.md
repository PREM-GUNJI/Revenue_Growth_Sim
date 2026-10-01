# Rubric Map: where the points are and what to do about it

Weights: Functionality 25 | Engineering and delivery discipline 20 | Evaluation and evidence 20 | Subject matter understanding 15 (individual) | Relevance to C5i 10 | Presentation 10.

**Key observation:** Functionality, Engineering and Evaluation together are 65 points, and all three are decided by *evidence the panel can verify*, not by polish. Subject matter (15) is scored *individually under questioning*, so a team can be strong while one member loses points. Treat UI polish as the lowest-return work in the project.

---

## 1. Effort allocation (suggested share of total team effort)

| Criterion | Weight | Suggested effort | Why |
|---|---|---|---|
| Functionality | 25% | 25% | Clean-clone live demo is binary: it works or it doesn't. Reliability matters more than breadth |
| Engineering and delivery | 20% | 20% | Phase 0, agent record, security, deploy and rollback are all concrete deliverables |
| Evaluation and evidence | 20% | 20% | Baselines, CI gate, review log with real defects |
| Subject matter | 15% | 15% (as study time, not build time) | Each member needs depth and cross-knowledge. Schedule explicit drill sessions |
| Relevance to C5i | 10% | 5% | Mostly framing work, cheap to do well |
| Presentation | 10% | 10% | Deck, rehearsal, Q&A prep |
| UI polish beyond MVP | n/a | Only if time remains | Not a rubric line; it only matters via the demo |

---

## 2. Criterion by criterion

### Functionality (25%): "works end to end, runs live from a clean clone, does what the brief asked"

What the panel will check:
- Clean clone, two commands, running system. This is non-negotiable; rehearse it on a machine that has never seen the repo.
- The brief's own asks: price, pack and promo scenarios; volume and margin outcomes; assumptions stated in interface and code; comparison as the primary interaction **including losing scenarios**; explicit refusal outside the supported range; fast enough for live use; plus the agent layer.

Do:
- Make the **MVP golden path bulletproof**: goal to board with a loser, refusal card with nearest alternative, "just ballpark it" refused, grounded badge, live 1,000-scenario sweep with compute time visible.
- Keep a **replay mode** (recorded traces and fake LLM) so the demo survives an LLM outage or flaky network, plus a recorded fallback clip.
- Add a `make demo-check` that runs the exact demo script headlessly; run it in CI.

Avoid: demoing features that are not in the clean-clone build; relying on live LLM calls with no fallback.

### Engineering and delivery discipline (20%): "standards, context, spec, planning, how the agent was driven and what was allowed to merge, security, deployment, rollback"

Map to deliverables:
| Rubric phrase | Evidence |
|---|---|
| Standards, context, project setup | Lint/format/pre-commit, `CLAUDE.md` plus nested files, skills, hooks (Phase 0) |
| Specification and planning | BRD with ACs mapped to tests, DESIGN, ADRs, TASKS.md |
| How the agent was driven | Review log, tool comparison note, examples of parallel cloud-agent work |
| What was allowed to merge | Branch protection, CI gates, a PR that was **blocked** |
| Security | Scan output, triage, secrets in a manager, agent boundary doc |
| Deployment and rollback | Non-prod deploy, health checks, rollback evidence, runbook |

Do: show **one blocked change** (a hook rejecting a protected-path edit, and a CI gate rejecting a regression). Blocking evidence persuades more than a list of controls.

### Evaluation and evidence (20%): "measured results vs a stated baseline, a working CI evaluation gate, a review record showing defects were caught"

- Every headline number is `baseline -> system -> delta` (baselines defined in CAPSTONE_COMPLIANCE.md section 4).
- The gate must be *demonstrated blocking*: keep a branch `demo/regression` that drops a metric below threshold and shows a red CI.
- The review log needs **real defects with root cause and prevention** (rule, hook or test added). Seed this honestly as you go; do not fabricate at the end.
- Report weak numbers honestly (for example plan stability 80%). A credible 80% beats a suspicious 100%.

### Subject matter understanding (15%): "command of techniques, why this approach, alternatives, where the method breaks. Tested individually."

This is the criterion most teams under-prepare. Each member must be able to answer for their area **why, what else, and where it breaks**, and ideally give a one-minute overview of the other three areas. Question bank by owner:

**A (data, model, assumptions)**
- Why log-log constant elasticity? Alternatives (linear, AIDS/almost-ideal demand systems, ML)? Where does constant elasticity break (large price moves, near kink points, thresholds)?
- Why is synthetic data legitimate here, and what can it *not* tell you? (No confounding unless you built it in, so real-world endogeneity of price and promo timing is unaddressed.)
- What do your bands represent, and what do they miss? (Sensitivity to assumption ranges only, not statistical confidence or misspecification.)
- How did you back-test the engine against the synthetic data, and what would you do with real data? (This is where calibration would come in.)

**B (engine, guardrails, performance)**
- Why refuse rather than extrapolate? Why a joint-density check rather than per-lever ranges or a convex hull? What does k-NN density miss in high dimensions?
- How is the EDGE threshold chosen, and what does it cost in false refusals?
- Why is the result byte-identical? (Dtype, reduction order, canonical JSON, seed handling.) Where could non-determinism sneak in?
- How was the performance budget set and met? What dominates the profile?

**C (agent, grounding, evals)**
- Why a tool-calling agent rather than a fixed pipeline or pure LLM? Why three roles? Why function calling vs MCP?
- Why programmatic grounding rather than LLM-as-judge? What can the grounding check *not* catch? (Wrong reasoning with correct numbers, misleading framing.)
- How do you handle prompt injection, and how did you test it?
- What does your baseline show, and how was the oracle for optimality built?

**D (platform, security, UI, ops)**
- What is the agent's permission boundary at build time versus run time? What happens if the key leaks?
- What did the scanners find, and which findings did you risk-accept and why?
- Walk through the rollback. What would break it?
- What fails if the LLM API is down?

**Everyone:** "What would change with real client data?", "Show me something the agent got wrong," "What would you cut if you had half the time?"

Preparation: weekly 30-minute cross-questioning rounds, where each member grills another on their area. Record unanswered questions and close them.

### Relevance to C5i (10%): "how closely the build maps to work C5i actually delivers, and whether the business case holds up under challenge"

I don't have verified details on C5i's service lines, so **check their published case studies and offerings and cite them directly**; don't assume. Likely angles to test and tighten:
- **Domain framing:** pricing, pack and promotion decision support maps to revenue growth management in consumer goods. Confirm this matches C5i's real work and use their vocabulary.
- **Business case numbers:** quantify decision latency with *your own measured baseline* (timed manual trial vs simulator), not invented ROI. State the assumption chain explicitly.
- **Challenge answers prepared:** "Why would a client trust synthetic-trained logic?" (It doesn't; the value is the architecture: guardrails, refusal, grounding, auditability that carry over to real data.) "How do you plug into client data?" (Replace the generator and refit; envelope and registry regenerate automatically; show the path in the README and a slide.) "Who pays and who uses it?"
- Include a "path to a client engagement" slide: data requirements, validation steps, deployment model, risks. Use no C5i or client data of any kind, only public or synthetic.

### Presentation quality (10%): "pitch, deck, quality of answers under Q&A"

- Deck of about 8-10 slides; the live demo carries the story. Each slide has one message.
- Q&A: answers go to the owner of the area; "I don't know, here's how I'd find out" beats bluffing; keep answers under 45 seconds.
- Two timed dry runs, one with a hostile panel (another team or mentor).

---

## 3. Revised 15-minute allocation (supersedes section 13 of CAPSTONE_COMPLIANCE.md)

Weighted by the rubric, and designed so that every member speaks and every rubric line has a visible proof moment.

| Min | Segment | Presenter | Rubric lines served | Proof shown |
|---|---|---|---|---|
| 0-1.5 | Problem, business case, baseline time | D | Relevance, Presentation | Measured manual baseline vs target |
| 1.5-5 | Live demo from clean clone | C drives, B narrates refusal and speed | Functionality | Board with loser, refusal, ballpark refused, sweep with compute time |
| 5-7.5 | Engine, guardrails, why this approach | B | Functionality, Subject matter | Naive vs envelope refusal comparison; determinism hash |
| 7.5-9 | Data and assumptions, honest limits | A | Subject matter, Evaluation | Back-test and sensitivity ranking; assumptions drawer |
| 9-11.5 | Agent and evaluation | C | Evaluation, Subject matter | Table of baseline -> system -> delta; **CI gate blocking a regression** |
| 11.5-14 | How it was built: agent record, security, ops | D | Engineering | Hook blocking an edit, defect log example, scan triage, rollback |
| 14-15 | Honesty, relevance to C5i, close | A | Relevance, Subject matter | Limitations, refusals, path to real data |

Q&A (5 min): route each question to its owner; the other members add only when invited.

---

## 4. Self-scoring checklist (run weekly, and in full before submission)

Use these as pass/fail gates that mirror what a panel can verify:

**Functionality**
- [ ] A person who has never seen the repo runs the demo from a clean clone in under 10 minutes
- [ ] The demo script runs end to end without manual fixes (`make demo-check` green)
- [ ] Each of the brief's asks is visibly present in the UI or API

**Engineering and delivery**
- [ ] BRD ACs all map to tests; the traceability check is green
- [ ] Hooks, skills and CLAUDE.md files exist and have demonstrably blocked something
- [ ] Review log has an entry for every agent-generated PR; defect log has real entries
- [ ] Scans are clear or risk-accepted with owners; key is not in repo, logs, traces
- [ ] Rollback demonstrated and recorded; runbook exists and was followed by someone who did not write it

**Evaluation and evidence**
- [ ] Every headline metric shows baseline, system and delta, and the evaluation set is committed
- [ ] The CI gate has blocked a deliberate regression, and the evidence is saved
- [ ] Weak or imperfect results are reported honestly

**Subject matter**
- [ ] Each member passed a 10-question cross-examination on their area, and a 3-question one on each other area
- [ ] Each member can state two alternatives to their main technique and where it breaks

**Relevance**
- [ ] Business case uses measured numbers and states assumptions
- [ ] Mapped explicitly to C5i's published work; path-to-real-data slide ready

**Presentation**
- [ ] Two timed dry runs inside 15 minutes; Q&A drilled with a hostile reviewer

---

## 5. Repo evidence index (`docs/RUBRIC_EVIDENCE.md`)

Create one page listing, for each rubric line, the exact file or command that proves it, so the panel (and your own rehearsal) can find evidence in seconds. Example rows:

| Rubric line | Evidence | Command or path |
|---|---|---|
| Runs from clean clone | CI clean-clone job | `.github/workflows/clean_clone.yml`, `make demo` |
| Evaluation gate blocks | Red CI on regression branch | PR link, `eval_thresholds.yaml` |
| Defects caught | Review and defect logs | `docs/agent-record/DEFECTS.md` |
| Rollback | Recording and script | `docs/ops/ROLLBACK_EVIDENCE.md`, `make rollback` |
| Subject matter | Q&A bank per member | `docs/QA_PREP.md` |
