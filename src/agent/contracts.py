"""The frozen spine of the repository.

Every pydantic model that crosses a component boundary lives here and ONLY
here. These contracts are frozen: components are written against them, evals
assert on them, and storage serializes them. Propose changes in plan mode and
have them reviewed field-by-field — never silently edit.

Design conventions
------------------
* Models are immutable (``frozen=True``). Pipelines build new objects rather
  than mutating in place, which keeps the data flow easy to reason about.
* Money is a ``Decimal`` plus an explicit ISO-4217 ``currency`` string. Never a
  float — floats lose cents. Serialization is round-trip safe (Decimal <->
  string in JSON).
* Every model round-trips: ``M.model_validate_json(m.model_dump_json()) == m``.
  This is enforced by tests/test_contracts.py and is the definition of "the
  contract holds".
* Timestamps are timezone-aware UTC ``datetime`` objects.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

__all__ = [
    "Condition",
    "VerdictSource",
    "RiskLevel",
    "AlertKind",
    "WishlistItem",
    "RawListing",
    "MatchVerdict",
    "RiskVerdict",
    "DealVerdict",
    "PriceObservation",
    "Alert",
    "CostEntry",
    "RunReport",
]


# --------------------------------------------------------------------------- #
# Enumerations
# --------------------------------------------------------------------------- #


class Condition(StrEnum):
    """Acceptable / observed item condition."""

    NEW = "new"
    USED = "used"
    REFURBISHED = "refurbished"
    ANY = "any"


class VerdictSource(StrEnum):
    """How a verdict was produced — a hard rule or a model.

    The confidence cascade (see PLAN.md WP-10) uses this to record whether a
    match came from cheap deterministic logic or a paid LLM call.
    """

    RULE = "rule"
    LLM = "llm"


class RiskLevel(StrEnum):
    """Coarse risk bucket for a candidate deal."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AlertKind(StrEnum):
    """What an alert is telling the user about."""

    DEAL = "deal"
    PRICE_DROP = "price_drop"
    BACK_IN_STOCK = "back_in_stock"
    DIGEST = "digest"


# --------------------------------------------------------------------------- #
# Base
# --------------------------------------------------------------------------- #


class _Frozen(BaseModel):
    """Shared config: immutable, strict-ish, enum values on the wire."""

    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=False)


# --------------------------------------------------------------------------- #
# Inputs: the wishlist and what fetchers return
# --------------------------------------------------------------------------- #


class WishlistItem(_Frozen):
    """A single thing the user wants, parsed from ``wishlist.yaml``.

    Editing ``wishlist.yaml`` is the UI, so the fields here are the vocabulary
    a person uses to describe what they want and what would count as a match.
    """

    id: str = Field(description="Stable slug, unique within the wishlist, e.g. 'sony-wh1000xm5'.")
    name: str = Field(description="Human-readable name shown in alerts.")
    query: str = Field(description="Free-text search string handed to fetchers.")

    target_price: Decimal = Field(
        description="Price at or below which this is interesting. Same currency as `currency`.",
        gt=0,
    )
    currency: str = Field(default="PLN", description="ISO-4217 code, e.g. 'PLN', 'EUR'.")

    acceptable_conditions: list[Condition] = Field(
        default_factory=lambda: [Condition.NEW],
        description="Which conditions the user will accept.",
    )

    brand: str | None = Field(default=None, description="Manufacturer, if it disambiguates.")
    model: str | None = Field(default=None, description="Specific model/SKU, if known.")

    must_have: list[str] = Field(
        default_factory=list,
        description="Attributes a listing MUST have to match, e.g. ['128GB', 'wifi model'].",
    )
    deal_breakers: list[str] = Field(
        default_factory=list,
        description="Attributes that DISqualify a listing, e.g. ['for parts', 'cracked screen'].",
    )

    shop_urls: list[HttpUrl] = Field(
        default_factory=list,
        description="Tier-2 direct product URLs to watch, in addition to marketplace search.",
    )
    notes: str | None = Field(default=None, description="Freeform context for the matcher/judge.")


class RawListing(_Frozen):
    """One listing as returned by a fetcher, before any judgement is applied."""

    source: str = Field(description="Fetcher that produced this, e.g. 'allegro', 'shop_url'.")
    source_id: str = Field(description="Listing id within that source; unique per source.")
    url: HttpUrl = Field(description="Canonical link to the listing.")

    title: str = Field(description="Listing title as shown on the source.")
    price: Decimal = Field(description="Item price in `currency`.", ge=0)
    currency: str = Field(default="PLN", description="ISO-4217 code.")
    shipping_price: Decimal | None = Field(
        default=None, description="Shipping cost if known, else None.", ge=0
    )

    condition: Condition | None = Field(
        default=None, description="Condition if the source reports it."
    )
    seller: str | None = Field(default=None, description="Seller name/handle if available.")
    available: bool = Field(default=True, description="Whether the listing is purchasable now.")

    description: str | None = Field(default=None, description="Longer text, used by the matcher.")
    fetched_at: datetime = Field(description="When this snapshot was taken (UTC).")

    @property
    def total_price(self) -> Decimal:
        """Item price plus shipping (shipping treated as 0 when unknown)."""
        return self.price + (self.shipping_price or Decimal("0"))


