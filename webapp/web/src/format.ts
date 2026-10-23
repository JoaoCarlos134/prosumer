// Numbers and dates for the person. The library's timestamps carry the site's offset ("...T10:00:00+01:00"):
// the page shows the SITE's wall clock wherever it is opened, so each one is read as its wall-clock part and
// handled as UTC (the charts set `useUTC`).
import type { Lang } from "./types";

const LOCALE: Record<Lang, string> = { en: "en-GB", pt: "pt-BR" };

/** Milliseconds of the wall-clock part of an ISO timestamp, as if it were UTC. */
export function wall(iso: string): number {
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?/.exec(iso);
  if (!m) return Number.NaN;
  return Date.UTC(+m[1], +m[2] - 1, +m[3], +(m[4] ?? 0), +(m[5] ?? 0), +(m[6] ?? 0));
}

/** The day of a timestamp, "YYYY-MM-DD". */
export function dayKey(iso: string): string {
  return iso.slice(0, 10);
}

export function num(lang: Lang, v: number | null | undefined, digits = 1): string {
  if (v == null || !Number.isFinite(v)) return "–";
  return new Intl.NumberFormat(LOCALE[lang], { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(v);
}

export function compact(lang: Lang, v: number | null | undefined, digits = 1): string {
  if (v == null || !Number.isFinite(v)) return "–";
  const a = Math.abs(v);
  const d = a >= 100 ? 0 : a >= 10 ? Math.min(digits, 1) : digits;
  return new Intl.NumberFormat(LOCALE[lang], { maximumFractionDigits: d, minimumFractionDigits: d }).format(v);
}

export function pct(lang: Lang, v: number | null | undefined, digits = 0): string {
  if (v == null || !Number.isFinite(v)) return "–";
  return new Intl.NumberFormat(LOCALE[lang], {
    style: "percent",
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(v);
}

export function money(lang: Lang, v: number | null | undefined, currency: string): string {
  if (v == null || !Number.isFinite(v)) return "–";
  try {
    return new Intl.NumberFormat(LOCALE[lang], { style: "currency", currency, maximumFractionDigits: 2 }).format(v);
  } catch {
    return `${num(lang, v, 2)} ${currency}`;
  }
}

function fmt(lang: Lang, ms: number, o: Intl.DateTimeFormatOptions): string {
  if (!Number.isFinite(ms)) return "–";
  return new Intl.DateTimeFormat(LOCALE[lang], { timeZone: "UTC", ...o }).format(new Date(ms));
}

export const date = (lang: Lang, iso: string) => fmt(lang, wall(iso), { day: "2-digit", month: "short", year: "numeric" });
export const dayLabel = (lang: Lang, iso: string) => fmt(lang, wall(iso), { weekday: "short", day: "2-digit", month: "short" });
/** A day under a bar: the weekday over the day and month, narrow enough for a phone. */
export const dayTick = (lang: Lang, iso: string) =>
  `${fmt(lang, wall(iso), { weekday: "short" })}\n${fmt(lang, wall(iso), { day: "2-digit", month: "2-digit" })}`;
export const weekday = (lang: Lang, iso: string) => fmt(lang, wall(iso), { weekday: "long" });
export const time = (lang: Lang, iso: string) => fmt(lang, wall(iso), { hour: "2-digit", minute: "2-digit", hour12: false });
export const monthLabel = (lang: Lang, iso: string) => fmt(lang, wall(iso), { month: "short", year: "numeric" });
export const dateTime = (lang: Lang, iso: string) =>
  fmt(lang, wall(iso), { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hour12: false });

/** The offset of `tz` from UTC at `ms`, in minutes. */
function offsetMinutes(tz: string, ms: number): number {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-US", { timeZone: tz, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })
      .formatToParts(new Date(ms))
      .map((p) => [p.type, p.value]),
  );
  return (Date.UTC(+parts.year, +parts.month - 1, +parts.day, +parts.hour, +parts.minute) - Math.floor(ms / 6e4) * 6e4) / 6e4;
}

/** The hours of a local day in `tz` ("YYYY-MM-DD"): 24, or 23 / 25 on a clock change. */
export function hoursInDay(tz: string, day: string): number {
  const start = (d: number) => {
    const guess = d - offsetMinutes(tz, d) * 6e4;
    return d - offsetMinutes(tz, guess) * 6e4;
  };
  try {
    const d = wall(day);
    return Math.round((start(d + 864e5) - start(d)) / 36e5);
  } catch {
    return 24; // an unknown time zone: the plain day
  }
}

/** A compass direction for an azimuth in degrees (0 north, 90 east). */
export function compass(lang: Lang, deg: number): string {
  const en = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  const pt = ["N", "NE", "L", "SE", "S", "SO", "O", "NO"];
  const i = Math.round((((deg % 360) + 360) % 360) / 45) % 8;
  return (lang === "pt" ? pt : en)[i];
}

/** Rows as CSV text (for "Export data"). */
export function toCsv(columns: { key: string; label: string }[], rows: Record<string, unknown>[]): string {
  const cell = (v: unknown) => {
    const s = v == null ? "" : String(v);
    return /[",\n;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [columns.map((c) => cell(c.label)).join(","), ...rows.map((r) => columns.map((c) => cell(r[c.key])).join(","))].join("\n");
}

export function download(name: string, text: string, type = "text/csv") {
  const url = URL.createObjectURL(new Blob([text], { type: `${type};charset=utf-8` }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
