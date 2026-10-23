// Small computations several pages share (sums over the series of a file, months, rolling means).
import { dayKey } from "./format";
import type { HistoryDay, Outlook, OutlookDay, Quantity, Result } from "./types";

export const QUANTITIES: Quantity[] = ["generation", "consumption"];

export function present(r: Result): Quantity[] {
  return QUANTITIES.filter((q) => r.outlooks[q]);
}

export interface DayTotal {
  date: string;
  lead_day: number;
  total: number;
  low: number;
  high: number;
  confidence: string;
  source: string;
  missing_hours: number;
}

/** A file's daily outlook summed over its series (a file may carry several inverters or meters). */
export function daily(o: Outlook | undefined): DayTotal[] {
  if (!o) return [];
  const by = new Map<string, DayTotal>();
  for (const d of o.daily as OutlookDay[]) {
    const k = dayKey(d.date);
    const x = by.get(k);
    if (x) {
      x.total += d.total ?? 0;
      x.low += d.low ?? 0;
      x.high += d.high ?? 0;
      x.missing_hours += d.missing_hours;
    } else {
      by.set(k, {
        date: k,
        lead_day: d.lead_day,
        total: d.total ?? 0,
        low: d.low ?? 0,
        high: d.high ?? 0,
        confidence: d.confidence,
        source: d.source,
        missing_hours: d.missing_hours,
      });
    }
  }
  return [...by.values()].sort((a, b) => a.date.localeCompare(b.date));
}

export interface HourTotal {
  ds: string;
  y: number | null;
  low: number | null;
  high: number | null;
  lead_day: number;
}

export function hourly(o: Outlook | undefined): HourTotal[] {
  if (!o) return [];
  const by = new Map<string, HourTotal>();
  for (const h of o.hourly) {
    const x = by.get(h.ds);
    if (x) {
      x.y = add(x.y, h.y_hat);
      x.low = add(x.low, h.low);
      x.high = add(x.high, h.high);
    } else by.set(h.ds, { ds: h.ds, y: h.y_hat, low: h.low, high: h.high, lead_day: h.lead_day });
  }
  return [...by.values()].sort((a, b) => a.ds.localeCompare(b.ds));
}

function add(a: number | null, b: number | null): number | null {
  return a == null ? b : b == null ? a : a + b;
}

export interface HistTotal {
  date: string;
  /** The file's energy that day: null unless every series of the file has a value (one inverter off would
   * otherwise show the others' energy as the file's). */
  energy: number | null;
  /** Hours measured, the mean over the series (0 to the hours of the local day: 23 or 25 on a clock change). */
  measured_hours: number;
}

/** Each day of a file, summed over its series. */
export function history(r: Result, q: Quantity): HistTotal[] {
  const rows = (q === "generation" ? r.charts.history_generation : r.charts.history_consumption) ?? [];
  const n = new Set(rows.map((d) => d.unique_id)).size || 1;
  const by = new Map<string, { energy: number; valid: number; hours: number }>();
  for (const d of rows as HistoryDay[]) {
    const k = dayKey(d.date);
    const x = by.get(k) ?? { energy: 0, valid: 0, hours: 0 };
    if (d.energy != null) {
      x.energy += d.energy;
      x.valid += 1;
    }
    x.hours += d.measured_hours;
    by.set(k, x);
  }
  return [...by.entries()]
    .map(([date, x]) => ({ date, energy: x.valid === n ? x.energy : null, measured_hours: x.hours / n }))
    .sort((a, b) => a.date.localeCompare(b.date));
}

export function rolling(values: (number | null)[], n: number): (number | null)[] {
  const out: (number | null)[] = [];
  let sum = 0;
  let count = 0;
  const q: (number | null)[] = [];
  for (const v of values) {
    q.push(v);
    if (v != null) {
      sum += v;
      count++;
    }
    if (q.length > n) {
      const old = q.shift()!;
      if (old != null) {
        sum -= old;
        count--;
      }
    }
    out.push(count >= Math.ceil(n / 2) ? sum / count : null);
  }
  return out;
}

/** Sum of daily energy by month "YYYY-MM". */
export function monthly(days: HistTotal[]): Map<string, number> {
  const m = new Map<string, number>();
  for (const d of days) {
    if (d.energy == null) continue;
    const k = d.date.slice(0, 7);
    m.set(k, (m.get(k) ?? 0) + d.energy);
  }
  return m;
}

export function sum(xs: (number | null | undefined)[]): number {
  return xs.reduce<number>((a, b) => a + (b ?? 0), 0);
}
