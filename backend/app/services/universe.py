from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Candle, Instrument
from app.services.candles import sync_instrument_candles
from app.services.iss import iss_json, table_to_dicts

logger = logging.getLogger(__name__)


def imoex_tickers() -> list[str]:
    payload = iss_json(
        "/statistics/engines/stock/markets/index/analytics/IMOEX.json",
        {"iss.meta": "off", "limit": 100},
    )
    rows = table_to_dicts(payload.get("analytics"))
    tickers = {str(row.get("secids") or row.get("ticker") or "").upper().strip() for row in rows}
    return sorted(t for t in tickers if t)


def universe_instruments(db: Session, kinds: tuple[str, ...]) -> list[Instrument]:
    """Акции — только из состава IMOEX; фонды и металлы — все, отсев неликвидных и
    фондов денежного рынка делается в модели по данным на каждую дату."""
    instruments: list[Instrument] = []
    if "share" in kinds:
        instruments += (
            db.query(Instrument)
            .filter(Instrument.ticker.in_(imoex_tickers()), Instrument.kind == "share")
            .all()
        )
    other = [kind for kind in kinds if kind != "share"]
    if other:
        instruments += db.query(Instrument).filter(Instrument.kind.in_(other)).all()
    return sorted(instruments, key=lambda i: (i.kind, i.ticker))


def sync_universe_candles(db: Session, kinds: tuple[str, ...], days: int = 1500) -> dict:
    """Догружает дневные свечи по выбранным классам активов на `days` календарных дней назад."""
    start = date.today() - timedelta(days=days)
    instruments = universe_instruments(db, kinds)
    synced = 0
    failed: list[str] = []
    for instrument in instruments:
        try:
            earliest = (
                db.query(func.min(Candle.ts))
                .filter(Candle.instrument_id == instrument.id, Candle.timeframe == "D")
                .scalar()
            )
            deep_enough = earliest is not None and earliest.date() <= start + timedelta(days=10)
            count = sync_instrument_candles(db, instrument, start=None if deep_enough else start)
            synced += 1
            logger.info("%s: +%s candles", instrument.ticker, count)
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            failed.append(instrument.ticker)
            logger.warning("%s: candle sync failed: %s", instrument.ticker, exc)
    by_kind: dict[str, int] = {}
    for instrument in instruments:
        by_kind[instrument.kind] = by_kind.get(instrument.kind, 0) + 1
    return {
        "instruments": len(instruments),
        "by_kind": by_kind,
        "synced": synced,
        "failed": failed,
        "start": start.isoformat(),
    }


def load_candles(db: Session, instrument_ids: list[int]) -> dict[int, list[Candle]]:
    rows = (
        db.query(Candle)
        .filter(Candle.instrument_id.in_(instrument_ids), Candle.timeframe == "D")
        .order_by(Candle.instrument_id.asc(), Candle.ts.asc())
        .all()
    )
    grouped: dict[int, list[Candle]] = {}
    for row in rows:
        grouped.setdefault(row.instrument_id, []).append(row)
    return grouped
