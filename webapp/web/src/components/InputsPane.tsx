import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, ChevronLeft, FileUp, Loader2, Play, Sparkles, X } from "lucide-react";
import { useRef, useState, type ReactNode } from "react";
import type { Key } from "../i18n";
import { start } from "../run";
import { useStore, useT, type Form, type PriceKind } from "../store";
import type { Quantity } from "../types";

/** The pane on the right, like a report's filter pane: everything the analysis asks, in folding sections. */
export function InputsPane() {
  const t = useT();
  const { pane, set, form, setForm, files, running, info } = useStore();
  const ready = Object.keys(files).length > 0 && (form.where === "address" ? !!form.address.trim() : !!form.latitude.trim() && !!form.longitude.trim());
  const problem = Object.keys(files).length === 0 ? t("needFile") : !ready ? t("needWhere") : "";

  if (!pane)
    return (
      <button
        type="button"
        onClick={() => set({ pane: true })}
        className="flex w-8 shrink-0 flex-col items-center gap-3 border-l border-line bg-pane pt-3 text-[12px] font-semibold text-muted hover:text-ink"
      >
        <ChevronLeft size={14} />
        <span style={{ writingMode: "vertical-rl" }}>{t("inputs")}</span>
      </button>
    );

  return (
    <motion.aside
      initial={{ width: 0, opacity: 0 }}
      animate={{ width: 330, opacity: 1 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="flex shrink-0 flex-col overflow-hidden border-l border-line bg-pane max-md:absolute max-md:inset-y-0 max-md:right-0 max-md:z-40 max-md:shadow-2xl"
    >
      <div className="flex items-center justify-between border-b border-line px-3 py-2">
        <h2 className="text-[14px] font-semibold text-ink">{t("inputs")}</h2>
        <button type="button" onClick={() => set({ pane: false })} className="rounded-sm p-1 text-muted hover:bg-hover hover:text-ink" aria-label={t("close")}>
          <X size={15} />
        </button>
      </div>
      <div className="min-h-0 flex-1 space-y-1 overflow-y-auto px-3 py-2">
        <Section title={t("sec_files")} open>
          <FileDrop quantity="generation" label={t("genFile")} />
          <FileDrop quantity="consumption" label={t("consFile")} />
        </Section>

        <Section title={t("sec_where")} open>
          <Seg
            value={form.where}
            options={[
              ["coords", t("byCoords")],
              ["address", t("byAddress")],
            ]}
            onChange={(v) => setForm({ where: v as Form["where"] })}
          />
          {form.where === "address" ? (
            <Field label={t("address")}>
              <input className="field" value={form.address} placeholder={t("addressHint")} onChange={(e) => setForm({ address: e.target.value })} />
            </Field>
          ) : (
            <div className="grid grid-cols-2 gap-2">
              <Field label={t("latitude")}>
                <input className="field" inputMode="decimal" value={form.latitude} placeholder="-25.43" onChange={(e) => setForm({ latitude: e.target.value })} />
              </Field>
              <Field label={t("longitude")}>
                <input className="field" inputMode="decimal" value={form.longitude} placeholder="-49.27" onChange={(e) => setForm({ longitude: e.target.value })} />
              </Field>
            </div>
          )}
          <Field label={t("timezone")} hint={t("timezoneHint")}>
            <input className="field" value={form.timezone} placeholder="America/Sao_Paulo" onChange={(e) => setForm({ timezone: e.target.value })} />
          </Field>
          <Field label={t("fileTimes")}>
            <Seg
              value={form.file_times}
              options={[
                ["local", t("local")],
                ["UTC", t("utc")],
              ]}
              onChange={(v) => setForm({ file_times: v as Form["file_times"] })}
            />
          </Field>
        </Section>

        <Section title={t("sec_forecast")} open>
          <Field label={`${t("days")}: ${form.days}`}>
            <input type="range" min={1} max={info?.max_days ?? 35} value={form.days} onChange={(e) => setForm({ days: +e.target.value })} className="w-full accent-[#118DFF]" />
          </Field>
          <Field label={t("models")}>
            <select className="field" value={form.models} onChange={(e) => setForm({ models: e.target.value })}>
              <option value="naive">{t("model_naive")}</option>
              <option value="lightgbm" disabled={info ? !info.models.lightgbm : false}>
                {t("model_lightgbm")}
              </option>
              <option value="all">{t("model_all")}</option>
            </select>
          </Field>
          <div className="grid grid-cols-3 gap-2">
            <Field label={t("loadHours")}>
              <input className="field" type="number" min={1} max={24} value={form.load_hours} onChange={(e) => setForm({ load_hours: +e.target.value || 1 })} />
            </Field>
            <Field label={t("loadKw")}>
              <input className="field" inputMode="decimal" value={form.load_kw} onChange={(e) => setForm({ load_kw: e.target.value })} />
            </Field>
            <Field label={t("testDays")}>
              <input className="field" type="number" min={2} value={form.test_days} onChange={(e) => setForm({ test_days: +e.target.value || 28 })} />
            </Field>
          </div>
        </Section>

        <Section title={t("sec_price")} open>
          <Seg
            value={form.price}
            options={[
              ["none", t("price_none")],
              ["flat", t("price_flat")],
              ["tou", t("price_tou")],
              ["brazil", t("price_brazil")],
            ]}
            onChange={(v) => setForm({ price: v as PriceKind })}
          />
          <PriceFields />
        </Section>

        <Section title={t("sec_panels")} hint={t("panelsHint")}>
          <div className="grid grid-cols-3 gap-2">
            <Field label={t("tilt")}>
              <input className="field" inputMode="decimal" value={form.tilt} onChange={(e) => setForm({ tilt: e.target.value })} />
            </Field>
            <Field label={t("azimuth")}>
              <input className="field" inputMode="decimal" value={form.azimuth} onChange={(e) => setForm({ azimuth: e.target.value })} />
            </Field>
            <Field label={t("kwp")}>
              <input className="field" inputMode="decimal" value={form.kwp} onChange={(e) => setForm({ kwp: e.target.value })} />
            </Field>
          </div>
        </Section>

        <Section title={t("sec_reading")} hint={t("readingHint")}>
          <div className="grid grid-cols-2 gap-2">
            <Field label={t("timeColumn")}>
              <input className="field" value={form.time_column} onChange={(e) => setForm({ time_column: e.target.value })} />
            </Field>
            <Field label={t("valueColumn")}>
              <input className="field" value={form.value_column} onChange={(e) => setForm({ value_column: e.target.value })} />
            </Field>
            <Field label={t("unit")}>
              <select className="field" value={form.unit} onChange={(e) => setForm({ unit: e.target.value })}>
                <option value="">{t("auto")}</option>
                {["kWh", "Wh", "kW", "W"].map((u) => (
                  <option key={u}>{u}</option>
                ))}
              </select>
            </Field>
            <Field label={t("kind")}>
              <select className="field" value={form.kind} onChange={(e) => setForm({ kind: e.target.value })}>
                <option value="">{t("auto")}</option>
                {(info?.read_kinds ?? ["interval", "cumulative", "power"]).map((k) => (
                  <option key={k} value={k}>
                    {t(`kind_${k}` as Key)}
                  </option>
                ))}
              </select>
            </Field>
          </div>
        </Section>
        <p className="px-1 pt-2 text-[10.5px] leading-snug text-muted">{t("privacy")}</p>
      </div>
      <div className="space-y-2 border-t border-line p-3">
        <button
          type="button"
          disabled={!ready || running}
          title={problem}
          onClick={() => start("run")}
          className="flex w-full items-center justify-center gap-2 rounded-[3px] bg-[#118DFF] py-2 text-[13px] font-semibold text-white shadow-sm transition enabled:hover:bg-[#0d7ae0] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {running ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
          {running ? t("running") : t("run")}
        </button>
        {problem && !running && <p className="text-center text-[11px] text-muted">{problem}</p>}
        <button
          type="button"
          disabled={running}
          onClick={() => start("demo")}
          className="flex w-full items-center justify-center gap-2 rounded-[3px] border border-line py-1.5 text-[12.5px] text-ink transition hover:bg-hover disabled:opacity-50"
        >
          <Sparkles size={14} className="text-[#F2B705]" />
          {t("tryDemo")}
        </button>
      </div>
    </motion.aside>
  );
}

function PriceFields() {
  const t = useT();
  const { form, setForm, info } = useStore();
  const schemes = info?.schemes ?? ["net_metering", "net_billing", "self_consumption"];
  if (form.price === "none") return null;
  if (form.price === "brazil") {
    const b = form.brazil;
    const up = (p: Partial<Form["brazil"]>) => setForm({ brazil: { ...b, ...p } });
    return (
      <div className="space-y-2">
        <Field label={t("distributor")}>
          <input className="field" value={b.distributor} onChange={(e) => up({ distributor: e.target.value })} />
        </Field>
        <div className="grid grid-cols-2 gap-2">
          <Field label={t("icms")}>
            <input className="field" inputMode="decimal" value={b.icms} onChange={(e) => up({ icms: e.target.value })} />
          </Field>
          <Field label={t("pisCofins")}>
            <input className="field" inputMode="decimal" value={b.pis_cofins} placeholder="9,25" onChange={(e) => up({ pis_cofins: e.target.value })} />
          </Field>
        </div>
        <Field label={t("connection")}>
          <select className="field" value={b.connection} onChange={(e) => up({ connection: e.target.value })}>
            {(info?.brazil.connections ?? ["monofasico", "bifasico_2", "bifasico_3", "trifasico"]).map((c) => (
              <option key={c} value={c}>
                {t(`conn_${c}` as Key)}
              </option>
            ))}
          </select>
        </Field>
        <div className="grid grid-cols-2 gap-2">
          <Field label={t("gd")}>
            <select className="field" value={b.gd} onChange={(e) => up({ gd: e.target.value })}>
              {(info?.brazil.gd ?? ["GD I", "GD II"]).map((g) => (
                <option key={g}>{g}</option>
              ))}
            </select>
          </Field>
          <Field label={t("cosip")}>
            <input className="field" inputMode="decimal" value={b.cosip} onChange={(e) => up({ cosip: e.target.value })} />
          </Field>
        </div>
        <p className="text-[10.5px] text-muted">{t("gdHelp", { date: info?.brazil.gd_i_requested_by ?? "2023-01-07" })}</p>
        <div className="grid grid-cols-2 gap-2">
          <Field label={t("modality")}>
            <select className="field" value={b.modality} onChange={(e) => up({ modality: e.target.value })}>
              {(info?.brazil.modalities ?? ["Convencional", "Branca"]).map((m) => (
                <option key={m}>{m}</option>
              ))}
            </select>
          </Field>
          {b.modality === "Branca" && (
            <Field label={t("peakStart")}>
              <input className="field" value={b.peak_start} onChange={(e) => up({ peak_start: e.target.value })} />
            </Field>
          )}
        </div>
      </div>
    );
  }
  const kind = form.price;
  const p = form[kind];
  const up = (patch: Record<string, string>) => setForm({ [kind]: { ...p, ...patch } } as Partial<Form>);
  return (
    <div className="space-y-2">
      {kind === "flat" ? (
        <Field label={t("pricePerKwh")}>
          <input className="field" inputMode="decimal" value={form.flat.price} onChange={(e) => up({ price: e.target.value })} />
        </Field>
      ) : (
        <>
          <Field label={t("peakHours")}>
            <input className="field" value={form.tou.peak_hours} onChange={(e) => up({ peak_hours: e.target.value })} />
          </Field>
          <div className="grid grid-cols-2 gap-2">
            <Field label={t("peakPrice")}>
              <input className="field" inputMode="decimal" value={form.tou.peak_price} onChange={(e) => up({ peak_price: e.target.value })} />
            </Field>
            <Field label={t("offpeakPrice")}>
              <input className="field" inputMode="decimal" value={form.tou.offpeak_price} onChange={(e) => up({ offpeak_price: e.target.value })} />
            </Field>
          </div>
        </>
      )}
      <div className="grid grid-cols-2 gap-2">
        <Field label={t("exportPrice")}>
          <input className="field" inputMode="decimal" value={p.export_price} onChange={(e) => up({ export_price: e.target.value })} />
        </Field>
        <Field label={t("fixed")}>
          <input className="field" inputMode="decimal" value={p.fixed} onChange={(e) => up({ fixed: e.target.value })} />
        </Field>
      </div>
      <div className="grid grid-cols-[90px_1fr] gap-2">
        <Field label={t("currency")}>
          <input className="field uppercase" maxLength={3} value={p.currency} onChange={(e) => up({ currency: e.target.value.toUpperCase() })} />
        </Field>
        <Field label={t("scheme")}>
          <select className="field" value={p.scheme} onChange={(e) => up({ scheme: e.target.value })}>
            {schemes.map((s) => (
              <option key={s} value={s}>
                {t(`scheme_${s}` as Key)}
              </option>
            ))}
          </select>
        </Field>
      </div>
    </div>
  );
}

function FileDrop({ quantity, label }: { quantity: Quantity; label: string }) {
  const t = useT();
  const file = useStore((s) => s.files[quantity]);
  const setFile = useStore((s) => s.setFile);
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const color = quantity === "generation" ? "#E66C37" : "#118DFF";
  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        const f = e.dataTransfer.files[0];
        if (f) setFile(quantity, f);
      }}
      onClick={() => input.current?.click()}
      className={`group relative cursor-pointer rounded-[3px] border border-dashed px-3 py-2.5 transition ${
        over ? "border-[#118DFF] bg-[#118DFF]/10" : "border-line hover:border-muted hover:bg-hover"
      }`}
    >
      <input
        ref={input}
        type="file"
        accept=".csv,.txt,.xlsx"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) setFile(quantity, f);
          e.target.value = "";
        }}
      />
      <div className="flex items-center gap-2.5">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full" style={{ background: `${color}1f`, color }}>
          <FileUp size={15} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-[12.5px] font-semibold text-ink">{label}</div>
          <AnimatePresence mode="wait">
            <motion.div key={file?.name ?? "none"} initial={{ opacity: 0, x: -4 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} className="truncate text-[11px] text-muted">
              {file ? `${file.name} · ${(file.size / 1024).toFixed(0)} KB` : t("dropHint")}
            </motion.div>
          </AnimatePresence>
        </div>
        {file && (
          <button
            type="button"
            aria-label={t("remove")}
            title={t("remove")}
            onClick={(e) => {
              e.stopPropagation();
              setFile(quantity, null);
            }}
            className="rounded-sm p-1 text-muted hover:bg-surface hover:text-ink"
          >
            <X size={13} />
          </button>
        )}
      </div>
    </div>
  );
}

