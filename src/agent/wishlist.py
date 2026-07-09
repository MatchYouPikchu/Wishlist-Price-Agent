"""Load and validate ``wishlist.yaml`` into ``WishlistItem`` objects.

Editing ``wishlist.yaml`` is the UI, and it is edited by hand, so validation
errors must say *which entry* is wrong — never a bare pydantic traceback.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import yaml
from pydantic import ValidationError

from agent.contracts import WishlistItem


class WishlistError(Exception):
    """Raised when wishlist.yaml is missing, malformed, or inconsistent."""


def load_wishlist(path: str | Path) -> list[WishlistItem]:
    """Parse ``path`` into a list of validated wishlist items.

    Raises ``WishlistError`` (never a raw ``ValidationError`` / ``YAMLError``)
    with a message that names the offending file or entry.
    """
    p = Path(path)
    try:
        raw = p.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise WishlistError(f"wishlist file not found: {p}") from exc
    except OSError as exc:
        raise WishlistError(f"could not read wishlist file {p}: {exc}") from exc

    try:
        doc = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise WishlistError(f"{p} is not valid YAML: {exc}") from exc

    if doc is None or "items" not in doc:
        raise WishlistError(f"{p} must have a top-level 'items:' list")

    entries = doc["items"]
    if not isinstance(entries, list):
        raise WishlistError(f"{p}: 'items' must be a list, got {type(entries).__name__}")

    items: list[WishlistItem] = []
    for index, entry in enumerate(entries):
        try:
            items.append(WishlistItem.model_validate(entry))
        except ValidationError as exc:
            label = _entry_label(entry, index)
            raise WishlistError(f"{p}: invalid wishlist item {label}:\n{exc}") from exc

    _reject_duplicate_ids(items, p)
    return items


def _entry_label(entry: object, index: int) -> str:
    """Name an entry by its id if present, else by position."""
    if isinstance(entry, dict) and isinstance(entry.get("id"), str):
        return f"'{entry['id']}'"
    return f"at position {index}"


def _reject_duplicate_ids(items: list[WishlistItem], path: Path) -> None:
    counts = Counter(item.id for item in items)
    duplicates = sorted(item_id for item_id, n in counts.items() if n > 1)
    if duplicates:
        raise WishlistError(f"{path}: duplicate item ids: {', '.join(duplicates)}")
