import { useEffect, useRef } from "react";
import { ColorType, createChart } from "lightweight-charts";
import type { Candle } from "../types";

export default function PriceChart({ candles }: { candles: Candle[] }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || candles.length === 0) return;
    const chart = createChart(ref.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#8b9d90",
      },
      grid: {
        vertLines: { color: "rgba(228, 195, 106, 0.08)" },
        horzLines: { color: "rgba(228, 195, 106, 0.08)" },
      },
      rightPriceScale: { borderColor: "rgba(214, 186, 92, 0.2)" },
      timeScale: { borderColor: "rgba(214, 186, 92, 0.2)" },
      autoSize: true,
    });
    const series = chart.addCandlestickSeries({
      upColor: "#3ad89a",
      downColor: "#ff6b75",
      wickUpColor: "#3ad89a",
      wickDownColor: "#ff6b75",
      borderVisible: false,
    });
    series.setData(
      candles.map((c) => ({
        time: c.ts.slice(0, 10),
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      })),
    );
    chart.timeScale().fitContent();
    const observer = new ResizeObserver(() => chart.applyOptions({ autoSize: true }));
    observer.observe(ref.current);
    return () => {
      observer.disconnect();
      chart.remove();
    };
  }, [candles]);

  if (candles.length === 0) {
    return <div className="muted">Нет свечей. Откройте карточку ещё раз после синхронизации ISS.</div>;
  }
  return <div className="chart-box" ref={ref} />;
}
