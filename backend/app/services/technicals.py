from __future__ import annotations

from math import sqrt

from app.models import Candle


def _closes(candles: list[Candle]) -> list[float]:
    return [c.close for c in candles]


def _sma(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    chunk = values[-window:]
    return sum(chunk) / window


def _rsi(values: list[float], window: int = 14) -> float | None:
    if len(values) <= window:
        return None
    gains = 0.0
    losses = 0.0
    for prev, current in zip(values[-window - 1 : -1], values[-window:]):
        delta = current - prev
        if delta >= 0:
            gains += delta
        else:
            losses -= delta
    if losses == 0:
        return 100.0
    rs = (gains / window) / (losses / window)
    return 100 - (100 / (1 + rs))


def _return_pct(values: list[float], bars: int) -> float | None:
    if len(values) <= bars:
        return None
    prev = values[-1 - bars]
    if not prev:
        return None
    return (values[-1] / prev - 1) * 100


def _atr(candles: list[Candle], window: int = 14) -> float | None:
    if len(candles) < window + 1:
        return None
    trs: list[float] = []
    for prev, current in zip(candles[:-1], candles[1:]):
        trs.append(
            max(
                current.high - current.low,
                abs(current.high - prev.close),
                abs(current.low - prev.close),
            )
        )
    return sum(trs[-window:]) / window


def _swings(candles: list[Candle], left: int = 2, right: int = 2) -> tuple[list[float], list[float]]:
    highs: list[float] = []
    lows: list[float] = []
    for i in range(left, len(candles) - right):
        high = candles[i].high
        low = candles[i].low
        window = candles[i - left : i + right + 1]
        if window and high >= max(c.high for c in window):
            highs.append(round(high, 4))
        if window and low <= min(c.low for c in window):
            lows.append(round(low, 4))
    return highs[-3:], lows[-3:]


def _structure(highs: list[float], lows: list[float]) -> str:
    hh = len(highs) >= 2 and highs[-1] > highs[-2]
    lh = len(highs) >= 2 and highs[-1] < highs[-2]
    hl = len(lows) >= 2 and lows[-1] > lows[-2]
    ll = len(lows) >= 2 and lows[-1] < lows[-2]
    if hh and hl:
        return "восходящая (higher highs и higher lows)"
    if lh and ll:
        return "нисходящая (lower highs и lower lows)"
    if hh or hl:
        return "смешанная с уклоном вверх"
    if lh or ll:
        return "смешанная с уклоном вниз"
    return "диапазон / нет ясной структуры"


def _last_candle(candles: list[Candle]) -> str:
    bar = candles[-1]
    span = bar.high - bar.low
    body = abs(bar.close - bar.open)
    if span <= 0:
        return "плоская свеча"
    body_share = body / span
    if body_share < 0.18:
        shape = "доджи / нерешительность"
    elif bar.close > bar.open:
        shape = "бычья"
    elif bar.close < bar.open:
        shape = "медвежья"
    else:
        shape = "доджи"
    close_pos = (bar.close - bar.low) / span
    if close_pos > 0.8:
        location = "закрытие у максимума"
    elif close_pos < 0.2:
        location = "закрытие у минимума"
    else:
        location = "закрытие в середине диапазона"
    return f"{shape}, тело {round(body_share * 100)}% диапазона, {location}"


def _streak(values: list[float]) -> str:
    if len(values) < 2:
        return "нет"
    direction = 1 if values[-1] >= values[-2] else -1
    length = 1
    for i in range(len(values) - 2, 0, -1):
        step = 1 if values[i] >= values[i - 1] else -1
        if step != direction:
            break
        length += 1
    if direction > 0:
        return f"{length} сессий роста подряд"
    return f"{length} сессий снижения подряд"


def _rsi_zone(rsi: float | None) -> str:
    if rsi is None:
        return "нет данных"
    if rsi >= 70:
        return "перекупленность"
    if rsi <= 30:
        return "перепроданность"
    return "нейтральная зона"


def _sma_regime(last: float, sma20: float | None, sma50: float | None) -> str:
    if sma20 is None:
        return "мало истории для средних"
    if sma50 is None:
        if last > sma20:
            return "цена выше SMA20"
        if last < sma20:
            return "цена ниже SMA20"
        return "цена у SMA20"
    if last > sma20 and last > sma50:
        return "цена выше SMA20 и SMA50"
    if last < sma20 and last < sma50:
        return "цена ниже SMA20 и SMA50"
    return "цена между SMA20 и SMA50"


def horizon_cap_pct(atr_pct: float | None, bars: int = 5) -> float:
    daily = atr_pct if atr_pct and atr_pct > 0 else 1.8
    return round(max(2.5, min(12.0, 2.2 * daily * sqrt(bars))), 2)


def technical_snapshot(candles: list[Candle]) -> dict:
    values = _closes(candles)
    if not values:
        return {}
    last = values[-1]
    sma20 = _sma(values, 20)
    sma50 = _sma(values, 50)
    trend = "боковик"
    if sma20:
        if last > sma20 * 1.01:
            trend = "восходящий"
        elif last < sma20 * 0.99:
            trend = "нисходящий"
    return {
        "last_close": round(last, 4),
        "change_1d_pct": round(_return_pct(values, 1) or 0, 2),
        "change_5d_pct": None if _return_pct(values, 5) is None else round(_return_pct(values, 5), 2),
        "change_20d_pct": None if _return_pct(values, 20) is None else round(_return_pct(values, 20), 2),
        "sma20": None if sma20 is None else round(sma20, 4),
        "sma50": None if sma50 is None else round(sma50, 4),
        "rsi14": None if _rsi(values) is None else round(_rsi(values), 1),
        "trend_vs_sma20": trend,
        "bars": len(values),
    }


def trader_brief(candles: list[Candle], horizon: int = 5) -> dict:
    snap = technical_snapshot(candles)
    if not snap:
        return {}
    last = float(snap["last_close"])
    window20 = candles[-20:] if len(candles) >= 20 else candles
    window60 = candles[-60:] if len(candles) >= 60 else candles
    high20 = max(c.high for c in window20)
    low20 = min(c.low for c in window20)
    high60 = max(c.high for c in window60)
    low60 = min(c.low for c in window60)
    atr = _atr(candles)
    atr_pct = round((atr / last) * 100, 2) if atr else None
    volumes = [c.volume for c in candles if c.volume is not None]
    vol_sma = _sma(volumes, 20) if volumes else None
    last_vol = candles[-1].volume
    if last_vol is not None and vol_sma:
        vol_vs = "выше среднего" if last_vol > vol_sma * 1.15 else "ниже среднего" if last_vol < vol_sma * 0.85 else "около среднего"
    else:
        vol_vs = "нет данных"
    resist, support = _swings(candles)
    sma20 = snap.get("sma20")
    sma50 = snap.get("sma50")
    rsi = snap.get("rsi14")
    snap.update(
        {
            "atr14": None if atr is None else round(atr, 4),
            "atr_pct": atr_pct,
            "sma_regime": _sma_regime(last, sma20, sma50),
            "rsi_zone": _rsi_zone(rsi),
            "high_20d": round(high20, 4),
            "low_20d": round(low20, 4),
            "dist_to_high_20d_pct": round((high20 / last - 1) * 100, 2) if last else None,
            "dist_to_low_20d_pct": round((last / low20 - 1) * 100, 2) if last and low20 else None,
            "high_60d": round(high60, 4),
            "low_60d": round(low60, 4),
            "volume_last": last_vol,
            "volume_sma20": None if vol_sma is None else round(vol_sma, 0),
            "volume_vs_avg": vol_vs,
            "resistance": resist,
            "support": support,
            "market_structure": _structure(resist, support),
            "last_candle": _last_candle(candles),
            "streak": _streak(_closes(candles)),
            "horizon_bars": horizon,
            "max_reasonable_move_pct": horizon_cap_pct(atr_pct, horizon),
        }
    )
    return snap
