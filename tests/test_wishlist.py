"""WP-2: wishlist.yaml loads into contracts with human-friendly errors."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.wishlist import WishlistError, load_wishlist

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "wishlist.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_committed_wishlist_parses():
    """Guards the sample staying valid against the contract."""
    items = load_wishlist(REPO_ROOT / "wishlist.yaml")
    assert [i.id for i in items] == ["sony-wh1000xm5", "kindle-paperwhite-2024"]


def test_empty_items_is_valid(tmp_path):
    assert load_wishlist(_write(tmp_path, "items: []")) == []


def test_missing_file_raises(tmp_path):
    with pytest.raises(WishlistError, match="not found"):
        load_wishlist(tmp_path / "nope.yaml")


def test_missing_items_key_raises(tmp_path):
    with pytest.raises(WishlistError, match="items"):
        load_wishlist(_write(tmp_path, "something_else: 1"))


def test_duplicate_ids_named(tmp_path):
    text = """
items:
  - {id: dup, name: A, query: a, target_price: 10}
  - {id: dup, name: B, query: b, target_price: 20}
"""
    with pytest.raises(WishlistError, match="duplicate item ids: dup"):
        load_wishlist(_write(tmp_path, text))


def test_invalid_field_names_entry(tmp_path):
    text = """
items:
  - {id: bad-item, name: A, query: a, target_price: 0}
"""
    with pytest.raises(WishlistError, match="bad-item"):
        load_wishlist(_write(tmp_path, text))


def test_invalid_entry_without_id_uses_position(tmp_path):
    text = """
items:
  - {name: A, query: a, target_price: 5}
"""
    with pytest.raises(WishlistError, match="position 0"):
        load_wishlist(_write(tmp_path, text))
