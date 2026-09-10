import type { Macro } from "../types";
import { money, signedPct, tone } from "../format";

const TILES: Array<{
  key: keyof Macro;
  change?: keyof Macro;
  label: string;
  hint: string;
  digits: number;
  suffix?: string;
}> = [
  { key: "imoex", change: "imoex_change_pct", label: "IMOEX", hint: "Индекс Мосбиржи", digits: 1 },
  { key: "rtsi", change: "rtsi_change_pct", label: "RTSI", hint: "Индекс РТС, $", digits: 1 },
  { key: "usd_rub", change: "usd_rub_change_pct", label: "USD/RUB", hint: "Доллар", digits: 2 },
  { key: "cny_rub", change: "cny_rub_change_pct", label: "CNY/RUB", hint: "Юань", digits: 3 },
  { key: "rgbi", change: "rgbi_change_pct", label: "RGBI", hint: "Облигации ОФЗ", digits: 1 },
  { key: "cbr_key_rate", label: "Ставка ЦБ", hint: "Ключевая ставка", digits: 2, suffix: "%" },
];

export default function MacroStrip({ macro }: { macro: Macro | null }) {
  if (!macro) {
    return <div className="note">Макро ещё не подтянулось. Worker синхронизирует ISS и ЦБ.</div>;
  }
  return (
    <div className="macro-strip">
      {TILES.map((tile) => {
        const raw = macro[tile.key] as number | null;
        const change = tile.change ? (macro[tile.change] as number | null) : undefined;
        return (
          <div className="chip" key={tile.label}>
            <div className="kicker">{tile.hint}</div>
            <div className="label">{tile.label}</div>
            <div className="value">
              {raw == null ? "—" : `${money(raw, tile.digits)}${tile.suffix ?? ""}`}
            </div>
            {change !== undefined ? (
              <div className={tone(change)}>{signedPct(change)}</div>
            ) : (
              <div className="hint">официальный ориентир</div>
            )}
          </div>
        );
      })}
    </div>
  );
}
