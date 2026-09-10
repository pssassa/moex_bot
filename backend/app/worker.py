from __future__ import annotations

import logging
import time

from apscheduler.schedulers.blocking import BlockingScheduler

from app.services.sync import run_instruments, run_macro, run_news, startup_sync

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("worker")


def _safe(fn, name: str) -> None:
    try:
        fn()
    except Exception:
        logger.exception("%s job failed", name)


def main() -> None:
    logger.info("Worker starting, waiting for database...")
    for attempt in range(20):
        try:
            startup_sync()
            break
        except Exception:
            logger.exception("Startup sync failed (attempt %s)", attempt + 1)
            time.sleep(5)
    else:
        logger.error("Startup sync did not succeed, scheduler will retry on schedule")

    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(lambda: _safe(run_instruments, "instruments"), "interval", hours=12, id="instruments")
    scheduler.add_job(lambda: _safe(run_macro, "macro"), "interval", hours=1, id="macro")
    scheduler.add_job(lambda: _safe(run_news, "news"), "interval", minutes=25, id="news")
    logger.info("Scheduler started")
    scheduler.start()


if __name__ == "__main__":
    main()
