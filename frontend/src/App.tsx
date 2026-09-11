import { Link, NavLink, Route, Routes } from "react-router-dom";
import { useEffect, useState } from "react";
import HomePage from "./pages/Home";
import InstrumentPage from "./pages/Instrument";
import NewsPage from "./pages/News";
import MacroPage from "./pages/Macro";
import { api } from "./api";
import { mskNow, relativeTime } from "./format";
import type { Health } from "./types";

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [clock, setClock] = useState(mskNow);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
    const id = window.setInterval(() => setClock(mskNow()), 30000);
    return () => window.clearInterval(id);
  }, []);

  return (
    <div className="shell">
      <header className="topbar">
        <Link to="/" className="brand">
          <div className="logo-mark">М</div>
          <div>
            <strong>MOEX ANALYST</strong>
            <span>акции · фонды · металлы · ИИ</span>
          </div>
        </Link>
        <div style={{ display: "flex", alignItems: "center" }}>
          <div className="clock">{clock} МСК</div>
          <nav>
            <NavLink to="/" end>
              Рынок
            </NavLink>
            <NavLink to="/news">Новости</NavLink>
            <NavLink to="/macro">Макро</NavLink>
          </nav>
        </div>
      </header>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/t/:ticker" element={<InstrumentPage />} />
        <Route path="/news" element={<NewsPage />} />
        <Route path="/macro" element={<MacroPage />} />
      </Routes>
      <footer className="status">
        <span className="badge">
          <i className={`dot ${health?.status === "ok" ? "" : "off"}`} />
          API {health?.status ?? "нет связи"}
        </span>
        <span className="badge">
          <i className={`dot ${health?.database === "ok" ? "" : "off"}`} />
          БД {health?.database ?? "—"}
        </span>
        <span className="badge">
          <i className={`dot ${health?.hf_configured ? "" : "off"}`} />
          {health?.hf_configured ? "Hugging Face подключён" : "нет HF_TOKEN"}
        </span>
        {health?.sync?.instruments && (
          <span className="badge">Справочник {relativeTime(health.sync.instruments)}</span>
        )}
        {health?.sync?.news && <span className="badge">Новости {relativeTime(health.sync.news)}</span>}
      </footer>
    </div>
  );
}
