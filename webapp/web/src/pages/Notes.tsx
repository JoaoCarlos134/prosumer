import { motion } from "framer-motion";
import { CheckCircle2, ExternalLink, Info, Lock, ShieldAlert } from "lucide-react";
import type { ReactNode } from "react";
import { Empty, Visual } from "../components/Visual";
import { present } from "../derive";
import { code } from "../i18n";
import { useStore, useT } from "../store";
import { C } from "../theme";
import type { Payload } from "../types";
import { NoteList, PageGrid } from "./common";

interface Source {
  role: string;
  name: string;
  license: string;
  sends_data: boolean | null;
  source: string;
  citation: string;
  url: string;
  conditions: string;
}

/** What each step did, every note of the library by where it came from, what is not done yet, the sources
 * and their licences, the privacy and the about. */
export function Notes({ payload }: { payload: Payload }) {
  const t = useT();
  const lang = useStore((s) => s.lang);
  const info = useStore((s) => s.info);
  const r = payload.result;

  // the diagnostics' notes are in the report's notes already; each note is shown once, in its first group
  const seen = new Set<string>();
  const once = (notes: string[]) =>
    notes.filter((n) => {
      if (seen.has(n)) return false;
      seen.add(n);
      return true;
    });
  const groups: { title: string; notes: string[]; color: string }[] = [
    { title: t("group_app"), notes: once(r.notes), color: C.measured },
    ...present(r).map((q) => ({ title: `${t("group_outlook")} · ${t(q)}`, notes: once(r.outlooks[q]?.notes ?? []), color: q === "generation" ? C.generation : C.consumption })),
    { title: t("group_report"), notes: once(r.report.notes), color: C.forecast },
    { title: t("group_bill"), notes: once(r.report.economics?.notes ?? []), color: C.grid },
  ].filter((g) => g.notes.length);

  const sources: Source[] = [
    ...r.credits.map((c) => ({ role: "", name: c.source, license: c.license, sends_data: null, source: c.notes, citation: c.citation, url: c.url, conditions: "" })),
    ...(r.report.provenance ?? []).map((p) => ({ ...p })),
    ...(r.report.economics?.provenance ?? []).map((p) => ({ ...p })),
  ];
  const pending = Object.entries(r.report.pending ?? {});

  return (
    <PageGrid>
      <Visual title={t("v_log")} className="col-span-12 lg:col-span-5">
        <Timeline items={r.log} />
      </Visual>
      <Visual title={t("v_notes")} className="col-span-12 lg:col-span-7">
        {groups.length ? (
          <div className="space-y-4">
            {groups.map((g) => (
              <div key={g.title}>
                <h4 className="mb-1.5 flex items-center gap-2 text-[12px] font-semibold uppercase tracking-wide text-muted">
                  <span className="h-2 w-2 rounded-full" style={{ background: g.color }} />
                  {g.title}
                  <span className="font-normal normal-case tracking-normal">({g.notes.length})</span>
                </h4>
                <NoteList notes={g.notes} />
              </div>
            ))}
          </div>
        ) : (
          <Empty>–</Empty>
        )}
      </Visual>
      <Visual
        title={t("v_sources")}
        className="col-span-12"
        data={{
          columns: [
            { key: "role", label: t("role"), format: (v: string) => code(lang, v) },
            { key: "name", label: t("name") },
            { key: "license", label: t("license") },
            { key: "sends_data", label: t("sendsData"), format: (v: boolean | null) => (v == null ? "–" : v ? t("yes") : t("no")) },
            { key: "source", label: t("source") },
            { key: "citation", label: t("citation") },
            { key: "url", label: "URL" },
            { key: "conditions", label: t("conditions") },
          ],
          rows: sources,
          file: "sources_and_licences",
        }}
      >
        <SourceTable rows={sources} />
      </Visual>
      {pending.length > 0 && (
        <Visual title={t("v_pending")} className="col-span-12 lg:col-span-6">
          <ul className="space-y-2">
            {pending.map(([k, v], i) => (
              <motion.li key={k} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.04 * i }} className="text-[12.5px] leading-snug">
                <span className="font-semibold text-ink">{k}</span>
                <span className="text-muted"> — {v}</span>
              </motion.li>
            ))}
          </ul>
        </Visual>
      )}
      <Visual title={t("v_privacy")} className={`col-span-12 ${pending.length ? "lg:col-span-3" : "lg:col-span-6"}`}>
        <Card icon={<Lock size={16} />} color={C.export}>
          {t("privacy")}
        </Card>
      </Visual>
      <Visual title={t("v_about")} className={`col-span-12 ${pending.length ? "lg:col-span-3" : "lg:col-span-6"}`}>
        <div className="space-y-3">
          <Card icon={<Info size={16} />} color={C.accent}>
            {t("about", { v: info?.version ?? "" })}
          </Card>
          {payload.meta.demo && payload.meta.source && (
            <Card icon={<CheckCircle2 size={16} />} color={C.generation}>
              {t("demoAbout", { c: payload.meta.source.citation })}{" "}
              <a className="text-[#118DFF] hover:underline" href={payload.meta.source.url} target="_blank" rel="noreferrer">
                {payload.meta.source.url}
              </a>
            </Card>
          )}
        </div>
      </Visual>
    </PageGrid>
  );
}

