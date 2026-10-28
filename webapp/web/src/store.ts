import { create } from "zustand";
import { translate, type Key } from "./i18n";
import type { Info, Lang, Payload, Quantity } from "./types";

export type PageId = "overview" | "next" | "history" | "check" | "system" | "bill" | "notes";
export type PriceKind = "none" | "flat" | "tou" | "brazil";

export interface Form {
  where: "address" | "coords";
  address: string;
  latitude: string;
  longitude: string;
  timezone: string;
  file_times: "local" | "UTC";
  days: number;
  models: string;
  test_days: number;
  load_hours: number;
  load_kw: string;
  weeks: number;
  issue_hour: number;
  tilt: string;
  azimuth: string;
  kwp: string;
  time_column: string;
  value_column: string;
  unit: string;
  kind: string;
  price: PriceKind;
  flat: { price: string; export_price: string; fixed: string; currency: string; scheme: string };
  tou: {
    peak_hours: string;
    peak_price: string;
    offpeak_price: string;
    export_price: string;
    fixed: string;
    currency: string;
    scheme: string;
  };
  brazil: {
    distributor: string;
    icms: string;
    pis_cofins: string;
    connection: string;
    gd: string;
    cosip: string;
    modality: string;
    peak_start: string;
    credit: string;
  };
}

export const DEFAULT_FORM: Form = {
  where: "coords",
  address: "",
  latitude: "",
  longitude: "",
  timezone: "",
  file_times: "local",
  days: 7,
  models: "lightgbm",
  test_days: 28,
  load_hours: 3,
  load_kw: "2",
  weeks: 4,
  issue_hour: 0,
  tilt: "",
  azimuth: "",
  kwp: "",
  time_column: "",
  value_column: "",
  unit: "",
  kind: "",
  price: "none",
  flat: { price: "", export_price: "", fixed: "", currency: "BRL", scheme: "net_metering" },
  tou: { peak_hours: "17-21", peak_price: "", offpeak_price: "", export_price: "", fixed: "", currency: "BRL", scheme: "net_metering" },
  brazil: {
    distributor: "COPEL-DIS",
    icms: "19",
    pis_cofins: "",
    connection: "bifasico_3",
    gd: "GD II",
    cosip: "",
    modality: "Convencional",
    peak_start: "18:00",
    credit: "",
  },
};

/** A saved form over the defaults, the nested prices too: a form saved before a field existed gets its default. */
function withDefaults(f: Partial<Form> | undefined): Form {
  return {
    ...DEFAULT_FORM,
    ...(f ?? {}),
    flat: { ...DEFAULT_FORM.flat, ...(f?.flat ?? {}) },
    tou: { ...DEFAULT_FORM.tou, ...(f?.tou ?? {}) },
    brazil: { ...DEFAULT_FORM.brazil, ...(f?.brazil ?? {}) },
  };
}

const SAVED = "prosumer-site";

function load(): Partial<{ lang: Lang; theme: "light" | "dark"; form: Form; pane: boolean }> {
  try {
    return JSON.parse(localStorage.getItem(SAVED) ?? "{}");
  } catch {
    return {};
  }
}

function save(s: { lang: Lang; theme: "light" | "dark"; form: Form; pane: boolean }) {
  try {
    localStorage.setItem(SAVED, JSON.stringify(s));
  } catch {
    /* private window: the page still works, it only forgets */
  }
}

const saved = load();
const browserLang: Lang = navigator.language?.toLowerCase().startsWith("pt") ? "pt" : "en";
const browserTheme = window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";

interface State {
  lang: Lang;
  theme: "light" | "dark";
  page: PageId;
  pane: boolean;
  /** the Inputs pane over the whole screen */
  paneWide: boolean;
  info: Info | null;
  payload: Payload | null;
  running: boolean;
  startedAt: number | null;
  error: string | null;
  form: Form;
  files: Partial<Record<Quantity, File>>;
  selectedDay: string | null;
  t: (key: Key, params?: Record<string, string | number>) => string;
  set: (patch: Partial<State>) => void;
  setForm: (patch: Partial<Form>) => void;
  setFile: (q: Quantity, f: File | null) => void;
  toggleDay: (day: string | null) => void;
}

export const useStore = create<State>((set, get) => ({
  lang: saved.lang ?? browserLang,
  theme: saved.theme ?? browserTheme,
  page: "overview",
  pane: saved.pane ?? true,
  paneWide: false,
  info: null,
  payload: null,
  running: false,
  startedAt: null,
  error: null,
  form: withDefaults(saved.form),
  files: {},
  selectedDay: null,
  t: (key, params) => translate(get().lang, key, params),
  set: (patch) => set(patch),
  setForm: (patch) => set((s) => ({ form: { ...s.form, ...patch } })),
  setFile: (q, f) =>
    set((s) => {
      const files = { ...s.files };
      if (f) files[q] = f;
      else delete files[q];
      return { files };
    }),
  toggleDay: (day) => set((s) => ({ selectedDay: day === null || s.selectedDay === day ? null : day })),
}));

useStore.subscribe((s) => save({ lang: s.lang, theme: s.theme, form: s.form, pane: s.pane }));

/** `t` bound to the current language, re-rendering when it changes. */
export function useT() {
  const lang = useStore((s) => s.lang);
  return (key: Key, params?: Record<string, string | number>) => translate(lang, key, params);
}
