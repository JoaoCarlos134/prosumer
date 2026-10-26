import { motion } from "framer-motion";
import { FileJson, Moon, PanelRightClose, PanelRightOpen, Plus, Sun } from "lucide-react";
import type { ReactNode } from "react";
import { download } from "../format";
import { Spin } from "./Spin";
import { useStore, useT } from "../store";
import type { Lang } from "../types";

export function Header() {
  const t = useT();
  const { lang, theme, payload, pane, set } = useStore();
  const files = payload ? Object.values(payload.meta.files).filter(Boolean).join(" · ") : "";
  return (
    <header className="flex h-12 shrink-0 items-center gap-2 bg-header px-3 sm:gap-3 text-white shadow-[0_1px_0_rgba(255,255,255,.06)]">
      <div className="flex items-center gap-2">
        <Logo />
        <div className="leading-tight">
          <div className="text-[15px] font-semibold tracking-tight">prosumer</div>
          <div className="hidden text-[10.5px] text-white/60 sm:block">{t("appTagline")}</div>
        </div>
      </div>
      <div className="mx-2 hidden h-6 w-px bg-white/15 md:block" />
      <div className="min-w-0 flex-1 overflow-hidden">
        {payload && (
          <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} className="flex min-w-0 items-center gap-2 text-[12.5px]">
            {payload.meta.demo && (
              <span className="shrink-0 rounded-md bg-[#F2B705] px-1.5 py-0.5 text-[10.5px] font-semibold text-black">
                <span className="sm:hidden">Demo</span>
                <span className="hidden sm:inline">{t("demoBadge")}</span>
              </span>
            )}
            <span className="hidden truncate text-white/90 sm:inline">{files}</span>
            <span className="hidden shrink-0 text-white/50 lg:inline">· {t("ranIn", { s: payload.meta.seconds.toLocaleString(lang === "pt" ? "pt-BR" : "en-GB") })}</span>
          </motion.div>
        )}
      </div>
      <Segmented value={lang} options={["en", "pt"]} onChange={(v) => set({ lang: v as Lang })} />
      <HeaderButton label={theme === "dark" ? t("themeLight") : t("themeDark")} onClick={() => set({ theme: theme === "dark" ? "light" : "dark" })}>
        {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
      </HeaderButton>
      {payload && (
        <>
          <HeaderButton label={t("downloadJson")} onClick={() => download(`prosumer_${payload.id}.json`, JSON.stringify(payload.result, null, 1), "application/json")}>
            <FileJson size={16} />
          </HeaderButton>
          <HeaderButton label={t("newAnalysis")} onClick={() => set({ payload: null, pane: true, selectedDay: null })}>
            <Plus size={16} />
          </HeaderButton>
        </>
      )}
      <HeaderButton label={t("inputs")} onClick={() => set({ pane: !pane })}>
        {pane ? <PanelRightClose size={16} /> : <PanelRightOpen size={16} />}
      </HeaderButton>
    </header>
  );
}

function HeaderButton({ label, onClick, children }: { label: string; onClick: () => void; children: ReactNode }) {
  return (
    <button type="button" title={label} aria-label={label} onClick={onClick} className="rounded-xl p-1.5 text-white/80 transition hover:bg-white/10 hover:text-white">
      {children}
    </button>
  );
}

function Segmented({ value, options, onChange }: { value: string; options: string[]; onChange: (v: string) => void }) {
  return (
    <div className="relative flex rounded-xl bg-white/10 p-0.5 text-[11px] font-semibold">
      {options.map((o) => (
        <button key={o} type="button" onClick={() => onChange(o)} className="relative z-10 px-2 py-0.5 uppercase">
          {value === o && <motion.span layoutId="lang-pill" className="absolute inset-0 -z-10 rounded-md bg-white" transition={{ type: "spring", stiffness: 500, damping: 35 }} />}
          <span className={value === o ? "text-black" : "text-white/75"}>{o}</span>
        </button>
      ))}
    </div>
  );
}

export function Logo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden>
      <rect width="32" height="32" rx="6" fill="#2b2a29" />
      {/* a full ring of rays turning about the sun's centre (16, 11) */}
      <Spin cx={16} cy={11} seconds={18}>
        {Array.from({ length: 8 }, (_, i) => (
          <line key={i} x1="16" y1="3.2" x2="16" y2="4.9" stroke="#F2B705" strokeWidth="1.8" strokeLinecap="round" transform={`rotate(${i * 45} 16 11)`} />
        ))}
      </Spin>
      <circle cx="16" cy="11" r="4.2" fill="#F2B705" />
      <rect x="7" y="22" width="4" height="5" rx="1" fill="#118DFF" />
      <rect x="14" y="20.5" width="4" height="6.5" rx="1" fill="#E66C37" />
      <rect x="21" y="23" width="4" height="4" rx="1" fill="#1AAB40" />
    </svg>
  );
}
