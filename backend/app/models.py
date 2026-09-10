from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Table, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

news_instruments = Table(
    "news_instruments",
    Base.metadata,
    Column("news_id", ForeignKey("news.id", ondelete="CASCADE"), primary_key=True),
    Column("instrument_id", ForeignKey("instruments.id", ondelete="CASCADE"), primary_key=True),
)


class Instrument(Base):
    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    shortname: Mapped[str] = mapped_column(String(255))
    name: Mapped[str | None] = mapped_column(String(512))
    isin: Mapped[str] = mapped_column(String(32), index=True)
    is_russian: Mapped[bool] = mapped_column(Boolean, default=True)
    board: Mapped[str] = mapped_column(String(16), default="TQBR")
    currency: Mapped[str] = mapped_column(String(8), default="SUR")
    list_level: Mapped[int | None] = mapped_column(Integer)
    lot_size: Mapped[int | None] = mapped_column(Integer)
    emitent_title: Mapped[str | None] = mapped_column(String(512))
    sec_type: Mapped[str | None] = mapped_column(String(64))
    last_close: Mapped[float | None] = mapped_column(Float)
    last_change_pct: Mapped[float | None] = mapped_column(Float)
    last_candle_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=func.now())

    candles: Mapped[list["Candle"]] = relationship(back_populates="instrument")
    forecasts: Mapped[list["Forecast"]] = relationship(back_populates="instrument")


class Candle(Base):
    __tablename__ = "candles"
    __table_args__ = (
        UniqueConstraint("instrument_id", "timeframe", "ts", name="uq_candles_inst_tf_ts"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"), index=True)
    timeframe: Mapped[str] = mapped_column(String(8))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float | None] = mapped_column(Float)
    value: Mapped[float | None] = mapped_column(Float)

    instrument: Mapped[Instrument] = relationship(back_populates="candles")


class MacroSnapshot(Base):
    __tablename__ = "macro_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    imoex: Mapped[float | None] = mapped_column(Float)
    imoex_change_pct: Mapped[float | None] = mapped_column(Float)
    rtsi: Mapped[float | None] = mapped_column(Float)
    rtsi_change_pct: Mapped[float | None] = mapped_column(Float)
    usd_rub: Mapped[float | None] = mapped_column(Float)
    usd_rub_change_pct: Mapped[float | None] = mapped_column(Float)
    cny_rub: Mapped[float | None] = mapped_column(Float)
    cny_rub_change_pct: Mapped[float | None] = mapped_column(Float)
    rgbi: Mapped[float | None] = mapped_column(Float)
    rgbi_change_pct: Mapped[float | None] = mapped_column(Float)
    cbr_key_rate: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(64), default="iss")


class NewsItem(Base):
    __tablename__ = "news"
    __table_args__ = (UniqueConstraint("url", name="uq_news_url"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(1024))
    url: Mapped[str] = mapped_column(String(1024))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    summary: Mapped[str | None] = mapped_column(Text)
    lang: Mapped[str] = mapped_column(String(8), default="ru")
    is_world: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    instruments: Mapped[list[Instrument]] = relationship(secondary=news_instruments)


class Forecast(Base):
    __tablename__ = "forecasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), index=True)
    direction: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[float | None] = mapped_column(Float)
    thesis: Mapped[str] = mapped_column(Text)
    news_factors: Mapped[str | None] = mapped_column(Text)
    macro_factors: Mapped[str | None] = mapped_column(Text)
    risks: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(String(128))
    raw_json: Mapped[str | None] = mapped_column(Text)

    instrument: Mapped[Instrument] = relationship(back_populates="forecasts")


class SyncState(Base):
    __tablename__ = "sync_state"

    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    last_ok_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    detail: Mapped[str | None] = mapped_column(String(255))
