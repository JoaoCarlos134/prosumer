import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, X } from "lucide-react";
import { useEffect, type JSX } from "react";
import { getInfo, getResult } from "./api";
import { Header } from "./components/Header";
import { InputsPane } from "./components/InputsPane";
import { Landing } from "./components/Landing";
import { Loading } from "./components/Loading";
import { PageTabs } from "./components/PageTabs";
import { Bill } from "./pages/Bill";
import { Check } from "./pages/Check";
import { HistoryPage } from "./pages/History";
import { NextDays } from "./pages/NextDays";
import { Notes } from "./pages/Notes";
import { Overview } from "./pages/Overview";
import { System } from "./pages/System";
import { useStore, useT, type PageId } from "./store";
import type { Payload } from "./types";

const PAGES: Record<PageId, (p: { payload: Payload }) => JSX.Element> = {
  overview: Overview,
  next: NextDays,
  history: HistoryPage,
  check: Check,
  system: System,
  bill: Bill,
  notes: Notes,
};

export default function App() {
  const { theme, lang, payload, running, page, error, set } = useStore();
  const t = useT();

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);
  useEffect(() => {
    document.documentElement.lang = lang === "pt" ? "pt-BR" : "en";
  }, [lang]);
  useEffect(() => {
    getInfo()
      .then((info) => set({ info }))
      .catch(() => undefined);
  }, [set]);
  // a language switch re-renders the kept result in the other language (the server keeps it: no new run)
  useEffect(() => {
    if (payload && payload.lang !== lang)
      getResult(payload.id, lang)
        .then((p) => set({ payload: p }))
        .catch(() => undefined);
  }, [lang, payload, set]);

  const Page = PAGES[payload?.result.outlooks.generation || page !== "system" ? page : "overview"];
  return (
    <div className="flex h-full flex-col">
      <Header />
      <div className="relative flex min-h-0 flex-1">
        <main className="min-w-0 flex-1 overflow-y-auto">
          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="sticky top-0 z-30 mx-3 mt-3 flex items-start gap-3 rounded-xl border border-[#D64550]/40 bg-[#FDE7E9] px-4 py-3 text-[13px] text-[#A4262C] shadow-md dark:bg-[#442726] dark:text-[#F1BBBC]"
              >
                <AlertTriangle size={17} className="mt-0.5 shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="font-semibold">{t("errorTitle")}</div>
                  <div className="whitespace-pre-wrap break-words">{error}</div>
                </div>
                <button type="button" onClick={() => set({ error: null })} aria-label={t("close")} className="rounded-sm p-0.5 hover:bg-black/10">
                  <X size={15} />
                </button>
              </motion.div>
            )}
          </AnimatePresence>
          <div className="mx-auto max-w-[1680px] p-3 md:p-4">
            {running ? (
              <Loading />
            ) : payload ? (
              <AnimatePresence mode="wait">
                <motion.div key={page} initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -12 }} transition={{ duration: 0.22 }}>
                  <Page payload={payload} />
                </motion.div>
              </AnimatePresence>
            ) : (
              <Landing />
            )}
          </div>
        </main>
        <InputsPane />
      </div>
      {payload && !running && <PageTabs />}
    </div>
  );
}
