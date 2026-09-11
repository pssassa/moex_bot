from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Candle, Instrument
from app.services.iss import fetch_candles, parse_iss_datetime


def _last_stored(db: Session, instrument_id: int, timeframe: str) -> datetime | None:
    row = (
        db.query(Candle.ts)
        .filter(Candle.instrument_id == instrument_id, Candle.timeframe == timeframe)
        .order_by(Candle.ts.desc())
        .first()
    )
    return row[0] if row else None


def candles_are_fresh(last_ts: datetime | None) -> bool:
    if last_ts is None:
        return False
    now = datetime.now(timezone.utc)
    # выходные: допускаем паузу до 3.5 суток
    return (now - last_ts) <= timedelta(hours=84)


def _iss_location(instrument: Instrument) -> tuple[str, str, str]:
    kind = (instrument.kind or "share").lower()
    if kind == "metal":
        return "currency", "selt", instrument.board or "CETS"
    return "stock", "shares", instrument.board or "TQBR"


def sync_instrument_candles(db: Session, instrument: Instrument, timeframe: str = "D") -> int:
    last = _last_stored(db, instrument.id, timeframe)
    today = date.today()
    if last is not None:
        start = last.date() - timedelta(days=1)
    else:
        start = today - timedelta(days=settings.candle_history_days)
    interval = 24 if timeframe == "D" else 60
    engine, market, board = _iss_location(instrument)
    raw = fetch_candles(
        instrument.ticker,
        start,
        today,
        engine=engine,
        market=market,
        board=board,
        interval=interval,
    )
    if not raw:
        return 0

    payload = []
    for row in raw:
        ts = parse_iss_datetime(row.get("begin") or row.get("end"))
        if ts is None or row.get("close") is None:
            continue
        payload.append(
            {
                "instrument_id": instrument.id,
                "timeframe": timeframe,
                "ts": ts,
                "open": float(row.get("open") or row["close"]),
                "high": float(row.get("high") or row["close"]),
                "low": float(row.get("low") or row["close"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]) if row.get("volume") is not None else None,
                "value": float(row["value"]) if row.get("value") is not None else None,
            }
        )
    if not payload:
        return 0

    stmt = insert(Candle).values(payload)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_candles_inst_tf_ts",
        set_={
            "open": stmt.excluded.open,
            "high": stmt.excluded.high,
            "low": stmt.excluded.low,
            "close": stmt.excluded.close,
            "volume": stmt.excluded.volume,
            "value": stmt.excluded.value,
        },
    )
    db.execute(stmt)

    last_two = (
        db.query(Candle)
        .filter(Candle.instrument_id == instrument.id, Candle.timeframe == timeframe)
        .order_by(Candle.ts.desc())
        .limit(2)
        .all()
    )
    if last_two:
        instrument.last_close = last_two[0].close
        instrument.last_candle_at = last_two[0].ts
        if len(last_two) > 1 and last_two[1].close:
            instrument.last_change_pct = (last_two[0].close / last_two[1].close - 1) * 100
    db.commit()
    return len(payload)


def ensure_candles(db: Session, instrument: Instrument, timeframe: str = "D") -> list[Candle]:
    last = _last_stored(db, instrument.id, timeframe)
    if not candles_are_fresh(last):
        sync_instrument_candles(db, instrument, timeframe)
    return (
        db.query(Candle)
        .filter(Candle.instrument_id == instrument.id, Candle.timeframe == timeframe)
        .order_by(Candle.ts.asc())
        .all()
    )
