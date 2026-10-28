// The calls to the FastAPI server (server/api.py) and the form -> `prosumer.app.Request` mapping.
import type { Form } from "./store";
import type { Info, Lang, Payload, Quantity } from "./types";

export class ApiError extends Error {}

async function call<T>(url: string, init?: RequestInit): Promise<T> {
  let r: Response;
  try {
    r = await fetch(url, init);
  } catch {
    throw new ApiError("");
  }
  const body = await r.json().catch(() => null);
  if (!r.ok) throw new ApiError(body?.error ?? `${r.status} ${r.statusText}`);
  return body as T;
}

export const getInfo = () => call<Info>("/api/info");

export const getResult = (id: string, lang: Lang) => call<Payload>(`/api/result/${id}?lang=${lang}`);

export function runDemo(lang: Lang, models: string) {
  const body = new FormData();
  body.set("lang", lang);
  body.set("models", models);
  return call<Payload>("/api/demo", { method: "POST", body });
}

/** How the analysis would read one file (`prosumer.app.peek`): the preview under a dropped file. */
export interface Peek {
  file: string;
  how: string;
  hours: number;
  start: string;
  end: string;
  measured: number;
  series: string[];
  tz: string;
  log: string[];
}

export function peekFile(quantity: Quantity, file: File, form: Form, lang: Lang, signal?: AbortSignal) {
  const body = new FormData();
  body.set("quantity", quantity);
  body.set("request", JSON.stringify(toRequest(form)));
  body.set("lang", lang);
  body.set("file", file, file.name);
  return call<Peek>("/api/peek", { method: "POST", body, signal });
}

export function runAnalysis(form: Form, files: Partial<Record<Quantity, File>>, lang: Lang) {
  const body = new FormData();
  body.set("request", JSON.stringify(toRequest(form)));
  body.set("lang", lang);
  for (const [q, f] of Object.entries(files)) if (f) body.set(q, f, f.name);
  return call<Payload>("/api/run", { method: "POST", body });
}

/** '19' or '9,25' (%, as a bill shows them) -> 0.19, 0.0925; blank stays blank (the library asks for it). */
function percent(text: string): string | number {
  const s = text.trim().replace(",", ".");
  if (!s) return "";
  const v = Number(s);
  return Number.isFinite(v) ? v / 100 : text;
}

/** The form as the library's request: blank boxes are "not given" there, so they are sent as they are. */
export function toRequest(f: Form): Record<string, unknown> {
  const r: Record<string, unknown> = {
    timezone: f.timezone,
    file_times: f.file_times,
    days: f.days,
    models: f.models,
    test_days: f.test_days,
    load_hours: f.load_hours,
    load_kw: f.load_kw,
    weeks: f.weeks,
    issue_hour: f.issue_hour,
    tilt: f.tilt,
    azimuth: f.azimuth,
    kwp: f.kwp,
    time_column: f.time_column,
    value_column: f.value_column,
    unit: f.unit,
    kind: f.kind,
  };
  if (f.where === "address") r.address = f.address;
  else Object.assign(r, { latitude: f.latitude, longitude: f.longitude });
  if (f.price === "flat") r.price = { kind: "flat", ...f.flat };
  if (f.price === "tou") r.price = { kind: "tou", ...f.tou };
  if (f.price === "brazil") {
    const b = f.brazil;
    r.price = {
      kind: "brazil",
      distributor: b.distributor,
      icms: percent(b.icms),
      pis_cofins: percent(b.pis_cofins),
      connection: b.connection,
      gd: b.gd,
      cosip: b.cosip,
      modality: b.modality,
      peak_start: b.modality === "Branca" ? b.peak_start : "",
      credit: b.credit,
    };
  }
  return r;
}
