# Wishlist Price Agent — Implementation Plan

How this gets built with a coding agent (Claude Code / Codex CLI): repo
structure, working method, and the ordered work packages. Companion to
`DESIGN.md` (the what and why); this is the how and when.

**Status:** Draft v0.1 · **Companion:** DESIGN.md v0.2

## 1. Working method with a coding agent

Principles that shape every work package below:

1. **Contracts first, components second.** The pydantic models are written and
   frozen before any component that uses them. Every later session can then be
   verified against a stable interface.
2. **The evals are the test suite.** For LLM components, the golden dataset is
   written before the prompt (eval-driven development). The agent's definition
   of done is "eval passes," not "code looks right."
3. **One work package = one session.** Each WP has a goal, explicit
   out-of-scope list, and a runnable definition of done. Start sessions in plan
   mode: have the agent propose its approach, review it, then let it execute.
4. **Walking skeleton before intelligence.** v1 ships with zero LLM calls.
   Boring code first; the brain is added to a system that already runs daily in
   CI.
5. **Human-only tasks are marked 🧑.** Labeling data, API credentials, budget
   thresholds, and judgment calls do not get delegated.
6. **Every WP ends with a `DECISIONS.md` entry.** One paragraph: what was
   decided, what was rejected, why. The agent drafts it; the human edits it.

### Agent instruction files

- `CLAUDE.md` (≈50 lines, stable): what the project is, layout map, commands
  (`uv run pytest`, `uv run python -m evals.matcher`), conventions (pydantic
  contracts in `contracts.py` are frozen — propose changes, never silently
  edit; structured JSON outputs only; no orchestration frameworks; no new
  dependencies without asking). Points to `DESIGN.md` for rationale — it does
  not duplicate it.
- `AGENTS.md`: same content, so Codex CLI and other tools read the identical
  brief. Keep one canonical file and symlink/copy the other.
- Anything long-lived learned during a session ("Allegro sandbox returns X")
  gets written back into `CLAUDE.md` or `docs/notes/` at session end.

## 2. Repository structure

```
wishlist-agent/
├── CLAUDE.md                  # agent brief (≤50 lines, stable)
├── AGENTS.md                  # same brief for non-Claude tools
├── DESIGN.md                  # the design doc (v0.2)
├── PLAN.md                    # this file
├── DECISIONS.md               # running decision log
├── README.md                  # product-framed: written last, updated often
├── wishlist.yaml              # the wishlist — editing this file is the UI
├── pyproject.toml             # uv-managed
├── .github/workflows/
│   ├── run.yml                # daily cron: pipeline run
│   ├── ci.yml                 # tests + evals on every PR
│   └── normalize.yml          # v2: LLM normalizer on wishlist.yaml change
├── src/agent/
│   ├── contracts.py           # ALL pydantic models — the spine of the repo
│   ├── config.py              # model names, thresholds, budgets (no code)
│   ├── pipeline.py            # orchestration: fetch → match → risk → judge → notify
│   ├── fetchers/
│   │   ├── base.py            # fetch(item_spec) -> list[RawListing]
│   │   ├── allegro.py         # Tier 1: official REST API
│   │   └── shop_url.py        # Tier 2: URL watcher + self-healing extractor
│   ├── llm/
│   │   ├── client.py          # LiteLLM wrapper: JSON mode, retries, cost capture
│   │   ├── matcher.py         # + confidence cascade
│   │   ├── risk.py
│   │   ├── judge.py
│   │   ├── composer.py
│   │   ├── extractor.py       # price + CSS selector from HTML
│   │   └── prompts/           # one .md file per prompt, versioned in git
│   ├── storage.py             # SQLite (v1); interface stable for DynamoDB (v2)
│   ├── notify/email.py        # SMTP (v1) → SES (v2)
│   └── costs.py               # per-component cost ledger + budget assertion
├── evals/
│   ├── datasets/
│   │   ├── matcher.jsonl      # 🧑 hand-labeled
│   │   ├── judge_scenarios.jsonl
│   │   ├── risk.jsonl
│   │   └── extractor_pages/   # saved HTML snapshots
│   ├── run_matcher.py         # prints P/R, exits non-zero below threshold
│   ├── run_judge.py
│   ├── run_risk.py
│   ├── run_extractor.py
│   └── cascade_curve.py       # accuracy-vs-cost chart for the README
├── tests/                     # plain unit tests for the boring code
└── infra/                     # v2: AWS SAM templates (empty until WP-10)
```

**Why this shape:** `contracts.py` as a single file makes the frozen spine
impossible to miss; `prompts/` as versioned markdown makes every prompt change
reviewable in a diff and re-runnable against evals; `evals/` mirrors the
component list one-to-one.

## 3. Work packages, in order

### Phase v1 — walking skeleton (no LLM)

- **WP-0 · Scaffold** — repo init, `uv`, pyproject, ruff/pytest, empty module
  tree, CI workflow running a placeholder test. **Done:** `ci.yml` green.
