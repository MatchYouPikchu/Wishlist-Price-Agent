"""WP-1 definition of done: every contract round-trips and is frozen.

If these pass, the spine holds: any component can serialize a model to JSON,
persist or transmit it, and reconstruct the exact same object.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import BaseModel, ValidationError

from agent import contracts
from agent.contracts import (
    Alert,
    AlertKind,
    Condition,
    CostEntry,
    DealVerdict,
    MatchVerdict,
    PriceObservation,
    RawListing,
    RiskLevel,
    RiskVerdict,
    RunReport,
    VerdictSource,
    WishlistItem,
)

UTC_NOW = datetime(2026, 7, 9, 12, 0, 0, tzinfo=UTC)


def _sample_instances() -> list[BaseModel]:
    """One fully-populated instance of every exported model."""
    return [
        WishlistItem(
            id="sony-wh1000xm5",
            name="Sony WH-1000XM5",
            query="Sony WH-1000XM5 headphones",
            target_price=Decimal("1100.00"),
            currency="PLN",
            acceptable_conditions=[Condition.NEW, Condition.REFURBISHED],
            brand="Sony",
            model="WH-1000XM5",
            must_have=["black", "boxed"],
            deal_breakers=["for parts", "no cushions"],
            shop_urls=["https://example.com/product/xm5"],
            notes="EU plug only.",
        ),
        RawListing(
            source="allegro",
            source_id="12345",
            url="https://allegro.pl/oferta/12345",
            title="Sony WH-1000XM5 Czarne",
            price=Decimal("1049.99"),
            currency="PLN",
            shipping_price=Decimal("14.99"),
            condition=Condition.NEW,
            seller="audio-store",
            available=True,
            description="Nowe, zapakowane.",
            fetched_at=UTC_NOW,
        ),
        MatchVerdict(
            item_id="sony-wh1000xm5",
            listing_source="allegro",
            listing_source_id="12345",
            is_match=True,
            confidence=0.97,
            reasoning="Title and model exactly match.",
            source=VerdictSource.LLM,
            model="claude-haiku-4-5",
        ),
        RiskVerdict(
            item_id="sony-wh1000xm5",
            listing_source="allegro",
            listing_source_id="12345",
            level=RiskLevel.LOW,
            flags=["established_seller"],
            reasoning="Price consistent with market; seller reputable.",
            model="claude-haiku-4-5",
        ),
        DealVerdict(
            item_id="sony-wh1000xm5",
            listing_source="allegro",
            listing_source_id="12345",
            is_deal=True,
            score=0.88,
            rationale="10% under target with free-ish shipping.",
            observed_price=Decimal("1064.98"),
            target_price=Decimal("1100.00"),
            currency="PLN",
            model="claude-sonnet-5",
        ),
        PriceObservation(
            item_id="sony-wh1000xm5",
            listing_source="allegro",
            listing_source_id="12345",
            price=Decimal("1064.98"),
            currency="PLN",
            available=True,
            observed_at=UTC_NOW,
        ),
        Alert(
            id="sony-wh1000xm5:allegro:12345:deal:2026-07-09",
            kind=AlertKind.DEAL,
            item_id="sony-wh1000xm5",
            title="Deal: Sony WH-1000XM5 at 1064.98 PLN",
            body="Below your 1100 target.",
            url="https://allegro.pl/oferta/12345",
            price=Decimal("1064.98"),
            currency="PLN",
            created_at=UTC_NOW,
            sent_at=None,
        ),
        CostEntry(
            component="matcher",
            model="claude-haiku-4-5",
            calls=3,
            input_tokens=1200,
            output_tokens=180,
            cost_usd=Decimal("0.0021"),
        ),
        RunReport(
            run_id="run-2026-07-09",
            started_at=UTC_NOW,
            finished_at=UTC_NOW,
            items_checked=5,
            listings_fetched=42,
            matches_found=7,
            alerts_sent=2,
            costs=[
                CostEntry(component="match", model="claude-haiku-4-5", cost_usd=Decimal("0.0021")),
                CostEntry(component="judge", model="claude-sonnet-5", cost_usd=Decimal("0.0130")),
            ],
            errors=["allegro: transient 503 on page 2"],
        ),
    ]


def test_every_exported_model_has_a_sample():
    """Guard against adding a model to __all__ without covering it here."""
    covered = {type(instance).__name__ for instance in _sample_instances()}
    exported = {
        name
        for name in contracts.__all__
        if isinstance(getattr(contracts, name), type)
        and issubclass(getattr(contracts, name), BaseModel)
    }
    assert exported <= covered, f"uncovered contract models: {exported - covered}"


@pytest.mark.parametrize("instance", _sample_instances(), ids=lambda m: type(m).__name__)
def test_json_round_trip(instance: BaseModel):
    """model_validate_json(model_dump_json(x)) == x for every contract."""
    rebuilt = type(instance).model_validate_json(instance.model_dump_json())
    assert rebuilt == instance


@pytest.mark.parametrize("instance", _sample_instances(), ids=lambda m: type(m).__name__)
def test_python_round_trip(instance: BaseModel):
    """model_validate(model_dump(x)) == x for every contract."""
    rebuilt = type(instance).model_validate(instance.model_dump())
    assert rebuilt == instance


@pytest.mark.parametrize("instance", _sample_instances(), ids=lambda m: type(m).__name__)
def test_models_are_frozen(instance: BaseModel):
    """Contracts are immutable — mutation must raise."""
    field = next(iter(type(instance).model_fields))
    with pytest.raises(ValidationError):
        setattr(instance, field, getattr(instance, field))


def test_extra_fields_forbidden():
    """extra='forbid' catches typos and drifted payloads."""
    with pytest.raises(ValidationError):
        WishlistItem(
            id="x",
            name="x",
            query="x",
            target_price=Decimal("1"),
            typo_field="oops",
        )


def test_money_precision_preserved():
    """Decimal cents survive a JSON round trip (the reason we don't use float)."""
    listing = RawListing(
        source="s",
        source_id="1",
        url="https://example.com",
        title="t",
        price=Decimal("19.99"),
        shipping_price=Decimal("0.01"),
        fetched_at=UTC_NOW,
    )
    rebuilt = RawListing.model_validate_json(listing.model_dump_json())
    assert rebuilt.price == Decimal("19.99")
    assert rebuilt.total_price == Decimal("20.00")


def test_run_report_total_cost():
    """RunReport.total_cost_usd sums the ledger exactly."""
    report = RunReport(
        run_id="r",
        started_at=UTC_NOW,
        costs=[
            CostEntry(component="a", model="m", cost_usd=Decimal("0.10")),
            CostEntry(component="b", model="m", cost_usd=Decimal("0.05")),
        ],
    )
    assert report.total_cost_usd == Decimal("0.15")


def test_bounds_enforced():
    """Field constraints (confidence 0..1, positive target price) are live."""
    with pytest.raises(ValidationError):
        MatchVerdict(
            item_id="i",
            listing_source="s",
            listing_source_id="1",
            is_match=True,
            confidence=1.5,
            reasoning="r",
            source=VerdictSource.RULE,
        )
    with pytest.raises(ValidationError):
        WishlistItem(id="i", name="n", query="q", target_price=Decimal("0"))
