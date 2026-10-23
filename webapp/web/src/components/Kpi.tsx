import { animate, motion, useMotionTemplate, useMotionValue, useReducedMotion, useSpring, useTransform } from "framer-motion";
import { useEffect, useRef, useState, type PointerEvent, type ReactNode } from "react";
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
  // a card that leans toward the pointer, a soft glare where it points
  const px = useMotionValue(0.5);
  const py = useMotionValue(0.5);
  const rotateX = useSpring(useTransform(py, [0, 1], [7, -7]), { stiffness: 220, damping: 18 });
  const rotateY = useSpring(useTransform(px, [0, 1], [-9, 9]), { stiffness: 220, damping: 18 });
  const gx = useTransform(px, (v) => `${v * 100}%`);
  const gy = useTransform(py, (v) => `${v * 100}%`);
  const glare = useMotionTemplate`radial-gradient(220px circle at ${gx} ${gy}, rgba(255,255,255,.22), transparent 60%)`;
  const still = useReducedMotion(); // the system asks for less motion: no tilt
  const move = (e: PointerEvent<HTMLElement>) => {
    if (still) return;
    const r = e.currentTarget.getBoundingClientRect();
    px.set((e.clientX - r.left) / r.width);
    py.set((e.clientY - r.top) / r.height);
  };
  const leave = () => {
    px.set(0.5);
    py.set(0.5);
  };
  return (
    <div style={{ perspective: 900 }} className="h-full">
    <motion.section
      variants={item}
      onPointerMove={move}
      onPointerLeave={leave}
      whileHover={still ? undefined : { scale: 1.025, z: 20 }}
      style={{ rotateX, rotateY, transformStyle: "preserve-3d" }}
      className="tile group relative flex h-full min-w-0 flex-col justify-between overflow-hidden px-4 py-3"
    >
      <motion.div className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100" style={{ background: glare }} />
      <div className="pointer-events-none absolute -right-8 -top-10 h-28 w-28 rounded-full opacity-[0.10] blur-2xl dark:opacity-[0.16]" style={{ background: color }} />
      <div className="absolute inset-x-4 top-0 h-[3px] rounded-b-full" style={{ background: color }} />
      <div className="flex items-start gap-2 text-[12px] font-semibold leading-tight text-muted" title={label}>
        {icon && <span className="mt-px shrink-0" style={{ color }}>{icon}</span>}
        <span className="line-clamp-2">{label}</span>
      </div>
      <div className="mt-1 flex items-baseline gap-1.5">
        <span className={`${text !== undefined && text.length > 7 ? "text-[19px] sm:text-[22px]" : "text-[22px] sm:text-[30px]"} font-light leading-none tracking-tight whitespace-nowrap text-ink tabular-nums`}>
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
        <div className="line-clamp-2 min-w-0 text-[11px] leading-snug text-muted">{sub}</div>
        {spark && spark.length > 1 && <Spark values={spark} color={color} />}
      </div>
    </motion.section>
    </div>
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
