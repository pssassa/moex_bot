export function money(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toLocaleString("ru-RU", {
    minimumFractionDigits: value >= 1000 ? 0 : Math.min(digits, 2),
    maximumFractionDigits: digits,
  });
}

export function signedPct(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}%`;
}

export function tone(value: number | null | undefined): "up" | "down" | "side" {
  if (value === null || value === undefined || value === 0) return "side";
  return value > 0 ? "up" : "down";
}

export function listingLabel(level: number | null | undefined): string {
  if (level === 1) return "1 котировка";
  if (level === 2) return "2 котировка";
  if (level === 3) return "3 котировка";
  return "вне списка";
}

export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const delta = Date.now() - then;
  const mins = Math.round(delta / 60000);
  if (mins < 1) return "только что";
  if (mins < 60) return `${mins} мин назад`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours} ч назад`;
  const days = Math.round(hours / 24);
  if (days < 14) return `${days} дн. назад`;
  return new Date(iso).toLocaleString("ru-RU", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function mskNow(): string {
  return new Date().toLocaleString("ru-RU", {
    timeZone: "Europe/Moscow",
    weekday: "short",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function ret(candles: { close: number }[], bars: number): number | null {
  if (candles.length <= bars) return null;
  const last = candles[candles.length - 1].close;
  const prev = candles[candles.length - 1 - bars].close;
  if (!prev) return null;
  return (last / prev - 1) * 100;
}
