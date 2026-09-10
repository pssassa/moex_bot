import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import PriceChart from "../components/Chart";
import ForecastCard from "../components/ForecastCard";
import NewsList from "../components/NewsList";
import type { Candle, Forecast, Instrument, NewsItem } from "../types";
import { listingLabel, money, relativeTime, ret, signedPct, tone } from "../format";

export default function InstrumentPage() {
  const { ticker = "" } = useParams();
  const code = ticker.toUpperCase();
  const [info, setInfo] = useState<Instrument | null>(null);
  const [candles, setCandles] = useState<Candle[]>([]);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [loadingForecast, setLoadingForecast] = useState(false);
  const [loadingChart, setLoadingChart] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forecastError, setForecastError] = useState<string | null>(null);

  useEffect(() => {
    document.title = `${code} — MOEX Analyst`;
    setError(null);
    setLoadingChart(true);
    api.instrument(code).then(setInfo).catch((err: Error) => setError(err.message));
    api
      .candles(code)
      .then(setCandles)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoadingChart(false));
    api.instrumentNews(code).then(setNews).catch(() => setNews([]));
    api.latestForecast(code).then(setForecast).catch(() => setForecast(null));
  }, [code]);

  const snapshot = useMemo(() => {
    const last = candles[candles.length - 1];
    const window = candles.slice(-60);
    const high = window.length ? Math.max(...window.map((c) => c.high)) : null;
    const low = window.length ? Math.min(...window.map((c) => c.low)) : null;
    return {
      price: last?.close ?? info?.last_close ?? null,
      day: ret(candles, 1) ?? info?.last_change_pct,
      week: ret(candles, 5),
      month: ret(candles, 20),
      high,
      low,
      volume: last?.volume ?? null,
      from: candles[0]?.ts,
      to: last?.ts,
    };
  }, [candles, info]);

  const generate = () => {
    setLoadingForecast(true);
    setForecastError(null);
    api
      .createForecast(code, Boolean(forecast))
      .then(setForecast)
      .catch((err: Error) => setForecastError(err.message))
      .finally(() => setLoadingForecast(false));
  };

  return (
    <div>
      <div className="crumb">
        <Link to="/">Рынок</Link> / {code}
      </div>
      {error && <div className="banner">{error}</div>}
      {info && (
        <div className="card paper-head">
          <div>
            <div className="ticker">{info.ticker}</div>
            <h1>{info.shortname}</h1>
            <div className="meta-row">
              <span className="badge">{listingLabel(info.list_level)}</span>
              <span className="badge">TQBR</span>
              {info.lot_size != null && <span className="badge">лот {info.lot_size}</span>}
              <span className="badge">{info.isin}</span>
            </div>
            {info.name && <p className="muted">{info.name}</p>}
          </div>
          <div style={{ textAlign: "right" }}>
            <div className="muted">Последняя цена</div>
            <div className={`price-xl ${tone(snapshot.day)}`}>{money(snapshot.price, 4)}</div>
            <div className={tone(snapshot.day)}>{signedPct(snapshot.day)} за день</div>
          </div>
        </div>
      )}

      <div className="kpi-row">
        <div className="kpi">
          <span>5 дней</span>
          <b className={tone(snapshot.week)}>{signedPct(snapshot.week)}</b>
        </div>
        <div className="kpi">
          <span>20 дней</span>
          <b className={tone(snapshot.month)}>{signedPct(snapshot.month)}</b>
        </div>
        <div className="kpi">
          <span>Макс. 60 дней</span>
          <b>{money(snapshot.high, 4)}</b>
        </div>
        <div className="kpi">
          <span>Мин. 60 дней</span>
          <b>{money(snapshot.low, 4)}</b>
        </div>
      </div>

      <div className="grid-2" style={{ marginTop: 16 }}>
        <div className="card">
          <h3>Дневной график</h3>
          {loadingChart ? (
            <div className="empty">Загружаю свечи с ISS…</div>
          ) : (
            <PriceChart candles={candles} />
          )}
          {snapshot.volume != null && (
            <div className="muted" style={{ marginTop: 10 }}>
              Объём последней сессии: {money(snapshot.volume, 0)}
              {snapshot.to ? ` · ${relativeTime(snapshot.to)}` : ""}
            </div>
          )}
        </div>
        <ForecastCard forecast={forecast} loading={loadingForecast} error={forecastError} onGenerate={generate} />
      </div>

      <div className="note" style={{ marginTop: 16 }}>
        ИИ собирает сценарий, а не гарантию результата. Сделки и убытки — ваша ответственность. Данные: MOEX ISS, RSS, ЦБ, Hugging Face.
      </div>

      <div className="card">
        <h3>Новости по эмитенту</h3>
        <NewsList items={news} />
      </div>
    </div>
  );
}
