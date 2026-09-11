from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Instrument
from app.services.iss import fetch_cets_security, fetch_tqbr_securities

METALS = [
    {
        "secid": "GLDRUB_TOM",
        "shortname": "Золото",
        "secname": "Золото / рубль, расчёты TOM",
        "aliases": "золото gold",
    },
    {
        "secid": "SLVRUB_TOM",
        "shortname": "Серебро",
        "secname": "Серебро / рубль, расчёты TOM",
        "aliases": "серебро silver",
    },
    {
        "secid": "PLTRUB_TOM",
        "shortname": "Платина",
        "secname": "Платина / рубль, расчёты TOM",
        "aliases": "платина platinum",
    },
    {
        "secid": "PLDRUB_TOM",
        "shortname": "Палладий",
        "secname": "Палладий / рубль, расчёты TOM",
        "aliases": "палладий palladium",
    },
]


def classify_tqbr(row: dict) -> str | None:
    isin = str(row.get("isin") or "").upper()
    if not isin.startswith("RU"):
        return None
    instrid = str(row.get("instrid") or "").upper()
    sectype = str(row.get("sectype") or "").upper()
    if instrid == "EQIN":
        return "share"
    if instrid == "IFTF" or sectype == "J":
        return "fund"
    return None


def _upsert_row(db: Session, ticker: str, now: datetime) -> Instrument:
    instrument = db.query(Instrument).filter(Instrument.ticker == ticker).one_or_none()
    if instrument is None:
        instrument = Instrument(ticker=ticker, shortname=ticker, isin=ticker)
        db.add(instrument)
    instrument.updated_at = now
    return instrument


def _apply_tqbr(instrument: Instrument, row: dict, kind: str) -> None:
    ticker = instrument.ticker
    instrument.shortname = str(row.get("shortname") or ticker)
    instrument.name = row.get("secname") or instrument.name
    instrument.isin = str(row.get("isin") or instrument.isin)
    instrument.is_russian = True
    instrument.kind = kind
    instrument.board = str(row.get("boardid") or "TQBR")
    instrument.currency = str(row.get("faceunit") or row.get("currencyid") or "SUR")
    list_level = row.get("listlevel")
    instrument.list_level = int(list_level) if list_level not in (None, "") else instrument.list_level
    lot_size = row.get("lotsize")
    instrument.lot_size = int(lot_size) if lot_size not in (None, "") else instrument.lot_size
    instrument.sec_type = row.get("sectype") or row.get("instrid") or instrument.sec_type
    prev = row.get("prevprice")
    if prev not in (None, ""):
        try:
            instrument.last_close = float(prev)
        except (TypeError, ValueError):
            pass


def _sync_metals(db: Session, now: datetime) -> int:
    saved = 0
    for spec in METALS:
        ticker = spec["secid"]
        row = fetch_cets_security(ticker) or {}
        instrument = _upsert_row(db, ticker, now)
        instrument.shortname = spec["shortname"]
        instrument.name = spec["secname"]
        instrument.isin = str(row.get("secid") or ticker)
        instrument.is_russian = True
        instrument.kind = "metal"
        instrument.board = str(row.get("boardid") or "CETS")
        instrument.currency = str(row.get("currencyid") or "RUB")
        instrument.list_level = None
        lot_size = row.get("lotsize")
        instrument.lot_size = int(lot_size) if lot_size not in (None, "") else 1
        instrument.sec_type = "metal"
        instrument.emitent_title = spec["aliases"]
        prev = row.get("prevprice")
        if prev not in (None, ""):
            try:
                instrument.last_close = float(prev)
            except (TypeError, ValueError):
                pass
        saved += 1
    return saved


def sync_instruments(db: Session) -> int:
    rows = fetch_tqbr_securities()
    saved = 0
    now = datetime.now(timezone.utc)
    for row in rows:
        ticker = str(row.get("secid") or "").upper().strip()
        kind = classify_tqbr(row)
        if not ticker or kind is None:
            continue
        instrument = _upsert_row(db, ticker, now)
        _apply_tqbr(instrument, row, kind)
        saved += 1
    saved += _sync_metals(db, now)
    db.commit()
    return saved
