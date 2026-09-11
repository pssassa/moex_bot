from datetime import datetime

from pydantic import BaseModel


class InstrumentOut(BaseModel):
    ticker: str
    shortname: str
    name: str | None = None
    isin: str
    list_level: int | None = None
    lot_size: int | None = None
    emitent_title: str | None = None
    sec_type: str | None = None
    kind: str = "share"
    board: str | None = None
    last_close: float | None = None
    last_change_pct: float | None = None
    last_candle_at: datetime | None = None

    model_config = {"from_attributes": True}


class CandleOut(BaseModel):
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None


class NewsOut(BaseModel):
    id: int
    source: str
    title: str
    url: str
    published_at: datetime | None = None
    summary: str | None = None
    is_world: bool
    tickers: list[str] = []

    model_config = {"from_attributes": True}


class MacroOut(BaseModel):
    ts: datetime
    imoex: float | None = None
    imoex_change_pct: float | None = None
    rtsi: float | None = None
    rtsi_change_pct: float | None = None
    usd_rub: float | None = None
    usd_rub_change_pct: float | None = None
    cny_rub: float | None = None
    cny_rub_change_pct: float | None = None
    rgbi: float | None = None
    rgbi_change_pct: float | None = None
    cbr_key_rate: float | None = None

    model_config = {"from_attributes": True}


class PathPoint(BaseModel):
    t: int
    change_pct: float


class ForecastOut(BaseModel):
    id: int
    ticker: str
    created_at: datetime
    direction: str
    confidence: float | None = None
    thesis: str
    news_factors: str | None = None
    macro_factors: str | None = None
    risks: str | None = None
    chart_analysis: str | None = None
    news_alignment: str | None = None
    news_vs_chart: str | None = None
    expected_change_pct: float | None = None
    range_low_pct: float | None = None
    range_high_pct: float | None = None
    horizon_days: int | None = None
    spot_price: float | None = None
    path: list[PathPoint] = []
    model: str | None = None

    model_config = {"from_attributes": True}


class HealthOut(BaseModel):
    status: str
    database: str
    hf_configured: bool
    sync: dict[str, str | None]
