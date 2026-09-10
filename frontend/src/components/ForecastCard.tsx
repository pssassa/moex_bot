import type { Forecast } from "../types";

const DIRECTION: Record<string, string> = {
  up: "Сценарий роста",
  down: "Сценарий снижения",
  sideways: "Боковой сценарий",
};

export default function ForecastCard({
  forecast,
  loading,
  error,
  onGenerate,
}: {
  forecast: Forecast | null;
  loading: boolean;
  error: string | null;
  onGenerate: () => void;
}) {
  const toneClass = forecast?.direction === "up" ? "up" : forecast?.direction === "down" ? "down" : "side";
  const confidence = forecast?.confidence != null ? Math.round(forecast.confidence * 100) : null;

  return (
    <div className="card forecast">
      <h3>ИИ-сценарий</h3>
      <p className="muted" style={{ marginTop: 0 }}>
        Оценка по дневным свечам, новостям эмитента и макрофону. Это не целевая цена и не рекомендация к сделке.
      </p>
      {forecast && (
        <>
          <div className={`direction ${toneClass}`}>{DIRECTION[forecast.direction] ?? forecast.direction}</div>
          {confidence != null && (
            <>
              <div className="muted">Уверенность модели {confidence}%</div>
              <div className="bar">
                <i style={{ width: `${confidence}%` }} />
              </div>
            </>
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
