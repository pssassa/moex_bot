from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from time import struct_time

import feedparser
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Instrument, NewsItem
from app.services.http import get_bytes
from app.services.iss import fetch_sitenews, parse_iss_datetime
from app.services.matching import match_instruments

RSS_FEEDS = [
    {"source": "ТАСС", "url": "https://tass.ru/rss/v2.xml", "world": False, "lang": "ru"},
    {"source": "Интерфакс", "url": "https://www.interfax.ru/rss.asp", "world": False, "lang": "ru"},
    {"source": "РБК", "url": "https://rssexport.rbc.ru/rbcnews/news/20/full.rss", "world": False, "lang": "ru"},
    {"source": "Коммерсантъ", "url": "https://www.kommersant.ru/RSS/news.xml", "world": False, "lang": "ru"},
    {"source": "Ведомости", "url": "https://www.vedomosti.ru/rss/news", "world": False, "lang": "ru"},
    {"source": "Лента", "url": "https://lenta.ru/rss", "world": False, "lang": "ru"},
    {"source": "РИА", "url": "https://ria.ru/export/rss2/index.xml", "world": False, "lang": "ru"},
    {"source": "BBC World", "url": "https://feeds.bbci.co.uk/news/world/rss.xml", "world": True, "lang": "en"},
]


def _strip_html(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = _re_sub_tags(unescape(text))
    return cleaned.strip()[:2000] or None


def _re_sub_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text)


def _published(entry: object) -> datetime | None:
    parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if isinstance(parsed, struct_time):
        return datetime(*parsed[:6], tzinfo=timezone.utc)
    raw = getattr(entry, "published", None) or getattr(entry, "updated", None)
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError):
        return None


def _upsert_news(
    db: Session,
    *,
    source: str,
    title: str,
    url: str,
    published_at: datetime | None,
    summary: str | None,
    lang: str,
    is_world: bool,
    instruments: list[Instrument],
) -> bool:
    if not title or not url:
        return False
    existing = db.query(NewsItem).filter(NewsItem.url == url).one_or_none()
    if existing:
        return False
    item = NewsItem(
        source=source,
        title=title[:1024],
        url=url[:1024],
        published_at=published_at,
        summary=summary,
        lang=lang,
        is_world=is_world,
        created_at=datetime.now(timezone.utc),
    )
    db.add(item)
    db.flush()
    if not is_world:
        item.instruments = match_instruments(f"{title} {summary or ''}", instruments)
    return True


def _sync_rss(db: Session, instruments: list[Instrument]) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.news_max_age_days)
    added = 0
    for feed in RSS_FEEDS:
        try:
            raw = get_bytes(feed["url"], timeout=25)
        except Exception:
            continue
        parsed = feedparser.parse(raw)
        for entry in parsed.entries:
            published = _published(entry)
            if published and published < cutoff:
                continue
            title = (getattr(entry, "title", None) or "").strip()
            link = (getattr(entry, "link", None) or "").strip()
            summary = _strip_html(getattr(entry, "summary", None) or getattr(entry, "description", None))
            if _upsert_news(
                db,
                source=feed["source"],
                title=title,
                url=link,
                published_at=published,
                summary=summary,
                lang=feed["lang"],
                is_world=feed["world"],
                instruments=instruments,
            ):
                added += 1
        db.commit()
    return added


def _sync_moex_news(db: Session, instruments: list[Instrument]) -> int:
    added = 0
    try:
        rows = fetch_sitenews(40)
    except Exception:
        return 0
    for row in rows:
        news_id = row.get("id")
        title = str(row.get("title") or "").strip()
        url = f"https://www.moex.com/n{news_id}" if news_id else f"https://www.moex.com/news/{title}"
        published = parse_iss_datetime(row.get("published_at") or row.get("publishedat"))
        if _upsert_news(
            db,
            source="MOEX",
            title=title,
            url=url,
            published_at=published,
            summary=None,
            lang="ru",
            is_world=False,
            instruments=instruments,
        ):
            added += 1
    db.commit()
    return added


def sync_news(db: Session) -> int:
    instruments = db.query(Instrument).all()
    return _sync_rss(db, instruments) + _sync_moex_news(db, instruments)
