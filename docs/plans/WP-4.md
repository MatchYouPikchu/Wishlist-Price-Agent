# WP-4 execution plan — URL watcher (dumb version), pulled ahead of WP-3

Session-ready plan. Reviewed by 🧑 before execution. Contracts are frozen and
sufficient — no contract changes.

## Why WP-4 before WP-3 (D1 — the reorder)

WP-3 (Allegro) is blocked on 🧑 credentials (developer.allegro.pl registration,
which can take days). WP-4 needs no credentials, no accounts, nothing external.
Both are independent implementations of the `Fetcher` protocol
(`fetchers/base.py`), so nothing downstream cares which lands first — WP-5 can
ship the walking skeleton on URL-watcher data alone, and Allegro slots in later
as an additive fetcher. PLAN.md §3 is annotated with the swap; this WP's
DECISIONS.md entry records it.

## Goal

`src/agent/fetchers/shop_url.py`: given a `WishlistItem` with `shop_urls`,
fetch each product page, extract the price with a **hand-written per-shop CSS
selector**, and return `RawListing`s. Failures are logged, never raised. The
self-healing LLM extractor is WP-11 — this version is deliberately dumb.

## Out of scope

- Allegro (WP-3, when creds arrive); pipeline wiring + cron (WP-5).
- Self-healing extraction, cooldowns (WP-11). JS-rendered/anti-bot shops —
  a shop that doesn't work with plain HTTP GET + CSS selector is documented
  as unsupported in v1, not fought.
- Search/discovery — this fetcher only watches exact URLs the user provides.

## Design decisions (pre-made; D2 needs explicit 🧑 approval)

- **D1 — reorder.** See above.
- **D2 — two new dependencies: `requests` + `beautifulsoup4`.** ⚠️ CLAUDE.md
  says no new dependencies without asking, so this is a 🧑 gate: fetching and
  parsing real-world HTML with stdlib alone is masochism. Both libraries are
  boring, ubiquitous, and agent-friendly. Rejected: `httpx`/`selectolax`
  (better perf we don't need at ~10 URLs/day); scrapy (a framework — banned).
  **Do not execute this WP until D2 is ratified.**
- **D3 — selector registry lives in `config.py`.** `SHOP_SELECTORS:
  dict[str, str]` mapping registrable domain → CSS selector for the price
  node. Data, no logic — fits config.py's charter. Unknown domain → logged
  skip, pointing at the registry (that's also WP-11's future hook).
- **D4 — `RawListing` mapping.** `source="shop_url"`; `source_id` = the URL
  (canonical enough for v1; it IS the identity of a watched page);
  `title` = page `<title>` text (trimmed); `condition=NEW` (shop pages sell
  new goods; used marketplaces are Tier 1's job); `shipping_price=None`
  (unknown); `available=False` when the page fetches but the price node is
  missing (likely delisted) — with the failure logged.
- **D5 — Polish price parsing is its own function.** `parse_price("1 099,00
  zł") -> (Decimal("1099.00"), "PLN")`. Handles: non-breaking/thin spaces,
  comma decimal separator, `zł`/`PLN` suffix, plain `1099` and `1099.00`
  forms. Unparseable → `None`, logged. This tiny function is where the bugs
  will live — test it hard.
- **D6 — tests run on committed HTML snapshots, live fetch is manual.** Real
  shops are flaky/bot-guarded from CI, so the test suite uses saved page
  snapshots under `tests/fixtures/shop_pages/` (trimmed to the relevant DOM,
  a few KB each — not full 2MB pages). The WP's "prices from 2–3 real shop
  pages land in storage" DoD is met by a one-shot manual run documented
  below. Bonus: these snapshots seed WP-11's extractor eval corpus.
- **D7 — politeness.** Honest descriptive User-Agent
  (`wishlist-price-agent/0.1 (+repo URL)`), 10s timeout, one GET per URL per
  run, no retries loops beyond a single second attempt. We are a personal
  price watcher, not a crawler.

## Deliverables

1. `src/agent/fetchers/shop_url.py`:

```python
class ShopUrlFetcher:
    """Tier-2 fetcher: watch exact product URLs with per-shop CSS selectors."""

    def __init__(self, selectors: Mapping[str, str] | None = None,
                 timeout: float = 10.0) -> None: ...
        # selectors defaults to config.SHOP_SELECTORS

    def fetch(self, item: WishlistItem) -> list[RawListing]: ...
        # one listing per item.shop_urls entry that yielded a price;
        # every failure (HTTP error, timeout, unknown domain, selector miss,
        # unparseable price) is logging.warning'd and skipped — NEVER raised

def parse_price(text: str) -> tuple[Decimal, str] | None: ...   # D5
def domain_of(url: str) -> str: ...                             # registry key
```

2. `config.py`: `SHOP_SELECTORS` with entries for the 2–3 real shops chosen
   at execution time (🧑 may pre-supply product URLs they actually want
   watched in `wishlist.yaml`; otherwise the executor picks 2–3 well-known
   server-rendered PL electronics shops and notes them in the session summary).
3. `pyproject.toml`: `requests`, `beautifulsoup4` (after D2 ratification).
4. Trimmed HTML snapshots in `tests/fixtures/shop_pages/`.
5. Manual DoD script (not CI): `uv run python -m agent.fetchers.shop_url
   --once` — fetches every `shop_urls` entry in `wishlist.yaml` live, prints
   the listings, and records observations into `Storage(config.DB_PATH)`.
   Paste its output into the PR description as DoD evidence.

## Tests (definition of done)

`tests/test_shop_url.py`:
- `parse_price`: `"1 099,00 zł"`, `"1099,00 zł"` (nbsp + thin-space variants),
  `"5 499 zł"`, `"549.00"`, `"PLN 549,00"`, garbage → `None`, empty → `None`.
- `domain_of` normalizes `www.` and ports.
- Selector extraction: each committed snapshot yields the expected
  `RawListing` with exact `Decimal` price, `source="shop_url"`,
  `source_id=url`, `condition=NEW`.
- Failure paths (mocked transport): HTTP 404, timeout, unknown domain,
  selector miss (→ `available=False` listing OR skip per D4), unparseable
  price — each returns without raising and logs a warning
  (`caplog` asserts).
- Integration: fetched listing → `PriceObservation` → `Storage` round-trip.
- Politeness: request carries the custom User-Agent and timeout (assert on
  the mocked call).

## Session checklist

1. Confirm D2 was ratified by 🧑 before adding dependencies.
2. `uv run pytest` + `uv run ruff check .` + `uv run ruff format --check .`
   green; run the manual `--once` script and capture output for the PR.
3. `DECISIONS.md`: WP-4 entry incl. the reorder (D1) and chosen shops.
4. `CLAUDE.md`/`AGENTS.md`: no layout change expected (shop_url.py already
   mapped); add a durable-facts line naming the supported shops.
5. Commit tagged `WP-4`; push; open PR; run plan-guardian; report verdict.
6. Do NOT touch `src/agent/contracts.py`.
