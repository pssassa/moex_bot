from __future__ import annotations

import argparse
import json
import logging
import warnings

from app.db import SessionLocal
from app.services.quant import KINDS, build_dataset, evaluate
from app.services.universe import load_candles, sync_universe_candles, universe_instruments

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
warnings.filterwarnings("ignore", message="Unknown solver options")


def main() -> None:
    parser = argparse.ArgumentParser(description="Локальная количественная модель по свечам")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sync = sub.add_parser("sync", help="Догрузить свечи: акции IMOEX, фонды, металлы")
    sync.add_argument("--days", type=int, default=1500, help="Глубина истории в календарных днях")
    sync.add_argument("--kinds", nargs="+", choices=KINDS, default=list(KINDS))

    ev = sub.add_parser("evaluate", help="Walk-forward оценка направления и 80%% интервала")
    ev.add_argument("--test-days", type=int, default=160)
    ev.add_argument("--folds", type=int, default=4)

    args = parser.parse_args()
    db = SessionLocal()
    try:
        if args.cmd == "sync":
            result = sync_universe_candles(db, tuple(args.kinds), days=args.days)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return
        instruments = universe_instruments(db, KINDS)
        series = load_candles(db, [i.id for i in instruments])
        dataset = build_dataset(series, {i.id: i.kind for i in instruments})
        report = evaluate(dataset, test_days=args.test_days, folds=args.folds)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