function Section({ title, hint, open = false, children }: { title: string; hint?: string; open?: boolean; children: ReactNode }) {
  const [shown, setShown] = useState(open);
  return (
    <div className="border-b border-line/70 pb-1">
      <button type="button" onClick={() => setShown(!shown)} className="flex w-full items-center justify-between py-2 text-left">
        <span className="text-[12.5px] font-semibold text-ink">
          {title}
          {hint && <span className="ml-1.5 font-normal text-muted">· {hint}</span>}
        </span>
        <motion.span animate={{ rotate: shown ? 0 : -90 }} className="text-muted">
          <ChevronDown size={14} />
        </motion.span>
      </button>
      <AnimatePresence initial={false}>
        {shown && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.2 }} className="overflow-hidden">
            <div className="space-y-2 pb-2">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-0.5 block text-[11px] font-semibold text-muted">
        {label}
        {hint && <span className="ml-1 font-normal opacity-80">({hint})</span>}
      </span>
      {children}
    </label>
  );
}

function Seg({ value, options, onChange }: { value: string; options: [string, string][]; onChange: (v: string) => void }) {
  return (
    <div className="flex rounded-[3px] border border-line bg-surface p-0.5">
      {options.map(([v, label]) => (
        <button
          key={v}
          type="button"
          onClick={() => onChange(v)}
          className={`relative flex-1 rounded-[2px] px-1.5 py-1 text-[11.5px] transition-colors ${value === v ? "font-semibold text-white" : "text-muted hover:text-ink"}`}
        >
          {value === v && <motion.span layoutId={`seg-${options.map((o) => o[0]).join("-")}`} className="absolute inset-0 rounded-[2px] bg-[#118DFF]" transition={{ type: "spring", stiffness: 500, damping: 38 }} />}
          <span className="relative">{label}</span>
        </button>
      ))}
    </div>
  );
}
