import type { EChartsOption } from "echarts";
import { CalendarRange, Gauge, Sigma, Target } from "lucide-react";
import { useMemo } from "react";
import { Chart } from "../components/Chart";
import { Kpi } from "../components/Kpi";
import { Empty, Visual } from "../components/Visual";
import { date, dateTime, num, pct, wall } from "../format";
import { code } from "../i18n";
import { useStore, useT } from "../store";
import { alpha, BASE, C, LEGEND, PALETTE } from "../theme";
import type { CheckHour, Payload } from "../types";
import { niceCeil, NoteList, PageGrid, startingWith } from "./common";

// the report's note when the check could not run (prosumer.analysis, `Forecast check skipped: {reason}`)
export const SKIPPED = ["Forecast check skipped", "Conferência da previsão não feita"];

/** How well the forecast did on the last weeks of the file, against the reference and the other rules. */
export function Check({ payload }: { payload: Payload }) {
  const t = useT();
  const lang = useStore((s) => s.lang);
  const dark = useStore((s) => s.theme) === "dark";
  const r = payload.result;
  const s = r.report.summary;
  const rows = r.report.forecast;
  const out = s.output ?? "median";
  const ref = s.reference ?? "";
  const median = rows?.find((f) => f.forecast === out);
  const names = useMemo(() => (rows ?? []).map((f) => f.forecast), [rows]);
  const color = (name: string) => (name === out ? C.forecast : name === ref ? C.withoutPv : PALETTE[(names.indexOf(name) + 2) % PALETTE.length]);

  // ------------------------------------------------------------ skill of each forecast with its 95% CI
  const skillOption = useMemo<EChartsOption | null>(() => {
    if (!rows?.length) return null;
    const sorted = [...rows].sort((a, b) => (a.skill ?? -9) - (b.skill ?? -9));
    return {
      ...BASE,
      grid: { ...BASE.grid, top: 12, right: 44 },
      tooltip: {
        trigger: "item",
        formatter: (p: any) => {
          const f = sorted[p.dataIndex];
          return `<b>${code(lang, f.forecast)}</b><br/>${t("skillLbl")}: ${pct(lang, f.skill, 1)}<br/><span style="color:#888">95%: ${pct(lang, f.skill_ci_low, 1)} – ${pct(lang, f.skill_ci_high, 1)}</span>`;
        },
      },
      xAxis: { type: "value", axisLabel: { hideOverlap: true, formatter: (v: number) => pct(lang, v, 0) } },
      yAxis: { type: "category", data: sorted.map((f) => code(lang, f.forecast)), axisLabel: { width: 120, overflow: "break", lineHeight: 12 } },
      series: [
        {
          id: "skill",
          type: "bar",
          barWidth: "52%",
          data: sorted.map((f) => ({
            value: f.skill,
            itemStyle: { color: (f.skill ?? 0) < 0 && f.forecast !== out ? alpha(C.warn, 0.75) : color(f.forecast), borderRadius: (f.skill ?? 0) < 0 ? [2, 0, 0, 2] : [0, 2, 2, 0] },
          })),
          markLine: {
            silent: true,
            symbol: "none",
            lineStyle: { color: C.measured, type: "solid", width: 1.2 },
            label: { show: false }, // the subtitle says what 0 is
            data: [{ xAxis: 0 }],
          },
          animationDelay: (k: number) => k * 70,
        },
        {
          id: "ci",
          type: "custom",
          silent: true,
          z: 3,
          tooltip: { show: false },
          encode: { y: 0, x: [1, 2] },
          data: sorted.map((f, k) => [k, f.skill_ci_low, f.skill_ci_high, f.skill]),
          renderItem: (_params: any, api: any) => {
            if (api.value(1) == null || Number.isNaN(api.value(1))) return null;
            const [lo, y] = api.coord([api.value(1), api.value(0)]);
            const [hi] = api.coord([api.value(2), api.value(0)]);
            const cap = Math.min(6, api.size([0, 1])[1] * 0.18);
            const style = { stroke: dark ? "rgba(243,242,241,.55)" : alpha(C.measured, 0.7), lineWidth: 1.3 };
            return {
              type: "group",
              children: [
                { type: "line", shape: { x1: lo, y1: y, x2: hi, y2: y }, style },
                { type: "line", shape: { x1: lo, y1: y - cap, x2: lo, y2: y + cap }, style },
                { type: "line", shape: { x1: hi, y1: y - cap, x2: hi, y2: y + cap }, style },
                // the skill after the whisker's end: clear of the bar and of the line
                { type: "text", style: { text: pct(lang, api.value(3), 0), x: Math.max(hi, lo) + 6, y, align: "left", verticalAlign: "middle", fill: dark ? "#D2D0CE" : "#3B3A39", font: "600 10px Segoe UI, sans-serif" } },
              ],
              enterFrom: { style: { opacity: 0 } },
            } as any;
          },
        },
      ],
    };
  }, [rows, out, ref, dark, lang, t]);

  // ------------------------------------------------------------ skill of the median by resolution
  const res = useMemo(() => (r.report.resolution ?? []).filter((x) => x.forecast === out), [r.report.resolution, out]);
  const resOption = useMemo<EChartsOption | null>(() => {
    if (!res.length) return null;
    return {
      ...BASE,
      legend: { ...LEGEND },
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, valueFormatter: (v: any) => num(lang, v, 2) },
      xAxis: { type: "category", data: res.map((x) => code(lang, x.level)), axisLabel: { interval: 0, fontSize: 10.5, width: 58, overflow: "break", lineHeight: 13 } },
      yAxis: { type: "value" },
      series: [
        { id: "res-skill", name: t("skillLbl"), type: "bar", barGap: "15%", itemStyle: { color: C.forecast, borderRadius: [2, 2, 0, 0] }, data: res.map((x) => x.skill) },
        { id: "res-r2", name: `R² ${code(lang, out)}`, type: "bar", itemStyle: { color: alpha(C.accent, 0.8), borderRadius: [2, 2, 0, 0] }, data: res.map((x) => x.R2) },
        { id: "res-r2ref", name: `R² ${code(lang, ref)}`, type: "bar", itemStyle: { color: C.withoutPv, borderRadius: [2, 2, 0, 0] }, data: res.map((x) => x.R2_reference) },
      ],
    };
  }, [res, out, ref, lang, t]);

  // ------------------------------------------------------------ the test hours: measured and the forecasts
  const hours = useMemo(() => sumByHour(r.charts.check ?? [], names), [r.charts.check, names]);
  const lineOption = useMemo<EChartsOption | null>(() => {
    if (!hours.length) return null;
    return {
      ...BASE,
      grid: { ...BASE.grid, bottom: 44, top: 48 },
      legend: { ...LEGEND, selected: Object.fromEntries(names.filter((n) => n !== out).map((n) => [code(lang, n), false])) },
      tooltip: { trigger: "axis", valueFormatter: (v: any) => (v == null ? "–" : `${num(lang, v, 2)} kWh`) },
      xAxis: { type: "time" },
      yAxis: { type: "value", name: "kWh" },
      dataZoom: [{ type: "inside" }, { type: "slider", height: 18, bottom: 8 }],
      series: [
        {
          id: "y",
          name: t("measured"),
          type: "line",
          showSymbol: false,
          lineStyle: { width: 2.6, color: C.measured },
          itemStyle: { color: C.measured },
          areaStyle: { color: alpha(C.measured, 0.06) },
          data: hours.map((h) => [wall(h.ds), h.y]),
        },
        ...names.map((n) => ({
          id: `f-${n}`,
          name: code(lang, n),
          type: "line" as const,
          showSymbol: false,
          lineStyle: { width: n === out ? 2 : 1.2, color: color(n), type: n === ref ? ("dashed" as const) : ("solid" as const) },
          itemStyle: { color: color(n) },
          data: hours.map((h) => [wall(h.ds), h.f[n] ?? null]),
        })),
      ],
    };
  }, [hours, names, out, ref, lang, t]);

  // ------------------------------------------------------------ measured vs the median, each evaluated hour
  const scatterOption = useMemo<EChartsOption | null>(() => {
    const pts = (r.charts.check ?? []).filter((h) => h.evaluated && h.y != null && typeof h[out] === "number").map((h) => [h[out] as number, h.y as number, h.ds]);
    if (!pts.length) return null;
    const max = niceCeil(Math.max(...pts.map((p) => Math.max(p[0] as number, p[1] as number)), 1e-6) * 1.02);
    return {
      ...BASE,
      grid: { ...BASE.grid, top: 16, right: 20 },
      tooltip: {
        trigger: "item",
        formatter: (p: any) => `<b>${dateTime(lang, p.value[2])}</b><br/>${t("measured")}: ${num(lang, p.value[1], 2)} kWh<br/>${code(lang, out)}: ${num(lang, p.value[0], 2)} kWh`,
      },
      xAxis: { type: "value", name: code(lang, out), nameLocation: "middle", nameGap: 26, min: 0, max, splitLine: { show: false } },
      yAxis: { type: "value", name: t("measured"), min: 0, max },
      series: [
        {
          id: "pts",
          type: "scatter",
          symbolSize: 5,
          large: pts.length > 2000,
          itemStyle: { color: alpha(C.forecast, 0.45) },
          data: pts,
        },
        {
          id: "diag",
          type: "line",
          silent: true,
          symbol: "none",
          lineStyle: { color: C.measured, type: "dashed", width: 1 },
          data: [
            [0, 0],
            [max, max],
          ],
        },
      ],
    };
  }, [r.charts.check, out, lang, t]);

  if (!rows) {
    const why = startingWith(r.report.notes, SKIPPED);
    return (
      <PageGrid>
        <Visual title={t("page_check")} className="col-span-12">
          <div className="space-y-3 py-2">
            <p className="text-[13px] font-semibold text-ink">{t("checkSkipped")}</p>
            <NoteList notes={why.length ? why : r.report.notes} />
          </div>
        </Visual>
      </PageGrid>
    );
  }

  const metricCols = [
    { key: "forecast", label: t("forecastName"), format: (v: string) => code(lang, v) },
    { key: "skill", label: t("skillLbl"), format: (v: number) => pct(lang, v, 1) },
    { key: "skill_ci_low", label: `${t("skillLbl")} 2.5%`, format: (v: number) => pct(lang, v, 1) },
    { key: "skill_ci_high", label: `${t("skillLbl")} 97.5%`, format: (v: number) => pct(lang, v, 1) },
    { key: "nRMSE", label: "nRMSE", format: (v: number) => num(lang, v, 3) },
    { key: "MBE", label: t("mbe"), format: (v: number) => num(lang, v, 3) },
    { key: "R2", label: "R²", format: (v: number) => num(lang, v, 3) },
    { key: "R2_daily", label: `R² ${code(lang, "day").toLowerCase()}`, format: (v: number) => num(lang, v, 3) },
  ];
  const hourCols = [
    { key: "ds", label: t("hour"), format: (v: string) => dateTime(lang, v) },
    { key: "y", label: t("measured"), format: (v: number) => num(lang, v, 3) },
    ...names.map((n) => ({ key: n, label: code(lang, n), format: (v: number) => num(lang, v, 3) })),
  ];
  const hourRows = hours.map((h) => ({ ds: h.ds, y: h.y, ...h.f }));

  return (
    <PageGrid>
      <div className="col-span-6 md:col-span-3">
        <Kpi
          label={t("kpi_skill")}
          value={median?.skill}
          format={(v) => pct(lang, v, 0)}
          sub={t("kpi_skillSub", { ref: code(lang, ref), lo: pct(lang, median?.skill_ci_low), hi: pct(lang, median?.skill_ci_high) })}
          color={C.forecast}
          icon={<Gauge size={14} />}
        />
      </div>
      <div className="col-span-6 md:col-span-3">
        <Kpi label={t("kpi_nrmse")} value={median?.nRMSE} format={(v) => num(lang, v, 2)} sub={`${t("mbe")} ${num(lang, median?.MBE, 3)} kWh`} color={C.accent} icon={<Sigma size={14} />} />
      </div>
      <div className="col-span-6 md:col-span-3">
        <Kpi label={t("kpi_r2")} value={median?.R2} format={(v) => num(lang, v, 2)} sub={`R² ${code(lang, "day").toLowerCase()} ${num(lang, median?.R2_daily, 2)}`} color={C.teal} icon={<Target size={14} />} />
      </div>
      <div className="col-span-6 md:col-span-3">
        <Kpi
          label={t("kpi_testDays")}
          value={s.test_windows}
          format={(v) => `${num(lang, v, 0)} ${t("daysCol").toLowerCase()}`}
          sub={s.test_start && s.test_end ? `${date(lang, s.test_start)} – ${date(lang, s.test_end)}` : undefined}
          color={C.withoutPv}
          icon={<CalendarRange size={14} />}
        />
      </div>

      <Visual title={t("v_skillBars")} subtitle={t("checkRef", { ref: code(lang, ref) })} className="col-span-12 lg:col-span-7" data={{ columns: metricCols, rows, file: "forecast_check" }}>
        {(big) => (skillOption ? <Chart option={skillOption} height={big ? "calc(100vh - 210px)" : Math.max(240, 34 * rows.length + 40)} /> : <Empty>{t("noData")}</Empty>)}
      </Visual>
      <Visual
        title={t("v_resolution")}
        className="col-span-12 lg:col-span-5"
        data={{
          columns: [
            { key: "level", label: t("level"), format: (v: string) => code(lang, v) },
            { key: "blocks", label: t("blocks") },
            { key: "skill", label: t("skillLbl"), format: (v: number) => pct(lang, v, 1) },
            { key: "R2", label: "R²", format: (v: number) => num(lang, v, 3) },
            { key: "R2_reference", label: `R² ${t("reference")}`, format: (v: number) => num(lang, v, 3) },
            { key: "nRMSE", label: "nRMSE", format: (v: number) => num(lang, v, 3) },
          ],
          rows: res,
          file: "skill_by_resolution",
        }}
      >
        {(big) => (resOption ? <Chart option={resOption} height={big ? "calc(100vh - 210px)" : Math.max(240, 34 * res.length + 40)} /> : <Empty>{t("noData")}</Empty>)}
      </Visual>
      <Visual title={t("v_checkLine")} subtitle={t("checkLegend")} className="col-span-12" data={{ columns: hourCols, rows: hourRows, file: "test_hours" }}>
        {(big) => (lineOption ? <Chart option={lineOption} height={big ? "calc(100vh - 210px)" : 320} /> : <Empty>{t("noData")}</Empty>)}
      </Visual>
      <Visual title={t("v_scatter")} subtitle={t("scatterSub")} className="col-span-12 lg:col-span-5">
        {(big) => (scatterOption ? <Chart option={scatterOption} height={big ? "calc(100vh - 210px)" : 320} /> : <Empty>{t("noData")}</Empty>)}
      </Visual>
      <Visual title={t("v_metrics")} className="col-span-12 lg:col-span-7" data={{ columns: metricCols, rows, file: "forecast_check" }}>
        <MetricTable out={out} refName={ref} />
      </Visual>
    </PageGrid>
  );
}

