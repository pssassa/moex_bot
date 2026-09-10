from sqlalchemy.orm import Session

from app.models import Instrument


def get_instrument(db: Session, ticker: str) -> Instrument | None:
    return db.query(Instrument).filter(Instrument.ticker == ticker.upper()).first()
