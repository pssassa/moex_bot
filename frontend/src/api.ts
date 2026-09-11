import type { Candle, Forecast, Health, Instrument, Macro, NewsItem } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (response.status === 204) {
    return null as T;
  }
  const text = await response.text();
  if (!text) return null as T;
  return JSON.parse(text) as T;
}

export const api = {
  health: () => request<Health>("/api/health"),
  instruments: (q = "", limit = 400, kind?: string) => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (q.trim()) params.set("q", q.trim());
    if (kind) params.set("kind", kind);
    return request<Instrument[]>(`/api/instruments?${params}`);
  },
  instrument: (ticker: string) => request<Instrument>(`/api/instruments/${ticker}`),
  candles: (ticker: string) => request<Candle[]>(`/api/instruments/${ticker}/candles`),
  instrumentNews: (ticker: string) => request<NewsItem[]>(`/api/instruments/${ticker}/news`),
  news: (world?: boolean) => {
    const params = world === undefined ? "" : `?world=${world}`;
    return request<NewsItem[]>(`/api/news${params}`);
  },
  macro: () => request<Macro | null>("/api/macro"),
  macroHistory: () => request<Macro[]>("/api/macro/history"),
  latestForecast: (ticker: string) => request<Forecast | null>(`/api/instruments/${ticker}/forecast`),
  createForecast: (ticker: string, force = false) =>
    request<Forecast>(`/api/instruments/${ticker}/forecast?force=${force}`, { method: "POST" }),
};
