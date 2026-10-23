// Colours and the chart themes: a report palette in the spirit of business dashboards (clean white visuals on a
// grey canvas, one strong colour per meaning), in light and dark.
import * as echarts from "echarts";

export const C = {
  generation: "#E66C37",
  consumption: "#118DFF",
  grid: "#12239E",
  export: "#1AAB40",
  self: "#D9B300",
  forecast: "#744EC2",
  savings: "#1AAB40",
  withoutPv: "#A19F9D",
  measured: "#3B3A39",
  accent: "#118DFF",
  warn: "#D64550",
  teal: "#197278",
  pink: "#E044A7",
  purple: "#6B007B",
};

export const PALETTE = [C.consumption, C.generation, C.forecast, C.grid, C.pink, C.self, C.teal, C.warn, C.purple, C.export];

export const CONFIDENCE: Record<string, string> = {
  high: "#1AAB40",
  medium: "#D9B300",
  low: "#E66C37",
  "seasonal only": "#A19F9D",
  "typical week": "#118DFF",
};

const FONT = '"Segoe UI", "Segoe UI Web (West European)", -apple-system, BlinkMacSystemFont, Roboto, "Helvetica Neue", sans-serif';

function theme(dark: boolean) {
  const text = dark ? "#D2D0CE" : "#605E5C";
  const strong = dark ? "#F3F2F1" : "#252423";
  const line = dark ? "#3B3A39" : "#E1DFDD";
  const split = dark ? "#2D2C2B" : "#EDEBE9";
  const axis = {
    axisLine: { show: true, lineStyle: { color: line } },
    axisTick: { show: false },
    axisLabel: { color: text, fontSize: 11 },
    splitLine: { show: true, lineStyle: { color: split, type: "dashed" } },
    nameTextStyle: { color: text, fontSize: 11 },
  };
  return {
    color: PALETTE,
    backgroundColor: "transparent",
    textStyle: { fontFamily: FONT, color: text },
    title: { textStyle: { color: strong, fontFamily: FONT } },
    legend: { textStyle: { color: text, fontSize: 11 }, itemWidth: 12, itemHeight: 8, icon: "roundRect" },
    tooltip: {
      backgroundColor: dark ? "#252423" : "#FFFFFF",
      borderColor: line,
      borderWidth: 1,
      textStyle: { color: strong, fontSize: 12, fontFamily: FONT },
      extraCssText: "box-shadow: 0 6px 18px rgba(0,0,0,.18); border-radius: 4px;",
    },
    categoryAxis: { ...axis, splitLine: { show: false } },
    valueAxis: { ...axis, axisLine: { show: false } },
    timeAxis: { ...axis, splitLine: { show: false } },
    logAxis: axis,
    dataZoom: {
      borderColor: line,
      fillerColor: dark ? "rgba(17,141,255,.18)" : "rgba(17,141,255,.12)",
      handleStyle: { color: C.accent, borderColor: C.accent },
      moveHandleStyle: { color: C.accent },
      textStyle: { color: text },
      dataBackground: { lineStyle: { color: line }, areaStyle: { color: split } },
    },
    calendar: {
      itemStyle: { color: dark ? "#252423" : "#FAF9F8", borderColor: dark ? "#1B1A19" : "#FFFFFF", borderWidth: 2 },
      splitLine: { show: false },
      dayLabel: { color: text, fontSize: 10 },
      monthLabel: { color: text, fontSize: 11 },
      yearLabel: { show: false },
    },
    gauge: { title: { color: text }, detail: { color: strong } },
  };
}

let registered = false;
export function registerThemes() {
  if (registered) return;
  echarts.registerTheme("report-light", theme(false));
  echarts.registerTheme("report-dark", theme(true));
  registered = true;
}

/** An rgba() of a hex colour. */
export function alpha(hex: string, a: number): string {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}

// what every chart shares: the site's wall clock (format.ts), a calm entrance animation
export const BASE = {
  useUTC: true,
  animationDuration: 900,
  animationEasing: "cubicOut",
  animationDurationUpdate: 600,
  animationEasingUpdate: "cubicInOut",
  grid: { left: 8, right: 16, top: 36, bottom: 8, containLabel: true },
};
