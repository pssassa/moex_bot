from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import SyncState
from app.services.instruments import sync_instruments
from app.services.macro import sync_macro
from app.services.news import sync_news

logger = logging.getLogger(__name__)


def _mark(db: Session, key: str, ok: bool, detail: str | None = None, error: str | None = None) -> None:
    row = db.get(SyncState, key)
    if row is None:
        row = SyncState(key=key)
        db.add(row)
    if ok:
        row.last_ok_at = datetime.now(timezone.utc)
        row.last_error = None
        row.detail = detail
    else:
        row.last_error = (error or "error")[:4000]
        row.detail = detail
    db.commit()


def run_instruments() -> int:
    db = SessionLocal()
    try:
        count = sync_instruments(db)
        _mark(db, "instruments", True, detail=f"{count} papers")
        logger.info("Synced %s instruments", count)
        return count
    except Exception as exc:
        db.rollback()
        _mark(db, "instruments", False, error=str(exc))
        logger.exception("Instrument sync failed")
        raise
    finally:
        db.close()


def run_news() -> int:
    db = SessionLocal()
    try:
        count = sync_news(db)
        _mark(db, "news", True, detail=f"+{count}")
        logger.info("Synced news, added %s", count)
        return count
    except Exception as exc:
        db.rollback()
        _mark(db, "news", False, error=str(exc))
        logger.exception("News sync failed")
        raise
    finally:
        db.close()


def run_macro() -> None:
    db = SessionLocal()
    try:
        snap = sync_macro(db)
        _mark(db, "macro", True, detail=f"IMOEX={snap.imoex}")
        logger.info("Synced macro")
    except Exception as exc:
        db.rollback()
        _mark(db, "macro", False, error=str(exc))
        logger.exception("Macro sync failed")
        raise
    finally:
        db.close()


def startup_sync() -> None:
    for fn, name in ((run_instruments, "instruments"), (run_macro, "macro"), (run_news, "news")):
        try:
            fn()
        except Exception:
            logger.exception("Startup step %s failed", name)
