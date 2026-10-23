import { motion } from "framer-motion";
import { BookOpen, CalendarDays, Gauge, History, LayoutDashboard, Receipt, SunMedium } from "lucide-react";
import type { ReactNode } from "react";
import type { Key } from "../i18n";
import { useStore, useT, type PageId } from "../store";

const PAGES: { id: PageId; key: Key; icon: ReactNode }[] = [
  { id: "overview", key: "page_overview", icon: <LayoutDashboard size={14} /> },
  { id: "next", key: "page_next", icon: <CalendarDays size={14} /> },
  { id: "history", key: "page_history", icon: <History size={14} /> },
  { id: "check", key: "page_check", icon: <Gauge size={14} /> },
  { id: "system", key: "page_system", icon: <SunMedium size={14} /> },
  { id: "bill", key: "page_bill", icon: <Receipt size={14} /> },
  { id: "notes", key: "page_notes", icon: <BookOpen size={14} /> },
];

/** The report's pages as tabs along the bottom edge, the active one marked by a sliding bar. */
export function PageTabs() {
  const t = useT();
  const { page, set, payload } = useStore();
  const hasPv = !!payload?.result.outlooks.generation;
  const pages = PAGES.filter((p) => p.id !== "system" || hasPv);
  return (
    <div className="shrink-0 border-t border-line/60 bg-tabs/70 px-2 py-1.5 backdrop-blur">
      <nav className="mx-auto flex w-fit max-w-full items-stretch gap-0.5 overflow-x-auto rounded-full border border-line/70 bg-surface p-1 shadow-tile">
        {pages.map((p) => {
          const active = p.id === page;
          return (
            <button
              key={p.id}
              type="button"
              onClick={() => set({ page: p.id })}
              className={`relative flex shrink-0 items-center gap-1.5 rounded-full px-3.5 py-1.5 text-[12.5px] transition-colors ${
                active ? "font-semibold text-white" : "text-muted hover:bg-hover hover:text-ink"
              }`}
            >
              {active && (
                <motion.span
                  layoutId="page-pill"
                  className="absolute inset-0 rounded-full bg-gradient-to-b from-[#2a9bff] to-[#0b74d8] shadow-[0_4px_12px_-2px_rgba(17,141,255,.55),inset_0_1px_0_rgba(255,255,255,.35)]"
                  transition={{ type: "spring", stiffness: 480, damping: 36 }}
                />
              )}
              <span className="relative flex items-center gap-1.5">
                {p.icon}
                {t(p.key)}
              </span>
            </button>
          );
        })}
      </nav>
    </div>
  );
}
