"""Per-component cost ledger and budget assertion.

Aggregates ``CostEntry`` records into a ``RunReport`` and asserts the run stays
under ``config.MAX_RUN_COST_USD``. Stub until WP-7.
"""

from __future__ import annotations
