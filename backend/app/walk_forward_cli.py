from __future__ import annotations

import argparse
import json
import logging

from app.db import SessionLocal
from app.services.walk_forward import run_walk_forward

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Walk-forward симуляция прогнозов на исторические даты")
    parser.add_argument(
        "--tickers",
        nargs="*",
        default=None,
        help="Ограничить список тикеров (по умолчанию — все уже синхронизированные)",
    )
    parser.add_argument("--horizon", type=int, default=5)
    parser.add_argument("--limit", type=int, default=200, help="Максимум новых LLM-вызовов за запуск")
    parser.add_argument("--sleep", type=float, default=1.0, help="Пауза между вызовами LLM, сек")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = run_walk_forward(
            db,
            tickers=args.tickers,
            horizon=args.horizon,
            limit=args.limit,
            sleep_seconds=args.sleep,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
