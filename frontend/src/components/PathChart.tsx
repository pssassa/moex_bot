import { useEffect, useRef } from "react";
import { ColorType, LineStyle, createChart } from "lightweight-charts";
import type { Candle, Forecast } from "../types";
import { nextWeekdays } from "../format";

export default function PathChart({
  candles,
  forecast,
}: {
  candles: Candle[];
  forecast: Forecast;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const path = forecast.path ?? [];
  const last = candles[candles.length - 1];
  const spot = forecast.spot_price ?? last?.close ?? null;
  const lastDay = (last?.ts || forecast.created_at || "").slice(0, 10);

  useEffect(() => {
    if (!ref.current || spot == null || !lastDay || path.length === 0) return;
    const history = candles.slice(-16).map((c) => ({
      time: c.ts.slice(0, 10) as `${number}-${number}-${number}`,
      value: c.close,
    }));
    if (history.length === 0) {
      history.push({ time: lastDay as `${number}-${number}-${number}`, value: spot });
    } else {
      history[history.length - 1] = {
        time: history[history.length - 1].time,
        value: spot,
      };
    }
    const futureDays = nextWeekdays(lastDay, path.length);
    const future = path.map((point, index) => ({
      time: (futureDays[index] ?? lastDay) as `${number}-${number}-${number}`,
      value: spot * (1 + point.change_pct / 100),
    }));
    const forecastLine = [
      { time: history[history.length - 1].time, value: spot },
      ...future,
    ];
    const horizon = Math.max(path.length, 1);
    const low = forecast.range_low_pct ?? path[path.length - 1]?.change_pct ?? 0;
    const high = forecast.range_high_pct ?? path[path.length - 1]?.change_pct ?? 0;
    const bandLow = [
      { time: history[history.length - 1].time, value: spot },
      ...future.map((point, index) => ({
        time: point.time,
        value: spot * (1 + (low * (index + 1)) / horizon / 100),
      })),
    ];
    const bandHigh = [
      { time: history[history.length - 1].time, value: spot },
      ...future.map((point, index) => ({
        time: point.time,
        value: spot * (1 + (high * (index + 1)) / horizon / 100),
      })),
    ];
    const tone =
      forecast.direction === "down" ? "#ff6b75" : forecast.direction === "up" ? "#3ad89a" : "#e4c36a";

    const chart = createChart(ref.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#8b9d90",
      },
      grid: {
        vertLines: { color: "rgba(228, 195, 106, 0.08)" },
        horzLines: { color: "rgba(228, 195, 106, 0.08)" },
      },
      rightPriceScale: { borderColor: "rgba(214, 186, 92, 0.2)", scaleMargins: { top: 0.12, bottom: 0.12 } },
      timeScale: { borderColor: "rgba(214, 186, 92, 0.2)", fixLeftEdge: true, fixRightEdge: true },
      autoSize: true,
      handleScroll: false,
      handleScale: false,
    });
    const historySeries = chart.addLineSeries({
      color: "rgba(238, 243, 234, 0.78)",
      lineWidth: 2,
      lastValueVisible: false,
      priceLineVisible: false,
    });
    const forecastSeries = chart.addLineSeries({
      color: tone,
      lineWidth: 2,
      lineStyle: LineStyle.Dashed,
      lastValueVisible: true,
      priceLineVisible: false,
    });
    const lowSeries = chart.addLineSeries({
      color: "rgba(139, 157, 144, 0.45)",
      lineWidth: 1,
      lineStyle: LineStyle.Dotted,
      lastValueVisible: false,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
    });
    const highSeries = chart.addLineSeries({
      color: "rgba(139, 157, 144, 0.45)",
      lineWidth: 1,
      lineStyle: LineStyle.Dotted,
      lastValueVisible: false,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
    });
    historySeries.setData(history);
    forecastSeries.setData(forecastLine);
    lowSeries.setData(bandLow);
    highSeries.setData(bandHigh);
    chart.timeScale().fitContent();
    const observer = new ResizeObserver(() => chart.applyOptions({ autoSize: true }));
    observer.observe(ref.current);
    return () => {
      observer.disconnect();
      chart.remove();
    };
  }, [candles, forecast, lastDay, path, spot]);

  if (spot == null || path.length === 0) return null;
  return <div className="chart-box mini" ref={ref} />;
}
