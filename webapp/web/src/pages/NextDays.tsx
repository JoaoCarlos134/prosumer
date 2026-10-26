import type { EChartsOption } from "echarts";
import { animate, motion } from "framer-motion";
import { Home, Sun } from "lucide-react";
import { useEffect, useMemo, useRef } from "react";
import { Chart } from "../components/Chart";
import { Empty, Visual } from "../components/Visual";
import { daily, hourly, present, type DayTotal } from "../derive";
import { compass, dateTime, dayKey, dayLabel, money, num, time, wall } from "../format";
import { code } from "../i18n";
import { useStore, useT } from "../store";
import { alpha, BASE, C, CONFIDENCE, LEGEND } from "../theme";
import type { Payload, PlantMethod, Quantity } from "../types";
import { Badge, Chips, NoteList, PageGrid } from "./common";
import { QCOLOR } from "./Overview";

const DAY = 864e5;

export function NextDays({ payload }: { payload: Payload }) {
  const t = useT();
  const lang = useStore((s) => s.lang);
  const selected = useStore((s) => s.selectedDay);
  const toggleDay = useStore((s) => s.toggleDay);
  const r = payload.result;
  const qs = present(r);
  const main: Quantity = qs.includes("generation") ? "generation" : "consumption";
  const days = useMemo(() => Object.fromEntries(qs.map((q) => [q, daily(r.outlooks[q])])) as Record<Quantity, DayTotal[]>, [r, qs]);
  const hours = useMemo(() => Object.fromEntries(qs.map((q) => [q, hourly(r.outlooks[q])])) as Record<Quantity, ReturnType<typeof hourly>>, [r, qs]);
  const dates = useMemo(() => [...new Set(qs.flatMap((q) => days[q].map((d) => d.date)))].sort(), [qs, days]);
  const loadHours = Number(payload.meta.request.load_hours ?? 3);
  const loadKw = Number(payload.meta.request.load_kw ?? 2);

  // ------------------------------------------------------------ hour by hour, with the range and the best hours
  const hourlyOption = useMemo<EChartsOption>(() => {
    const series: any[] = [];
    for (const q of qs) {
      const h = hours[q];
      series.push(
        {
          id: `lo-${q}`,
          type: "line",
          stack: `band-${q}`,
          symbol: "none",
          lineStyle: { opacity: 0 },
          tooltip: { show: false },
          data: h.map((x) => [wall(x.ds), x.low]),
          silent: true,
        },
        {
          id: `band-${q}`,
          name: `${t(q)} · ${t("range")}`,
          type: "line",
          stack: `band-${q}`,
          symbol: "none",
          lineStyle: { opacity: 0 },
          areaStyle: { color: alpha(QCOLOR[q], 0.16) },
          tooltip: { show: false },
          data: h.map((x) => [wall(x.ds), x.high == null || x.low == null ? null : x.high - x.low]),
          silent: true,
        },
        {
          id: `y-${q}`,
          name: t(q),
          type: "line",
          symbol: "none",
          smooth: 0.25,
          lineStyle: { width: 2, color: QCOLOR[q] },
          itemStyle: { color: QCOLOR[q] },
          data: h.map((x) => [wall(x.ds), x.y]),
          markArea:
            q === main
              ? {
                  silent: true,
                  itemStyle: { color: alpha(C.export, 0.12), borderColor: alpha(C.export, 0.5), borderWidth: 1, borderType: "dashed" },
                  data: r.windows.map((w) => [{ xAxis: wall(w.start) }, { xAxis: wall(w.end) }]),
                }
              : undefined,
        },
      );
    }
    const lo = selected ? wall(selected) : undefined;
    return {
      ...BASE,
      grid: { ...BASE.grid, bottom: 44 },
      legend: { ...LEGEND, data: qs.map((q) => t(q)) },
      tooltip: {
        trigger: "axis",
        formatter: (ps: any) => {
          const x = ps[0]?.value?.[0];
          const iso = new Date(x).toISOString();
          const rows = qs
            .map((q) => {
              const h = hours[q].find((y) => wall(y.ds) === x);
              if (!h) return "";
              return `<div><span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${QCOLOR[q]};margin-right:6px"></span>${t(q)}: <b>${num(lang, h.y, 2)}</b> kWh <span style="color:#888">(${num(lang, h.low, 2)}–${num(lang, h.high, 2)})</span></div>`;
            })
            .join("");
          return `<b>${dateTime(lang, iso)}</b>${rows}`;
        },
      },
      xAxis: { type: "time", min: lo, max: lo !== undefined ? lo + DAY : undefined },
      yAxis: { type: "value", name: "kWh" },
      dataZoom: [{ type: "inside" }, { type: "slider", height: 18, bottom: 8 }],
      series,
    };
  }, [qs, hours, r.windows, main, selected, lang, t]);

  // ------------------------------------------------------------ the blocks of each day: best by energy, cheapest by cost
  const costs = r.windows_by_cost ?? [];
  const timelineOption = useMemo<EChartsOption>(() => {
    const yLabels = dates.map((d) => dayLabel(lang, d));
    const idx = new Map(dates.map((d, i) => [d, i]));
    const hourOf = (iso: string, day: string) => (wall(iso) - wall(day)) / 36e5;
    const sunRows = dates.map((d, i) => {
      const sun = (r.outlooks.generation?.hourly ?? []).filter((h) => dayKey(h.ds) === d && h.sun);
      if (!sun.length) return [i, null, null];
      return [i, hourOf(sun[0].ds, d), hourOf(sun[sun.length - 1].ds, d) + 1];
    });
    const bar = (kind: number) => (params: any, api: any) => {
      void params;
      if (api.value(1) == null || Number.isNaN(api.value(1))) return null;
      const [x0, y] = api.coord([api.value(1), api.value(0)]);
      const [x1] = api.coord([api.value(2), api.value(0)]);
      const h = api.size([0, 1])[1];
      const bh = kind === 0 ? h * 0.7 : h * 0.26;
      const off = kind === 0 ? -bh / 2 : kind === 1 ? -h * 0.3 : h * 0.04;
      const color = kind === 0 ? alpha("#F2B705", 0.14) : kind === 1 ? C.forecast : C.export;
      return {
        type: "rect",
        shape: { x: x0, y: y + off, width: Math.max(x1 - x0, 2), height: bh, r: kind === 0 ? 0 : 3 },
        style: { fill: color },
        enterFrom: { shape: { width: 0 } },
      };
    };
    return {
      ...BASE,
      legend: { ...LEGEND, data: [`${t("window")} · ${t("energy")}`, ...(costs.length ? [`${t("window")} · ${t("cost")}`] : [])] },
      tooltip: {
        trigger: "item",
        formatter: (p: any) => {
          const [, a, b, extra] = p.value;
          const day = dates[p.value[0]];
          const span = `${String(Math.floor(a)).padStart(2, "0")}:00–${String(Math.floor(b) % 24).padStart(2, "0")}:00`;
          return `<b>${dayLabel(lang, day)}</b><br/>${p.seriesName}: ${span}${extra ? `<br/>${extra}` : ""}`;
        },
      },
      grid: { ...BASE.grid, left: 8 },
      xAxis: { type: "value", min: 0, max: 24, interval: 3, axisLabel: { formatter: (v: number) => `${String(v).padStart(2, "0")}h` } },
      yAxis: { type: "category", data: yLabels, inverse: true, splitLine: { show: true, lineStyle: { type: "dashed" } } },
      series: [
        { id: "sun", type: "custom", renderItem: bar(0) as any, data: sunRows, silent: true, tooltip: { show: false }, z: 1, encode: { x: [1, 2], y: 0 } },
        {
          id: "best",
          name: `${t("window")} · ${t("energy")}`,
          type: "custom",
          itemStyle: { color: C.forecast },
          renderItem: bar(1) as any,
          encode: { x: [1, 2], y: 0 },
          data: r.windows.map((w) => {
            const d = dayKey(w.date);
            return [idx.get(d) ?? 0, hourOf(w.start, d), hourOf(w.end, d), `${num(lang, w.energy, 1)} kWh · ${code(lang, w.confidence)}`];
          }),
        },
        ...(costs.length
          ? [
              {
                id: "cheap",
                name: `${t("window")} · ${t("cost")}`,
                type: "custom" as const,
                itemStyle: { color: C.export },
                renderItem: bar(2) as any,
                encode: { x: [1, 2], y: 0 },
                data: costs.map((w) => {
                  const d = dayKey(w.date);
                  return [idx.get(d) ?? 0, hourOf(w.start, d), hourOf(w.end, d), `${money(lang, w.cost, w.currency)} · ${num(lang, w.grid_kwh, 1)} ${t("gridKwh")}`];
                }),
              },
            ]
          : []),
      ],
    };
  }, [dates, r.windows, r.outlooks.generation, costs, lang, t]);

  // ------------------------------------------------------------ how far ahead the weather helps (generation)
  const gm = r.outlooks.generation?.method;
  const trustOption = useMemo<EChartsOption | null>(() => {
    if (!gm?.trust || !gm.skill) return null;
    const leads = gm.trust.map((_, i) => t("leadDay", { n: i + 1 }));
    return {
      ...BASE,
      legend: { ...LEGEND },
      tooltip: { trigger: "axis", valueFormatter: (v: any) => num(lang, v, 2) },
      xAxis: { type: "category", data: leads, boundaryGap: false },
      yAxis: { type: "value", min: 0, max: 1 },
      series: [
        { id: "trust", name: t("trust"), type: "line", data: gm.trust, symbolSize: 7, lineStyle: { width: 2, color: C.accent }, itemStyle: { color: C.accent }, areaStyle: { color: alpha(C.accent, 0.08) } },
        {
          id: "skill",
          name: t("skill"),
          type: "line",
          data: gm.skill,
          symbolSize: 7,
          lineStyle: { width: 2, color: C.generation },
          itemStyle: { color: C.generation },
          markLine: {
            silent: true,
            symbol: "none",
            lineStyle: { type: "dashed" },
            label: { formatter: "{b}", position: "insideEndTop", fontSize: 10 },
            data: [
              { yAxis: 0.4, name: t("thresholdHigh"), lineStyle: { color: CONFIDENCE.high } },
              { yAxis: 0.25, name: t("thresholdMedium"), lineStyle: { color: CONFIDENCE.medium } },
            ],
          },
        },
      ],
    };
  }, [gm, lang, t]);

  const notes = qs.flatMap((q) => r.outlooks[q]?.notes ?? []);
  const plants = Object.entries(gm?.series ?? {});

  return (
    <PageGrid>
      <Chips
        value={selected}
        allLabel={t("all")}
        options={dates.map((d) => ({ value: d, label: dayLabel(lang, d) }))}
        onChange={(v) => toggleDay(v)}
      />
      <Visual
        title={t("v_hourly")}
        className="col-span-12"
        data={{
          columns: [
            { key: "ds", label: t("hour"), format: (v: string) => dateTime(lang, v) },
            ...qs.flatMap((q) => [
              { key: `${q}_y`, label: `${t(q)} kWh` },
              { key: `${q}_low`, label: `${t(q)} ${t("low")}` },
              { key: `${q}_high`, label: `${t(q)} ${t("high")}` },
            ]),
          ],
          rows: hourRows(qs, hours, selected),
          file: "next_days_hourly",
        }}
      >
        {(big) => <Chart option={hourlyOption} height={big ? "calc(100vh - 210px)" : 330} />}
      </Visual>

      <div className="col-span-12 grid grid-cols-[repeat(auto-fill,minmax(140px,1fr))] gap-2">
        {dates.map((d, i) => {
          const x = days[main].find((y) => y.date === d);
          const active = selected === d;
          return (
            <motion.button
              key={d}
              type="button"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: selected && !active ? 0.55 : 1, y: 0 }}
              transition={{ delay: 0.04 * i }}
              whileHover={{ y: -2 }}
              onClick={() => toggleDay(d)}
              className={`tile min-w-0 p-3 text-left ${active ? "!border-[#118DFF] ring-2 ring-[#118DFF]/50" : ""}`}
            >
              <div className="flex items-center justify-between">
                <span className="truncate text-[12.5px] font-semibold text-ink">{dayLabel(lang, d)}</span>
                <span className="shrink-0 text-[10.5px] text-muted">{x?.lead_day === 0 ? t("today") : t("leadDay", { n: x?.lead_day ?? i + 1 })}</span>
              </div>
              {qs.map((q) => {
                const y = days[q].find((z) => z.date === d);
                return (
                  <div key={q} className="mt-1.5 flex items-center gap-1.5 text-[12px]">
                    <span style={{ color: QCOLOR[q] }}>{q === "generation" ? <Sun size={12} /> : <Home size={12} />}</span>
                    <span className="font-semibold tabular-nums text-ink">{num(lang, y?.total, 1)}</span>
                    <span className="text-muted">kWh</span>
                  </div>
                );
              })}
              {x && (
                <div className="mt-2 flex flex-wrap items-center gap-1">
                  <Badge color={CONFIDENCE[x.confidence] ?? "#888"}>{code(lang, x.confidence)}</Badge>
                  <span className="text-[10px] text-muted">{code(lang, x.source)}</span>
                </div>
              )}
            </motion.button>
          );
        })}
      </div>

      <Visual
        title={t("v_windows", { h: loadHours })}
        subtitle={costs.length ? t("v_costWindows", { h: loadHours, kw: num(lang, loadKw, 1) }) : undefined}
        className="col-span-12 lg:col-span-7"
        data={{
          columns: [
            { key: "date", label: t("date"), format: (v: string) => dayLabel(lang, v) },
            { key: "start", label: t("start"), format: (v: string) => time(lang, v) },
            { key: "end", label: t("end"), format: (v: string) => time(lang, v) },
            { key: "energy", label: t("kwhBlock"), format: (v: number) => num(lang, v, 2) },
            { key: "confidence", label: t("confidence"), format: (v: string) => code(lang, v) },
          ],
          rows: r.windows,
          file: "best_hours",
        }}
      >
        {(big) => <Chart option={timelineOption} height={big ? "calc(100vh - 210px)" : Math.max(220, 40 + dates.length * 34)} />}
      </Visual>

      {trustOption ? (
        <Visual title={t("v_trust")} className="col-span-12 lg:col-span-5">
          {(big) => <Chart option={trustOption} height={big ? "calc(100vh - 210px)" : 260} />}
        </Visual>
      ) : (
        <Visual title={t("v_learnt")} className="col-span-12 lg:col-span-5">
          <ProfileRule rule={r.outlooks.consumption?.method.rule} />
        </Visual>
      )}

      {costs.length > 0 && (
        <Visual
          title={t("v_costWindows", { h: loadHours, kw: num(lang, loadKw, 1) })}
          className="col-span-12 lg:col-span-7"
          data={{
            columns: [
              { key: "date", label: t("date"), format: (v: string) => dayLabel(lang, v) },
              { key: "start", label: t("start"), format: (v: string) => time(lang, v) },
              { key: "end", label: t("end"), format: (v: string) => time(lang, v) },
              { key: "cost", label: t("cost"), format: (v: number, row: any) => money(lang, v, row.currency) },
              { key: "grid_kwh", label: t("gridKwh"), format: (v: number) => num(lang, v, 2) },
              { key: "pv_kwh", label: t("pvKwh"), format: (v: number) => num(lang, v, 2) },
              { key: "confidence", label: t("confidence"), format: (v: string) => code(lang, v) },
            ],
            rows: costs,
            file: "cheapest_hours",
          }}
        >
          <CostList />
        </Visual>
      )}

      {plants.length > 0 && (
        <Visual title={t("v_learnt")} className={`col-span-12 ${costs.length ? "lg:col-span-5" : "lg:col-span-6"}`}>
          <div className="space-y-4">
            {plants.map(([uid, m]) => (
              <Plant key={uid} uid={uid} m={m} many={plants.length > 1} />
            ))}
          </div>
        </Visual>
      )}

      {notes.length > 0 && (
        <Visual title={t("v_notes")} className={`col-span-12 ${plants.length && !costs.length ? "lg:col-span-6" : ""}`}>
          <NoteList notes={notes} />
        </Visual>
      )}
    </PageGrid>
  );
}

