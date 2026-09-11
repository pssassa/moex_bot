import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import MacroStrip from "../components/MacroStrip";
import type { Instrument, Macro } from "../types";
import { kindLabel, listingLabel, money, signedPct, tone } from "../format";

const KINDS = [
  { id: "", label: "Все" },
  { id: "share", label: "Акции" },
  { id: "fund", label: "Фонды" },
  { id: "metal", label: "Металлы" },
];

export default function HomePage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("");
  const [items, setItems] = useState<Instrument[]>([]);
  const [macro, setMacro] = useState<Macro | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    document.title = "Рынок — MOEX Analyst";
    api.macro().then(setMacro).catch(() => setMacro(null));
  }, []);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      api
        .instruments(query, 400)
        .then(setItems)
        .catch((err: Error) => setError(err.message));
    }, 220);
    return () => window.clearTimeout(handle);
  }, [query]);

  const visible = useMemo(
    () => (kind ? items.filter((item) => item.kind === kind) : items),
    [items, kind],
  );
  const shares = useMemo(() => items.filter((item) => item.kind === "share").length, [items]);
  const funds = useMemo(() => items.filter((item) => item.kind === "fund").length, [items]);
  const metals = useMemo(() => items.filter((item) => item.kind === "metal").length, [items]);

  return (
    <div>
      <section className="hero">
        <div className="hero-copy">
          <h1>Акции, фонды и металлы — с новостями и ИИ-сценарием.</h1>
          <p>
            Акции и биржевые фонды TQBR (ISIN RU), золото, серебро, платина и палладий — с валютного рынка MOEX.
            Модель разбирает график, сверяет его с новостями и даёт сценарий хода на 5 сессий — не целевую цену.
          </p>
        </div>
        <div className="stats">
          <div className="stat">
            <span className="muted">Акции</span>
            <b>{shares || "—"}</b>
          </div>
          <div className="stat">
            <span className="muted">Фонды</span>
            <b>{funds || "—"}</b>
          </div>
          <div className="stat">
            <span className="muted">Металлы</span>
            <b>{metals || "—"}</b>
          </div>
          <div className="stat">
            <span className="muted">IMOEX за день</span>
            <b className={tone(macro?.imoex_change_pct)}>{signedPct(macro?.imoex_change_pct)}</b>
          </div>
        </div>
      </section>

      <MacroStrip macro={macro} />

      <div className="seg">
        {KINDS.map((item) => (
          <button
            key={item.id || "all"}
            className={kind === item.id ? "btn" : "btn ghost"}
            onClick={() => setKind(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="search-row">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Найти: SBER, LQDT, золото…"
        />
        <div className="count-pill">{visible.length} бумаг</div>
      </div>
      {error && <div className="banner">{error}</div>}
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Тикер</th>
              <th>Название</th>
              <th>Цена</th>
              <th>День</th>
              <th>Класс</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((item) => (
              <tr key={item.ticker} onClick={() => navigate(`/t/${encodeURIComponent(item.ticker)}`)}>
                <td>
                  <Link className="ticker" to={`/t/${encodeURIComponent(item.ticker)}`}>
                    {item.ticker}
                  </Link>
                </td>
                <td>
                  <div className="company">
                    {item.shortname}
                    {item.name && item.name !== item.shortname && <small>{item.name}</small>}
                  </div>
                </td>
                <td className="mono">{money(item.last_close, 4)}</td>
                <td className={tone(item.last_change_pct)}>{signedPct(item.last_change_pct)}</td>
                <td>
                  <span className="badge">{kindLabel(item.kind)}</span>
                  {item.kind !== "metal" && (
                    <span className="badge" style={{ marginLeft: 6 }}>
                      {listingLabel(item.list_level)}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {visible.length === 0 && (
          <div className="empty">Ничего не нашлось. Смените фильтр или дождитесь синка справочника.</div>
        )}
      </div>
    </div>
  );
}
