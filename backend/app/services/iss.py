from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any
from xml.etree import ElementTree as ET

from app.services.http import ISS_TIMEOUT, USER_AGENT, _get, iss_get

ISS_BASE = "https://iss.moex.com/iss"


def _json_has_rows(payload: dict[str, Any]) -> bool:
    for block in payload.values():
        if isinstance(block, dict) and block.get("data"):
            return True
    return False


def iss_json(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = iss_get(path, params, accept="application/json")
    payload = json.loads(raw)
    if _json_has_rows(payload):
        return payload
    response = _get(
        f"{ISS_BASE}{path}",
        params,
        {"User-Agent": USER_AGENT, "Accept": "application/json"},
        follow_redirects=True,
        timeout=ISS_TIMEOUT,
    )
    return response.json()


def table_to_dicts(block: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not block:
        return []
    columns = [str(col).lower() for col in block.get("columns", [])]
    rows = []
    for raw in block.get("data") or []:
        rows.append({columns[i]: raw[i] if i < len(raw) else None for i in range(len(columns))})
    return rows


def xml_table(xml_bytes: bytes, data_id: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_bytes)
    rows: list[dict[str, Any]] = []
    for data in root.findall("data"):
        if data.get("id") != data_id:
            continue
        for row in data.findall("./rows/row"):
            rows.append({key.lower(): value for key, value in row.attrib.items()})
    return rows


def fetch_tqbr_securities() -> list[dict[str, Any]]:
    raw = iss_get(
        "/engines/stock/markets/shares/boards/TQBR/securities.xml",
        params={"iss.only": "securities"},
    )
    return xml_table(raw, "securities")


def fetch_cets_security(secid: str) -> dict[str, Any] | None:
    payload = iss_json(
        f"/engines/currency/markets/selt/boards/CETS/securities/{secid}.json",
        params={"iss.meta": "off", "iss.only": "securities"},
    )
    rows = table_to_dicts(payload.get("securities"))
    return rows[0] if rows else None


def fetch_candles(
    ticker: str,
    start: date,
    end: date,
    *,
    engine: str,
    market: str,
    board: str,
    interval: int = 24,
) -> list[dict[str, Any]]:
    path = f"/engines/{engine}/markets/{market}/boards/{board}/securities/{ticker}/candles.json"
    rows: list[dict[str, Any]] = []
    cursor = 0
    while True:
        payload = iss_json(
            path,
            params={
                "iss.meta": "off",
                "from": start.isoformat(),
                "till": end.isoformat(),
                "interval": interval,
                "start": cursor,
            },
        )
        chunk = table_to_dicts(payload.get("candles"))
        if not chunk:
            break
        rows.extend(chunk)
        cursor += len(chunk)
        if len(chunk) < 100:
            break
    return rows


def fetch_board_candles(
    ticker: str,
    start: date,
    end: date,
    interval: int = 24,
) -> list[dict[str, Any]]:
    return fetch_candles(
        ticker,
        start,
        end,
        engine="stock",
        market="shares",
        board="TQBR",
        interval=interval,
    )


def fetch_index_candles(
    secid: str,
    start: date,
    end: date,
    interval: int = 24,
) -> list[dict[str, Any]]:
    path = f"/engines/stock/markets/index/securities/{secid}/candles.json"
    payload = json.loads(
        iss_get(
            path,
            params={
                "iss.meta": "off",
                "from": start.isoformat(),
                "till": end.isoformat(),
                "interval": interval,
            },
            accept="application/json",
        )
    )
    return table_to_dicts(payload.get("candles"))


def fetch_fx_candles(
    secid: str,
    start: date,
    end: date,
    interval: int = 24,
) -> list[dict[str, Any]]:
    path = f"/engines/currency/markets/selt/boards/CETS/securities/{secid}/candles.json"
    payload = json.loads(
        iss_get(
            path,
            params={
                "iss.meta": "off",
                "from": start.isoformat(),
                "till": end.isoformat(),
                "interval": interval,
            },
            accept="application/json",
        )
    )
    return table_to_dicts(payload.get("candles"))


def fetch_sitenews(limit: int = 30) -> list[dict[str, Any]]:
    payload = json.loads(
        iss_get("/sitenews.json", params={"iss.meta": "off", "limit": limit}, accept="application/json")
    )
    return table_to_dicts(payload.get("contents") or payload.get("sitenews"))


def parse_iss_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(text[:19] if fmt.endswith("%S") else text[:10], fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None
