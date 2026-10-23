import * as echarts from "echarts";
// @ts-expect-error: the locale file has no typings
import langPT from "echarts/lib/i18n/langPT-br.js";
import { useEffect, useRef } from "react";
import { useStore } from "../store";
import { registerThemes } from "../theme";

type Handler = (params: any) => void;

echarts.registerLocale("PT-br", langPT); // month and day names of the time axes, the toolbox

interface Props {
  option: echarts.EChartsOption;
  height?: number | string;
  onClick?: Handler;
  className?: string;
}

/** An ECharts canvas that follows the theme, resizes with its box and animates option changes. */
export function Chart({ option, height = 280, onClick, className }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  const theme = useStore((s) => s.theme);
  const lang = useStore((s) => s.lang);
  const click = useRef<Handler | undefined>(onClick);
  click.current = onClick;

  useEffect(() => {
    registerThemes();
    const c = echarts.init(box.current!, theme === "dark" ? "report-dark" : "report-light", { locale: lang === "pt" ? "PT-br" : "EN" });
    chart.current = c;
    c.on("click", (p) => click.current?.(p));
    const ro = new ResizeObserver(() => c.resize({ animation: { duration: 200 } }));
    ro.observe(box.current!);
    return () => {
      ro.disconnect();
      c.dispose();
      chart.current = null;
    };
  }, [theme, lang]);

  useEffect(() => {
    // series keep their ids across updates, so a cross-filter or a slicer animates instead of redrawing
    chart.current?.setOption(option, { replaceMerge: ["series", "xAxis", "yAxis", "dataZoom", "visualMap", "calendar", "polar", "angleAxis", "radiusAxis"] });
  }, [option, theme, lang]);

  return <div ref={box} className={className} style={{ width: "100%", height }} />;
}
