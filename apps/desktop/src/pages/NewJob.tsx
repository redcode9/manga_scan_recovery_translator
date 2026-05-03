/**
 * Nuovo Job — UI per un singolo job (cartella locale o URL capitolo).
 *
 * Le batch su intere serie hanno una pagina dedicata (``/batch``)
 * con dry-run, copertura e gap-fill: lì la UX è studiata per il
 * caso batch e replicarla qui sarebbe ridondante. Tutto quello che
 * non è batch passa da questa pagina.
 *
 * Modalità:
 *  - **Cartella locale** → ``kind: "local"`` (input_dir).
 *  - **URL singolo capitolo** → ``kind: "url"`` (input_url + i_own_rights).
 */

import { ChevronDown, FolderOpen, Globe, Layers, ShieldAlert } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { api } from "../lib/api";
import type { JobCreate, JobKind } from "../lib/api";

type FormMode = "local" | "url";

interface FormState {
  mode: FormMode;
  inputUrl: string;
  inputDir: string;
  outDir: string;
  series: string;
  chapter: string;
  title: string;
  format: "pdf" | "cbz" | "both";
  model: string;
  renderer: "custom-postprocess" | "mitr-manga2eng" | "mitr-default";
  langSource: string;
  langTarget: string;
  noGpu: boolean;
  autoGlossary: boolean;
  glossaryPath: string;
  preDictPath: string;
  fontPath: string;
  site: string;
  skipExisting: boolean;
  continueOnError: boolean;
  rangeFilter: string;
  chaptersFilter: string;
  limit: string;
  iOwnRights: boolean;
}

const INITIAL: FormState = {
  mode: "local",
  inputUrl: "",
  inputDir: "",
  outDir: "out",
  series: "",
  chapter: "",
  title: "",
  format: "pdf",
  model: "",
  renderer: "custom-postprocess",
  langSource: "en",
  langTarget: "it",
  noGpu: false,
  autoGlossary: true,
  glossaryPath: "",
  preDictPath: "",
  fontPath: "",
  site: "auto",
  skipExisting: true,
  continueOnError: true,
  rangeFilter: "",
  chaptersFilter: "",
  limit: "",
  iOwnRights: false,
};

