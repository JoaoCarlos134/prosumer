import { motion } from "framer-motion";
import { CalendarClock, PlugZap, Receipt, ShieldCheck, Sparkles, Upload } from "lucide-react";
import { start } from "../run";
import { useStore, useT } from "../store";
import { Sun } from "./Sun";

const container = { hidden: {}, show: { transition: { staggerChildren: 0.08 } } };
const rise = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1] as const } } };

/** The first page: what the site does, the demo, and where the files go. */
export function Landing() {
  const t = useT();
  const set = useStore((s) => s.set);
  const running = useStore((s) => s.running);
  const features = [
    { icon: <CalendarClock size={18} />, text: t("feature1"), color: "#E66C37" },
    { icon: <PlugZap size={18} />, text: t("feature2"), color: "#118DFF" },
    { icon: <ShieldCheck size={18} />, text: t("feature3"), color: "#744EC2" },
    { icon: <Receipt size={18} />, text: t("feature4"), color: "#1AAB40" },
  ];
  return (
    <motion.div variants={container} initial="hidden" animate="show" className="mx-auto max-w-6xl py-6 md:py-10">
      <div className="grid items-center gap-8 md:grid-cols-[1.1fr_1fr]">
        <div>
          <motion.h1 variants={rise} className="text-[28px] font-semibold leading-tight tracking-tight text-ink md:text-[36px]">
            {t("heroTitle")}
          </motion.h1>
          <motion.p variants={rise} className="mt-3 max-w-xl text-[14px] leading-relaxed text-muted">
            {t("heroText")}
          </motion.p>
          <motion.div variants={rise} className="mt-6 flex flex-wrap items-center gap-3">
            <button
              type="button"
              disabled={running}
              onClick={() => start("demo")}
              className="flex items-center gap-2 rounded-xl bg-[#118DFF] px-4 py-2.5 text-[13.5px] font-semibold text-white shadow-md transition hover:-translate-y-0.5 hover:bg-[#0d7ae0] hover:shadow-lg disabled:opacity-50"
            >
              <Sparkles size={16} />
              {t("tryDemo")}
            </button>
            <button
              type="button"
              onClick={() => set({ pane: true, paneWide: true })}
              className="flex items-center gap-2 rounded-xl border border-line bg-surface px-4 py-2.5 text-[13.5px] text-ink transition hover:bg-hover"
            >
              <Upload size={16} />
              {t("orUpload")}
            </button>
          </motion.div>
          <motion.p variants={rise} className="mt-3 text-[12px] text-muted">
            {t("demoText")}
          </motion.p>
        </div>
        <motion.div variants={rise}>
          <Illustration />
        </motion.div>
      </div>
      <div className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {features.map((f) => (
          <motion.div key={f.text} variants={rise} className="rounded-xl border border-line bg-surface p-4 shadow-tile transition hover:-translate-y-0.5 hover:shadow-tile-hover">
            <span className="flex h-9 w-9 items-center justify-center rounded-full" style={{ background: `${f.color}1f`, color: f.color }}>
              {f.icon}
            </span>
            <p className="mt-3 text-[13px] font-semibold leading-snug text-ink">{f.text}</p>
          </motion.div>
        ))}
      </div>
      <motion.p variants={rise} className="mt-8 max-w-3xl text-[11.5px] leading-relaxed text-muted">
        {t("privacy")}
      </motion.p>
    </motion.div>
  );
}

/** A small animated scene: the sun over a roof with panels, energy flowing to the house and the grid. */
function Illustration() {
  const flow = { strokeDasharray: "6 8", animate: { strokeDashoffset: [0, -28] }, transition: { duration: 1.2, repeat: Infinity, ease: "linear" as const } };
  return (
    <div className="relative overflow-hidden rounded-2xl border border-line bg-surface p-4 shadow-tile">
      <svg viewBox="0 0 420 260" className="w-full">
        <defs>
          <linearGradient id="sky" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor="#118DFF" stopOpacity="0.16" />
            <stop offset="1" stopColor="#118DFF" stopOpacity="0" />
          </linearGradient>
        </defs>
        <rect width="420" height="260" fill="url(#sky)" />
        <Sun cx={86} cy={64} r={22} rays={12} rayFrom={32} rayLength={14} rayWidth={4} turn={30} pulse={3} />
        {/* rays onto the panels */}
        <motion.path d="M110 80 L200 120" stroke="#F2B705" strokeWidth="2.5" fill="none" {...flow} />
        <motion.path d="M100 92 L180 140" stroke="#F2B705" strokeWidth="2.5" fill="none" {...flow} />
        {/* house */}
        <path d="M170 150 L250 98 L330 150 Z" fill="#3B3A39" />
        <path d="M188 138 L250 98 L312 138" fill="none" stroke="#12239E" strokeWidth="0" />
        <g transform="translate(196 112) skewX(-30) scale(1 0.62)">
          {[0, 1, 2, 3].map((i) => (
            <rect key={i} x={i * 26} y="0" width="22" height="34" fill="#12239E" stroke="#118DFF" strokeWidth="1.5" />
          ))}
        </g>
        <rect x="185" y="150" width="130" height="80" fill="#605E5C" />
        <rect x="235" y="182" width="30" height="48" fill="#E66C37" />
        <motion.rect x="200" y="166" width="22" height="18" fill="#F2B705" animate={{ opacity: [0.5, 1, 0.5] }} transition={{ duration: 2.4, repeat: Infinity }} />
        <motion.rect x="278" y="166" width="22" height="18" fill="#F2B705" animate={{ opacity: [1, 0.5, 1] }} transition={{ duration: 2.4, repeat: Infinity }} />
        {/* grid pole and the flows */}
        <path d="M380 230 L380 120 M362 132 L398 132 M366 146 L394 146" stroke="#A19F9D" strokeWidth="4" strokeLinecap="round" />
        <motion.path d="M315 196 C340 196 350 150 372 140" stroke="#1AAB40" strokeWidth="3" fill="none" {...flow} />
        <motion.path d="M40 230 L170 230" stroke="#118DFF" strokeWidth="3" fill="none" {...flow} />
        {/* bars */}
        {[48, 72, 60, 92, 80, 104, 66].map((h, i) => (
          <motion.rect
            key={i}
            x={26 + i * 18}
            width="12"
            rx="2"
            fill={i === 5 ? "#E66C37" : "#118DFF"}
            initial={{ height: 0, y: 214 }}
            animate={{ height: h * 0.5, y: 214 - h * 0.5 }}
            transition={{ delay: 0.4 + i * 0.08, duration: 0.7, ease: "easeOut" }}
            opacity={0.85}
          />
        ))}
      </svg>
    </div>
  );
}
