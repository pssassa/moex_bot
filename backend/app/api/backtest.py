from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.backtest import BacktestRow, run_backtest, summarize

router = APIRouter(prefix="/backtest", tags=["backtest"])


def _row_out(row: BacktestRow) -> dict:
    return {
        "forecast_id": row.forecast_id,
        "source": row.source,
        "ticker": row.ticker,
        "created_at": row.created_at.isoformat(),
        "horizon_days": row.horizon_days,
        "direction": row.direction,
        "confidence": row.confidence,
        "expected_change_pct": row.expected_change_pct,
        "range_low_pct": row.range_low_pct,
        "range_high_pct": row.range_high_pct,
        "actual_change_pct": row.actual_change_pct,
        "actual_direction": row.actual_direction,
        "direction_correct": row.direction_correct,
        "within_range": row.within_range,
        "abs_error_pct": row.abs_error_pct,
        "baseline_direction": row.baseline_direction,
        "baseline_correct": row.baseline_correct,
    }


@router.get("")
def get_backtest(ticker: str | None = Query(default=None), db: Session = Depends(get_db)) -> dict:
    rows = run_backtest(db, ticker=ticker)
    return {"summary": summarize(rows), "rows": [_row_out(row) for row in rows]}
