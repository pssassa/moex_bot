from __future__ import annotations

import re

from app.models import Instrument


_TICKER_RE_CACHE: dict[str, re.Pattern[str]] = {}


def _ticker_re(ticker: str) -> re.Pattern[str]:
    compiled = _TICKER_RE_CACHE.get(ticker)
    if compiled is None:
        compiled = re.compile(rf"(?<![A-Z0-9]){re.escape(ticker)}(?![A-Z0-9])", re.IGNORECASE)
        _TICKER_RE_CACHE[ticker] = compiled
    return compiled


def _name_needles(instrument: Instrument) -> list[str]:
    needles: list[str] = []
    for raw in (instrument.shortname, instrument.name, instrument.emitent_title):
        if not raw:
            continue
        cleaned = re.sub(r"\b(ПАО|АО|ОАО|ао|ап|др)\b", " ", raw, flags=re.IGNORECASE)
        for token in re.split(r"[\s,./]+", cleaned):
            token = token.strip("-«»\"' ")
            if len(token) >= 4:
                needles.append(token)
        if len(cleaned.strip()) >= 5:
            needles.append(cleaned.strip())
    # уникальные, длинные сначала — меньше ложных срабатываний коротких кусков
    unique = sorted(set(needles), key=len, reverse=True)
    return unique[:4]


def match_instruments(title: str, instruments: list[Instrument]) -> list[Instrument]:
    if not title:
        return []
    hits: list[Instrument] = []
    seen: set[int] = set()
    for inst in instruments:
        matched = bool(_ticker_re(inst.ticker).search(title))
        if not matched:
            lower = title.lower()
            for needle in _name_needles(inst):
                if needle.lower() in lower:
                    matched = True
                    break
        if matched and inst.id not in seen:
            seen.add(inst.id)
            hits.append(inst)
    return hits