function hourRows(qs: Quantity[], hours: Record<Quantity, ReturnType<typeof hourly>>, selected: string | null) {
  const by = new Map<string, Record<string, unknown>>();
  for (const q of qs)
    for (const h of hours[q]) {
      if (selected && dayKey(h.ds) !== selected) continue;
      const row = by.get(h.ds) ?? { ds: h.ds };
      row[`${q}_y`] = h.y == null ? null : +h.y.toFixed(3);
      row[`${q}_low`] = h.low == null ? null : +h.low.toFixed(3);
      row[`${q}_high`] = h.high == null ? null : +h.high.toFixed(3);
      by.set(h.ds, row);
    }
  return [...by.values()].sort((a, b) => String(a.ds).localeCompare(String(b.ds)));
}

function CostList() {
  const t = useT();
  const lang = useStore((s) => s.lang);
  const r = useStore((s) => s.payload!.result);
  const costs = r.windows_by_cost ?? [];
  const max = Math.max(...costs.map((c) => c.cost ?? 0), 1e-9);
  return (
    <div className="space-y-1.5">
      {costs.map((c, i) => (
        <div key={i} className="grid grid-cols-[110px_90px_1fr_auto] items-center gap-2 text-[12px]">
          <span className="text-ink">{dayLabel(lang, c.date)}</span>
          <span className="tabular-nums text-muted">
            {time(lang, c.start)}–{time(lang, c.end)}
          </span>
          <div className="h-2 overflow-hidden rounded-full bg-hover">
            <motion.div className="h-full rounded-full" style={{ background: C.export }} initial={{ width: 0 }} animate={{ width: `${((c.cost ?? 0) / max) * 100}%` }} transition={{ duration: 0.8, delay: 0.05 * i }} />
          </div>
          <span className="text-right font-semibold tabular-nums text-ink">{money(lang, c.cost, c.currency)}</span>
        </div>
      ))}
      <p className="pt-1 text-[11px] text-muted">{t("tariffLine", { t: costs[0]?.tariff ?? "" })}</p>
    </div>
  );
}

