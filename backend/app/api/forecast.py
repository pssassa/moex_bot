import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Forecast, Instrument
from app.schemas import ForecastOut, PathPoint
from app.services.forecast import create_forecast
from app.services.llm import LlmError

router = APIRouter(prefix="/instruments", tags=["forecast"])


def _path_points(forecast: Forecast) -> list[PathPoint]:
    raw = forecast.path_json
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:  # noqa: BLE001
        return []
    if not isinstance(data, list):
        return []
    points: list[PathPoint] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            points.append(PathPoint(t=int(item["t"]), change_pct=float(item["change_pct"])))
        except (KeyError, TypeError, ValueError):
            continue
    return points


def _to_out(forecast: Forecast, ticker: str) -> ForecastOut:
    return ForecastOut(
        id=forecast.id,
        ticker=ticker,
        created_at=forecast.created_at,
        direction=forecast.direction,
        confidence=forecast.confidence,
        thesis=forecast.thesis,
        news_factors=forecast.news_factors,
        macro_factors=forecast.macro_factors,
        risks=forecast.risks,
        chart_analysis=forecast.chart_analysis,
        news_alignment=forecast.news_alignment,
        news_vs_chart=forecast.news_vs_chart,
        expected_change_pct=forecast.expected_change_pct,
        range_low_pct=forecast.range_low_pct,
        range_high_pct=forecast.range_high_pct,
        horizon_days=forecast.horizon_days,
        spot_price=forecast.spot_price,
        path=_path_points(forecast),
        model=forecast.model,
    )


@router.get("/{ticker}/forecast", response_model=ForecastOut | None)
def get_forecast(ticker: str, db: Session = Depends(get_db)) -> ForecastOut | None:
    instrument = db.query(Instrument).filter(Instrument.ticker == ticker.upper()).first()
    if instrument is None:
        raise HTTPException(status_code=404, detail="Тикер не найден")
    row = (
        db.query(Forecast)
        .filter(Forecast.instrument_id == instrument.id)
        .order_by(Forecast.created_at.desc())
        .first()
    )
    if row is None:
        return None
    return _to_out(row, instrument.ticker)


@router.post("/{ticker}/forecast", response_model=ForecastOut)
def post_forecast(
    ticker: str,
    force: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> ForecastOut:
    instrument = db.query(Instrument).filter(Instrument.ticker == ticker.upper()).first()
    if instrument is None:
        raise HTTPException(status_code=404, detail="Тикер не найден")
    try:
        forecast = create_forecast(db, instrument, force=force)
    except LlmError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Не удалось построить сценарий: {exc}") from exc
    return _to_out(forecast, instrument.ticker)
