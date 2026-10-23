import { animate, motion } from "framer-motion";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { item } from "./Visual";

/** A number that counts up to its value (and glides to a new one). */
export function CountUp({ value, format }: { value: number | null | undefined; format: (v: number) => string }) {
  const [shown, setShown] = useState(0);
  const from = useRef(0);
  useEffect(() => {
    if (value == null || !Number.isFinite(value)) return;
    const controls = animate(from.current, value, {
      duration: 1.1,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: (v) => setShown(v),
    });
    from.current = value;
    return () => controls.stop();
  }, [value]);
  if (value == null || !Number.isFinite(value)) return <>–</>;
  return <>{format(shown)}</>;
}

interface Props {
  label: string;
  value?: number | null;
  format?: (v: number) => string;
  text?: string;
  unit?: string;
  sub?: ReactNode;
  color?: string;
  icon?: ReactNode;
  spark?: number[];
}

/** A card visual: the big number, its label and a line under it, with a sparkline when given. */
export function Kpi({ label, value, format = (v) => v.toFixed(1), text, unit, sub, color = "#118DFF", icon, spark }: Props) {
  return (
    <motion.section
      variants={item}
      className="relative flex min-w-0 flex-col justify-between overflow-hidden rounded-[3px] border border-line bg-surface px-4 py-3 shadow-tile transition-shadow hover:shadow-tile-hover"
    >
      <div className="absolute inset-x-0 top-0 h-[3px]" style={{ background: color }} />
      <div className="flex items-center gap-2 text-[12px] font-semibold text-muted">
        {icon && <span style={{ color }}>{icon}</span>}
        <span className="truncate">{label}</span>
      </div>
      <div className="mt-1 flex items-baseline gap-1.5">
        <span className="text-[30px] font-light leading-none tracking-tight text-ink tabular-nums">
          {text !== undefined ? (
            <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 }}>
              {text}
            </motion.span>
          ) : (
            <CountUp value={value} format={format} />
          )}
        </span>
        {unit && <span className="text-sm text-muted">{unit}</span>}
      </div>
      <div className="mt-1.5 flex items-end justify-between gap-2">
        <div className="min-w-0 truncate text-[11px] text-muted">{sub}</div>
        {spark && spark.length > 1 && <Spark values={spark} color={color} />}
      </div>
    </motion.section>
  );
}

function Spark({ values, color }: { values: number[]; color: string }) {
  const w = 84;
  const h = 26;
  const max = Math.max(...values, 1e-9);
  const min = Math.min(...values, 0);
  const pts = values.map((v, i) => [(i / (values.length - 1)) * w, h - ((v - min) / (max - min || 1)) * (h - 2) - 1]);
  const d = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  return (
    <svg width={w} height={h} className="shrink-0 overflow-visible">
      <motion.path
        d={`${d} L${w},${h} L0,${h} Z`}
        fill={color}
        opacity={0.12}
        initial={{ opacity: 0 }}
        animate={{ opacity: 0.12 }}
        transition={{ delay: 0.6, duration: 0.6 }}
      />
      <motion.path
        d={d}
        fill="none"
        stroke={color}
        strokeWidth={1.6}
        strokeLinecap="round"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 1.2, ease: "easeOut" }}
      />
    </svg>
  );
}
