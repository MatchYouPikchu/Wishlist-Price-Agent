"""Persistence layer.

SQLite in v1; the public interface here is the stable part so a DynamoDB
implementation can slot in for v2 (WP-12). To keep that port honest:
signatures never expose SQL types or cursors, every lookup is keyed by
``item_id`` / ``(source, source_id)`` / ``alert_id``, and there are no joins.

Each row stores the full contract model as JSON (round-trip guaranteed by the
WP-1 tests) plus typed columns only for what we query on — storage never
re-models the domain. Money is stored as the exact ``Decimal`` string, never a
float; timestamps as ISO-8601 UTC text. Comparisons happen in Python after
rehydration.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from types import TracebackType

from agent.contracts import Alert, PriceObservation

_VALID_FEEDBACK = frozenset({"up", "down"})

_SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
  rowid_pk          INTEGER PRIMARY KEY AUTOINCREMENT,
  item_id           TEXT NOT NULL,
  listing_source    TEXT NOT NULL,
  listing_source_id TEXT NOT NULL,
  price             TEXT NOT NULL,
  currency          TEXT NOT NULL,
  available         INTEGER NOT NULL,
  observed_at       TEXT NOT NULL,
  payload           TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_obs_item
  ON observations(item_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_obs_listing
  ON observations(item_id, listing_source, listing_source_id, observed_at);

CREATE TABLE IF NOT EXISTS alerts (
  id         TEXT PRIMARY KEY,
  kind       TEXT NOT NULL,
  item_id    TEXT NOT NULL,
  created_at TEXT NOT NULL,
  sent_at    TEXT,
  payload    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alerts_item ON alerts(item_id, created_at);

CREATE TABLE IF NOT EXISTS feedback (
  rowid_pk   INTEGER PRIMARY KEY AUTOINCREMENT,
  alert_id   TEXT NOT NULL,
  verdict    TEXT NOT NULL CHECK (verdict IN ('up', 'down')),
  created_at TEXT NOT NULL
);
"""


class Storage:
    """SQLite persistence. The interface is the stable part (DynamoDB in v2)."""

    def __init__(self, path: str | Path) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Storage:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # --- observations ----------------------------------------------------- #

    def record_observation(self, obs: PriceObservation) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO observations (item_id, listing_source, listing_source_id, "
                "price, currency, available, observed_at, payload) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    obs.item_id,
                    obs.listing_source,
                    obs.listing_source_id,
                    str(obs.price),
                    obs.currency,
                    int(obs.available),
                    obs.observed_at.isoformat(),
                    obs.model_dump_json(),
                ),
            )

    def observations_for(self, item_id: str, *, limit: int | None = None) -> list[PriceObservation]:
        """Observations for an item, newest first."""
        sql = (
            "SELECT payload FROM observations WHERE item_id = ? "
            "ORDER BY observed_at DESC, rowid_pk DESC"
        )
        params: tuple[object, ...] = (item_id,)
        if limit is not None:
            sql += " LIMIT ?"
            params += (limit,)
        rows = self._conn.execute(sql, params).fetchall()
        return [PriceObservation.model_validate_json(r["payload"]) for r in rows]

    def latest_observation(
        self, item_id: str, source: str, source_id: str
    ) -> PriceObservation | None:
        """Newest observation for one listing, or None if never seen."""
        row = self._conn.execute(
            "SELECT payload FROM observations "
            "WHERE item_id = ? AND listing_source = ? AND listing_source_id = ? "
            "ORDER BY observed_at DESC, rowid_pk DESC LIMIT 1",
            (item_id, source, source_id),
        ).fetchone()
        return PriceObservation.model_validate_json(row["payload"]) if row else None

    # --- alerts ----------------------------------------------------------- #

    def record_alert(self, alert: Alert) -> bool:
        """Persist an alert. Returns False if one with this id already exists."""
        with self._conn:
            cur = self._conn.execute(
                "INSERT OR IGNORE INTO alerts (id, kind, item_id, created_at, sent_at, payload) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    alert.id,
                    str(alert.kind),
                    alert.item_id,
                    alert.created_at.isoformat(),
                    alert.sent_at.isoformat() if alert.sent_at else None,
                    alert.model_dump_json(),
                ),
            )
        return cur.rowcount == 1

    def alert_exists(self, alert_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM alerts WHERE id = ? LIMIT 1", (alert_id,)
        ).fetchone()
        return row is not None

    def alerts_for(self, item_id: str) -> list[Alert]:
        """Alerts for an item, newest first."""
        rows = self._conn.execute(
            "SELECT payload FROM alerts WHERE item_id = ? ORDER BY created_at DESC, id DESC",
            (item_id,),
        ).fetchall()
        return [Alert.model_validate_json(r["payload"]) for r in rows]

    def mark_alert_sent(self, alert_id: str, sent_at: datetime) -> None:
        """Stamp an alert as delivered. Raises KeyError if it does not exist."""
        row = self._conn.execute("SELECT payload FROM alerts WHERE id = ?", (alert_id,)).fetchone()
        if row is None:
            raise KeyError(alert_id)
        updated = Alert.model_validate_json(row["payload"]).model_copy(update={"sent_at": sent_at})
        with self._conn:
            self._conn.execute(
                "UPDATE alerts SET sent_at = ?, payload = ? WHERE id = ?",
                (sent_at.isoformat(), updated.model_dump_json(), alert_id),
            )

    # --- feedback (D4: primitives until WP-13 defines a contract) ---------- #

    def record_feedback(self, alert_id: str, verdict: str, created_at: datetime) -> None:
        if verdict not in _VALID_FEEDBACK:
            raise ValueError(f"verdict must be one of {sorted(_VALID_FEEDBACK)}, got {verdict!r}")
        with self._conn:
            self._conn.execute(
                "INSERT INTO feedback (alert_id, verdict, created_at) VALUES (?, ?, ?)",
                (alert_id, verdict, created_at.isoformat()),
            )
