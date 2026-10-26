import type { EChartsOption } from "echarts";
import { ArrowUpFromLine, CalendarClock, PiggyBank, Receipt, Recycle, Zap } from "lucide-react";
import { useMemo, useState } from "react";
import { Chart } from "../components/Chart";
import { Kpi } from "../components/Kpi";
import { Empty, Visual } from "../components/Visual";
import { sum } from "../derive";
import { money, monthLabel, num, pct } from "../format";
import { code } from "../i18n";
import { useStore, useT } from "../store";
import { alpha, BASE, C, LEGEND } from "../theme";
import type { BillMonth, Lang, Payload } from "../types";
import { NoteList, PageGrid } from "./common";

const BLOCK_COLOR: Record<string, string> = {
  peak: C.warn,
  ponta: C.warn,
  intermediario: C.self,
  off_peak: C.accent,
  fora_ponta: C.accent,
  all: C.grid,
};

/** The bill month by month, with and without the PV, where the energy went, and the table the library made.
 * A click on a month filters the flows and the blocks to it. */
export function Bill({ payload }: { payload: Payload }) {
  const t = useT();
  const lang = useStore((s) => s.lang);
  const dark = useStore((s) => s.theme) === "dark";
  const r = payload.result;
  const econ = r.report.economics;
  const withPv = !!r.outlooks.generation;
  const [month, setMonth] = useState<string | null>(null);
  const pick = (m: string | null) => setMonth((x) => (m === null || x === m ? null : m));

  // the months summed over the series (one bill per meter; a file may carry several)
  const months = useMemo(() => {
    const by = new Map<string, BillMonth>();
    for (const m of econ?.monthly ?? []) {
      const k = m.month.slice(0, 7);
      const x = by.get(k);
      if (!x) by.set(k, { ...m, month: k });
      else for (const [c, v] of Object.entries(m)) if (!RATIOS.has(c) && typeof v === "number" && typeof x[c] === "number") x[c] = (x[c] as number) + v;
    }
    return [...by.values()].sort((a, b) => a.month.localeCompare(b.month));
  }, [econ]);
  const cur = econ?.currency ?? "";
  const scope = month ? months.filter((m) => m.month === month) : months;

  // ------------------------------------------------------------ the bill per month, with and without PV
  const billOption = useMemo<EChartsOption>(
    () => ({
      ...BASE,
      legend: { ...LEGEND },
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, valueFormatter: (v: any) => money(lang, v, cur) },
      xAxis: { type: "category", data: months.map((m) => monthLabel(lang, `${m.month}-01`)) },
      yAxis: { type: "value", name: cur },
      series: [
        ...(withPv
          ? [
              {
                id: "without",
                name: t("withoutPv"),
                type: "bar" as const,
                barGap: "8%",
                itemStyle: { color: C.withoutPv },
                data: months.map((m) => ({ value: round(m.without_pv), itemStyle: { color: C.withoutPv, opacity: month && m.month !== month ? 0.3 : 1, borderRadius: [2, 2, 0, 0] } })),
                animationDelay: (k: number) => k * 50,
              },
            ]
          : []),
        {
          id: "with",
          name: withPv ? t("withPv") : t("total"),
          type: "bar" as const,
          itemStyle: { color: C.grid },
          data: months.map((m) => ({ value: round(m.total), itemStyle: { color: C.grid, opacity: month && m.month !== month ? 0.3 : 1, borderRadius: [2, 2, 0, 0] } })),
          animationDelay: (k: number) => k * 50 + 120,
        },
        ...(withPv
          ? [
              {
                id: "savings",
                name: t("savings"),
                type: "line" as const,
                smooth: true,
                symbolSize: 7,
                lineStyle: { width: 2.4, color: C.savings },
                itemStyle: { color: C.savings },
                data: months.map((m) => round(m.savings)),
              },
            ]
          : []),
      ],
    }),
    [months, month, withPv, cur, lang, t],
  );

  // ------------------------------------------------------------ the flows: PV -> home / exported, grid -> home
  const flows = useMemo(
    () => ({
      self: sum(scope.map((m) => m.self_consumption)),
      export: sum(scope.map((m) => m.export)),
      grid: sum(scope.map((m) => m.grid_import)),
    }),
    [scope],
  );
  const flowOption = useMemo<EChartsOption>(() => {
    const links = [
      ...(withPv ? [{ source: t("pv"), target: t("home"), value: flows.self }] : []),
      ...(withPv ? [{ source: t("pv"), target: t("exported"), value: flows.export }] : []),
      { source: t("grid"), target: t("home"), value: flows.grid },
    ].filter((l) => l.value > 0);
    const nodes = [
      // the sources' labels on their left, the targets' on their right: no label over a flow
      ...(withPv ? [{ name: t("pv"), itemStyle: { color: C.generation }, label: { position: "left" as const } }] : []),
      { name: t("grid"), itemStyle: { color: C.grid }, label: { position: "left" as const } },
      { name: t("home"), itemStyle: { color: C.consumption } },
      ...(withPv ? [{ name: t("exported"), itemStyle: { color: C.export } }] : []),
    ].filter((n) => links.some((l) => l.source === n.name || l.target === n.name));
    return {
      ...BASE,
      tooltip: { trigger: "item", valueFormatter: (v: any) => `${num(lang, v, 0)} kWh` },
      series: [
        {
          id: "flows",
          type: "sankey",
          left: 96,
          right: 96,
          top: 12,
          bottom: 12,
          nodeWidth: 16,
          nodeGap: 18,
          draggable: false,
          emphasis: { focus: "adjacency" },
          lineStyle: { color: "gradient", opacity: 0.38, curveness: 0.5 },
          label: { fontSize: 11.5, color: dark ? "#D2D0CE" : "#3B3A39", formatter: (p: any) => `${p.name}\n${num(lang, p.value, 0)} kWh` },
          data: nodes,
          links,
        },
      ],
    };
  }, [flows, withPv, dark, lang, t]);

  // ------------------------------------------------------------ the grid import by tariff block
  const blocks = useMemo(() => {
    const by = new Map<string, number>();
    for (const b of econ?.by_block ?? []) {
      if (month && b.month.slice(0, 7) !== month) continue;
      by.set(b.block, (by.get(b.block) ?? 0) + (b.grid_import ?? 0));
    }
    return [...by.entries()].map(([block, value]) => ({ block, value }));
  }, [econ, month]);
  const donutOption = useMemo<EChartsOption>(() => {
    // one block only (a flat or conventional price): the donut says where the home's energy came from instead
    const one = blocks.length < 2;
    const data = one
      ? [
          ...(withPv ? [{ name: t("selfConsumed"), value: round(flows.self) ?? 0, itemStyle: { color: C.generation } }] : []),
          { name: t("gridImport"), value: round(flows.grid) ?? 0, itemStyle: { color: C.grid } },
        ]
      : blocks.map((b) => ({ name: code(lang, b.block), value: round(b.value) ?? 0, itemStyle: { color: BLOCK_COLOR[b.block] ?? C.purple } }));
    const total = sum(data.map((d) => d.value));
    return {
      ...BASE,
      legend: { bottom: 0, left: "center" },
      tooltip: { trigger: "item", formatter: (p: any) => `${p.name}: ${num(lang, p.value, 0)} kWh (${pct(lang, p.percent / 100, 0)})` },
      title: {
        text: `${num(lang, total, 0)}`,
        subtext: "kWh",
        left: "center",
        top: "36%",
        textStyle: { fontSize: 22, fontWeight: 300 },
        subtextStyle: { fontSize: 11 },
      },
      series: [
        {
          id: "blocks",
          type: "pie",
          radius: ["52%", "74%"],
          center: ["50%", "44%"],
          avoidLabelOverlap: true,
          itemStyle: { borderColor: "transparent", borderWidth: 2, borderRadius: 3 },
          label: { show: false },
          emphasis: { scale: true, scaleSize: 6 },
          animationType: "expansion",
          data,
        },
      ],
    };
  }, [blocks, flows, withPv, lang, t]);

  // ------------------------------------------------------------ the energy of the bill per month
  const energyOption = useMemo<EChartsOption>(() => {
    const line = (id: string, name: string, color: string, values: (number | null)[], area = false) => ({
      id,
      name,
      type: "line" as const,
      smooth: true,
      symbolSize: 5,
      lineStyle: { width: 2, color },
      itemStyle: { color },
      areaStyle: area ? { color: alpha(color, 0.1) } : undefined,
      data: values.map(round),
    });
    return {
      ...BASE,
      grid: { ...BASE.grid, right: 34 },
      legend: { ...LEGEND },
      tooltip: { trigger: "axis", valueFormatter: (v: any) => `${num(lang, v, 0)} kWh` },
      xAxis: { type: "category", boundaryGap: false, data: months.map((m) => monthLabel(lang, `${m.month}-01`)) },
      yAxis: { type: "value", name: "kWh" },
      series: [
        line("e-cons", t("consumption"), C.consumption, months.map((m) => m.consumption), true),
        ...(withPv ? [line("e-gen", t("generation"), C.generation, months.map((m) => m.generation), true)] : []),
        line("e-grid", t("gridImport"), C.grid, months.map((m) => m.grid_import)),
        ...(withPv ? [line("e-exp", t("exported"), C.export, months.map((m) => m.export))] : []),
      ],
    };
  }, [months, withPv, lang, t]);

  if (!econ) {
    const why = r.report.skipped?.economics ? [r.report.skipped.economics] : []; // the library says why
    return (
      <PageGrid>
        <Visual title={t("page_bill")} className="col-span-12">
          <div className="space-y-3 py-2">
            <p className="text-[13px] text-ink">{t("billEmpty")}</p>
            {why.length > 0 && <NoteList notes={why} />}
          </div>
        </Visual>
      </PageGrid>
    );
  }

  const tot = {
    total: sum(scope.map((m) => m.total)),
    without: sum(scope.map((m) => m.without_pv)),
    savings: sum(scope.map((m) => m.savings)),
    consumption: sum(scope.map((m) => m.consumption)),
  };
  const totals = econ.totals;
  const meanMonth = month ? tot.total : sum(totals.map((x) => x.mean_month));
  const complete = Math.min(...totals.map((x) => x.complete_months));
  const selfShare = tot.consumption > 0 ? flows.self / tot.consumption : null;
  const label = month ? monthLabel(lang, `${month}-01`) : t("allMonths", { n: months.length });
  const kpis = [
    <Kpi key="total" label={t("kpi_billTotal", { p: label })} value={tot.total} format={(v) => money(lang, v, econ.currency)} sub={econ.tariff} color={C.grid} icon={<Receipt size={14} />} />,
    ...(withPv
      ? [
          <Kpi key="without" label={t("withoutPv")} value={tot.without} format={(v) => money(lang, v, econ.currency)} sub={label} color={C.withoutPv} icon={<Zap size={14} />} />,
          <Kpi
            key="savings"
            label={t("kpi_savings")}
            value={tot.savings}
            format={(v) => money(lang, v, econ.currency)}
            sub={tot.without > 0 ? t("savedShare", { p: pct(lang, tot.savings / tot.without, 0) }) : undefined}
            color={C.savings}
            icon={<PiggyBank size={14} />}
          />,
        ]
      : []),
    <Kpi
      key="mean"
      label={month ? t("kpi_billMonth") : t("kpi_bill")}
      value={meanMonth}
      format={(v) => money(lang, v, econ.currency)}
      sub={month ? label : t("kpi_billSub", { n: complete })}
      color={C.accent}
      icon={<CalendarClock size={14} />}
    />,
    ...(withPv
      ? [
          <Kpi key="self" label={t("kpi_selfShare")} value={selfShare} format={(v) => pct(lang, v, 0)} sub={t("kpi_selfShareSub", { kwh: num(lang, flows.self, 0) })} color={C.generation} icon={<Recycle size={14} />} />,
          <Kpi key="export" label={t("exported")} value={flows.export} format={(v) => num(lang, v, 0)} unit="kWh" sub={label} color={C.export} icon={<ArrowUpFromLine size={14} />} />,
        ]
      : []),
  ];
  const span = kpis.length >= 6 ? "2xl:col-span-2" : kpis.length === 4 ? "xl:col-span-3" : "xl:col-span-6";

  const columns = billColumns(econ.monthly, lang, econ.currency);
  return (
    <PageGrid>
      {kpis.map((k, i) => (
        <div key={i} className={`col-span-6 ${kpis.length > 2 ? "md:col-span-4" : ""} ${span}`}>
          {k}
        </div>
      ))}
      <Visual
        title={t("v_billMonthly")}
        subtitle={month ? `${label} · ${t("clearSelection")}` : t("clickMonth")}
        className="col-span-12 lg:col-span-8"
        data={{ columns, rows: months, file: "bill_per_month" }}
        actions={
          month ? (
            <button type="button" className="rounded-sm px-1.5 text-[11px] text-[#118DFF] hover:underline" onClick={() => pick(null)}>
              {t("clearSelection")}
            </button>
          ) : undefined
        }
      >
        {(big) => <Chart option={billOption} height={big ? "calc(100vh - 210px)" : 300} onColumnClick={(k) => months[k] && pick(months[k].month)} />}
      </Visual>
      <Visual title={blocks.length < 2 ? t("v_homeFrom") : t("v_blocks")} subtitle={label} className="col-span-12 lg:col-span-4">
        {(big) => <Chart option={donutOption} height={big ? "calc(100vh - 210px)" : 300} />}
      </Visual>
      <Visual title={t("v_flows")} subtitle={label} className="col-span-12 lg:col-span-6">
        {(big) => (flows.grid + flows.self + flows.export > 0 ? <Chart option={flowOption} height={big ? "calc(100vh - 210px)" : 280} /> : <Empty>{t("noData")}</Empty>)}
      </Visual>
      <Visual title={t("v_billEnergy")} className="col-span-12 lg:col-span-6">
        {(big) => <Chart option={energyOption} height={big ? "calc(100vh - 210px)" : 280} />}
      </Visual>
      <Visual title={t("v_billTable")} subtitle={t("tariffLine", { t: econ.tariff })} className="col-span-12 xl:col-span-8" data={{ columns, rows: econ.monthly, file: "bill" }}>
        <BillTable columns={columns} rows={months} month={month} onPick={pick} />
      </Visual>
      <Visual title={t("v_notes")} subtitle={`${t("scheme")}: ${econ.scheme}`} className="col-span-12 xl:col-span-4">
        <NoteList notes={econ.notes} />
      </Visual>
    </PageGrid>
  );
}

