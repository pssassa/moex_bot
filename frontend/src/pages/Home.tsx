import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import MacroStrip from "../components/MacroStrip";
import type { Instrument, Macro } from "../types";
import { listingLabel, money, signedPct, tone } from "../format";

export default function HomePage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
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
        .instruments(query, 250)
        .then(setItems)
        .catch((err: Error) => setError(err.message));
    }, 220);
    return () => window.clearTimeout(handle);
  }, [query]);

  const priced = useMemo(() => items.filter((item) => item.last_close != null).length, [items]);
  const firstList = useMemo(() => items.filter((item) => item.list_level === 1).length, [items]);

  return (
    <div>
      <section className="hero">
        <div className="hero-copy">
          <h1>Российские акции, новости и спокойный ИИ-сценарий.</h1>
          <p>
            Только TQBR и эмитенты с ISIN RU. Котировки — с Московской биржи, фон — индексы, валюта и ставка ЦБ.
            Модель не обещает цену, а собирает картину дня.
          </p>
        </div>
        <div className="stats">
          <div className="stat">
            <span className="muted">В справочнике</span>
            <b>{items.length || "—"}</b>
          </div>
          <div className="stat">
            <span className="muted">С ценой закрытия</span>
            <b>{priced || "—"}</b>
          </div>
          <div className="stat">
            <span className="muted">Первый список</span>
            <b>{firstList || "—"}</b>
          </div>
          <div className="stat">
            <span className="muted">IMOEX за день</span>
            <b className={tone(macro?.imoex_change_pct)}>{signedPct(macro?.imoex_change_pct)}</b>
          </div>
        </div>
      </section>

      <MacroStrip macro={macro} />

      <div className="search-row">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Найти бумагу: SBER, Газпром, YDEX…"
        />
        <div className="count-pill">{items.length} бумаг</div>
      </div>
      {error && <div className="banner">{error}</div>}
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Тикер</th>
              <th>Компания</th>
              <th>Цена</th>
              <th>День</th>
              <th>Листинг</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.ticker} onClick={() => navigate(`/t/${item.ticker}`)}>
                <td>
                  <Link className="ticker" to={`/t/${item.ticker}`}>
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
                  <span className="badge">{listingLabel(item.list_level)}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {items.length === 0 && <div className="empty">Ничего не нашлось. Смените запрос или дождитесь синка TQBR.</div>}
      </div>
    </div>
  );
}
