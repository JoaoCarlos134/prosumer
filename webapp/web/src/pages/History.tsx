import type { EChartsOption } from "echarts";
import { useMemo, useState } from "react";
import { Chart } from "../components/Chart";
import { Empty, Visual } from "../components/Visual";
import { history, monthly, present, rolling } from "../derive";
import { date, dayLabel, monthLabel, num, pct, wall } from "../format";
import { useStore, useT } from "../store";
import { alpha, BASE, C, LEGEND } from "../theme";
import type { Payload, Quantity } from "../types";
import { Chips, PageGrid } from "./common";
import { QCOLOR } from "./Overview";

const DAY = 864e5;

/** The file's past: a calendar of the last year, each day with its 30-day mean, the months, the hours measured
 * and the quality table. A click on a day (calendar or line) marks it on every visual of the page. */
export function HistoryPage({ payload }: { payload: Payload }) {
  const t = useT();
  const lang = useStore((s) => s.lang);
  const r = payload.result;
  const qs = present(r).filter((q) => history(r, q).length > 0);
  const [chosen, setQ] = useState<Quantity | null>(null);
  const q: Quantity = chosen && qs.includes(chosen) ? chosen : (qs[0] ?? "generation");
  const [day, setDay] = useState<string | null>(null);
  const pick = (d: string | null) => setDay((x) => (d === null || x === d ? null : d));

  const days = useMemo(() => history(r, q), [r, q]);
  const all = useMemo(() => Object.fromEntries(qs.map((x) => [x, history(r, x)])) as Record<Quantity, ReturnType<typeof history>>, [r, qs]);
  const last = days.at(-1)?.date;
  const color = QCOLOR[q];

  // ------------------------------------------------------------ calendar of the last 365 days
  const calendarOption = useMemo<EChartsOption | null>(() => {
    if (!last) return null;
    const from = new Date(wall(last) - 364 * DAY).toISOString().slice(0, 10);
    const year = days.filter((d) => d.date >= from);
    const values = year.map((d) => d.energy).filter((v): v is number => v != null);
    const max = values.length ? Math.max(...values) : 1;
    return {
      ...BASE,
      tooltip: {
        formatter: (p: any) => `<b>${dayLabel(lang, p.value[0])}</b><br/>${t(q)}: ${num(lang, p.value[1], 1)} kWh`,
      },
      visualMap: {
        min: 0,
        max: max || 1,
        calculable: true,
        orient: "horizontal",
        left: "center",
        bottom: 0,
        itemHeight: 140,
        itemWidth: 10,
        formatter: (v: any) => `${num(lang, v, 0)} kWh`,
        inRange: { color: [alpha(color, 0.08), alpha(color, 0.45), color] },
      },
      calendar: {
        top: 28,
        left: 36,
        right: 12,
        bottom: 44,
        range: [from, last],
        cellSize: ["auto", "auto"],
        dayLabel: { firstDay: 1, nameMap: lang === "pt" ? ["D", "S", "T", "Q", "Q", "S", "S"] : ["S", "M", "T", "W", "T", "F", "S"] },
        monthLabel: { nameMap: lang === "pt" ? ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"] : "EN" },
      },
      series: [
        {
          id: `cal-${q}`,
          type: "heatmap",
          coordinateSystem: "calendar",
          data: year.map((d) => [d.date, d.energy == null ? null : +d.energy.toFixed(2)]),
          itemStyle: { borderRadius: 2 },
          emphasis: { itemStyle: { borderColor: C.measured, borderWidth: 1.5 } },
        },
        ...(day
          ? [
              {
                id: "cal-day",
                type: "scatter" as const,
                coordinateSystem: "calendar" as const,
                symbol: "rect",
                symbolSize: 9,
                silent: true,
                itemStyle: { color: "transparent", borderColor: C.measured, borderWidth: 2 },
                data: [[day, 1]],
              },
            ]
          : []),
      ],
    };
  }, [days, last, q, color, day, lang, t]);

  // ------------------------------------------------------------ each day and its 30-day mean
  const lineOption = useMemo<EChartsOption>(() => {
    const mean = rolling(
      days.map((d) => d.energy),
      30,
    );
    const end = last ? wall(last) : 0;
    return {
      ...BASE,
      grid: { ...BASE.grid, bottom: 44 },
      legend: { ...LEGEND },
      tooltip: { trigger: "axis", valueFormatter: (v: any) => (v == null ? "–" : `${num(lang, v, 1)} kWh`) },
      xAxis: { type: "time" },
      yAxis: { type: "value", name: "kWh" },
      dataZoom: [
        { type: "inside", startValue: end - 365 * DAY },
        { type: "slider", height: 18, bottom: 8, startValue: end - 365 * DAY },
      ],
      series: [
        {
          id: `day-${q}`,
          name: t(q),
          type: "line",
          showSymbol: false,
          sampling: "lttb",
          lineStyle: { width: 1, color: alpha(color, 0.75) },
          itemStyle: { color },
          areaStyle: { color: alpha(color, 0.1) },
          data: days.map((d) => [wall(d.date), d.energy == null ? null : +d.energy.toFixed(2)]),
          markLine: day
            ? { silent: true, symbol: "none", lineStyle: { color: C.measured, type: "solid", width: 1.5 }, label: { formatter: date(lang, day), fontSize: 10 }, data: [{ xAxis: wall(day) }] }
            : undefined,
        },
        {
          id: `mean-${q}`,
          name: t("rolling"),
          type: "line",
          showSymbol: false,
          smooth: true,
          lineStyle: { width: 2.4, color: C.measured },
          itemStyle: { color: C.measured },
          data: days.map((d, i) => [wall(d.date), mean[i] == null ? null : +mean[i]!.toFixed(2)]),
        },
      ],
    };
  }, [days, last, q, color, day, lang, t]);

  // ------------------------------------------------------------ energy per month, both files
  const months = useMemo(() => {
    const by = Object.fromEntries(qs.map((x) => [x, monthly(all[x])])) as Record<Quantity, Map<string, number>>;
    return [...new Set(qs.flatMap((x) => [...by[x].keys()]))].sort().map((m) => ({ month: m, ...Object.fromEntries(qs.map((x) => [x, by[x].get(m) ?? null])) }) as Record<string, any>);
  }, [qs, all]);
  const monthOption = useMemo<EChartsOption>(
    () => ({
      ...BASE,
      legend: { ...LEGEND },
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, valueFormatter: (v: any) => `${num(lang, v, 0)} kWh` },
      xAxis: { type: "category", data: months.map((m) => monthLabel(lang, `${m.month}-01`)) },
      yAxis: { type: "value", name: "kWh" },
      series: qs.map((x, i) => ({
        id: `month-${x}`,
        name: t(x),
        type: "bar",
        barGap: "10%",
        itemStyle: {
          color: QCOLOR[x],
          borderRadius: [2, 2, 0, 0],
          opacity: 1,
        },
        data: months.map((m) => ({
          value: m[x] == null ? null : +m[x].toFixed(1),
          itemStyle: { opacity: day && m.month !== day.slice(0, 7) ? 0.3 : 1 },
        })),
        animationDelay: (k: number) => k * 40 + i * 100,
      })),
    }),
    [months, qs, day, lang, t],
  );

  // ------------------------------------------------------------ hours measured per day
  const coverageOption = useMemo<EChartsOption>(() => {
    const end = last ? wall(last) : 0;
    return {
      ...BASE,
      grid: { ...BASE.grid, bottom: 44 },
      tooltip: { trigger: "axis", valueFormatter: (v: any) => `${num(lang, v, 0)} h` },
      xAxis: { type: "time" },
      yAxis: { type: "value", min: 0, max: 24, interval: 6, name: t("hours") },
      dataZoom: [
        { type: "inside", startValue: end - 365 * DAY },
        { type: "slider", height: 18, bottom: 8, startValue: end - 365 * DAY },
      ],
      series: [
        {
          id: `cov-${q}`,
          name: t("hours"),
          type: "bar",
          barMaxWidth: 6,
          data: days.map((d) => ({
            value: [wall(d.date), d.measured_hours],
            itemStyle: { color: d.measured_hours >= 24 ? alpha(C.teal, 0.75) : d.measured_hours === 0 ? C.warn : C.self },
          })),
          markLine: day ? { silent: true, symbol: "none", lineStyle: { color: C.measured }, label: { show: false }, data: [{ xAxis: wall(day) }] } : undefined,
        },
      ],
    };
  }, [days, last, q, day, lang, t]);

  if (!qs.length)
    return (
      <PageGrid>
        <Visual title={t("page_history")} className="col-span-12">
          <Empty>{t("noData")}</Empty>
        </Visual>
      </PageGrid>
    );

  const quality = r.report.quality;
  const picked = day ? days.find((d) => d.date === day) : undefined;
  return (
    <PageGrid>
      {qs.length > 1 && <Chips value={q} options={qs.map((x) => ({ value: x, label: t(x), color: QCOLOR[x] }))} onChange={(v) => v && setQ(v)} />}
      <Visual
        title={t("v_calendar")}
        subtitle={picked ? `${dayLabel(lang, picked.date)}: ${num(lang, picked.energy, 1)} kWh · ${num(lang, picked.measured_hours, 0)} h · ${t("clearSelection")}` : undefined}
        className="col-span-12 xl:col-span-7"
        data={{
          columns: [
            { key: "date", label: t("date"), format: (v: string) => date(lang, v) },
            { key: "energy", label: `${t(q)} kWh`, format: (v: number) => num(lang, v, 2) },
            { key: "measured_hours", label: t("hours") },
          ],
          rows: days,
          file: `history_${q}`,
        }}
        actions={
          day ? (
            <button type="button" className="rounded-sm px-1.5 text-[11px] text-[#118DFF] hover:underline" onClick={() => pick(null)}>
              {t("clearSelection")}
            </button>
          ) : undefined
        }
      >
        {(big) => (calendarOption ? <Chart option={calendarOption} height={big ? "calc(100vh - 210px)" : 250} onClick={(p) => p.seriesType === "heatmap" && pick(p.value[0])} /> : <Empty>{t("noData")}</Empty>)}
      </Visual>
      <Visual
        title={t("v_monthly")}
        className="col-span-12 xl:col-span-5"
        data={{
          columns: [{ key: "month", label: t("month") }, ...qs.map((x) => ({ key: x, label: `${t(x)} kWh`, format: (v: number) => num(lang, v, 1) }))],
          rows: months,
          file: "energy_per_month",
        }}
      >
        {(big) => <Chart option={monthOption} height={big ? "calc(100vh - 210px)" : 250} />}
      </Visual>
      <Visual title={`${t("v_historyLine")} · ${t(q)}`} className="col-span-12">
        {(big) => (
          <Chart
            option={lineOption}
            height={big ? "calc(100vh - 210px)" : 300}
            onClick={(p) => {
              const d = days[p.dataIndex];
              if (d) pick(d.date);
            }}
          />
        )}
      </Visual>
      <Visual title={t("v_coverage")} className="col-span-12 lg:col-span-6">
        {(big) => <Chart option={coverageOption} height={big ? "calc(100vh - 210px)" : 240} />}
      </Visual>
      <Visual
        title={t("v_quality")}
        className="col-span-12 lg:col-span-6"
        data={{ columns: qualityColumns(t, lang), rows: quality, file: "data_quality" }}
      >
        <QualityCards />
      </Visual>
    </PageGrid>
  );
}