function round(v: number | null | undefined): number | null {
  return v == null || !Number.isFinite(v) ? null : +v.toFixed(2);
}

// the bill's columns, in the order the library gives them; a Brazilian bill has more (charges, flag, credits)
const MONEY = new Set(["energy_cost", "export_value", "fixed", "minimum_value", "energy_charge", "compensation_charge", "energy_bill", "cosip", "total", "without_pv", "savings"]);
const RATIOS = new Set(["coverage", "price", "charge_share", "hours"]); // not summed over the series
const SKIP = new Set(["unique_id", "hours", "charge_base"]);
const LABELS: Record<Lang, Record<string, string>> = {
  en: {
    month: "Month",
    coverage: "Coverage",
    consumption: "Consumption kWh",
    generation: "Generation kWh",
    self_consumption: "Self-consumed kWh",
    grid_import: "From the grid kWh",
    export: "Exported kWh",
    compensated: "Compensated kWh",
    credit_used: "Credits used kWh",
    credit_new: "New credits kWh",
    credit_expired: "Credits expired kWh",
    credit_balance: "Credit balance kWh",
    energy_cost: "Energy",
    export_value: "Export value",
    fixed: "Fixed",
    gd_class: "GD class",
    charge_share: "Fio B share",
    flag: "Flag",
    price: "Price per kWh",
    minimum_value: "Minimum (availability)",
    energy_charge: "Energy charge",
    compensation_charge: "Charge on compensated",
    minimum_applied: "Minimum applied",
    energy_bill: "Energy bill",
    cosip: "COSIP",
    total: "Total",
    without_pv: "Without PV",
    savings: "Savings",
  },
  pt: {
    month: "Mês",
    coverage: "Cobertura",
    consumption: "Consumo kWh",
    generation: "Geração kWh",
    self_consumption: "Autoconsumo kWh",
    grid_import: "Da rede kWh",
    export: "Injetada kWh",
    compensated: "Compensada kWh",
    credit_used: "Créditos usados kWh",
    credit_new: "Créditos novos kWh",
    credit_expired: "Créditos expirados kWh",
    credit_balance: "Saldo de créditos kWh",
    energy_cost: "Energia",
    export_value: "Valor da injeção",
    fixed: "Fixo",
    gd_class: "Classe GD",
    charge_share: "Parcela do Fio B",
    flag: "Bandeira",
    price: "Preço por kWh",
    minimum_value: "Mínimo (disponibilidade)",
    energy_charge: "Encargo de energia",
    compensation_charge: "Encargo sobre a compensada",
    minimum_applied: "Mínimo aplicado",
    energy_bill: "Conta de energia",
    cosip: "COSIP",
    total: "Total",
    without_pv: "Sem FV",
    savings: "Economia",
  },
};

