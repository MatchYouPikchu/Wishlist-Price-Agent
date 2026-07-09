"""Fetcher protocol: ``fetch(item) -> list[RawListing]``.

Concrete fetchers (allegro, shop_url) implement this. Failures are logged and
swallowed — a broken fetcher must not crash the run (WP-3). Stub until WP-3.
"""

from __future__ import annotations

from typing import Protocol

from agent.contracts import RawListing, WishlistItem


class Fetcher(Protocol):
    """Anything that can turn a wishlist item into candidate listings."""

    def fetch(self, item: WishlistItem) -> list[RawListing]:
        """Return candidate listings for ``item``; never raise on remote errors."""
        ...
