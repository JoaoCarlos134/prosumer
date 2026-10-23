import type { EChartsOption } from "echarts";
import { Clock, Compass, TrendingDown, Zap } from "lucide-react";
import { useMemo, useState } from "react";
import { Chart } from "../components/Chart";
import { Kpi } from "../components/Kpi";
import { Empty, Visual } from "../components/Visual";
import { compass, date, monthLabel, num, wall } from "../format";
import { code } from "../i18n";
import { useStore, useT } from "../store";
import { alpha, BASE, C, LEGEND } from "../theme";
import type { Diagnostics, Payload } from "../types";
import { Chips, NoteList, PageGrid } from "./common";
import { Plant } from "./NextDays";

/** The PV system as the data show it: its effective power, the roof, the clear-day performance over time with
 * its trend and steps, and the file's clock against the sun. */
export function System({ payload }: { payload: Payload }) {
  const t = useT();
  const lang = useStore((s) => s.lang);
  const r = payload.result;
  const diag = r.report.diagnostics;
  const plants = r.outlooks.generation?.method.series ?? {};
  const uids = useMemo(
    () => [...new Set([...Object.keys(plants), ...(diag?.orientation ?? []).map((o) => o.unique_id), ...(r.charts.performance ?? []).map((p) => p.unique_id)])],
    [plants, diag, r.charts.performance],
  );
  const [chosen, setUid] = useState<string | null>(null);
  const uid = chosen && uids.includes(chosen) ? chosen : uids[0];

  const plant = uid ? plants[uid] : undefined;
  const roof = diag?.orientation.find((o) => o.unique_id === uid);
  const segments = useMemo(() => (diag?.segments ?? []).filter((s) => s.unique_id === uid), [diag, uid]);
  const steps = useMemo(() => (diag?.steps ?? []).filter((s) => s.unique_id === uid), [diag, uid]);
  const perf = useMemo(() => (r.charts.performance ?? []).filter((p) => p.unique_id === uid), [r.charts.performance, uid]);
  const clock = useMemo(() => (r.report.clock ?? []).filter((c) => c.unique_id === uid), [r.report.clock, uid]);
  const clockAll = clock.find((c) => c.period === "all");
  const clockMonths = clock.filter((c) => c.period !== "all");

  // what the library reports (prosumer.diagnostics): the roof good enough for steps, a trend and a loss to
  // mean anything (`reliable`), and on the last period whether its trend and its loss are worth a note; the
  // page shows those numbers only, as the notes do. A typed roof has no fit (r2 null).
  const reliable = roof?.reliable ?? false;
  const given = roof != null && roof.r2 == null && reliable;
  const lastSeg = segments.at(-1);
  const trendShown = !!lastSeg?.trend_reported;
  const lossShown = !!lastSeg?.loss_reported;

  // ------------------------------------------------------------ clear-day performance index, segments, steps
  const perfOption = useMemo<EChartsOption | null>(() => {
    if (!perf.length) return null;
    const segData: (number | null)[][] = [];
    for (const s of segments) {
      segData.push([wall(s.start), s.level_start], [wall(s.end), s.level_end], [wall(s.end), null]);
    }
    return {
      ...BASE,
      grid: { ...BASE.grid, bottom: 44 },
      legend: { ...LEGEND },
      tooltip: {
        trigger: "item",
        formatter: (p: any) => {
          if (p.seriesId !== "index") return `${p.seriesName}: ${num(lang, p.value?.[1], 2)}`;
          const d = perf[p.dataIndex];
          return `<b>${date(lang, d.date)}</b><br/>${t("index")}: ${num(lang, d.index, 2)}<br/><span style="color:#888">${t("measured")} ${num(lang, d.energy, 1)} kWh · ${t("expected")} ${num(lang, d.expected, 1)} kWh</span>`;
        },
      },
      xAxis: { type: "time" },
      yAxis: { type: "value", name: t("index"), scale: true },
      dataZoom: [{ type: "inside" }, { type: "slider", height: 18, bottom: 8 }],
      series: [
        {
          id: "index",
          name: t("index"),
          type: "scatter",
          symbolSize: 6,
          itemStyle: { color: alpha(C.generation, 0.55) },
          data: perf.map((p) => [wall(p.date), p.index]),
          markLine: steps.length
            ? {
                symbol: "none",
                lineStyle: { color: C.warn, type: "dashed", width: 1.3 },
                label: { formatter: (p: any) => p.name, fontSize: 10, position: "insideEndTop" },
                data: steps.map((s) => ({ xAxis: wall(s.date), name: `${s.step_pct != null && s.step_pct > 0 ? "+" : ""}${num(lang, s.step_pct, 0)}%` })),
              }
            : undefined,
        },
        {
          id: "segments",
          name: t("segment"),
          type: "line",
          symbol: "circle",
          symbolSize: 5,
          connectNulls: false,
          lineStyle: { width: 3, color: reliable ? C.measured : alpha(C.measured, 0.4), type: reliable ? "solid" : "dashed" },
          itemStyle: { color: C.measured },
          data: segData,
        },
      ],
    };
  }, [perf, segments, steps, reliable, lang, t]);

  // ------------------------------------------------------------ the clock against the sun, by month
  const clockOption = useMemo<EChartsOption | null>(() => {
    if (!clockMonths.length) return null;
    return {
      ...BASE,
      grid: { ...BASE.grid, top: 28 },
      legend: { ...LEGEND, data: [t("confident"), t("notConfident")] },
      tooltip: {
        trigger: "item",
        formatter: (p: any) => {
          const c = clockMonths[p.dataIndex];
          return `<b>${monthLabel(lang, `${c.period}-01`)}</b><br/>${t("offset")}: ${num(lang, c.offset_h, 1)} h<br/><span style="color:#888">${num(lang, c.days, 0)} ${t("daysCol").toLowerCase()} · ${t("agreement")} ${num(lang, (c.agreement ?? 0) * 100, 0)}%</span>`;
        },
      },
      xAxis: { type: "category", data: clockMonths.map((c) => monthLabel(lang, `${c.period}-01`)) },
      yAxis: { type: "value", name: "h", minInterval: 1 },
      series: [
        {
          id: "clock",
          name: t("confident"),
          type: "bar",
          barWidth: "55%",
          itemStyle: { color: C.teal },
          data: clockMonths.map((c) => ({ value: c.offset_h, itemStyle: { color: c.confident ? C.teal : alpha(C.withoutPv, 0.7), borderRadius: 2 } })),
          markLine: { silent: true, symbol: "none", lineStyle: { color: C.measured, type: "solid" }, label: { show: false }, data: [{ yAxis: 0 }] },
          animationDelay: (k: number) => k * 45,
        },
        // legend entry only
        { id: "clock-no", name: t("notConfident"), type: "bar", itemStyle: { color: alpha(C.withoutPv, 0.7) }, data: [] },
      ],
    };
  }, [clockMonths, lang, t]);

  if (!r.outlooks.generation)
    return (
      <PageGrid>
        <Visual title={t("page_system")} className="col-span-12">
          <Empty>{t("systemEmpty")}</Empty>
        </Visual>
      </PageGrid>
    );

  const roofText = roof && roof.tilt != null && roof.azimuth != null ? `${num(lang, roof.tilt, 0)}° · ${num(lang, roof.azimuth, 0)}° ${compass(lang, roof.azimuth)}` : "–";
  return (
    <PageGrid>
      {uids.length > 1 && <Chips value={uid} options={uids.map((u) => ({ value: u, label: u, color: C.generation }))} onChange={(v) => v && setUid(v)} />}
      <div className="col-span-6 md:col-span-3">
        <Kpi
          label={t("kpi_kwEff")}
          value={plant?.kw_eff}
          format={(v) => num(lang, v, 2)}
          unit="kW"
          sub={plant?.clear_days_used != null ? t("kpi_kwEffSub", { n: plant.clear_days_used }) : plant?.kw_eff_from}
          color={C.generation}
          icon={<Zap size={14} />}
        />
      </div>
      <div className="col-span-6 md:col-span-3">
        <Kpi
          label={t("v_roof")}
          text={roofText}
          sub={roof ? (given ? capital(code(lang, "given")) : roof.edge ? t("edge") : `${t("r2")} ${num(lang, roof.r2, 2)}`) : undefined}
          color={roof?.edge && !given ? C.warn : C.accent}
          icon={<Compass size={14} />}
        />
      </div>
      <div className="col-span-6 md:col-span-3">
        <Kpi
          label={t("kpi_trend")}
          {...(trendShown && lastSeg?.trend_pct_per_year != null
            ? { value: lastSeg.trend_pct_per_year, format: (v: number) => num(lang, v, 1), unit: t("perYear") }
            : { text: "–" })}
          sub={!reliable ? t("trendNotReported") : lossShown ? t("kpi_trendSub", { lost: num(lang, lastSeg?.lost_pct, 0) }) : t("trendNone")}
          color={trendShown || lossShown ? C.warn : reliable ? C.export : C.withoutPv}
          icon={<TrendingDown size={14} />}
        />
      </div>
      <div className="col-span-6 md:col-span-3">
        <Kpi
          label={t("kpi_clock")}
          value={clockAll?.offset_h}
          format={(v) => `${v > 0 ? "+" : ""}${num(lang, v, 1)}`}
          unit="h"
          sub={clockAll ? `${t("kpi_clockSub", { days: num(lang, clockAll.days, 0) })} · ${clockAll.confident ? t("confident").toLowerCase() : t("notConfident").toLowerCase()}` : undefined}
          color={clockAll?.confident ? C.teal : C.withoutPv}
          icon={<Clock size={14} />}
        />
      </div>

      <Visual
        title={t("v_perf")}
        subtitle={reliable ? t("perfSub") : t("perfSubUncertain")}
        className="col-span-12 xl:col-span-8"
        data={{
          columns: [
            { key: "date", label: t("date"), format: (v: string) => date(lang, v) },
            { key: "energy", label: `${t("measured")} kWh`, format: (v: number) => num(lang, v, 2) },
            { key: "expected", label: `${t("expected")} kWh`, format: (v: number) => num(lang, v, 2) },
            { key: "index", label: t("index"), format: (v: number) => num(lang, v, 3) },
          ],
          rows: perf,
          file: "performance_index",
        }}
      >
        {(big) => (perfOption ? <Chart option={perfOption} height={big ? "calc(100vh - 210px)" : 330} /> : <Empty>{t("noData")}</Empty>)}
      </Visual>
      <Visual title={t("v_learnt")} className="col-span-12 xl:col-span-4">
        {plant ? <Plant uid={uid!} m={plant} many={uids.length > 1} /> : <Empty>–</Empty>}
      </Visual>
      <Visual
        title={t("v_clock")}
        subtitle={t("clockSub")}
        className="col-span-12 lg:col-span-7"
        data={{
          columns: [
            { key: "period", label: t("period") },
            { key: "offset_h", label: t("offset"), format: (v: number) => num(lang, v, 1) },
            { key: "centroid_shift_h", label: t("centroid"), format: (v: number) => num(lang, v, 2) },
            { key: "days", label: t("daysCol") },
            { key: "agreement", label: t("agreement"), format: (v: number) => num(lang, v, 2) },
            { key: "confident", label: t("confident"), format: (v: boolean) => (v ? t("yes") : t("no")) },
          ],
          rows: clock,
          file: "clock_vs_sun",
        }}
      >
        {(big) => (clockOption ? <Chart option={clockOption} height={big ? "calc(100vh - 210px)" : 260} /> : <Empty>{t("noData")}</Empty>)}
      </Visual>
      <Visual title={t("v_notes")} className="col-span-12 lg:col-span-5">
        {diag?.notes.length ? <NoteList notes={diag.notes} /> : <Empty>–</Empty>}
      </Visual>
      {segments.length > 0 && (
        <Visual
          title={t("v_segments")}
          className="col-span-12"
          data={{
            columns: [
              { key: "start", label: t("start"), format: (v: string) => date(lang, v) },
              { key: "end", label: t("end"), format: (v: string) => date(lang, v) },
              { key: "days", label: t("daysCol") },
              { key: "level_start", label: `${t("index")} (${t("start").toLowerCase()})`, format: (v: number) => num(lang, v, 2) },
              { key: "level_end", label: `${t("index")} (${t("end").toLowerCase()})`, format: (v: number) => num(lang, v, 2) },
              // the trend and the loss of a period only where the library reports them (its notes say why not)
              { key: "trend_pct_per_year", label: t("perYear"), format: (v: number, row: Segment) => (row.trend_reported ? num(lang, v, 1) : "–") },
              { key: "lost_pct", label: `% ${t("lostPct")}`, format: (v: number, row: Segment) => (row.loss_reported ? num(lang, v, 0) : "–") },
            ],
            rows: segments,
            file: "segments",
          }}
        >
          <SegmentStrip segments={segments} reliable={reliable} />
        </Visual>
      )}
    </PageGrid>
  );
}

