# Wishlist Price Agent — Design

**Status:** v0.2 (stub) · **Companion:** [`PLAN.md`](PLAN.md)

> ⚠️ **Placeholder.** `PLAN.md` and `CLAUDE.md` reference this document as the
> home of the *what and why*. The canonical v0.2 design content is authored and
> owned by the human (it predates the code and is a PM artifact). This file
> exists so cross-references resolve and so the section headers the plan points
> at have a landing spot — fill each section in rather than treating the stub as
> final.

## 1. Problem & principle
_What the agent is for: alert on genuinely good deals, not threshold crossings._

## 2. Architecture
_fetch → match → risk → judge → notify. See the module map in PLAN.md §2._

## 3. Fetching (tiers)
_Tier 1 official APIs (Allegro); Tier 2 URL watcher with self-healing extractor._

## 4. Matching & the confidence cascade
_Cheap pass first, escalate below a confidence threshold (see config.py)._

## 5. Judging a deal
_Judge produces a DealVerdict with a rationale; replaces the threshold rule._

## 6. Risk
_Too-good-to-be-true / seller-risk assessment before alerting._

## 7. Cost & budgets
_Per-component ledger, hard per-run ceiling (config.MAX_RUN_COST_USD)._

## 8. Evaluation datasets
_Golden sets for matcher, judge, and risk (referenced by PLAN.md WP-6):_
- _Matcher: ~100 hand-labeled listing/item pairs, precision-oriented._
- _Judge: scenario set of unambiguous good/bad deals._
- _Risk: cases spanning the risk flags, recall-oriented._

## 9. Deliberately not built
_Scope boundaries kept out of v1/v1.5._