export function NewJobPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState<FormState>(INITIAL);
  const submit = useMutation({
    mutationFn: (request: JobCreate) => api.createJob(request),
    onSuccess: (job) => navigate(`/jobs/${job.id}`),
  });

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const request = buildJobCreate(form);
    if (!request) return;
    submit.mutate(request);
  };

  const update = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const requiresRights = form.mode !== "local";
  const submitDisabled =
    submit.isPending ||
    (requiresRights && !form.iOwnRights) ||
    (form.mode === "local" && !form.inputDir.trim()) ||
    (form.mode !== "local" && !form.inputUrl.trim());

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Nuovo Job</h1>
          <p className="text-sm text-zinc-500">
            Una cartella locale di immagini o un singolo URL capitolo.
            Per scaricare un'intera serie usa la pagina <strong>Batch</strong>.
          </p>
        </div>
        <Link
          to="/batch"
          className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-zinc-200 transition hover:bg-white/10"
        >
          <Layers size={14} />
          Batch su una serie →
        </Link>
      </header>

      <form
        onSubmit={onSubmit}
        className="space-y-6 rounded-xl border border-white/5 bg-zinc-900/60 p-6 shadow-sm"
      >
        <ModeSwitch mode={form.mode} onChange={(mode) => update("mode", mode)} />

        {form.mode === "local" ? (
          <Field
            label="Cartella sorgente"
            hint="Path assoluto. Una directory di immagini PNG/JPG/WebP."
          >
            <input
              value={form.inputDir}
              onChange={(e) => update("inputDir", e.target.value)}
              className="w-full rounded-md border border-white/10 px-3 py-2 font-mono text-sm shadow-sm transition focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-400 focus:ring-offset-1 focus:ring-offset-zinc-950"
              placeholder="/Users/me/Desktop/Wistoria/Capitolo_50"
            />
          </Field>
        ) : (
          <Field
            label="URL"
            hint="Capitolo o serie supportata da MangaDex / MangaFire."
          >
            <input
              value={form.inputUrl}
              onChange={(e) => update("inputUrl", e.target.value)}
              className="w-full rounded-md border border-white/10 px-3 py-2 font-mono text-sm shadow-sm transition focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-400 focus:ring-offset-1 focus:ring-offset-zinc-950"
              placeholder="https://mangadex.org/chapter/<UUID>"
            />
          </Field>
        )}

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Field label="Output dir">
            <input
              value={form.outDir}
              onChange={(e) => update("outDir", e.target.value)}
              className="w-full rounded-md border border-white/10 px-3 py-2 font-mono text-sm shadow-sm transition focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-400 focus:ring-offset-1 focus:ring-offset-zinc-950"
            />
          </Field>
          <Field label="Formato">
            <select
              value={form.format}
              onChange={(e) =>
                update("format", e.target.value as FormState["format"])
              }
              className="w-full rounded-md border border-white/10 px-3 py-2 text-sm shadow-sm transition focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-400 focus:ring-offset-1 focus:ring-offset-zinc-950"
            >
              <option value="pdf">PDF</option>
              <option value="cbz">CBZ</option>
              <option value="both">PDF + CBZ</option>
            </select>
          </Field>
          <Field label="Renderer">
            <select
              value={form.renderer}
              onChange={(e) =>
                update("renderer", e.target.value as FormState["renderer"])
              }
              className="w-full rounded-md border border-white/10 px-3 py-2 text-sm shadow-sm transition focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-400 focus:ring-offset-1 focus:ring-offset-zinc-950"
            >
              <option value="custom-postprocess">
                custom-postprocess (default)
              </option>
              <option value="mitr-manga2eng">mitr-manga2eng</option>
              <option value="mitr-default">mitr-default</option>
            </select>
          </Field>
        </div>

        {form.mode === "local" && (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <Field label="Serie" hint="Per metadata CBZ + auto-glossary.">
              <input
                value={form.series}
                onChange={(e) => update("series", e.target.value)}
                className="w-full rounded-md border border-white/10 px-3 py-2 text-sm shadow-sm transition focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-400 focus:ring-offset-1 focus:ring-offset-zinc-950"
                placeholder="Wistoria"
              />
            </Field>
            <Field label="Numero capitolo">
              <input
                value={form.chapter}
                onChange={(e) => update("chapter", e.target.value)}
                className="w-full rounded-md border border-white/10 px-3 py-2 text-sm shadow-sm transition focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-400 focus:ring-offset-1 focus:ring-offset-zinc-950"
                placeholder="50"
              />
            </Field>
            <Field label="Titolo (opzionale)">
              <input
                value={form.title}
                onChange={(e) => update("title", e.target.value)}
                className="w-full rounded-md border border-white/10 px-3 py-2 text-sm shadow-sm transition focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-400 focus:ring-offset-1 focus:ring-offset-zinc-950"
              />
            </Field>
          </div>
        )}

        <details className="rounded-lg border border-white/5 p-4 [&_summary]:cursor-pointer">
          <summary className="flex items-center gap-1.5 text-sm font-medium text-zinc-300">
            <ChevronDown size={14} className="transition-transform [details[open]_&]:rotate-180" />
            Opzioni avanzate
          </summary>
          <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
            <Field label="Model alias (vuoto = MSRT_MODEL)">
              <input
                value={form.model}
                onChange={(e) => update("model", e.target.value)}
                className="w-full rounded-md border border-white/10 px-3 py-2 text-sm shadow-sm transition focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-400 focus:ring-offset-1 focus:ring-offset-zinc-950"
                placeholder="gpt | sonnet | gemini-pro …"
              />
            </Field>
            <Field label="Site adapter">
              <input
                value={form.site}
                onChange={(e) => update("site", e.target.value)}
                className="w-full rounded-md border border-white/10 px-3 py-2 text-sm shadow-sm transition focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-400 focus:ring-offset-1 focus:ring-offset-zinc-950"
              />
            </Field>
            <Field label="Glossary path">
              <input
                value={form.glossaryPath}
                onChange={(e) => update("glossaryPath", e.target.value)}
                className="w-full rounded-md border border-white/10 px-3 py-2 font-mono text-sm shadow-sm transition focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-400 focus:ring-offset-1 focus:ring-offset-zinc-950"
              />
            </Field>
            <Field label="Pre-dict path">
              <input
                value={form.preDictPath}
                onChange={(e) => update("preDictPath", e.target.value)}
                className="w-full rounded-md border border-white/10 px-3 py-2 font-mono text-sm shadow-sm transition focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-400 focus:ring-offset-1 focus:ring-offset-zinc-950"
              />
            </Field>
            <Field label="Font path">
              <input
                value={form.fontPath}
                onChange={(e) => update("fontPath", e.target.value)}
                className="w-full rounded-md border border-white/10 px-3 py-2 font-mono text-sm shadow-sm transition focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-400 focus:ring-offset-1 focus:ring-offset-zinc-950"
              />
            </Field>
            <div className="flex flex-col justify-end gap-2 text-sm">
              <Toggle
                checked={form.autoGlossary}
                onChange={(v) => update("autoGlossary", v)}
                label="Auto-glossary (consigliato)"
              />
              <Toggle
                checked={form.noGpu}
                onChange={(v) => update("noGpu", v)}
                label="Disabilita GPU (--no-gpu)"
              />
            </div>
          </div>
        </details>

        {requiresRights && (
          <div className="flex items-start gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4">
            <ShieldAlert className="mt-0.5 text-amber-300" size={18} />
            <div className="flex-1 space-y-2">
              <p className="text-sm text-amber-100">
                Stai scaricando contenuti da Internet. Conferma di avere il
                diritto di farlo (contenuto tuo, pubblico dominio, o
                licenza che lo consente). Guardrail UX, non tutela legale.
              </p>
              <Toggle
                checked={form.iOwnRights}
                onChange={(v) => update("iOwnRights", v)}
                label="Confermo di avere i diritti (--i-own-rights)"
              />
            </div>
          </div>
        )}

        {submit.error && (
          <div className="rounded-md border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-300">
            {submit.error.message}
          </div>
        )}

        <div className="flex items-center justify-between border-t border-white/5 pt-4">
          <p className="text-xs text-zinc-500">
            Il job viene messo in coda nel worker FIFO del backend.
          </p>
          <button
            type="submit"
            disabled={submitDisabled}
            className="inline-flex items-center gap-2 rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submit.isPending ? "Invio…" : "Avvia job"}
          </button>
        </div>
      </form>
    </div>
  );
}