function qualityColumns(t: ReturnType<typeof useT>, lang: "en" | "pt") {
  return [
    { key: "series", label: t("series") },
    { key: "first", label: t("first"), format: (v: string) => date(lang, v) },
    { key: "last_valid", label: t("lastValid"), format: (v: string) => date(lang, v) },
    { key: "steps", label: t("hours"), format: (v: number) => num(lang, v, 0) },
    { key: "coverage", label: t("coverage"), format: (v: number) => pct(lang, v, 1) },
    { key: "gaps", label: t("gaps"), format: (v: number) => num(lang, v, 0) },
    { key: "longest_gap_h", label: t("longestGap"), format: (v: number) => num(lang, v, 0) },
  ];
}

/** The quality table of the analysis, one card per series with its coverage bar. */
function QualityCards() {
  const t = useT();
  const lang = useStore((s) => s.lang);
  const rows = useStore((s) => s.payload!.result.report.quality);
  if (!rows.length) return <Empty>{t("noData")}</Empty>;
  return (
    <div className="space-y-3">
      {rows.map((q) => (
        <div key={q.series} className="rounded-xl border border-line p-3">
          <div className="flex items-center justify-between gap-2 text-[12.5px]">
            <span className="truncate font-semibold text-ink">{q.series}</span>
            <span className="tabular-nums text-muted">{pct(lang, q.coverage, 1)}</span>
          </div>
          <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-hover">
            <div className="h-full rounded-full transition-[width] duration-1000" style={{ width: `${(q.coverage ?? 0) * 100}%`, background: C.teal }} />
          </div>
          <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-0.5 text-[11.5px] sm:grid-cols-4">
            <dt className="text-muted">{t("first")}</dt>
            <dd className="text-ink">{date(lang, q.first)}</dd>
            <dt className="text-muted">{t("lastValid")}</dt>
            <dd className="text-ink">{date(lang, q.last_valid)}</dd>
            <dt className="text-muted">{t("gaps")}</dt>
            <dd className="tabular-nums text-ink">{num(lang, q.gaps, 0)}</dd>
            <dt className="text-muted">{t("longestGap")}</dt>
            <dd className="tabular-nums text-ink">{num(lang, q.longest_gap_h, 0)}</dd>
          </dl>
        </div>
      ))}
    </div>
  );
}
