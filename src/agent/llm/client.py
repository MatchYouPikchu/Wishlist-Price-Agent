"""LiteLLM wrapper: JSON-schema outputs, retries, per-call cost capture.

Every LLM component calls through here so cost accounting and retry policy live
in one place. Stub until WP-7.
"""

from __future__ import annotations
