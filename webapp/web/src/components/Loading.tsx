import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import type { Key } from "../i18n";
import { useStore, useT } from "../store";
import { Spin } from "./Spin";

const STEPS: Key[] = ["step1", "step2", "step3", "step4", "step5", "step6", "step7"];

/** While `app.run` works: its seven steps (it reports none of them as it goes, so no fake progress), an
 * indeterminate bar, the seconds so far, and skeleton tiles behind. */
export function Loading() {
  const t = useT();
  const startedAt = useStore((s) => s.startedAt);
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 200);
    return () => clearInterval(id);
  }, []);
  const seconds = startedAt ? (now - startedAt) / 1000 : 0;
  return (
    <div className="relative h-full min-h-[560px]">
      <Skeleton />
      <div className="absolute inset-0 flex items-start justify-center pt-[12vh]">
        <motion.div
          initial={{ opacity: 0, y: 12, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          className="w-[min(420px,92vw)] rounded-2xl border border-line bg-surface p-5 shadow-2xl"
        >
          <div className="flex items-center gap-3">
            <SunSpinner />
            <div>
              <h2 className="text-[15px] font-semibold text-ink">{t("loadingTitle")}</h2>
              <p className="text-[12px] tabular-nums text-muted">{seconds.toFixed(1)} s</p>
            </div>
          </div>
          <div className="relative mt-4 h-1 overflow-hidden rounded-full bg-hover">
            <motion.div
              className="absolute inset-y-0 w-1/3 rounded-full bg-gradient-to-r from-[#118DFF] via-[#744EC2] to-[#E66C37]"
              animate={{ x: ["-100%", "300%"] }}
              transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
            />
          </div>
          <ol className="mt-4 space-y-1.5">
            {STEPS.map((k, i) => (
              <motion.li
                key={k}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.08 * i }}
                className="flex items-center gap-2 text-[12.5px] text-muted"
              >
                <span className="flex h-5 w-5 items-center justify-center rounded-full border border-line text-[10px] font-semibold text-ink">{i + 1}</span>
                {t(k)}
              </motion.li>
            ))}
          </ol>
          <p className="mt-4 text-[11px] text-muted">{t("loadingNote")}</p>
        </motion.div>
      </div>
    </div>
  );
}

function SunSpinner() {
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" aria-hidden>
      <Spin cx={20} cy={20} seconds={6}>
        {Array.from({ length: 8 }, (_, i) => (
          <rect key={i} x="19" y="2" width="2" height="6" rx="1" fill="#F2B705" transform={`rotate(${i * 45} 20 20)`} opacity={0.4 + (i % 2) * 0.6} />
        ))}
      </Spin>
      <motion.circle cx="20" cy="20" r="7" fill="#F2B705" style={{ transformBox: "fill-box", transformOrigin: "center" }} animate={{ scale: [0.93, 1.14, 0.93] }} transition={{ duration: 1.6, repeat: Infinity }} />
    </svg>
  );
}

function Skeleton() {
  return (
    <div className="pointer-events-none grid grid-cols-12 gap-3 opacity-70">
      {[3, 3, 3, 3, 8, 4, 8, 4].map((span, i) => (
        <div key={i} className="shimmer rounded-xl border border-line" style={{ gridColumn: `span ${span} / span ${span}`, height: i < 4 ? 104 : 280 }} />
      ))}
    </div>
  );
}
