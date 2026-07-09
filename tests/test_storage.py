"""WP-2: SQLite storage round-trips, orders, and stays idempotent."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from agent.contracts import Alert, AlertKind, PriceObservation
from agent.storage import Storage

BASE = datetime(2026, 7, 9, 12, 0, 0, tzinfo=UTC)


def _obs(
    price: str, *, when: datetime = BASE, source_id: str = "1", available: bool = True
) -> PriceObservation:
    return PriceObservation(
        item_id="sony-wh1000xm5",
        listing_source="allegro",
        listing_source_id=source_id,
        price=Decimal(price),
        currency="PLN",
        available=available,
        observed_at=when,
    )


def _alert(
    alert_id: str = "a1", *, item_id: str = "sony-wh1000xm5", when: datetime = BASE
) -> Alert:
    return Alert(
        id=alert_id,
        kind=AlertKind.DEAL,
        item_id=item_id,
        title="Deal",
        body="body",
        created_at=when,
    )


@pytest.fixture
def store(tmp_path):
    with Storage(tmp_path / "test.db") as s:
        yield s


def test_schema_created_and_reopen_is_idempotent(tmp_path):
    path = tmp_path / "nested" / "wishlist.db"
    Storage(path).close()  # creates parent dir + schema
    assert path.exists()
    with Storage(path) as s:  # reopening the same file must not error
        assert s.observations_for("nope") == []


def test_observation_round_trip_preserves_decimal(store):
    obs = _obs("19.99")
    store.record_observation(obs)
    got = store.observations_for("sony-wh1000xm5")
    assert got == [obs]
    assert got[0].price == Decimal("19.99")


def test_observations_newest_first_and_limit(store):
    a = _obs("10.00", when=BASE, source_id="1")
    b = _obs("11.00", when=BASE + timedelta(hours=1), source_id="2")
    c = _obs("12.00", when=BASE + timedelta(hours=2), source_id="3")
    for o in (a, b, c):
        store.record_observation(o)
    assert [o.price for o in store.observations_for("sony-wh1000xm5")] == [
        Decimal("12.00"),
        Decimal("11.00"),
        Decimal("10.00"),
    ]
    assert [o.price for o in store.observations_for("sony-wh1000xm5", limit=2)] == [
        Decimal("12.00"),
        Decimal("11.00"),
    ]


def test_latest_observation_by_listing(store):
    store.record_observation(_obs("10.00", when=BASE, source_id="1"))
    store.record_observation(_obs("9.00", when=BASE + timedelta(hours=1), source_id="1"))
    store.record_observation(_obs("5.00", when=BASE, source_id="2"))
    latest = store.latest_observation("sony-wh1000xm5", "allegro", "1")
    assert latest is not None and latest.price == Decimal("9.00")
    assert store.latest_observation("sony-wh1000xm5", "allegro", "missing") is None


def test_alert_idempotency(store):
    alert = _alert("dup")
    assert store.record_alert(alert) is True
    assert store.record_alert(alert) is False  # same id -> ignored
    assert store.alert_exists("dup") is True
    assert store.alert_exists("other") is False
    assert len(store.alerts_for("sony-wh1000xm5")) == 1


def test_mark_alert_sent(store):
    store.record_alert(_alert("a1"))
    sent = BASE + timedelta(minutes=5)
    store.mark_alert_sent("a1", sent)
    assert store.alerts_for("sony-wh1000xm5")[0].sent_at == sent


def test_mark_alert_sent_missing_raises(store):
    with pytest.raises(KeyError):
        store.mark_alert_sent("ghost", BASE)


def test_feedback_records_and_validates(store):
    store.record_feedback("a1", "up", BASE)
    store.record_feedback("a1", "down", BASE)  # a second vote is allowed
    with pytest.raises(ValueError):
        store.record_feedback("a1", "sideways", BASE)
