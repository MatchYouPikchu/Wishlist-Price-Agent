# evals/

The eval harnesses are the test suite for the LLM components. This directory
mirrors the component list one-to-one and is populated eval-first, starting at
WP-6 (golden datasets) — before the prompts they grade exist.

Planned shape (see PLAN.md):

```
datasets/
  matcher.jsonl          # 🧑 hand-labeled (WP-6)
  judge_scenarios.jsonl  # 🧑 (WP-6)
  risk.jsonl             # 🧑 (WP-6)
  extractor_pages/       # saved HTML snapshots (WP-11)
run_matcher.py           # prints P/R, exits non-zero below threshold (WP-8)
run_judge.py             # (WP-9)
run_risk.py              # (WP-10)
run_extractor.py         # (WP-11)
cascade_curve.py         # accuracy-vs-cost chart for the README (WP-10)
```

Nothing here is implemented yet — WP-0/WP-1 only reserve the shape.
