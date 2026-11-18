import { ApiError, runAnalysis, runDemo } from "./api";
import { translate } from "./i18n";
import { useStore } from "./store";

/** Start an analysis (the person's files) or the demo; the page shows the loading screen meanwhile. */
export async function start(kind: "run" | "demo") {
  const s = useStore.getState();
  if (s.running) return;
  s.set({ running: true, startedAt: Date.now(), error: null, paneWide: false });
  try {
    const p = kind === "demo" ? await runDemo(s.lang, s.form.models) : await runAnalysis(s.form, s.files, s.lang);
    // the pane folds into its rail after a run, on every screen: the report gets the width (product review
    // 16/11: it stayed open, a fifth of the width); one click on the rail opens it again
    useStore.getState().set({ payload: p, page: "overview", selectedDay: null, pane: false });
  } catch (e) {
    const msg = e instanceof ApiError && e.message ? e.message : translate(useStore.getState().lang, "serverDown");
    useStore.getState().set({ error: msg });
  } finally {
    useStore.getState().set({ running: false, startedAt: null });
  }
}