- **WP-1 · Contracts ⭐** the highest-leverage session — all pydantic models:
  `WishlistItem`, `RawListing`, `MatchVerdict`, `RiskVerdict`, `DealVerdict`,
  `PriceObservation`, `Alert`, `RunReport`. Agent proposes in plan mode; 🧑
  review field-by-field — this is the PM artifact of the repo. **Done:** models
  + round-trip serialization tests; marked frozen in `CLAUDE.md`.
- **WP-2 · Storage + wishlist loader** — SQLite schema (observations, alerts,
  feedback), `wishlist.yaml` parsing into `WishlistItem`. **Done:** unit tests;
  DB file committed back by CI dry-run.
- **WP-3 · Allegro fetcher** — 🧑 register at developer.allegro.pl first
  (sandbox + prod keys). Agent builds OAuth flow + search → `RawListing`.
  **Done:** live sandbox call returns parsed listings; failures logged, not
  raised. *(Reordered after WP-4 — blocked on credentials; see DECISIONS.md.)*
- **WP-4 · URL watcher (dumb version)** — fetch configured product URLs,
  extract price via hand-written per-shop selectors (self-healing comes later).
  **Done:** prices from 2–3 real shop pages land in storage. *(Pulled ahead of
  WP-3: needs no credentials; both implement the same `Fetcher` protocol, so
  v1 can go live Allegro-free and Allegro lands later as additive.)*
- **WP-5 · Threshold notifier + daily run** — hard rule `price <= target`, SMTP
  email, `run.yml` cron wired end-to-end. **Done:** a real email arrives from a
  scheduled CI run. v1 is live; price history starts accumulating.

### Phase v1.5 — add the brain, eval-first

- **WP-6 · 🧑 Golden datasets** — human-only session: run fetchers broadly, dump
  ~100 listings, hand-label matcher cases; write judge scenarios and risk cases
  per DESIGN.md §8. The agent can build the labeling helper (CLI that shows a
  listing and records the label), not the labels.
- **WP-7 · LLM client + cost ledger** — LiteLLM wrapper: JSON-schema outputs,
  retries, per-call cost capture into `RunReport`. **Done:** fake-model unit
  tests; budget assertion fires in a test.
- **WP-8 · Matcher + eval harness** — first real eval-driven session: agent
  iterates the prompt against `matcher.jsonl` until P ≥ 95%. Eval wired into CI
  as a gate. **Done:** CI fails if a prompt edit drops precision.
- **WP-9 · Judge** — same method against scenario set; verdict + rationale
  contract from WP-1. **Done:** 100% on unambiguous scenarios; live pipeline
  switches from threshold rule to judge behind a config flag (instant
  rollback).
- **WP-10 · Risk assessor + cascade** — risk eval (recall ≥ 90%); confidence
  cascade on the matcher; `cascade_curve.py` produces the accuracy-vs-cost
  chart. 🧑 pick the threshold from the curve — a genuine PM decision, logged in
  `DECISIONS.md`. **Done:** chart in README.
- **WP-11 · Self-healing extractor + polish** — LLM fallback when a selector
  breaks (eval: 10 saved HTML snapshots); cooldown policy; weekly digest via
  composer. **Done:** v1.5 feature-complete, running daily.

### Phase v2 — productize on AWS

- **WP-12 · SAM skeleton** — 🧑 AWS account/budget alarm first. Lambda +
  EventBridge + DynamoDB + SES defined in `infra/`; storage interface from WP-2
  gets its DynamoDB implementation. **Done:** `sam deploy` runs the same
  pipeline in the cloud; GH Actions cron retired (or kept as fallback).
- **WP-13 · Feedback loop** — 👍/👎 links in alert emails → API Gateway + Lambda
  → DynamoDB; weekly precision metric in the digest. **Done:** a tap on a real
  email records a row.
- **WP-14 · PR wizard** — `normalize.yml`: on `wishlist.yaml` change, the
  normalizer LLM comments the structured spec card on the PR; merge = confirm,
  sync to DynamoDB. **Done:** fuzzy entry → PR comment → merged spec, captured
  as a GIF for the README.
- **WP-15 · README as product page** — written by 🧑 with agent assistance, not
  the reverse: principle, architecture, cascade chart, live precision number,
  "deliberately not built," link to DECISIONS.md.

## 4. Session hygiene checklist

Before each session: pick one WP; confirm contracts unchanged; start in plan
mode. During: agent runs tests/evals itself before claiming done. After: review
the diff like a PR (especially prompts and contracts); DECISIONS.md entry;
update CLAUDE.md if the agent learned a durable fact; commit with the WP number
in the message.

Rough calendar effort: WP-0…5 ≈ a week of evenings; WP-6 is one honest 🧑
afternoon; WP-7…11 ≈ 2–3 weeks; v2 ≈ 2 weekends. The dataset labeling (WP-6) is
the only task that cannot be compressed — budget it honestly.
