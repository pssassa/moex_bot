import type { NewsItem } from "../types";
import { Link } from "react-router-dom";
import { relativeTime } from "../format";

export default function NewsList({ items }: { items: NewsItem[] }) {
  if (items.length === 0) {
    return <div className="empty">Пока нет заголовков. Подождите ближайший цикл RSS.</div>;
  }
  return (
    <div>
      {items.map((item) => (
        <article className="news-item" key={item.id}>
          <div className="news-meta">
            <span className="badge">{item.source}</span>
            {item.is_world && <span className="badge">мир</span>}
            {item.published_at && <span>{relativeTime(item.published_at)}</span>}
          </div>
          <a href={item.url} target="_blank" rel="noreferrer">
            {item.title}
          </a>
          {item.tickers.length > 0 && (
            <div className="tags">
              {item.tickers.map((ticker) => (
                <Link className="tag" key={ticker} to={`/t/${ticker}`}>
                  {ticker}
                </Link>
              ))}
            </div>
          )}
        </article>
      ))}
    </div>
  );
}