const capital = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** The periods between changes as a strip along time, each with its trend. */
type Segment = Diagnostics["segments"][number];

function SegmentStrip({ segments, reliable }: { segments: Segment[]; reliable: boolean }) {
  const t = useT();
  const lang = useStore((s) => s.lang);
  const t0 = wall(segments[0].start);
  const t1 = wall(segments.at(-1)!.end);
  const span = Math.max(t1 - t0, 1);
  return (
    <div className="space-y-2 py-1">
      <div className="flex h-9 overflow-hidden rounded-xl border border-line">
        {segments.map((s, i) => {
          const w = ((wall(s.end) - wall(s.start)) / span) * 100;
          const tr = s.trend_pct_per_year ?? 0;
          const color = !reliable ? C.withoutPv : s.trend_reported || s.loss_reported ? C.warn : C.accent;
          return (
            <div
              key={i}
              title={`${date(lang, s.start)} – ${date(lang, s.end)}`}
              className="flex items-center justify-center border-r border-surface text-[11px] font-semibold text-white transition-[flex-basis] duration-700 last:border-r-0"
              style={{ flexBasis: `${w}%`, background: color }}
            >
              {w > 8 && (s.trend_reported ? `${num(lang, tr, 0)}${t("perYear")}` : `${num(lang, s.days, 0)} ${t("daysCol").toLowerCase()}`)}
            </div>
          );
        })}
      </div>
      <div className="flex justify-between text-[11px] text-muted">
        <span>{date(lang, segments[0].start)}</span>
        <span>{date(lang, segments.at(-1)!.end)}</span>
      </div>
    </div>
  );
}
