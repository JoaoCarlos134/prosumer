import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp } from "lucide-react";

export interface Column {
  key: string;
  label: string;
  format?: (v: any, row: any) => string;
  align?: "left" | "right";
}

/** A sortable report table: sticky header, zebra rows, numbers to the right. */
export function DataTable({ columns, rows, maxHeight = 320 }: { columns: Column[]; rows: any[]; maxHeight?: number | string }) {
  const [sort, setSort] = useState<{ key: string; desc: boolean } | null>(null);
  const sorted = useMemo(() => {
    if (!sort) return rows;
    const out = [...rows];
    out.sort((a, b) => {
      const x = a[sort.key];
      const y = b[sort.key];
      const c = typeof x === "number" && typeof y === "number" ? x - y : String(x ?? "").localeCompare(String(y ?? ""));
      return sort.desc ? -c : c;
    });
    return out;
  }, [rows, sort]);
  return (
    <div className="overflow-auto rounded-sm" style={{ maxHeight }}>
      <table className="w-full border-collapse text-[12px]">
        <thead className="sticky top-0 z-10 bg-surface">
          <tr>
            {columns.map((c) => {
              const right = c.align ? c.align === "right" : rows.some((r) => typeof r[c.key] === "number");
              return (
                <th
                  key={c.key}
                  onClick={() => setSort((s) => (s?.key === c.key ? { key: c.key, desc: !s.desc } : { key: c.key, desc: false }))}
                  className={`cursor-pointer select-none whitespace-nowrap border-b-2 border-line px-2 py-1.5 font-semibold text-ink hover:bg-hover ${right ? "text-right" : "text-left"}`}
                >
                  <span className="inline-flex items-center gap-1">
                    {c.label}
                    {sort?.key === c.key && (sort.desc ? <ArrowDown size={11} /> : <ArrowUp size={11} />)}
                  </span>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((r, i) => (
            <tr key={i} className="odd:bg-zebra hover:bg-hover">
              {columns.map((c) => {
                const v = r[c.key];
                const right = c.align ? c.align === "right" : typeof v === "number";
                return (
                  <td key={c.key} className={`border-b border-line/60 px-2 py-1 text-muted ${right ? "text-right tabular-nums" : "text-left"}`}>
                    {c.format ? c.format(v, r) : v == null ? "–" : String(v)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
