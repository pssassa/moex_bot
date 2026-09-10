from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import SyncState
from app.schemas import HealthOut
from app.services.sync import run_instruments, run_macro, run_news

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
def health(db: Session = Depends(get_db)) -> HealthOut:
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"
    sync_rows = db.query(SyncState).all()
    sync = {row.key: (row.last_ok_at.isoformat() if row.last_ok_at else row.last_error) for row in sync_rows}
    return HealthOut(
        status="ok" if db_status == "ok" else "degraded",
        database=db_status,
        hf_configured=bool(settings.hf_token),
        sync=sync,
    )


@router.post("/sync")
def trigger_sync() -> dict[str, str]:
    errors: dict[str, str] = {}
    for fn, name in ((run_instruments, "instruments"), (run_macro, "macro"), (run_news, "news")):
        try:
            fn()
        except Exception as exc:
            errors[name] = str(exc)
    if errors:
        raise HTTPException(status_code=502, detail=errors)
    return {"status": "ok"}