/** The app's log as a timeline that draws itself step by step. */
function Timeline({ items }: { items: string[] }) {
  if (!items.length) return <Empty>–</Empty>;
  return (
    <ol className="relative ml-2 border-l-2 border-line">
      {items.map((s, i) => (
        <motion.li key={i} className="relative pb-3 pl-5 last:pb-0" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 * i, duration: 0.3 }}>
          <motion.span
            className="absolute -left-[7px] top-1 h-3 w-3 rounded-full border-2 border-surface"
            style={{ background: C.export }}
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ delay: 0.08 * i + 0.1, type: "spring", stiffness: 400, damping: 18 }}
          />
          <p className="text-[12.5px] leading-snug text-ink">{s}</p>
        </motion.li>
      ))}
    </ol>
  );
}

function Card({ icon, color, children }: { icon: ReactNode; color: string; children: ReactNode }) {
  return (
    <div className="flex gap-2.5 text-[12.5px] leading-relaxed text-muted">
      <span className="mt-0.5 shrink-0" style={{ color }}>
        {icon}
      </span>
      <div className="min-w-0 break-words">{children}</div>
    </div>
  );
}

/** Every source of the result with its licence, a warning where the licence is unknown or the data go out. */
function SourceTable({ rows }: { rows: Source[] }) {
  const t = useT();
  const lang = useStore((s) => s.lang);
  if (!rows.length) return <Empty>–</Empty>;
  return (
    <div className="max-h-[420px] overflow-auto">
      <table className="w-full border-collapse text-[12px]">
        <thead className="sticky top-0 z-10 bg-surface">
          <tr className="text-ink">
            {[t("role"), t("name"), t("license"), t("sendsData"), t("source")].map((h) => (
              <th key={h} className="whitespace-nowrap border-b-2 border-line px-2 py-1.5 text-left font-semibold">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((s, i) => {
            const unknown = !s.license || s.license === "unknown";
            return (
              <tr key={i} className="border-b border-line/60 align-top odd:bg-zebra">
                <td className="whitespace-nowrap px-2 py-1 text-muted">{s.role ? code(lang, s.role) : t("credit")}</td>
                <td className="px-2 py-1 text-ink">
                  {s.url ? (
                    <a href={s.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[#118DFF] hover:underline">
                      {s.name || s.url}
                      <ExternalLink size={11} />
                    </a>
                  ) : (
                    s.name
                  )}
                  {s.citation && <div className="mt-0.5 text-[11px] text-muted">{s.citation}</div>}
                </td>
                <td className="whitespace-nowrap px-2 py-1">
                  <span className={`inline-flex items-center gap-1 ${unknown ? "text-[#D64550]" : "text-ink"}`}>
                    {unknown && <ShieldAlert size={12} />}
                    {s.license || "unknown"}
                  </span>
                </td>
                <td className="whitespace-nowrap px-2 py-1 text-muted">{s.sends_data == null ? "–" : s.sends_data ? <span className="font-semibold text-[#D64550]">{t("yes")}</span> : t("no")}</td>
                <td className="px-2 py-1 text-muted">
                  <div className="line-clamp-3" title={[s.source, s.conditions].filter(Boolean).join(" · ")}>
                    {[s.source, s.conditions].filter(Boolean).join(" · ")}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
