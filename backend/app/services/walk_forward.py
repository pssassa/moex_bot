from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import BacktestForecast, Candle, Instrument, MacroSnapshot, NewsItem
from app.services.forecast import build_prompt, normalize_outlook
from app.services.llm import LlmError, complete_analyst
from app.services.technicals import trader_brief

logger = logging.getLogger(__name__)

# запас баров до "as of" даты, чтобы SMA50/ATR14/структура считались по
# достаточной истории, а не по обрезку в 10-20 свечей
MIN_HISTORY_BARS = 60


def _as_utc(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def _candles_for(db: Session, instrument_id: int) -> list[Candle]:
    return (
        db.query(Candle)
        .filter(Candle.instrument_id == instrument_id, Candle.timeframe == "D")
        .order_by(Candle.ts.asc())
        .all()
    )


def _news_macro_floor(db: Session) -> datetime | None:
    """Самая ранняя дата, на которую у нас реально есть И новости, И макро —
    раньше неё симуляция была бы прогнозом без контекста, который эта модель
    не должна давать."""
    news_floor = db.query(func.min(NewsItem.published_at)).scalar()
    macro_floor = db.query(func.min(MacroSnapshot.ts)).scalar()
    if news_floor is None or macro_floor is None:
        return None
    return max(_as_utc(news_floor), _as_utc(macro_floor))


def eligible_as_of_dates(candles: list[Candle], horizon: int, floor_date: datetime) -> list[datetime]:
    """Свечи, для которых уже известен исход через `horizon` сессий, достаточно
    истории до них для индикаторов, и дата не раньше floor_date."""
    dates: list[datetime] = []
    for idx in range(MIN_HISTORY_BARS, len(candles) - horizon):
        ts = _as_utc(candles[idx].ts)
        if ts < floor_date:
            continue
        dates.append(ts)
    return dates


def simulate_instrument_date(
    db: Session,
    instrument: Instrument,
    as_of: datetime,
    candles_all: list[Candle],
    horizon: int = 5,
) -> BacktestForecast | None:
    as_of = _as_utc(as_of)
    existing = (
        db.query(BacktestForecast)
        .filter(BacktestForecast.instrument_id == instrument.id, BacktestForecast.as_of == as_of)
        .one_or_none()
    )
    if existing:
        return existing

    idx = None
    for i, candle in enumerate(candles_all):
        if _as_utc(candle.ts) <= as_of:
            idx = i
        else:
            break
    if idx is None or idx < MIN_HISTORY_BARS or idx + horizon >= len(candles_all):
        return None

    candles = candles_all[: idx + 1]
    tech = trader_brief(candles, horizon)
    if not tech:
        return None

    cutoff = as_of - timedelta(days=settings.news_max_age_days)
    company_news = (
        db.query(NewsItem)
        .join(NewsItem.instruments)
        .filter(
            Instrument.id == instrument.id,
            NewsItem.published_at >= cutoff,
            NewsItem.published_at <= as_of,
        )
        .order_by(NewsItem.published_at.desc())
        .limit(12)
        .all()
    )
    world_news = (
        db.query(NewsItem)
        .filter(
            NewsItem.is_world.is_(True),
            NewsItem.published_at >= cutoff,
            NewsItem.published_at <= as_of,
        )
        .order_by(NewsItem.published_at.desc())
        .limit(8)
        .all()
    )
    macro = (
        db.query(MacroSnapshot)
        .filter(MacroSnapshot.ts <= as_of)
        .order_by(MacroSnapshot.ts.desc())
        .first()
    )

    prompt = build_prompt(instrument, tech, company_news + world_news, macro)
    parsed, _raw = complete_analyst(prompt)
    outlook = normalize_outlook(parsed, tech)

    row = BacktestForecast(
        instrument_id=instrument.id,
        as_of=as_of,
        horizon_days=outlook["horizon_days"],
        direction=outlook["direction"],
        confidence=parsed.get("confidence"),
        expected_change_pct=outlook["expected_change_pct"],
        range_low_pct=outlook["range_low_pct"],
        range_high_pct=outlook["range_high_pct"],
        spot_price=tech.get("last_close"),
        path_json=json.dumps(outlook["path"], ensure_ascii=False),
        thesis=parsed.get("thesis"),
        news_vs_chart=parsed.get("news_vs_chart"),
        model=f"{settings.hf_model}-backtest",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def run_walk_forward(
    db: Session,
    tickers: list[str] | None = None,
    horizon: int = 5,
    limit: int | None = 200,
    sleep_seconds: float = 1.0,
) -> dict:
    floor_date = _news_macro_floor(db)
    if floor_date is None:
        return {
            "created": 0,
            "skipped_existing": 0,
            "failed": 0,
            "llm_calls": 0,
            "note": "Нет ни одной новости или макро-снимка в базе — симулировать нечего.",
        }

    query = db.query(Instrument)
    if tickers:
        query = query.filter(Instrument.ticker.in_([t.upper() for t in tickers]))
    else:
        synced_ids = db.query(Candle.instrument_id).filter(Candle.timeframe == "D").distinct()
        query = query.filter(Instrument.id.in_(synced_ids))
    instruments = query.all()

    created = 0
    skipped_existing = 0
    failed = 0
    calls = 0
    truncated = False

    for instrument in instruments:
        candles_all = _candles_for(db, instrument.id)
        if len(candles_all) < MIN_HISTORY_BARS + horizon + 1:
            continue
        for as_of in eligible_as_of_dates(candles_all, horizon, floor_date):
            if limit is not None and calls >= limit:
                truncated = True
                break
            already = (
                db.query(BacktestForecast.id)
                .filter(BacktestForecast.instrument_id == instrument.id, BacktestForecast.as_of == as_of)
                .first()
            )
            if already:
                skipped_existing += 1
                continue
            calls += 1
            try:
                row = simulate_instrument_date(db, instrument, as_of, candles_all, horizon)
                if row is not None:
                    created += 1
                    logger.info("Simulated %s @ %s -> %s", instrument.ticker, as_of.date(), row.direction)
            except LlmError as exc:
                failed += 1
                logger.warning("Simulation failed for %s @ %s: %s", instrument.ticker, as_of.date(), exc)
            except Exception:
                failed += 1
                logger.exception("Simulation crashed for %s @ %s", instrument.ticker, as_of.date())
            time.sleep(sleep_seconds)
        if truncated:
            break

    return {
        "created": created,
        "skipped_existing": skipped_existing,
        "failed": failed,
        "llm_calls": calls,
        "floor_date": floor_date.isoformat(),
        "truncated_by_limit": truncated,
    }