/** The metrics table, the output and the reference marked. */
function MetricTable({ out, refName }: { out: string; refName: string }) {
  const t = useT();
  const lang = useStore((s) => s.lang);
  const rows = useStore((s) => s.payload!.result.report.forecast) ?? [];
  return (
    <div className="overflow-auto">
      <table className="w-full border-collapse whitespace-nowrap text-[12px]">
        <thead>
          <tr className="border-b-2 border-line text-ink">
            <th className="px-2 py-1.5 text-left font-semibold">{t("forecastName")}</th>
            <th className="px-2 py-1.5 text-right font-semibold">{t("skillLbl")}</th>
            <th className="px-2 py-1.5 text-right font-semibold">95%</th>
            <th className="px-2 py-1.5 text-right font-semibold">nRMSE</th>
            <th className="px-2 py-1.5 text-right font-semibold">{t("mbe")}</th>
            <th className="px-2 py-1.5 text-right font-semibold">R²</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((f) => (
            <tr key={f.forecast} className={`border-b border-line/60 ${f.forecast === out ? "bg-[#744EC2]/10 font-semibold" : "odd:bg-zebra"}`}>
              <td className="px-2 py-1 text-ink">
                {code(lang, f.forecast)}
                {f.forecast === refName && <span className="ml-1.5 text-[10.5px] font-normal text-muted">({t("reference")})</span>}
              </td>
              <td className={`px-2 py-1 text-right tabular-nums ${(f.skill ?? 0) < 0 ? "text-[#D64550]" : "text-ink"}`}>{pct(lang, f.skill, 1)}</td>
              <td className="px-2 py-1 text-right tabular-nums text-muted">
                {pct(lang, f.skill_ci_low, 0)} – {pct(lang, f.skill_ci_high, 0)}
              </td>
              <td className="px-2 py-1 text-right tabular-nums text-muted">{num(lang, f.nRMSE, 3)}</td>
              <td className="px-2 py-1 text-right tabular-nums text-muted">{num(lang, f.MBE, 3)}</td>
              <td className="px-2 py-1 text-right tabular-nums text-muted">{num(lang, f.R2, 3)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface HourSum {
  ds: string;
  y: number | null;
  f: Record<string, number | null>;
}

/** The test hours summed over the series of the file (a file may carry several inverters or meters); an hour
 * that one series lacks is null, not the others' energy. */
function sumByHour(rows: CheckHour[], names: string[]): HourSum[] {
  const n = new Set(rows.map((h) => h.unique_id)).size || 1;
  const by = new Map<string, { ds: string; y: number; ny: number; f: Record<string, number>; nf: Record<string, number> }>();
  for (const h of rows) {
    const x = by.get(h.ds) ?? { ds: h.ds, y: 0, ny: 0, f: {}, nf: {} };
    if (typeof h.y === "number") {
      x.y += h.y;
      x.ny += 1;
    }
    for (const k of names) {
      const v = h[k];
      if (typeof v !== "number") continue;
      x.f[k] = (x.f[k] ?? 0) + v;
      x.nf[k] = (x.nf[k] ?? 0) + 1;
    }
    by.set(h.ds, x);
  }
  return [...by.values()]
    .map((x) => ({ ds: x.ds, y: x.ny === n ? x.y : null, f: Object.fromEntries(names.map((k) => [k, x.nf[k] === n ? x.f[k] : null])) }))
    .sort((a, b) => a.ds.localeCompare(b.ds));
}
