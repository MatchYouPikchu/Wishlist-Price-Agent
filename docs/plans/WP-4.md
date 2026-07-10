# WP-4 execution plan — URL watcher (browser-based), pulled ahead of WP-3

Session-ready plan, **revision 2**. Reviewed by 🧑 before execution. Contracts
are frozen and sufficient — no contract changes.

Revision 2 replaces the plain-HTTP design after a live feasibility probe
(2026-07-09, from the dev container):

| Site            | Plain HTTP GET                  | Verdict for `requests` |
| --------------- | ------------------------------- | ---------------------- |
| ceneo.pl        | JS fingerprint challenge        | blocked                |
| x-kom.pl        | HTTP 403 + challenge            | blocked                |
| mediaexpert.pl  | HTTP 403 + challenge            | blocked                |
| morele.net      | HTTP 200, full page             | works                  |

Most Polish shops — and Ceneo — require a real browser. Chromium + Playwright
are pre-installed in the dev container and standard in GitHub Actions.

## Why WP-4 before WP-3 (D1 — the reorder)

Unchanged from revision 1: WP-3 is blocked on 🧑 Allegro credentials; WP-4
needs nothing external. Both implement the `Fetcher` protocol independently,
so WP-5 can ship the walking skeleton on URL-watcher data alone.

## Goal

`src/agent/fetchers/shop_url.py`: given a `WishlistItem` with `shop_urls`,
open each product page in headless Chromium, extract the price with a
**hand-written per-shop CSS selector**, and return `RawListing`s. Failures are
logged, never raised. Ceneo product pages are first-class citizens: one Ceneo
URL yields the *lowest price across shops* — the best market-context signal
this product can get before the LLM judge exists.

## Out of scope

- Allegro (WP-3, when creds arrive); pipeline wiring + cron (WP-5).
- Self-healing extraction, cooldowns (WP-11).
- Ceneo *search* (robots-disallowed; we only watch exact product URLs the
  user supplies) and Ceneo multi-offer parsing (one lowest-price listing per
  page in v1; a per-shop-offer `ceneo.py` fetcher is a possible later WP).
- Retry/anti-blocking arms races: if a page challenges even a real browser,
  log and skip. We do not fight.

## Design decisions (pre-made; D2 needs explicit 🧑 approval)

- **D1 — reorder WP-4 ahead of WP-3.** Logged in DECISIONS.md.
- **D2 — ⚠️ one new dependency: `playwright`.** 🧑 gate — do not execute
  until ratified. Headless Chromium fetches AND extracts (Playwright
  locators); no separate HTML-parser library. CI installs the browser with
  `playwright install chromium` (cacheable); the dev container has it
  pre-installed (launch via `executablePath` env already configured).
  *Rejected:* `requests`+`beautifulsoup4` (probe: 3 of 4 targets blocked);
  hybrid HTTP+browser (two code paths to maintain for ~10 URLs/day — the
  browser handles morele-class shops too); scrapy (framework — banned).
- **D3 — selector registry in `config.py`.** `SHOP_SELECTORS: dict[str, str]`
  mapping registrable domain → CSS selector for the price node. Ships with
  entries for `ceneo.pl`, `morele.net`, and 1–2 more chosen at execution
  time. Unknown domain → logged skip pointing at the registry.
- **D4 — `RawListing` mapping.** `source="shop_url"`; `source_id` = the URL;
  `title` = page `<title>` (trimmed); `condition=NEW`; `shipping_price=None`;
  price node present but empty/unparseable or missing → `available=False`
  listing with the failure logged. For Ceneo pages the extracted price is the
  page's lowest offer; `seller="ceneo:lowest"` marks that provenance.
- **D5 — Polish price parsing is its own function.** `parse_price("1 099,00
  zł") -> (Decimal("1099.00"), "PLN")`. Handles non-breaking/thin spaces,
  comma decimals, `zł`/`PLN` suffixes, bare numbers. Unparseable → `None`,
  logged. Test it hard — this is where the bugs live.
