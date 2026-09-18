from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import BacktestForecast, Candle, Forecast, Instrument

# порог направления совпадает с normalize_outlook: |change| <= 0.45% считается sideways
SIDEWAYS_BAND_PCT = 0.45


@dataclass
class BacktestRow:
    forecast_id: int
    source: str  # "live" | "simulated"
    ticker: str
    created_at: datetime
    horizon_days: int
    direction: str
    confidence: float | None
    expected_change_pct: float | None
    range_low_pct: float | None
    range_high_pct: float | None
    spot_price: float
    actual_close: float
    actual_change_pct: float
    actual_direction: str
    direction_correct: bool
    within_range: bool
    abs_error_pct: float | None
    baseline_direction: str
    baseline_correct: bool


def _direction_from_change(change_pct: float) -> str:
    if change_pct > SIDEWAYS_BAND_PCT:
        return "up"
    if change_pct < -SIDEWAYS_BAND_PCT:
        return "down"
    return "sideways"


def _as_utc(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def _candles_for(db: Session, instrument_id: int) -> list[Candle]:
    return (
        db.query(Candle)
        .filter(Candle.instrument_id == instrument_id, Candle.timeframe == "D")
        .order_by(Candle.ts.asc())
        .all()
    )


def _evaluate(
    *,
    row_id: int,
    source: str,
    ticker: str,
    created: datetime,
    horizon_days: int | None,
    direction: str,
    confidence: float | None,
    expected_change_pct: float | None,
    range_low_pct: float | None,
    range_high_pct: float | None,
    spot_price: float | None,
    candles: list[Candle],
) -> BacktestRow | None:
    """Сверяет один прогноз с фактической ценой. None, если горизонт ещё не наступил
    или не хватает данных (свечи ещё не подтянуты/устарели)."""
    if not candles or spot_price is None or not horizon_days:
        return None

    created = _as_utc(created)

    as_of_idx: int | None = None
    for i, candle in enumerate(candles):
        if _as_utc(candle.ts) <= created:
            as_of_idx = i
        else:
            break
    if as_of_idx is None:
        return None

    target_idx = as_of_idx + horizon_days
    if target_idx >= len(candles):
        return None

    baseline_direction = "sideways"
    baseline_idx = as_of_idx - 5
    if baseline_idx >= 0 and candles[baseline_idx].close:
        past_change = (candles[as_of_idx].close / candles[baseline_idx].close - 1) * 100
        baseline_direction = _direction_from_change(past_change)

    actual_close = candles[target_idx].close
    actual_change_pct = (actual_close / spot_price - 1) * 100
    actual_direction = _direction_from_change(actual_change_pct)

    within_range = (
        range_low_pct is not None
        and range_high_pct is not None
        and range_low_pct <= actual_change_pct <= range_high_pct
    )
    abs_error_pct = (
        round(abs(actual_change_pct - expected_change_pct), 3) if expected_change_pct is not None else None
    )

    return BacktestRow(
        forecast_id=row_id,
        source=source,
        ticker=ticker,
        created_at=created,
        horizon_days=horizon_days,
        direction=direction,
        confidence=confidence,
        expected_change_pct=expected_change_pct,
        range_low_pct=range_low_pct,
        range_high_pct=range_high_pct,
        spot_price=spot_price,
        actual_close=round(actual_close, 4),
        actual_change_pct=round(actual_change_pct, 3),
        actual_direction=actual_direction,
        direction_correct=direction == actual_direction,
        within_range=within_range,
        abs_error_pct=abs_error_pct,
        baseline_direction=baseline_direction,
        baseline_correct=baseline_direction == actual_direction,
    )


def run_backtest(
    db: Session,
    ticker: str | None = None,
    include_live: bool = True,
    include_simulated: bool = True,
) -> list[BacktestRow]:
    candles_cache: dict[int, list[Candle]] = {}

    def candles_for(instrument_id: int) -> list[Candle]:
        candles = candles_cache.get(instrument_id)
        if candles is None:
            candles = _candles_for(db, instrument_id)
            candles_cache[instrument_id] = candles
        return candles

    rows: list[BacktestRow] = []

    if include_live:
        query = db.query(Forecast).join(Forecast.instrument)
        if ticker:
            query = query.filter(Instrument.ticker == ticker.upper())
        for forecast in query.order_by(Forecast.created_at.asc()).all():
            row = _evaluate(
                row_id=forecast.id,
                source="live",
                ticker=forecast.instrument.ticker,
                created=forecast.created_at,
                horizon_days=forecast.horizon_days,
                direction=forecast.direction,
                confidence=forecast.confidence,
                expected_change_pct=forecast.expected_change_pct,
                range_low_pct=forecast.range_low_pct,
                range_high_pct=forecast.range_high_pct,
                spot_price=forecast.spot_price,
                candles=candles_for(forecast.instrument_id),
            )
            if row is not None:
                rows.append(row)

    if include_simulated:
        query = db.query(BacktestForecast).join(BacktestForecast.instrument)
        if ticker:
            query = query.filter(Instrument.ticker == ticker.upper())
        for sim in query.order_by(BacktestForecast.as_of.asc()).all():
            row = _evaluate(
                row_id=sim.id,
                source="simulated",
                ticker=sim.instrument.ticker,
                created=sim.as_of,
                horizon_days=sim.horizon_days,
                direction=sim.direction,
                confidence=sim.confidence,
                expected_change_pct=sim.expected_change_pct,
                range_low_pct=sim.range_low_pct,
                range_high_pct=sim.range_high_pct,
                spot_price=sim.spot_price,
                candles=candles_for(sim.instrument_id),
            )
            if row is not None:
                rows.append(row)

    rows.sort(key=lambda r: r.created_at)
    return rows


def _confidence_bucket(confidence: float | None) -> str:
    if confidence is None:
        return "n/a"
    if confidence < 0.4:
        return "<0.4"
    if confidence < 0.6:
        return "0.4-0.6"
    if confidence < 0.8:
        return "0.6-0.8"
    return "0.8+"


def summarize(rows: list[BacktestRow]) -> dict:
    if not rows:
        return {"count": 0}

    n = len(rows)
    direction_hits = sum(r.direction_correct for r in rows)
    baseline_hits = sum(r.baseline_correct for r in rows)
    within_range_hits = sum(r.within_range for r in rows)
    errors = [r.abs_error_pct for r in rows if r.abs_error_pct is not None]

    buckets: dict[str, list[BacktestRow]] = {}
    for row in rows:
        buckets.setdefault(_confidence_bucket(row.confidence), []).append(row)

    calibration = {
        key: {
            "count": len(items),
            "hit_rate": round(sum(i.direction_correct for i in items) / len(items), 3),
        }
        for key, items in sorted(buckets.items())
    }

    by_source: dict[str, list[BacktestRow]] = {}
    for row in rows:
        by_source.setdefault(row.source, []).append(row)
    source_breakdown = {
        source: {
            "count": len(items),
            "direction_accuracy": round(sum(i.direction_correct for i in items) / len(items), 3),
            "baseline_accuracy": round(sum(i.baseline_correct for i in items) / len(items), 3),
        }
        for source, items in sorted(by_source.items())
    }

    return {
        "count": n,
        "direction_accuracy": round(direction_hits / n, 3),
        "baseline_accuracy": round(baseline_hits / n, 3),
        "edge_vs_baseline": round((direction_hits - baseline_hits) / n, 3),
        "within_range_rate": round(within_range_hits / n, 3),
        "mean_abs_error_pct": round(sum(errors) / len(errors), 3) if errors else None,
        "calibration_by_confidence": calibration,
        "by_source": source_breakdown,
    }
