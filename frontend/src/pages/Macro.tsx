import { useEffect, useState } from "react";
import { api } from "../api";
import MacroStrip from "../components/MacroStrip";
import type { Macro, NewsItem } from "../types";
import NewsList from "../components/NewsList";
import { relativeTime } from "../format";

export default function MacroPage() {
  const [macro, setMacro] = useState<Macro | null>(null);
  const [worldNews, setWorldNews] = useState<NewsItem[]>([]);

  useEffect(() => {
    document.title = "Макро — MOEX Analyst";
    api.macro().then(setMacro).catch(() => setMacro(null));
    api.news(true).then(setWorldNews).catch(() => setWorldNews([]));
  }, []);

  return (
    <div>
      <section className="hero" style={{ gridTemplateColumns: "1fr" }}>
        <div className="hero-copy">
          <h1>Фон, в котором торгуется рублёвый рынок.</h1>
          <p>
            Индексы Мосбиржи и РТС, доллар и юань, RGBI и ключевая ставка. Рядом — мировые заголовки BBC, чтобы
            сценарий по акции не смотрел только внутрь стакана.
          </p>
        </div>
      </section>
      {macro?.ts && <div className="count-pill" style={{ marginBottom: 12 }}>Снимок {relativeTime(macro.ts)}</div>}
      <MacroStrip macro={macro} />
      <div className="card">
        <h3>Мировые заголовки</h3>
        <NewsList items={worldNews} />
      </div>
    </div>
  );
}