function ProfileRule({ rule }: { rule?: string }) {
  if (!rule) return <Empty>–</Empty>;
  return <p className="text-[13px] leading-relaxed text-muted">{rule}</p>;
}

/** The plant the forecast is built on: a compass with the panels' azimuth, the tilt, the effective power. */
export function Plant({ uid, m, many }: { uid: string; m: PlantMethod; many: boolean }) {
  const t = useT();
  const lang = useStore((s) => s.lang);
  const az = m.azimuth ?? 0;
  const tilt = m.tilt ?? 0;
  // the panel rises to its tilt about its lower end (20, 70): an SVG rotate(a, cx, cy), animated by hand
  // (CSS transform origins on SVG are not the same in every browser)
  const panel = useRef<SVGGElement>(null);
  const needle = useRef<SVGGElement>(null); // swings to the azimuth about the compass centre (0, 0)
  useEffect(() => {
    const c = animate(az - 120, az, { type: "spring", stiffness: 60, damping: 9, onUpdate: (a) => needle.current?.setAttribute("transform", `rotate(${a})`) });
    return () => c.stop();
  }, [az]);
  useEffect(() => {
    const c = animate(0, -tilt, { duration: 1.2, ease: "easeOut", onUpdate: (a) => panel.current?.setAttribute("transform", `rotate(${a} 20 70)`) });
    return () => c.stop();
  }, [tilt]);
  return (
    <div className="flex flex-wrap items-center gap-5">
      <svg width="120" height="120" viewBox="-60 -60 120 120" className="shrink-0">
        <circle r="54" fill="none" stroke="var(--line)" strokeWidth="1.5" />
        {Array.from({ length: 36 }, (_, i) => (
          <line key={i} x1="0" y1={-54} x2="0" y2={i % 9 === 0 ? -46 : -50} stroke="var(--muted)" strokeWidth={i % 9 === 0 ? 1.5 : 0.7} transform={`rotate(${i * 10})`} />
        ))}
        {(lang === "pt" ? ["N", "L", "S", "O"] : ["N", "E", "S", "W"]).map((l, i) => (
          <text key={l} x={Math.sin((i * Math.PI) / 2) * 36} y={-Math.cos((i * Math.PI) / 2) * 36 + 4} textAnchor="middle" fontSize="11" fontWeight="600" fill="var(--muted)">
            {l}
          </text>
        ))}
        <g ref={needle}>
          <path d="M0 -44 L7 0 L0 6 L-7 0 Z" fill={C.generation} />
          <path d="M0 44 L7 0 L0 -6 L-7 0 Z" fill="var(--line)" />
        </g>
        <circle r="4" fill="var(--surface)" stroke={C.generation} strokeWidth="2" />
      </svg>
      <svg width="110" height="96" viewBox="0 0 110 96" className="shrink-0">
        <line x1="5" y1="70" x2="105" y2="70" stroke="var(--muted)" strokeWidth="1.5" />
        <g ref={panel}>
          <rect x="20" y="64" width="78" height="6" rx="1" fill="#12239E" stroke="#118DFF" />
        </g>
        <path d={`M 60 70 A 40 40 0 0 0 ${20 + 40 * Math.cos((tilt * Math.PI) / 180)} ${70 - 40 * Math.sin((tilt * Math.PI) / 180)}`} fill="none" stroke={C.generation} strokeDasharray="3 3" />
        <text x="60" y="90" textAnchor="middle" fontSize="12" fontWeight="600" fill="var(--ink)">
          {num(lang, tilt, 0)}°
        </text>
      </svg>
      <dl className="grid min-w-[180px] flex-1 grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[12px]">
        {many && (
          <>
            <dt className="text-muted">{t("series")}</dt>
            <dd className="font-semibold text-ink">{uid}</dd>
          </>
        )}
        <dt className="text-muted">{t("tiltLbl")}</dt>
        <dd className="text-ink">{num(lang, tilt, 0)}°</dd>
        <dt className="text-muted">{t("azimuthLbl")}</dt>
        <dd className="text-ink">
          {num(lang, az, 0)}° ({compass(lang, az)})
        </dd>
        <dt className="text-muted">{t("orientation")}</dt>
        <dd className="text-ink">{code(lang, m.orientation)}</dd>
        <dt className="text-muted">{t("kwEff")}</dt>
        <dd className="font-semibold text-ink">{num(lang, m.kw_eff, 2)} kW</dd>
        {m.kw_eff_from && <dd className="col-span-2 text-[11px] text-muted">{m.kw_eff_from}</dd>}
      </dl>
    </div>
  );
}
