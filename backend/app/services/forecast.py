from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Forecast, Instrument, MacroSnapshot, NewsItem
from app.services.candles import ensure_candles
from app.services.llm import LlmError, complete_analyst
from app.services.technicals import technical_snapshot


def _latest_forecast(db: Session, instrument_id: int) -> Forecast | None:
    return (
        db.query(Forecast)
        .filter(Forecast.instrument_id == instrument_id)
        .order_by(Forecast.created_at.desc())
        .first()
    )


def _join_list(items: list[str], sep: str = "\n") -> str | None:
    cleaned = [item.strip() for item in items if item and str(item).strip()]
    return sep.join(cleaned) if cleaned else None


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

    return (
        f"Тикер: {instrument.ticker}\n"
        f"Компания: {instrument.shortname}\n"
        f"Полное имя: {instrument.name or instrument.emitent_title or '—'}\n"
        f"ISIN: {instrument.isin}, уровень листинга: {instrument.list_level}\n\n"
        f"Техническая картина (дневные свечи):\n{tech}\n\n"
        f"Макро / мир:\n{macro_lines}\n\n"
        f"Новости:\n" + ("\n".join(news_lines) if news_lines else "нет свежих новостей")
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

    tech = technical_snapshot(candles)
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

    thesis = str(parsed.get("thesis") or "").strip() or "Модель не сформулировала тезис."
    news_factors = parsed.get("news_factors")
    macro_factors = parsed.get("macro_factors")
    risks = parsed.get("risks")
    if isinstance(news_factors, list):
        news_factors = _join_list([str(x) for x in news_factors])
    if isinstance(macro_factors, list):
        macro_factors = _join_list([str(x) for x in macro_factors])
    if isinstance(risks, list):
        risks = _join_list([str(x) for x in risks])

    forecast = Forecast(
        instrument_id=instrument.id,
        created_at=datetime.now(timezone.utc),
        direction=parsed["direction"],
        confidence=parsed.get("confidence"),
        thesis=thesis,
        news_factors=str(news_factors) if news_factors else None,
        macro_factors=str(macro_factors) if macro_factors else None,
        risks=str(risks) if risks else None,
        model=settings.hf_model,
        raw_json=raw[:8000],
    )
    db.add(forecast)
    db.commit()
    db.refresh(forecast)
    return forecast