# --------------------------------------------------------------------------- #
# Verdicts: outputs of the LLM (and rule) components
# --------------------------------------------------------------------------- #


class MatchVerdict(_Frozen):
    """Does this listing correspond to the wishlist item the user meant?"""

    item_id: str = Field(description="WishlistItem.id this verdict is about.")
    listing_source: str = Field(description="RawListing.source of the judged listing.")
    listing_source_id: str = Field(description="RawListing.source_id of the judged listing.")

    is_match: bool = Field(description="True if the listing is the wished-for item.")
    confidence: float = Field(description="0..1 confidence in `is_match`.", ge=0.0, le=1.0)
    reasoning: str = Field(description="Short justification, human-readable.")
    source: VerdictSource = Field(description="Whether a rule or an LLM produced this.")
    model: str | None = Field(default=None, description="Model id if source == LLM.")


class RiskVerdict(_Frozen):
    """Is this deal too good to be true / otherwise risky?"""

    item_id: str = Field(description="WishlistItem.id this verdict is about.")
    listing_source: str = Field(description="RawListing.source of the judged listing.")
    listing_source_id: str = Field(description="RawListing.source_id of the judged listing.")

    level: RiskLevel = Field(description="Coarse risk bucket.")
    flags: list[str] = Field(
        default_factory=list,
        description="Named concerns, e.g. ['price_too_low', 'new_seller', 'stock_photo'].",
    )
    reasoning: str = Field(description="Short justification, human-readable.")
    model: str | None = Field(default=None, description="Model id that produced this, if any.")


class DealVerdict(_Frozen):
    """The judge's call: is this a genuinely good deal worth alerting on?"""

    item_id: str = Field(description="WishlistItem.id this verdict is about.")
    listing_source: str = Field(description="RawListing.source of the judged listing.")
    listing_source_id: str = Field(description="RawListing.source_id of the judged listing.")

    is_deal: bool = Field(description="True if worth notifying the user about.")
    score: float = Field(description="0..1 desirability score.", ge=0.0, le=1.0)
    rationale: str = Field(description="Why this is (or isn't) a deal — shown in the alert.")

    observed_price: Decimal = Field(description="Total price the verdict was made against.", ge=0)
    target_price: Decimal = Field(description="The item's target price at judgement time.", gt=0)
    currency: str = Field(default="PLN", description="ISO-4217 code.")
    model: str | None = Field(default=None, description="Model id that produced this, if any.")


# --------------------------------------------------------------------------- #
# Persisted records and outputs
# --------------------------------------------------------------------------- #


class PriceObservation(_Frozen):
    """A single price data point, written to storage to build history."""

    item_id: str = Field(description="WishlistItem.id observed.")
    listing_source: str = Field(description="RawListing.source.")
    listing_source_id: str = Field(description="RawListing.source_id.")

    price: Decimal = Field(description="Total price observed (item + shipping).", ge=0)
    currency: str = Field(default="PLN", description="ISO-4217 code.")
    available: bool = Field(default=True, description="Whether the listing was purchasable.")
    observed_at: datetime = Field(description="Observation timestamp (UTC).")


class Alert(_Frozen):
    """A notification queued for (or already sent to) the user."""

    id: str = Field(description="Idempotency key, e.g. hash of item_id + listing + kind + day.")
    kind: AlertKind = Field(description="What the alert is about.")
    item_id: str = Field(description="WishlistItem.id this alert concerns.")

    title: str = Field(description="Email subject / notification headline.")
    body: str = Field(description="Rendered notification body.")
    url: HttpUrl | None = Field(default=None, description="Deep link to the listing, if any.")

    price: Decimal | None = Field(default=None, description="Price highlighted in the alert.", ge=0)
    currency: str = Field(default="PLN", description="ISO-4217 code.")

    created_at: datetime = Field(description="When the alert was generated (UTC).")
    sent_at: datetime | None = Field(default=None, description="Delivery time, or None if pending.")


class CostEntry(_Frozen):
    """One line in the per-run cost ledger (see costs.py / RunReport)."""

    component: str = Field(description="Which component spent, e.g. 'matcher', 'judge'.")
    model: str = Field(description="Model id charged.")
    calls: int = Field(default=1, description="Number of LLM calls aggregated here.", ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cost_usd: Decimal = Field(default=Decimal("0"), description="Dollar cost of these calls.", ge=0)


class RunReport(_Frozen):
    """Summary of a single pipeline run: what happened and what it cost."""

    run_id: str = Field(description="Unique id for this run.")
    started_at: datetime = Field(description="Run start (UTC).")
    finished_at: datetime | None = Field(
        default=None, description="Run end (UTC), None if running."
    )

    items_checked: int = Field(default=0, ge=0)
    listings_fetched: int = Field(default=0, ge=0)
    matches_found: int = Field(default=0, ge=0)
    alerts_sent: int = Field(default=0, ge=0)

    costs: list[CostEntry] = Field(default_factory=list, description="Per-component cost ledger.")
    errors: list[str] = Field(default_factory=list, description="Non-fatal errors during the run.")

    @property
    def total_cost_usd(self) -> Decimal:
        """Sum of every ledger entry — asserted against the budget in costs.py."""
        return sum((entry.cost_usd for entry in self.costs), start=Decimal("0"))
