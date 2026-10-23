import { AnimatePresence, motion } from "framer-motion";
import { BarChart3, Download, Maximize2, Minimize2, Table2 } from "lucide-react";
import { useState, type ReactNode } from "react";
import { download, toCsv } from "../format";
import { useT } from "../store";
import { DataTable, type Column } from "./DataTable";

export interface VisualData {
  columns: Column[];
  rows: any[];
  file?: string;
}

interface Props {
  title: string;
  subtitle?: string;
  children: ReactNode | ((focused: boolean) => ReactNode);
  data?: VisualData;
  className?: string;
  actions?: ReactNode;
}

export const item = {
  hidden: { opacity: 0, y: 14, scale: 0.985 },
  show: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.45, ease: [0.22, 1, 0.36, 1] as const } },
};

/** A report visual: a white tile with its title, and on hover the icons of focus mode, show as a table and
 * export data. Focus mode opens the same visual over the whole canvas. */
export function Visual({ title, subtitle, children, data, className = "", actions }: Props) {
  const t = useT();
  const [focused, setFocused] = useState(false);
  const [table, setTable] = useState(false);

  const body = (big: boolean) =>
    table && data ? (
      <DataTable columns={data.columns} rows={data.rows} maxHeight={big ? "calc(100vh - 220px)" : 300} />
    ) : typeof children === "function" ? (
      children(big)
    ) : (
      children
    );

  const tools = (big: boolean) => (
    <div className={`flex items-center gap-0.5 ${big ? "" : "opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100"}`}>
      {actions}
      {data && (
        <>
          <IconButton label={table ? t("showChart") : t("showTable")} onClick={() => setTable((v) => !v)}>
            {table ? <BarChart3 size={14} /> : <Table2 size={14} />}
          </IconButton>
          <IconButton
            label={t("exportCsv")}
            onClick={() => download(`${data.file ?? title.replace(/[^\w]+/g, "_").toLowerCase()}.csv`, toCsv(data.columns, data.rows))}
          >
            <Download size={14} />
          </IconButton>
        </>
      )}
      <IconButton label={big ? t("back") : t("focus")} onClick={() => setFocused(!big)}>
        {big ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
      </IconButton>
    </div>
  );

  return (
    <>
      <motion.section
        variants={item}
        whileHover={{ y: -3, transition: { type: "spring", stiffness: 300, damping: 22 } }}
        className={`tile group relative flex min-w-0 flex-col p-4 ${className}`}
      >
        <header className="mb-2 flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="text-[13.5px] font-semibold leading-snug text-ink">{title}</h3>
            {subtitle && <p className="text-[11px] leading-snug text-muted">{subtitle}</p>}
          </div>
          {tools(false)}
        </header>
        <div className="min-h-0 flex-1">{!focused && body(false)}</div>
      </motion.section>
      <AnimatePresence>
        {focused && (
          <motion.div
            className="fixed inset-0 z-50 flex bg-black/40 p-4 pt-16 backdrop-blur-[2px] md:p-10 md:pt-16"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setFocused(false)}
          >
            <motion.section
              initial={{ opacity: 0, scale: 0.94, y: 16 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 8 }}
              transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
              onClick={(e) => e.stopPropagation()}
              className="tile flex w-full flex-col p-5 !shadow-2xl"
            >
              <header className="mb-2 flex items-start justify-between gap-2">
                <div>
                  <h3 className="text-base font-semibold text-ink">{title}</h3>
                  {subtitle && <p className="text-xs text-muted">{subtitle}</p>}
                </div>
                {tools(true)}
              </header>
              <div className="min-h-0 flex-1">{body(true)}</div>
            </motion.section>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

export function IconButton({ label, onClick, children }: { label: string; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      onClick={onClick}
      className="rounded-lg p-1.5 text-muted transition hover:bg-hover hover:text-ink active:scale-90"
    >
      {children}
    </button>
  );
}

/** A message inside a visual when there is nothing to draw. */
export function Empty({ children }: { children: ReactNode }) {
  return <div className="flex h-full min-h-[120px] items-center justify-center px-6 text-center text-sm text-muted">{children}</div>;
}
