from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any
from xml.etree import ElementTree as ET

from app.services.http import iss_get

ISS_BASE = "https://iss.moex.com/iss"


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


def fetch_board_candles(
    ticker: str,
    start: date,
    end: date,
    interval: int = 24,
) -> list[dict[str, Any]]:
    path = f"/engines/stock/markets/shares/boards/TQBR/securities/{ticker}/candles.json"
    rows: list[dict[str, Any]] = []
    cursor = 0
    while True:
        payload = json.loads(
            iss_get(
                path,
                params={
                    "iss.meta": "off",
                    "from": start.isoformat(),
                    "till": end.isoformat(),
                    "interval": interval,
                    "start": cursor,
                },
                accept="application/json",
            )
        )
        chunk = table_to_dicts(payload.get("candles"))
        if not chunk:
            break
        rows.extend(chunk)
        cursor += len(chunk)
        if len(chunk) < 100:
            break
    return rows


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
