from __future__ import annotations

from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree

from sqlalchemy.orm import Session

from app.models import MacroSnapshot
from app.services.http import get_text
from app.services.iss import fetch_fx_candles, fetch_index_candles


def _change_pct(candles: list[dict]) -> tuple[float | None, float | None]:
    closes = [float(row["close"]) for row in candles if row.get("close") is not None]
    if not closes:
        return None, None
    last = closes[-1]
    prev = closes[-2] if len(closes) > 1 else None
    change = ((last / prev) - 1) * 100 if prev else None
    return last, change


def _safe_index(secid: str, start, end) -> tuple[float | None, float | None]:
    try:
        return _change_pct(fetch_index_candles(secid, start, end))
    except Exception:
        return None, None


def _safe_fx(secids: list[str], start, end) -> tuple[float | None, float | None]:
    for secid in secids:
        try:
            last, change = _change_pct(fetch_fx_candles(secid, start, end))
            if last is not None:
                return last, change
        except Exception:
            continue
    return None, None


def _fetch_cbr_key_rate() -> float | None:
    today = datetime.now().date()
    start = today - timedelta(days=40)
    url = "https://www.cbr.ru/hd_base/KeyRate/KeyRateXML/"
    xml = get_text(
        url,
        params={
            "UniDbQuery.Posted": "True",
            "UniDbQuery.From": start.strftime("%d.%m.%Y"),
            "UniDbQuery.To": today.strftime("%d.%m.%Y"),
        },
    )
    root = ElementTree.fromstring(xml)
    rates: list[tuple[str, float]] = []
    for item in root.iter():
        tag = item.tag.lower()
        if "item" in tag or item.tag == "Record":
            date_attr = item.get("Date") or item.get("date")
            rate_text = item.get("Rate") or (item.findtext("Rate") if item.find("Rate") is not None else item.text)
            if date_attr and rate_text:
                try:
                    rates.append((date_attr, float(str(rate_text).replace(",", "."))))
                except ValueError:
                    continue
    if not rates:
        # запасной разбор: <KR Date="..." Rate="..."/>
        for node in root.findall(".//*"):
            if node.get("Rate") and node.get("Date"):
                try:
                    rates.append((node.get("Date"), float(node.get("Rate").replace(",", "."))))
                except ValueError:
                    continue
    if not rates:
        return None
    rates.sort(key=lambda pair: pair[0])
    return rates[-1][1]


def sync_macro(db: Session) -> MacroSnapshot:
    end = datetime.now().date()
    start = end - timedelta(days=10)

    imoex, imoex_chg = _safe_index("IMOEX", start, end)
    rtsi, rtsi_chg = _safe_index("RTSI", start, end)
    rgbi, rgbi_chg = _safe_index("RGBI", start, end)
    usd, usd_chg = _safe_fx(["USD000UTSTOM"], start, end)
    cny, cny_chg = _safe_fx(["CNYRUB_TOM", "CNY000000TOD"], start, end)

    rate = None
    try:
        rate = _fetch_cbr_key_rate()
    except Exception:
        rate = None

    snapshot = MacroSnapshot(
        ts=datetime.now(timezone.utc),
        imoex=imoex,
        imoex_change_pct=imoex_chg,
        rtsi=rtsi,
        rtsi_change_pct=rtsi_chg,
        usd_rub=usd,
        usd_rub_change_pct=usd_chg,
        cny_rub=cny,
        cny_rub_change_pct=cny_chg,
        rgbi=rgbi,
        rgbi_change_pct=rgbi_chg,
        cbr_key_rate=rate,
        source="iss+cbr",
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot
