import { motion } from "framer-motion";
import { Info } from "lucide-react";
import type { ReactNode } from "react";

const container = { hidden: {}, show: { transition: { staggerChildren: 0.06, delayChildren: 0.05 } } };

/** A page of the report: a 12-column grid whose tiles come in one after the other. */
export function PageGrid({ children }: { children: ReactNode }) {
  return (
    <motion.div variants={container} initial="hidden" animate="show" className="grid grid-cols-12 gap-3">
      {children}
    </motion.div>
  );
}

/** A slicer: chips, one active (or none, "all"), the active one filled. */
export function Chips<T extends string>({
  value,
  options,
  onChange,
  allLabel,
}: {
  value: T | null;
  options: { value: T; label: string; color?: string }[];
  onChange: (v: T | null) => void;
  allLabel?: string;
}) {
  const chip = (active: boolean) =>
    `rounded-full border px-3 py-1 text-[12px] transition ${active ? "border-transparent text-white shadow-sm" : "border-line bg-surface text-muted hover:text-ink"}`;
  return (
    <div className="col-span-12 flex flex-wrap items-center gap-1.5">
      {allLabel && (
        <button type="button" className={chip(value === null)} style={value === null ? { background: "#605E5C" } : undefined} onClick={() => onChange(null)}>
          {allLabel}
        </button>
      )}
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          className={chip(value === o.value)}
          style={value === o.value ? { background: o.color ?? "#118DFF" } : undefined}
          onClick={() => onChange(value === o.value && allLabel ? null : o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/** Notes of the library, each as a line with an icon. */
export function NoteList({ notes }: { notes: string[] }) {
  return (
    <ul className="space-y-2">
      {notes.map((n, i) => (
        <motion.li
          key={i}
          initial={{ opacity: 0, x: -6 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.03 * i }}
          className="flex gap-2 text-[12.5px] leading-snug text-muted"
        >
          <Info size={14} className="mt-0.5 shrink-0 text-[#118DFF]" />
          <span>{n}</span>
        </motion.li>
      ))}
    </ul>
  );
}

/** A coloured label for a day's confidence. */
export function Badge({ color, children }: { color: string; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10.5px] font-semibold" style={{ background: `${color}22`, color }}>
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: color }} />
      {children}
    </span>
  );
}

/** A round number at or above `v` (1, 1.2, 1.5, 2, 2.5, ... x 10^n), for an axis top. */
export function niceCeil(v: number): number {
  const p = 10 ** Math.floor(Math.log10(v));
  for (const m of [1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]) if (m * p >= v - 1e-12) return m * p;
  return 10 * p;
}