- **D6 — tests run on committed HTML snapshots via `file://`.** The fetcher
  accepts any URL, so tests point it at trimmed snapshot files under
  `tests/fixtures/shop_pages/` — the *same* code path as live pages, no
  mocking of the extraction logic. Live fetching is a manual DoD script, not
  CI. Snapshots seed WP-11's extractor eval corpus.
- **D7 — politeness.** One page-load per URL per run, 15s navigation timeout,
  no retries, no parallel hammering (sequential fetches), default Chromium
  UA (being a real browser is the mechanism, not a disguise). Volume: a
  handful of pages, once daily.
- **D8 — ToS posture (🧑 acknowledges at D2 ratification).** Ceneo robots.txt
  permits product pages and disallows search; we never search. Shop ToS
  generally frown on automated collection; at personal, low-volume,
  non-commercial use this is accepted by the owner. If a site blocks the
  browser, we skip it permanently rather than escalate.

## Deliverables

1. `src/agent/fetchers/shop_url.py`:

```python
class ShopUrlFetcher:
    """Tier-2 fetcher: watch exact product URLs in headless Chromium."""

    def __init__(self, selectors: Mapping[str, str] | None = None,
                 nav_timeout_ms: int = 15_000) -> None: ...
        # selectors defaults to config.SHOP_SELECTORS

    def fetch(self, item: WishlistItem) -> list[RawListing]: ...
        # one listing per shop_urls entry; every failure (nav error, timeout,
        # unknown domain, selector miss, unparseable price) is
        # logging.warning'd and handled per D4 — NEVER raised

def parse_price(text: str) -> tuple[Decimal, str] | None: ...   # D5
def domain_of(url: str) -> str: ...                             # registry key
```

   Browser lifecycle: one Playwright/Chromium instance per `fetch()` call
   (context-managed), pages opened sequentially. Honor
   `PLAYWRIGHT_BROWSERS_PATH`/pre-installed Chromium; never run
   `playwright install` at import or fetch time.

2. `config.py`: `SHOP_SELECTORS` (D3).
3. `pyproject.toml`: `playwright` (after D2 ratification). `ci.yml`: browser
   install step with cache for the test job.
4. Trimmed snapshots in `tests/fixtures/shop_pages/` (a few KB each — the
   relevant DOM around the price node, not 2MB dumps), including one Ceneo
   product page and one morele product page.
5. Manual DoD script: `uv run python -m agent.fetchers.shop_url --once` —
   live-fetches every `shop_urls` entry in `wishlist.yaml`, prints listings,
   records observations into `Storage(config.DB_PATH)`. Output pasted into
   the PR as DoD evidence ("prices from 2–3 real shop pages land in storage").

## Tests (definition of done)

`tests/test_shop_url.py`:
- `parse_price`: `"1 099,00 zł"` (nbsp + thin-space variants), `"1099,00 zł"`,
  `"5 499 zł"`, `"549.00"`, `"PLN 549,00"`, garbage → `None`, empty → `None`.
- `domain_of`: normalizes `www.`, ports, and maps subdomains to the
  registrable domain used by the registry.
- Snapshot extraction (real browser over `file://`): each committed snapshot
  yields the expected `RawListing` — exact `Decimal`, `source="shop_url"`,
  `source_id`=url, `condition=NEW`; Ceneo snapshot carries
  `seller="ceneo:lowest"`.
- Failure paths: nonexistent `file://` path (nav error), snapshot without the
  price node (→ `available=False` per D4), unknown domain (skip), unparseable
  price text — each returns without raising and logs (`caplog`).
- Integration: fetched listing → `PriceObservation` → `Storage` round-trip.

## Session checklist

1. Confirm D2 (and D8) were ratified by 🧑 before adding the dependency.
2. `uv run pytest` + `uv run ruff check .` + `uv run ruff format --check .`
   green; run the manual `--once` script; capture output for the PR.
3. `DECISIONS.md`: WP-4 entry incl. D1 reorder, probe table, chosen shops.
4. `CLAUDE.md`/`AGENTS.md`: durable-facts lines — supported shops and "URL
   watcher needs Chromium (Playwright); never `playwright install` in-session".
5. Commit tagged `WP-4`; push; open PR; run plan-guardian; report verdict.
6. Do NOT touch `src/agent/contracts.py`.
