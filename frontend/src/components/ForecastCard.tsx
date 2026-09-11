import type { Candle, Forecast } from "../types";
import { signedPct } from "../format";
import PathChart from "./PathChart";

const DIRECTION: Record<string, string> = {
  up: "Сценарий роста",
  down: "Сценарий снижения",
  sideways: "Боковой сценарий",
};

const ALIGNMENT: Record<string, string> = {
  confirm: "График и новости совпадают",
  contradict: "Новости спорят с графиком",
  mixed: "Смешанный фон",
};

export default function ForecastCard({
  forecast,
  candles,
  loading,
  error,
  onGenerate,
}: {
  forecast: Forecast | null;
  candles: Candle[];
  loading: boolean;
  error: string | null;
  onGenerate: () => void;
}) {
  const toneClass = forecast?.direction === "up" ? "up" : forecast?.direction === "down" ? "down" : "side";
  const confidence = forecast?.confidence != null ? Math.round(forecast.confidence * 100) : null;
  const horizon = forecast?.horizon_days ?? 5;
  const hasPath = Boolean(forecast?.path?.length && (forecast.spot_price != null || candles.length));

  return (
    <div className="card forecast">
      <h3>ИИ-сценарий</h3>
      <p className="muted" style={{ marginTop: 0 }}>
        Сначала разбор дневного графика, затем сверка с новостями и макро. Ожидаемый ход на {horizon} сессий —
        сценарий, не целевая цена и не рекомендация к сделке.
      </p>
      {forecast && (
        <>
          <div className={`direction ${toneClass}`}>{DIRECTION[forecast.direction] ?? forecast.direction}</div>
          {forecast.expected_change_pct != null && (
            <div className="outlook">
              <div>
                <span>Ожидаемо за {horizon} сессий</span>
                <b className={toneClass}>{signedPct(forecast.expected_change_pct)}</b>
              </div>
              <div>
                <span>Коридор</span>
                <b>
                  {signedPct(forecast.range_low_pct)} … {signedPct(forecast.range_high_pct)}
                </b>
              </div>
            </div>
          )}
          {hasPath && <PathChart candles={candles} forecast={forecast} />}
          {forecast.news_vs_chart && (
            <div className={`align-pill ${forecast.news_vs_chart}`}>
              {ALIGNMENT[forecast.news_vs_chart] ?? forecast.news_vs_chart}
            </div>
          )}
          {confidence != null && (
            <>
              <div className="muted">Уверенность модели {confidence}%</div>
              <div className="bar">
                <i style={{ width: `${confidence}%` }} />
              </div>
            </>
          )}
          {forecast.chart_analysis && (
            <div className="factor">
              <h4>График</h4>
              <p>{forecast.chart_analysis}</p>
            </div>
          )}
          {forecast.news_alignment && (
            <div className="factor">
              <h4>Сверка с новостями</h4>
              <p>{forecast.news_alignment}</p>
            </div>
          )}
          <p>{forecast.thesis}</p>
          {forecast.news_factors && (
            <div className="factor">
              <h4>Новости</h4>
              <p>{forecast.news_factors}</p>
            </div>
          )}
          {forecast.macro_factors && (
            <div className="factor">
              <h4>Макро и мир</h4>
              <p>{forecast.macro_factors}</p>
            </div>
          )}
          {forecast.risks && (
            <div className="factor">
              <h4>Риски</h4>
              <p>{forecast.risks}</p>
            </div>
          )}
          <div className="muted" style={{ margin: "12px 0" }}>
            {forecast.model} · {new Date(forecast.created_at).toLocaleString("ru-RU")}
          </div>
        </>
      )}
      {error && <div className="banner">{error}</div>}
      <button className="btn" disabled={loading} onClick={onGenerate}>
        {loading ? "Модель думает…" : forecast ? "Обновить сценарий" : "Построить сценарий"}
      </button>
    </div>
  );
}
