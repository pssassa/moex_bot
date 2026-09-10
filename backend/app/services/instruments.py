from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Instrument
from app.services.iss import fetch_tqbr_securities


def _is_russian_share(row: dict) -> bool:
    isin = str(row.get("isin") or "").upper()
    if not isin.startswith("RU"):
        return False
    instrid = str(row.get("instrid") or "").upper()
    if instrid and instrid != "EQIN":
        return False
    sectype = str(row.get("sectype") or "").upper()
    if sectype in {"J"}:
        return False
    return True


def sync_instruments(db: Session) -> int:
    rows = fetch_tqbr_securities()
    saved = 0
    now = datetime.now(timezone.utc)
    for row in rows:
        ticker = str(row.get("secid") or "").upper().strip()
        if not ticker or not _is_russian_share(row):
            continue
        instrument = db.query(Instrument).filter(Instrument.ticker == ticker).one_or_none()
        if instrument is None:
            instrument = Instrument(ticker=ticker, shortname=ticker, isin=str(row.get("isin") or ticker))
            db.add(instrument)
        instrument.shortname = str(row.get("shortname") or ticker)
        instrument.name = row.get("secname") or instrument.name
        instrument.isin = str(row.get("isin") or instrument.isin)
        instrument.is_russian = True
        instrument.board = str(row.get("boardid") or "TQBR")
        instrument.currency = str(row.get("faceunit") or row.get("currencyid") or "SUR")
        list_level = row.get("listlevel")
        instrument.list_level = int(list_level) if list_level is not None else instrument.list_level
        lot_size = row.get("lotsize")
        instrument.lot_size = int(lot_size) if lot_size is not None else instrument.lot_size
        instrument.sec_type = row.get("sectype") or row.get("type") or instrument.sec_type
        prev = row.get("prevprice")
        if prev not in (None, ""):
            try:
                instrument.last_close = float(prev)
            except (TypeError, ValueError):
                pass
        instrument.updated_at = now
        saved += 1
    db.commit()
    return saved
