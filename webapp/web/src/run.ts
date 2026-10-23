import { ApiError, runAnalysis, runDemo } from "./api";
import { translate } from "./i18n";
import { useStore } from "./store";

/** Start an analysis (the person's files) or the demo; the page shows the loading screen meanwhile. */
export async function start(kind: "run" | "demo") {
  const s = useStore.getState();
  if (s.running) return;
  s.set({ running: true, startedAt: Date.now(), error: null });
  try {
    const p = kind === "demo" ? await runDemo(s.lang, s.form.models) : await runAnalysis(s.form, s.files, s.lang);
    useStore.getState().set({ payload: p, page: "overview", selectedDay: null });
    // on a phone the pane covers the report: close it to show the result
    if (window.matchMedia?.("(max-width: 767px)").matches) useStore.getState().set({ pane: false });
  } catch (e) {
    const msg = e instanceof ApiError && e.message ? e.message : translate(useStore.getState().lang, "serverDown");
    useStore.getState().set({ error: msg });
  } finally {
    useStore.getState().set({ running: false, startedAt: null });
  }
}
