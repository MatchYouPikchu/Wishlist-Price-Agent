# How to drive this repo

The one-pager for the human. Every work package (WP) goes through the same
five-step loop; you type the prompts, the agent does the work, you make the
judgment calls. Rationale: `PLAN.md` §1 and §4.

```
 ①  PLAN          ②  YOU REVIEW      ③  EXECUTE         ④  GUARD           ⑤  YOU MERGE
 agent writes  →  the plan (5 min) →  agent implements → plan-guardian   →  read verdict,
 docs/plans/       veto decisions      tests, pushes      reviews the PR     merge on GitHub
 WP-N.md           D1, D2, ...         DECISIONS entry    ALIGNED/BLOCKED
```

One WP = one session (fresh context, fewer mistakes). Steps ① and ③ can be
different sessions — the plan file is the handoff.

## The prompts (copy-paste, replace N)

**① Plan** — new session:
> Write the execution plan for WP-N as `docs/plans/WP-N.md`, same format as
> WP-2's: goal, out-of-scope, pre-made design decisions (D1…), deliverables
> with signatures, full test list, session checklist. Don't implement. Push it.

**② You review the plan.** Read only the *Design decisions* section. Each D-item
is a pre-made call — veto by replying "change D2 to …". Silence = consent.

**③ Execute** — new session (start it in plan mode if the WP is large):
> Execute WP-N exactly as specified in `docs/plans/WP-N.md`. The plan is
> pre-reviewed — don't re-plan, implement it. Contracts are frozen; do not
> touch `src/agent/contracts.py`. Done = every test in the plan's test list
> passes plus the session checklist at the bottom.

**④ Guard + PR** — same session, after it claims done:
> Create a PR for WP-N, then run the plan-guardian subagent on the PR diff
> and give me its verdict verbatim.

**⑤ You merge.** Read the verdict: BLOCKING findings → send back ("fix the
blocking findings"); ADVISORY findings → they're your judgment calls, ratify
or reject in a reply; ALIGNED → skim the diff on GitHub, merge.

## Who does what

| You (🧑, never delegated)                    | Agent                          | Automatic                     |
| -------------------------------------------- | ------------------------------ | ----------------------------- |
| Veto/ratify design decisions & deviations     | Plans, implements, tests       | `uv sync` on session start    |
| Credentials (Allegro, SMTP, AWS)              | Drafts DECISIONS.md entries    | Challenge on contracts.py edit|
| Label golden datasets (WP-6)                  | Runs the plan-guardian         | CI: lint + tests on every PR  |
| Thresholds & budgets (WP-10)                  | Opens PRs                      | Permissions for uv/pytest/ruff|
| Merge PRs                                     |                                |                               |

## Rules of thumb

- **Never let a session edit `src/agent/contracts.py` casually.** A hook makes
  it ask for confirmation — that prompt appearing IS the review request.
- If a session proposes a new dependency, that's a decision, not a detail —
  it must ask first.
- After merging, start the next WP from a **fresh session** so it picks up the
  merged `main` (hooks, agents, and CLAUDE.md all load from the checked-out
  branch).
- Anything durable a session learns goes into `CLAUDE.md` (≤50 lines) at
  session end; anything decided goes into `DECISIONS.md`. If it's in neither,
  it didn't happen.

## Current state (update when merging)

- ✅ WP-0 scaffold · ✅ WP-1 contracts · ✅ WP-2 storage + loader (PR #1)
- ⏭️ Next: WP-3 Allegro fetcher — **blocked on 🧑: register at
  developer.allegro.pl (sandbox + prod keys)**
- 🧑 open items: ratify D3 (DB commit-back deferred to WP-5); field-by-field
  sign-off of `WishlistItem` vocabulary (WP-1 note in DECISIONS.md).
