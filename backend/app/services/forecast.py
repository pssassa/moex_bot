from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Forecast, Instrument, MacroSnapshot, NewsItem
from app.services.candles import ensure_candles
from app.services.llm import LlmError, complete_analyst
from app.services.technicals import horizon_cap_pct, trader_brief


def _latest_forecast(db: Session, instrument_id: int) -> Forecast | None:
    return (
        db.query(Forecast)
        .filter(Forecast.instrument_id == instrument_id)
        .order_by(Forecast.created_at.desc())
        .first()
    )


def _linear_path(expected: float, horizon: int) -> list[dict]:
    if horizon <= 0:
        return []
    return [
        {"t": day, "change_pct": round(expected * day / horizon, 3)}
        for day in range(1, horizon + 1)
    ]


def normalize_outlook(parsed: dict, tech: dict) -> dict:
    horizon = int(tech.get("horizon_bars") or settings.forecast_horizon_days)
    cap = float(tech.get("max_reasonable_move_pct") or horizon_cap_pct(tech.get("atr_pct"), horizon))
    expected = parsed.get("expected_change_pct")
    if expected is None:
        direction = parsed.get("direction")
        if direction == "up":
            expected = min(cap * 0.35, 2.0)
        elif direction == "down":
            expected = -min(cap * 0.35, 2.0)
        else:
            expected = 0.0
    expected = max(-cap, min(cap, float(expected)))

    low = parsed.get("range_low_pct")
    high = parsed.get("range_high_pct")
    if low is None:
        low = expected - cap * 0.45
    if high is None:
        high = expected + cap * 0.45
    low = max(-cap * 1.15, min(float(low), expected))
    high = min(cap * 1.15, max(float(high), expected))
    if high - low < 0.4:
        pad = max(0.4, cap * 0.15)
        low = expected - pad
        high = expected + pad

    raw_path = parsed.get("path") if isinstance(parsed.get("path"), list) else []
    by_t = {}
    for point in raw_path:
        try:
            t = int(point["t"])
            by_t[t] = float(point["change_pct"])
        except (KeyError, TypeError, ValueError):
            continue
    if len(by_t) < horizon:
        path = _linear_path(expected, horizon)
    else:
        path = []
        for day in range(1, horizon + 1):
            value = max(-cap * 1.15, min(cap * 1.15, by_t[day]))
            path.append({"t": day, "change_pct": round(value, 3)})
        path[-1]["change_pct"] = round(expected, 3)

    if expected > 0.45:
        direction = "up"
    elif expected < -0.45:
        direction = "down"
    else:
        direction = "sideways"

    return {
        "direction": direction,
        "expected_change_pct": round(expected, 3),
        "range_low_pct": round(low, 3),
        "range_high_pct": round(high, 3),
        "path": path,
        "horizon_days": horizon,
    }


