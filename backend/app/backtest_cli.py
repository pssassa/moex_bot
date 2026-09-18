from __future__ import annotations

import json

from app.db import SessionLocal
from app.services.backtest import run_backtest, summarize


def main() -> None:
    db = SessionLocal()
    try:
        rows = run_backtest(db)
        summary = summarize(rows)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        if not rows:
            return
        print()
        print(f"{'src':<10}{'ticker':<8}{'created':<12}{'dir':<10}{'conf':<6}{'exp%':<8}{'act%':<8}{'ok':<4}{'range':<6}{'base_ok':<8}")
        for row in rows:
            print(
                f"{row.source:<10}{row.ticker:<8}{row.created_at.date().isoformat():<12}{row.direction:<10}"
                f"{(row.confidence or 0):<6.2f}{(row.expected_change_pct or 0):<8.2f}"
                f"{row.actual_change_pct:<8.2f}{'Y' if row.direction_correct else 'N':<4}"
                f"{'Y' if row.within_range else 'N':<6}{'Y' if row.baseline_correct else 'N':<8}"
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()
