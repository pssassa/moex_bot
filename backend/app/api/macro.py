from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import MacroSnapshot
from app.schemas import MacroOut

router = APIRouter(prefix="/macro", tags=["macro"])


@router.get("", response_model=MacroOut | None)
def latest_macro(db: Session = Depends(get_db)) -> MacroSnapshot | None:
    return db.query(MacroSnapshot).order_by(MacroSnapshot.ts.desc()).first()


@router.get("/history", response_model=list[MacroOut])
def macro_history(limit: int = Query(default=90, ge=1, le=400), db: Session = Depends(get_db)) -> list[MacroSnapshot]:
    rows = db.query(MacroSnapshot).order_by(MacroSnapshot.ts.desc()).limit(limit).all()
    return list(reversed(rows))
