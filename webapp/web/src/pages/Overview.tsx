import type { EChartsOption } from "echarts";
import { motion } from "framer-motion";
import { Clock, FileText, Gauge, Home, PiggyBank, Receipt, Sun } from "lucide-react";
import { useMemo } from "react";
import { Chart } from "../components/Chart";
import { Kpi } from "../components/Kpi";
import { SiteMap } from "../components/SiteMap";
import { Visual } from "../components/Visual";
import { daily, history, present, type DayTotal } from "../derive";
import { compact, date, dayLabel, money, num, pct, time, wall } from "../format";
import { code } from "../i18n";
import { useStore, useT } from "../store";
import { alpha, BASE, C, CONFIDENCE } from "../theme";
import type { Payload, Quantity } from "../types";
import { PageGrid } from "./common";

export const QCOLOR: Record<Quantity, string> = { generation: C.generation, consumption: C.consumption };

export function Overview({ payload }: { payload: Payload }) {
  const t = useT();
  const lang = useStore((s) => s.lang);
  const selected = useStore((s) => s.selectedDay);
  const toggleDay = useStore((s) => s.toggleDay);
  const r = payload.result;
  const qs = present(r);
  const days = useMemo(() => Object.fromEntries(qs.map((q) => [q, daily(r.outlooks[q])])) as Record<Quantity, DayTotal[]>, [r, qs]);
  const main: Quantity = qs.includes("generation") ? "generation" : "consumption";

  const out = r.report.summary.output ?? "median";
  const median = r.report.forecast?.find((f) => f.forecast === out);
  const econ = r.report.economics;
  const tot = econ?.totals[0];
  const tomorrow = days[main]?.find((d) => d.lead_day === 1)?.date;
  const best = r.windows.find((w) => w.date.slice(0, 10) === tomorrow) ?? r.windows[0];

  const kpis = [];
  for (const q of qs) {
    const d = days[q];
    kpis.push(
      <Kpi
        key={q}
        label={t(q === "generation" ? "kpi_gen" : "kpi_cons", { n: d.length })}
        value={d.reduce((a, x) => a + x.total, 0)}
        format={(v) => compact(lang, v)}
        unit="kWh"
        sub={t("kpi_range", { lo: compact(lang, d.reduce((a, x) => a + x.low, 0)), hi: compact(lang, d.reduce((a, x) => a + x.high, 0)) })}
        spark={d.map((x) => x.total)}
        color={QCOLOR[q]}
        icon={q === "generation" ? <Sun size={14} /> : <Home size={14} />}
      />,
    );
  }
  if (best)
    kpis.push(
      <Kpi
        key="best"
        label={t("kpi_best")}
        text={`${time(lang, best.start)}–${time(lang, best.end)}`}
        sub={t("kpi_bestSub", { kwh: num(lang, best.energy, 1), what: t(main === "generation" ? "bestWhatGen" : "bestWhatCons") })}
        color={C.forecast}
        icon={<Clock size={14} />}
      />,
    );
  if (median)
    kpis.push(
      <Kpi
        key="skill"
        label={t("kpi_skill")}
        value={median.skill}
        format={(v) => pct(lang, v, 0)}
        sub={t("kpi_skillSub", { ref: code(lang, r.report.summary.reference), lo: pct(lang, median.skill_ci_low), hi: pct(lang, median.skill_ci_high) })}
        color={C.accent}
        icon={<Gauge size={14} />}
      />,
    );
  if (econ && tot && tot.mean_month != null)
    kpis.push(
      <Kpi
        key="bill"
        label={t("kpi_bill")}
        value={tot.mean_month}
        format={(v) => money(lang, v, econ.currency)}
        sub={t("kpi_billSub", { n: tot.complete_months })}
        color={C.grid}
        icon={<Receipt size={14} />}
      />,
    );
  if (econ && tot && qs.includes("generation") && tot.savings != null)
    kpis.push(
      <Kpi
        key="savings"
        label={t("kpi_savings")}
        value={tot.savings}
        format={(v) => money(lang, v, econ.currency)}
        sub={t("kpi_savingsSub", { v: money(lang, (tot.savings / Math.max(tot.months, 1)) * 12, econ.currency) })}
        color={C.savings}
        icon={<PiggyBank size={14} />}
      />,
    );
  const read = r.read[main];
  if (kpis.length < 6 && read)
    kpis.push(
      <Kpi
        key="measured"
        label={t("kpi_measured")}
        value={read.measured}
        format={(v) => pct(lang, v, 1)}
        sub={t("kpi_measuredSub", { h: num(lang, read.hours, 0) })}
        color={C.teal}
        icon={<FileText size={14} />}
      />,
    );

  // ------------------------------------------------------------ next days per day, with the range
  const dates = useMemo(() => [...new Set(qs.flatMap((q) => days[q].map((d) => d.date)))].sort(), [qs, days]);
  const dailyOption = useMemo<EChartsOption>(() => {
    const two = qs.length > 1;
    const offset = (i: number) => (two ? (i === 0 ? -0.18 : 0.18) : 0);
    const series: any[] = [];
    qs.forEach((q, i) => {
      const by = new Map(days[q].map((d) => [d.date, d]));
      series.push({
        id: `bar-${q}`,
        name: t(q),
        type: "bar",
        barWidth: two ? "30%" : "42%",
        barGap: "20%",
        data: dates.map((d) => {
          const x = by.get(d);
          return {
            value: x ? +x.total.toFixed(2) : null,
            itemStyle: { color: QCOLOR[q], opacity: selected && selected !== d ? 0.28 : 1, borderRadius: [2, 2, 0, 0] },
          };
        }),
        label: { show: true, position: "top", fontSize: 10, formatter: (p: any) => (p.value == null ? "" : compact(lang, p.value)) },
        animationDelay: (k: number) => k * 60 + i * 120,
        emphasis: { focus: "none" },
      });
      series.push({
        id: `err-${q}`,
        name: `${t(q)} ${t("range")}`,
        type: "custom",
        z: 3,
        silent: true,
        tooltip: { show: false },
        data: dates.map((d, k) => {
          const x = by.get(d);
          return x ? [k, x.low, x.high] : [k, null, null];
        }),
        renderItem: (params: any, api: any) => {
          if (api.value(1) == null || Number.isNaN(api.value(1))) return null;
          const w = api.size([1, 0])[0];
          const [cx, lo] = api.coord([api.value(0), api.value(1)]);
          const [, hi] = api.coord([api.value(0), api.value(2)]);
          const x = cx + offset(i) * w;
          const cap = Math.min(8, w * 0.08);
          const style = { stroke: alpha(C.measured, 0.55), lineWidth: 1.2 };
          return {
            type: "group",
            children: [
              { type: "line", shape: { x1: x, y1: lo, x2: x, y2: hi }, style },
              { type: "line", shape: { x1: x - cap, y1: lo, x2: x + cap, y2: lo }, style },
              { type: "line", shape: { x1: x - cap, y1: hi, x2: x + cap, y2: hi }, style },
            ],
            // grows in with the bars
            enterFrom: { style: { opacity: 0 } },
            ...(params ? {} : {}),
          };
        },
      });
    });
    return {
      ...BASE,
      legend: { top: 0, left: 0, data: qs.map((q) => t(q)) },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        formatter: (ps: any) => {
          const d = dates[ps[0].dataIndex];
          const lines = qs
            .map((q) => {
              const x = days[q].find((y) => y.date === d);
              if (!x) return "";
              const c = CONFIDENCE[x.confidence] ?? "#888";
              return `<div style="margin-top:4px"><span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${QCOLOR[q]};margin-right:6px"></span><b>${t(q)}</b>: ${num(lang, x.total, 1)} kWh<br/><span style="color:#888">${t("range")} ${num(lang, x.low, 1)}–${num(lang, x.high, 1)} · </span><span style="color:${c}">${code(lang, x.confidence)}</span></div>`;
            })
            .join("");
          return `<b>${dayLabel(lang, d)}</b>${lines}`;
        },
      },
      xAxis: { type: "category", data: dates.map((d) => dayLabel(lang, d)) },
      yAxis: { type: "value", name: "kWh" },
      series,
    };
  }, [qs, days, dates, selected, lang, t]);

  // ------------------------------------------------------------ history: each day of the file
  const hist = useMemo(() => Object.fromEntries(qs.map((q) => [q, history(r, q)])) as Record<Quantity, ReturnType<typeof history>>, [r, qs]);
  const histOption = useMemo<EChartsOption>(() => {
    const last = Math.max(...qs.map((q) => wall(hist[q].at(-1)?.date ?? "1970-01-01")));
    return {
      ...BASE,
      grid: { ...BASE.grid, bottom: 44 },
      legend: { top: 0, left: 0 },
      tooltip: { trigger: "axis", valueFormatter: (v: any) => (v == null ? "–" : `${num(lang, v, 1)} kWh`) },
      xAxis: { type: "time" },
      yAxis: { type: "value", name: "kWh" },
      dataZoom: [
        { type: "inside", startValue: last - 365 * 864e5 },
        { type: "slider", height: 18, bottom: 8, startValue: last - 365 * 864e5 },
      ],
      series: qs.map((q) => ({
        id: `hist-${q}`,
        name: t(q),
        type: "line",
        showSymbol: false,
        sampling: "lttb",
        lineStyle: { width: 1.4, color: QCOLOR[q] },
        itemStyle: { color: QCOLOR[q] },
        areaStyle: { color: alpha(QCOLOR[q], q === "generation" ? 0.18 : 0.08) },
        data: hist[q].map((d) => [wall(d.date), d.energy == null ? null : +d.energy.toFixed(2)]),
      })),
    };
  }, [qs, hist, lang, t]);

  const dailyRows = dates.map((d) => {
    const row: Record<string, unknown> = { date: d };
    for (const q of qs) {
      const x = days[q].find((y) => y.date === d);
      row[`${q}_total`] = x ? +x.total.toFixed(2) : null;
      row[`${q}_low`] = x ? +x.low.toFixed(2) : null;
      row[`${q}_high`] = x ? +x.high.toFixed(2) : null;
      row[`${q}_conf`] = x ? code(lang, x.confidence) : "";
    }
    return row;
  });
  const dailyCols = [
    { key: "date", label: t("date"), format: (v: string) => dayLabel(lang, v) },
    ...qs.flatMap((q) => [
      { key: `${q}_total`, label: `${t(q)} kWh` },
      { key: `${q}_low`, label: `${t(q)} ${t("low")}` },
      { key: `${q}_high`, label: `${t(q)} ${t("high")}` },
      { key: `${q}_conf`, label: `${t(q)} ${t("confidence")}` },
    ]),
  ];

  return (
    <PageGrid>
      {kpis.slice(0, 6).map((k, i) => (
        <div key={i} className="col-span-6 md:col-span-4 xl:col-span-2 [&>section]:h-full">
          {k}
        </div>
      ))}
      <Visual
        title={t("v_daily")}
        subtitle={selected ? `${dayLabel(lang, selected)} · ${t("clearSelection")}` : undefined}
        className="col-span-12 lg:col-span-8"
        data={{ columns: dailyCols, rows: dailyRows, file: "next_days" }}
      >
        {(big) => <Chart option={dailyOption} height={big ? "calc(100vh - 210px)" : 300} onClick={(p) => p.dataIndex != null && toggleDay(dates[p.dataIndex])} />}
      </Visual>
      <Visual title={t("v_site")} subtitle={`${num(lang, r.site.latitude, 2)}, ${num(lang, r.site.longitude, 2)} · ${r.site.timezone}`} className="col-span-12 lg:col-span-4">
        {(big) => (
          <SiteMap
            lat={r.site.latitude}
            lon={r.site.longitude}
            label={r.site.address_found ?? `${r.site.latitude}, ${r.site.longitude}`}
            height={big ? "calc(100vh - 200px)" : 300}
          />
        )}
      </Visual>
      <Visual
        title={t("v_historyLine")}
        className="col-span-12 lg:col-span-8"
        data={{
          columns: [{ key: "date", label: t("date"), format: (v: string) => date(lang, v) }, ...qs.map((q) => ({ key: q, label: `${t(q)} kWh` }))],
          rows: mergeByDate(qs, hist),
          file: "history_daily",
        }}
      >
        {(big) => <Chart option={histOption} height={big ? "calc(100vh - 210px)" : 300} />}
      </Visual>
      <Visual title={t("v_files")} className="col-span-12 lg:col-span-4">
        <div className="space-y-3">
          {qs.map((q) => {
            const f = r.read[q];
            if (!f) return null;
            return (
              <div key={q} className="rounded-[3px] border border-line p-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-[12.5px] font-semibold text-ink">{f.file}</span>
                  <span className="shrink-0 text-[11px] font-semibold" style={{ color: QCOLOR[q] }}>
                    {t(q)}
                  </span>
                </div>
                <p className="mt-1 line-clamp-3 text-[11.5px] leading-snug text-muted" title={f.how}>
                  {f.how}
                </p>
                <div className="mt-2 flex items-center justify-between text-[11px] text-muted">
                  <span>
                    {date(lang, f.start)} – {date(lang, f.end)}
                  </span>
                  <span className="tabular-nums">
                    {num(lang, f.hours, 0)} {t("hours").toLowerCase()} · {pct(lang, f.measured, 1)}
                  </span>
                </div>
                <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-hover">
                  <motion.div className="h-full rounded-full" style={{ background: QCOLOR[q] }} initial={{ width: 0 }} animate={{ width: `${f.measured * 100}%` }} transition={{ duration: 1.1, ease: "easeOut" }} />
                </div>
              </div>
            );
          })}
        </div>
      </Visual>
    </PageGrid>
  );
}

function mergeByDate(qs: Quantity[], hist: Record<Quantity, { date: string; energy: number | null }[]>) {
  const by = new Map<string, Record<string, unknown>>();
  for (const q of qs)
    for (const d of hist[q]) {
      const row = by.get(d.date) ?? { date: d.date };
      row[q] = d.energy == null ? null : +d.energy.toFixed(3);
      by.set(d.date, row);
    }
  return [...by.values()].sort((a, b) => String(a.date).localeCompare(String(b.date)));
}