def build_prompt(instrument: Instrument, tech: dict, news: list[NewsItem], macro: MacroSnapshot | None) -> str:
    news_lines = []
    for item in news[:18]:
        when = item.published_at.strftime("%Y-%m-%d") if item.published_at else "?"
        kind = "мир" if item.is_world else "РФ"
        news_lines.append(f"- [{kind}] {when} {item.source}: {item.title}")

    macro_lines = "нет данных"
    if macro:
        macro_lines = (
            f"IMOEX={macro.imoex} ({macro.imoex_change_pct}%), "
            f"RTSI={macro.rtsi} ({macro.rtsi_change_pct}%), "
            f"USD/RUB={macro.usd_rub} ({macro.usd_rub_change_pct}%), "
            f"CNY/RUB={macro.cny_rub} ({macro.cny_rub_change_pct}%), "
            f"RGBI={macro.rgbi} ({macro.rgbi_change_pct}%), "
            f"ставка ЦБ={macro.cbr_key_rate}%"
        )

    levels = {
        "support": tech.get("support"),
        "resistance": tech.get("resistance"),
        "sma20": tech.get("sma20"),
        "sma50": tech.get("sma50"),
        "high_20d": tech.get("high_20d"),
        "low_20d": tech.get("low_20d"),
        "atr_pct": tech.get("atr_pct"),
        "max_reasonable_move_pct": tech.get("max_reasonable_move_pct"),
        "last_close": tech.get("last_close"),
    }

    return (
        f"Тикер: {instrument.ticker}\n"
        f"Класс: { {'share': 'акция TQBR', 'fund': 'биржевой фонд / БПИФ', 'metal': 'драгоценный металл CETS'}.get(instrument.kind or 'share', instrument.kind) }\n"
        f"Компания / имя: {instrument.shortname}\n"
        f"Полное имя: {instrument.name or instrument.emitent_title or '—'}\n"
        f"ISIN: {instrument.isin}, режим: {instrument.board}, уровень листинга: {instrument.list_level}\n\n"
        f"Горизонт прогноза: {tech.get('horizon_bars', 5)} торговых сессий.\n\n"
        f"Бриф трейдера (дневные свечи, факты, не выдумывать уровни):\n"
        f"- last_close={tech.get('last_close')}, 1д {tech.get('change_1d_pct')}%, "
        f"5д {tech.get('change_5d_pct')}%, 20д {tech.get('change_20d_pct')}%\n"
        f"- структура: {tech.get('market_structure')}\n"
        f"- режим средних: {tech.get('sma_regime')}, тренд vs SMA20: {tech.get('trend_vs_sma20')}\n"
        f"- RSI14={tech.get('rsi14')} ({tech.get('rsi_zone')})\n"
        f"- ATR14={tech.get('atr14')} ({tech.get('atr_pct')}% от цены)\n"
        f"- к хаю 20д {tech.get('dist_to_high_20d_pct')}%, к лою 20д {tech.get('dist_to_low_20d_pct')}%\n"
        f"- объём: {tech.get('volume_vs_avg')} (последний={tech.get('volume_last')}, SMA20={tech.get('volume_sma20')})\n"
        f"- последняя свеча: {tech.get('last_candle')}\n"
        f"- серия: {tech.get('streak')}\n"
        f"- уровни: {json.dumps(levels, ensure_ascii=False)}\n"
        f"- потолок правдоподобного хода за горизонт: ±{tech.get('max_reasonable_move_pct')}%\n\n"
        f"Макро / мир:\n{macro_lines}\n\n"
        f"Новости:\n" + ("\n".join(news_lines) if news_lines else "нет свежих новостей")
        + "\n\nВерни только один JSON-объект. Первый символ — {."
    )


def create_forecast(db: Session, instrument: Instrument, force: bool = False) -> Forecast:
    cached = _latest_forecast(db, instrument.id)
    if cached and not force:
        created = cached.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - created
        if age <= timedelta(hours=settings.forecast_cache_hours):
            return cached

    candles = ensure_candles(db, instrument)
    if len(candles) < 20:
        raise LlmError("Недостаточно истории котировок для сценария")

    tech = trader_brief(candles, settings.forecast_horizon_days)
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.news_max_age_days)
    company_news = (
        db.query(NewsItem)
        .join(NewsItem.instruments)
        .filter(Instrument.id == instrument.id, NewsItem.published_at >= cutoff)
        .order_by(NewsItem.published_at.desc())
        .limit(12)
        .all()
    )
    world_news = (
        db.query(NewsItem)
        .filter(NewsItem.is_world.is_(True), NewsItem.published_at >= cutoff)
        .order_by(NewsItem.published_at.desc())
        .limit(8)
        .all()
    )
    macro = db.query(MacroSnapshot).order_by(MacroSnapshot.ts.desc()).first()
    prompt = build_prompt(instrument, tech, company_news + world_news, macro)
    parsed, raw = complete_analyst(prompt)
    outlook = normalize_outlook(parsed, tech)

    forecast = Forecast(
        instrument_id=instrument.id,
        created_at=datetime.now(timezone.utc),
        direction=outlook["direction"],
        confidence=parsed.get("confidence"),
        thesis=parsed.get("thesis") or "Модель не сформулировала тезис.",
        news_factors=parsed.get("news_factors") or None,
        macro_factors=parsed.get("macro_factors") or None,
        risks=parsed.get("risks") or None,
        chart_analysis=parsed.get("chart_analysis") or None,
        news_alignment=parsed.get("news_alignment") or None,
        news_vs_chart=parsed.get("news_vs_chart") or "mixed",
        expected_change_pct=outlook["expected_change_pct"],
        range_low_pct=outlook["range_low_pct"],
        range_high_pct=outlook["range_high_pct"],
        horizon_days=outlook["horizon_days"],
        spot_price=tech.get("last_close"),
        path_json=json.dumps(outlook["path"], ensure_ascii=False),
        model=settings.hf_model,
        raw_json=raw[:8000],
    )
    db.add(forecast)
    db.commit()
    db.refresh(forecast)
    return forecast
