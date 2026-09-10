from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Instrument
from app.schemas import CandleOut, InstrumentOut, NewsOut
from app.services.candles import ensure_candles

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/instruments", tags=["instruments"])


@router.get("", response_model=list[InstrumentOut])
def list_instruments(
    q: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=80, ge=1, le=300),
    db: Session = Depends(get_db),
) -> list[Instrument]:
    query = db.query(Instrument).filter(Instrument.is_russian.is_(True))
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Instrument.ticker.ilike(like),
                Instrument.shortname.ilike(like),
                Instrument.name.ilike(like),
            )
        )
    return (
        query.order_by(Instrument.ticker.asc())
        .limit(limit)
        .all()
    )


@router.get("/{ticker}", response_model=InstrumentOut)
def get_one(ticker: str, db: Session = Depends(get_db)) -> Instrument:
    instrument = db.query(Instrument).filter(Instrument.ticker == ticker.upper()).first()
    if instrument is None:
        raise HTTPException(status_code=404, detail="Тикер не найден среди российских акций TQBR")
    return instrument


@router.get("/{ticker}/candles", response_model=list[CandleOut])
def get_candles(ticker: str, db: Session = Depends(get_db)) -> list[CandleOut]:
    instrument = db.query(Instrument).filter(Instrument.ticker == ticker.upper()).first()
    if instrument is None:
        raise HTTPException(status_code=404, detail="Тикер не найден")
    try:
        candles = ensure_candles(db, instrument)
    except Exception as exc:
        logger.exception("Candle fetch failed for %s", ticker)
        raise HTTPException(status_code=502, detail=f"MOEX ISS недоступен: {exc}") from exc
    return [
        CandleOut(
            ts=c.ts,
            open=c.open,
            high=c.high,
            low=c.low,
            close=c.close,
            volume=c.volume,
        )
        for c in candles
    ]


@router.get("/{ticker}/news", response_model=list[NewsOut])
def get_instrument_news(ticker: str, limit: int = 30, db: Session = Depends(get_db)) -> list[NewsOut]:
    from app.models import NewsItem

    instrument = db.query(Instrument).filter(Instrument.ticker == ticker.upper()).first()
    if instrument is None:
        raise HTTPException(status_code=404, detail="Тикер не найден")
    rows = (
        db.query(NewsItem)
        .join(NewsItem.instruments)
        .filter(Instrument.id == instrument.id)
        .order_by(NewsItem.published_at.desc().nullslast())
        .limit(limit)
        .all()
    )
    return [
        NewsOut(
            id=item.id,
            source=item.source,
            title=item.title,
            url=item.url,
            published_at=item.published_at,
            summary=item.summary,
            is_world=item.is_world,
            tickers=[ticker.upper()],
        )
        for item in rows
    ]
