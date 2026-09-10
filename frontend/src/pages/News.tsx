import { useEffect, useState } from "react";
import { api } from "../api";
import NewsList from "../components/NewsList";
import type { NewsItem } from "../types";

export default function NewsPage() {
  const [items, setItems] = useState<NewsItem[]>([]);
  const [world, setWorld] = useState<boolean | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    document.title = "Новости — MOEX Analyst";
    api
      .news(world)
      .then(setItems)
      .catch((err: Error) => setError(err.message));
  }, [world]);

  return (
    <div>
      <section className="hero" style={{ gridTemplateColumns: "1fr" }}>
        <div className="hero-copy">
          <h1>Лента, которая влияет на российские бумаги.</h1>
          <p>
            Россия — ТАСС, Интерфакс, РБК, Коммерсантъ, Ведомости, Лента, РИА и MOEX. Мир — BBC World.
            Тикеры в карточке появляются, если название эмитента есть в заголовке.
          </p>
        </div>
      </section>
      <div className="seg">
        <button className={world === undefined ? "btn" : "btn ghost"} onClick={() => setWorld(undefined)}>
          Все
        </button>
        <button className={world === false ? "btn" : "btn ghost"} onClick={() => setWorld(false)}>
          Россия
        </button>
        <button className={world === true ? "btn" : "btn ghost"} onClick={() => setWorld(true)}>
          Мир
        </button>
      </div>
      {error && <div className="banner">{error}</div>}
      <div className="card">
        <div className="muted" style={{ marginBottom: 8 }}>
          {items.length} материалов
        </div>
        <NewsList items={items} />
      </div>
    </div>
  );
}