function ModeSwitch({
  mode,
  onChange,
}: {
  mode: FormMode;
  onChange: (mode: FormMode) => void;
}) {
  const options: {
    value: FormMode;
    label: string;
    description: string;
    icon: React.ReactNode;
  }[] = [
    {
      value: "local",
      label: "Cartella locale",
      description: "Hai già le immagini su disco e vuoi solo tradurle.",
      icon: <FolderOpen size={16} />,
    },
    {
      value: "url",
      label: "URL capitolo",
      description: "Un singolo capitolo da MangaDex o MangaFire.",
      icon: <Globe size={16} />,
    },
  ];
  return (
    <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          className={`flex items-start gap-3 rounded-xl border px-4 py-3 text-left transition ${
            mode === opt.value
              ? "border-sky-400/40 bg-sky-500/10"
              : "border-white/5 bg-white/5 hover:bg-white/10"
          }`}
        >
          <span
            className={`mt-0.5 grid h-7 w-7 place-items-center rounded-md ring-1 ${
              mode === opt.value
                ? "bg-sky-500/15 text-sky-200 ring-sky-400/30"
                : "bg-zinc-950/60 text-zinc-400 ring-white/10"
            }`}
          >
            {opt.icon}
          </span>
          <span>
            <span className="block text-sm font-medium text-zinc-100">
              {opt.label}
            </span>
            <span className="mt-0.5 block text-xs text-zinc-500">
              {opt.description}
            </span>
          </span>
        </button>
      ))}
    </div>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-zinc-500">
        {label}
      </span>
      {children}
      {hint && <span className="mt-1 block text-[11px] text-zinc-500">{hint}</span>}
    </label>
  );
}

function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  label: string;
}) {
  return (
    <label className="inline-flex items-center gap-2 text-sm text-zinc-300">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 rounded border-white/10 text-sky-600 focus:ring-sky-400"
      />
      {label}
    </label>
  );
}

function buildJobCreate(form: FormState): JobCreate | null {
  const kind: JobKind = form.mode;
  // ``url_batch`` is no longer a NewJob mode; the dedicated /batch
  // page owns that flow. The cast below stays for type compatibility
  // with ``JobKind`` (which still accepts the literal for the API).
  const options: JobCreate["options"] = {
    format: form.format,
    renderer: form.renderer,
    lang_source: form.langSource,
    lang_target: form.langTarget,
    no_gpu: form.noGpu,
    auto_glossary: form.autoGlossary,
    site: form.site || "auto",
    skip_existing: form.skipExisting,
    continue_on_error: form.continueOnError,
  };
  if (form.model.trim()) options.model = form.model.trim();
  if (form.glossaryPath.trim()) options.glossary_path = form.glossaryPath.trim();
  if (form.preDictPath.trim()) options.pre_dict_path = form.preDictPath.trim();
  if (form.fontPath.trim()) options.font_path = form.fontPath.trim();
  if (form.rangeFilter.trim()) options.range_filter = form.rangeFilter.trim();
  if (form.chaptersFilter.trim())
    options.chapters_filter = form.chaptersFilter.trim();
  if (form.limit.trim()) {
    const parsed = Number.parseInt(form.limit, 10);
    if (Number.isFinite(parsed) && parsed > 0) options.limit = parsed;
  }
  const request: JobCreate = { kind, out_dir: form.outDir, options };
  if (form.mode === "local") {
    request.input_dir = form.inputDir.trim();
    if (form.series.trim()) request.series = form.series.trim();
    if (form.chapter.trim()) request.chapter_number = form.chapter.trim();
    if (form.title.trim()) request.chapter_title = form.title.trim();
  } else {
    request.input_url = form.inputUrl.trim();
    request.i_own_rights = form.iOwnRights;
  }
  return request;
}
