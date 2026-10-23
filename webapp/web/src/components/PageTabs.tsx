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
    <nav className="flex h-9 shrink-0 items-stretch overflow-x-auto border-t border-line bg-tabs px-2">
      {pages.map((p) => {
        const active = p.id === page;
        return (
          <button
            key={p.id}
            type="button"
            onClick={() => set({ page: p.id })}
            className={`relative flex shrink-0 items-center gap-1.5 px-3.5 text-[12.5px] transition-colors ${
              active ? "bg-surface font-semibold text-ink" : "text-muted hover:bg-hover hover:text-ink"
            }`}
          >
            {active && <motion.span layoutId="page-bar" className="absolute inset-x-0 bottom-0 h-[3px] bg-[#F2B705]" transition={{ type: "spring", stiffness: 520, damping: 40 }} />}
            {p.icon}
            {t(p.key)}
          </button>
        );
      })}
    </nav>
  );
}
