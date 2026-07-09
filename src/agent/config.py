"""Configuration values — model names, thresholds, budgets. No behaviour here.

Keeping these as data (not code) means a person can tune the agent without a
code review of logic. Components import from here rather than hard-coding.
"""

from __future__ import annotations

from decimal import Decimal

# --- Models (v1.5+, wired in WP-7 onward) --------------------------------- #
# Placeholders until the LLM client lands; kept here so there is one place to
# change them. See PLAN.md WP-7..WP-11.
MATCHER_MODEL: str = "claude-haiku-4-5"
JUDGE_MODEL: str = "claude-sonnet-5"
RISK_MODEL: str = "claude-haiku-4-5"
EXTRACTOR_MODEL: str = "claude-sonnet-5"
COMPOSER_MODEL: str = "claude-haiku-4-5"

# --- Thresholds ------------------------------------------------------------ #
# Confidence cascade: matches at/above this from a cheap pass are trusted;
# below it, escalate to a stronger model. The real value is picked from the
# accuracy-vs-cost curve in WP-10 and logged in DECISIONS.md.
MATCHER_CASCADE_CONFIDENCE: float = 0.85

# Eval gates (enforced in CI once the harnesses exist).
MATCHER_MIN_PRECISION: float = 0.95
RISK_MIN_RECALL: float = 0.90

# --- Budgets --------------------------------------------------------------- #
# Hard ceiling per pipeline run; costs.py asserts against this.
MAX_RUN_COST_USD: Decimal = Decimal("0.50")

# --- Storage --------------------------------------------------------------- #
# SQLite location (v1). The DynamoDB port (WP-12) replaces the implementation,
# not this value. The `data/` dir is created on first open and gitignored until
# WP-5 decides how history is persisted across runs.
DB_PATH: str = "data/wishlist.db"

# --- Defaults -------------------------------------------------------------- #
DEFAULT_CURRENCY: str = "PLN"