function billColumns(rows: BillMonth[], lang: Lang, currency: string) {
  const keys = rows.length ? Object.keys(rows[0]).filter((k) => !SKIP.has(k)) : [];
  return keys.map((k) => ({
    key: k,
    label: LABELS[lang][k] ?? k,
    format: (v: unknown): string => {
      if (k === "month") return monthLabel(lang, `${String(v).slice(0, 7)}-01`);
      if (typeof v === "boolean") return v ? (lang === "pt" ? "sim" : "yes") : lang === "pt" ? "não" : "no";
      if (typeof v !== "number") return v == null ? "–" : code(lang, String(v));
      if (k === "coverage" || k === "charge_share") return pct(lang, v, 0);
      if (MONEY.has(k)) return money(lang, v, currency);
      if (k === "price") return num(lang, v, 3);
      return num(lang, v, 1);
    },
  }));
}

/** The bill as a table, the chosen month marked; a click on a row chooses it. */
function BillTable({ columns, rows, month, onPick }: { columns: ReturnType<typeof billColumns>; rows: BillMonth[]; month: string | null; onPick: (m: string) => void }) {
  return (
    <div className="max-h-[340px] overflow-auto">
      <table className="w-full border-collapse text-[12px]">
        <thead className="sticky top-0 z-10 bg-surface">
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={`whitespace-nowrap border-b-2 border-line px-2 py-1.5 font-semibold text-ink ${c.key === "month" ? "text-left" : "text-right"}`}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.month}
              onClick={() => onPick(r.month)}
              className={`cursor-pointer border-b border-line/60 hover:bg-hover ${month === r.month ? "bg-[#118DFF]/10" : "odd:bg-zebra"}`}
            >
              {columns.map((c) => (
                <td key={c.key} className={`whitespace-nowrap px-2 py-1 ${c.key === "month" ? "text-left text-ink" : "text-right tabular-nums text-muted"} ${c.key === "total" ? "font-semibold text-ink" : ""}`}>
                  {c.format(r[c.key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
