export type Instrument = {
  ticker: string;
  shortname: string;
  name: string | null;
  isin: string;
  list_level: number | null;
  lot_size: number | null;
  emitent_title: string | null;
  sec_type: string | null;
  kind: "share" | "fund" | "metal" | string;
  board: string | null;
  last_close: number | null;
  last_change_pct: number | null;
  last_candle_at: string | null;
};

export type Candle = {
  ts: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number | null;
};

export type NewsItem = {
  id: number;
  source: string;
  title: string;
  url: string;
  published_at: string | null;
  summary: string | null;
  is_world: boolean;
  tickers: string[];
};

export type Macro = {
  ts: string;
  imoex: number | null;
  imoex_change_pct: number | null;
  rtsi: number | null;
  rtsi_change_pct: number | null;
  usd_rub: number | null;
  usd_rub_change_pct: number | null;
  cny_rub: number | null;
  cny_rub_change_pct: number | null;
  rgbi: number | null;
  rgbi_change_pct: number | null;
  cbr_key_rate: number | null;
};

export type PathPoint = {
  t: number;
  change_pct: number;
};

export type Forecast = {
  id: number;
  ticker: string;
  created_at: string;
  direction: "up" | "down" | "sideways" | string;
  confidence: number | null;
  thesis: string;
  news_factors: string | null;
  macro_factors: string | null;
  risks: string | null;
  chart_analysis: string | null;
  news_alignment: string | null;
  news_vs_chart: "confirm" | "contradict" | "mixed" | string | null;
  expected_change_pct: number | null;
  range_low_pct: number | null;
  range_high_pct: number | null;
  horizon_days: number | null;
  spot_price: number | null;
  path: PathPoint[];
  model: string | null;
};

export type Health = {
  status: string;
  database: string;
  hf_configured: boolean;
  sync: Record<string, string | null>;
};
