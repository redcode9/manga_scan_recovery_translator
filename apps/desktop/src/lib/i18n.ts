/**
 * Lightweight, in-house i18n.
 *
 * No external library: the whole vocabulary is one typed dictionary,
 * the active language lives in a React context, and the ``t()`` helper
 * is the only entry point pages need to translate strings. Substitutions
 * use ``{name}`` placeholders interpolated at call time.
 *
 * Design choices:
 *   - **Types over runtime checks.** ``TranslationKey`` is the union of
 *     every key in the Italian dictionary, so ``t("foo.bar")`` errors at
 *     compile time if ``foo.bar`` doesn't exist. The English dictionary
 *     must mirror the same shape (enforced by the type system).
 *   - **Italian is the source of truth.** New strings land in ``it``
 *     first; ``en`` follows. Missing English entries fall back to the
 *     Italian copy at runtime so a partial migration never breaks the
 *     UI.
 *   - **Persisted via the backend.** ``MSRT_UI_LANG`` lives in ``.env``
 *     so a CLI user, or a fresh tab, picks up the same preference. The
 *     localStorage cache is just a startup fast-path so first paint is
 *     in the right language without waiting on ``/api/settings``.
 */

import {
  createContext,
  createElement,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { api } from "./api";

export type Language = "it" | "en";

const LOCAL_STORAGE_KEY = "msrt-ui-lang";

const ITALIAN_DICTIONARY = {
  // ---- Navigation ----
  nav: {
    skipToContent: "Vai al contenuto",
    primaryAriaLabel: "Navigazione principale",
    sections: "Sezioni",
    home: "Libreria",
    add: "Aggiungi manga",
    library: "Tutti i capitoli",
    activity: "Attività",
    settings: "Impostazioni",
  },
  // ---- App-wide statuses & primitives ----
  common: {
    loading: "Caricamento…",
    ready: "Pronto",
    save: "Salva",
    cancel: "Annulla",
    confirm: "Conferma",
    close: "Chiudi",
    retry: "Riprova",
    delete: "Elimina",
    open: "Apri",
    edit: "Modifica",
    yes: "Sì",
    no: "No",
    back: "Indietro",
    unsavedChanges: "Modifiche non salvate",
    presentBadge: "presente",
    absentBadge: "assente",
    unknown: "?",
  },
  // ---- LiteLLM proxy / runtime ----
  proxy: {
    label: "LiteLLM",
    running: "running",
    unhealthy: "unhealthy",
    stopped: "stopped",
    mitrLabel: "MITR",
    mitrConfigured: "configurato",
    mitrMissing: "mancante",
    modelLabel: "model",
    title: "LiteLLM proxy",
    statusUp: "attivo",
    statusUnhealthy: "avviato (KO)",
    statusDown: "spento",
    portLabel: "Porta",
    baseUrlLabel: "Base URL",
    restart: "Riavvia",
    stop: "Stop",
    start: "Start",
    restartHint:
      "Stop + Start: fa rileggere al proxy le variabili d'ambiente correnti.",
    restartedSuccess: "LiteLLM riavviato",
    restartedHealthcheckFailed: "Riavvio: healthcheck KO",
    restartFailed: "Riavvio fallito",
    started: "LiteLLM avviato",
    stopped_toast: "LiteLLM fermato",
    startFailed: "Avvio fallito",
    stopFailed: "Stop fallito",
  },
  // ---- Active job banner ----
  banner: {
    batchInProgress: "Batch in corso · {done}/{total} capitoli",
    jobInProgress: "Job in corso · fase {phase}",
    open: "apri →",
    failedSuffix: "{count} falliti",
  },
  // ---- Settings page ----
  settings: {
    title: "Impostazioni",
    subtitle: "Provider, modello di default, runtime e diagnostica. Tutto qui.",
    sectionKeys: "Chiavi API provider",
    sectionRuntime: "Runtime",
    modelsCard: {
      title: "Modelli e fallback",
      description:
        "Modello primario: usato quando un job non specifica un override. Se la sua quota si esaurisce a metà run, msrt passa automaticamente al modello preferito di un altro provider per cui hai una chiave attiva.",
      primaryLabel: "Modello primario",
      fallbackTitle: "Fallback per provider",
      saveSuccess: "Modelli aggiornati",
      saveError: "Salvataggio fallito",
      customSuffix: "(custom)",
      perMTokSuffix: "/MTok",
    },
    autoCover: {
      title: "Recupero automatico copertine",
      description:
        "Ogni serie nella libreria riceve automaticamente la migliore copertina disponibile, in quest'ordine: MangaDex → AniList → composito locale dalle scan → generata da AI. Disattiva il toggle se preferisci il poster a gradiente.",
      enabled: "Attivo",
      disabled: "Disattivato",
      enabledHint:
        "Le card della libreria mostrano la copertina ufficiale o generata.",
      disabledHint:
        "Tutte le card mostrano il poster a gradiente con le iniziali.",
      toggleAria: "Recupero automatico copertine",
      enabledSuccess: "Recupero copertine attivato",
      disabledSuccess: "Recupero copertine disattivato",
    },
    language: {
      title: "Lingua interfaccia",
      description:
        "Scegli la lingua dei testi mostrati nell'app. La preferenza è salvata e seguirà l'app su ogni sessione.",
      italian: "Italiano",
      english: "English",
      saved: "Lingua aggiornata",
      saveError: "Cambio lingua fallito",
    },
    apiKey: {
      newLabel: "Nuova API key",
      whereToFind: "Dove la trovo:",
      saveButton: "Salva",
      removeButton: "Rimuovi",
      removeAriaLabel: "Rimuovi chiave {provider}",
      testButton: "Test ({model})",
      testAriaLabel: "Test della chiave {provider} ({model})",
      testHint: "Mini-chiamata reale a {model} (~ < 0,001 €)",
      testOk: "Test {provider} OK ({model})",
      testFailed: "Test {provider} fallito",
      latency: "Latenza {ms} ms.",
      removeConfirm:
        "Rimuovere la chiave {key}? L'azione cancella la voce dal portachiavi e dal file .env.",
      saved: "Chiave {provider} salvata",
      savedKeychain: "Conservata nel portachiavi macOS.",
      savedDotenv: "Conservata in .env (portachiavi non disponibile).",
      removed: "Chiave {provider} rimossa",
      saveFailed: "Salvataggio fallito",
      removeFailed: "Rimozione fallita",
    },
    info: {
      portLabel: "Porta",
      baseUrlLabel: "Base URL",
      mitr: "MITR",
      binPath: "Bin path",
      cache: "Cache",
      directory: "Directory",
      notConfigured: "non configurato",
    },
    diagnostics: {
      title: "Diagnostica",
      description:
        "Snapshot redatto: chiavi solo come flag presente/assente, doctor report e ultimi 20 job. Da allegare alle issue.",
      download: "Scarica diagnostica",
      generating: "Genero…",
      success: "Diagnostica scaricata",
      error: "Scaricamento diagnostica fallito",
    },
    speed: {
      ultra: "ultra-veloce",
      fast: "veloce",
      standard: "standard",
      reasoning: "lento (ragionamento profondo)",
    },
  },
  // ---- Add manga / batch page ----
  add: {
    title: "Aggiungi manga",
    subtitle:
      "Incolla l'URL di un capitolo o di una serie. Le copertine, i titoli e la pianificazione del batch li ricostruisce msrt.",
    urlLabel: "URL del capitolo o della serie",
    urlPlaceholder: "https://mangafire.to/manga/...",
    detectButton: "Analizza link",
    analyzing: "Analisi in corso…",
    invalidUrl: "URL non valido",
    detectError: "Impossibile analizzare il link",
    advancedToggle: "Opzioni avanzate",
    optionsTitle: "Opzioni",
    formatLabel: "Formato output",
    rangeLabel: "Range capitoli",
    rangePlaceholder: "es. 1-10",
    chaptersLabel: "Capitoli specifici",
    chaptersPlaceholder: "es. 1, 3, 5-7",
    limitLabel: "Limite",
    skipExistingLabel: "Salta capitoli già presenti",
    continueOnErrorLabel: "Continua in caso di errore",
    autoGlossaryLabel: "Glossario automatico",
    rendererLabel: "Renderer",
    submitButton: "Avvia",
    submitting: "Invio in corso…",
    submitSuccess: "Job creato",
    submitError: "Creazione job fallita",
  },
  // ---- Dashboard / library overview ----
  dashboard: {
    title: "Libreria",
    subtitle: "Le serie tradotte e le scan recuperate, raggruppate per titolo.",
    empty: "Niente in libreria. Aggiungi un manga per iniziare.",
    addFirst: "Aggiungi manga",
    chapterCount: "{count} capitoli",
    chapterCountSingular: "1 capitolo",
    lastUpdated: "Aggiornata {date}",
    seriesCard: {
      open: "Apri",
    },
  },
  // ---- Library (chapter list) ----
  library: {
    title: "Tutti i capitoli",
    subtitle:
      "Elenco di tutti i capitoli tradotti, filtrabile per serie e ordinabile per data.",
    empty: "Nessun capitolo presente. Avvia un job dalla pagina Aggiungi.",
    filterPlaceholder: "Filtra per serie o capitolo…",
    sortNewest: "Più recenti",
    sortOldest: "Più vecchi",
    actions: {
      open: "Apri",
      reveal: "Mostra in Finder",
      delete: "Elimina",
      retry: "Riavvia",
    },
    chapterLabel: "ch. {number}",
  },
  // ---- Activity / logs ----
  logs: {
    title: "Attività",
    subtitle: "I job recenti e il loro stato. Clicca per dettagli.",
    empty: "Nessuna attività ancora. Avvia un job per vedere i log qui.",
    columns: {
      kind: "Tipo",
      status: "Stato",
      progress: "Progresso",
      created: "Creato",
      finished: "Concluso",
    },
  },
  // ---- Job progress ----
  job: {
    headerLabel: "Job",
    title: "Job {id}",
    backToLibrary: "← Torna alla libreria",
    cancelButton: "Annulla job",
    retryFailedButton: "Riprova falliti",
    statusLabel: "Stato",
    phaseLabel: "Fase",
    chaptersLabel: "Capitoli",
    progressLabel: "Progresso",
    startedAt: "Avviato",
    finishedAt: "Concluso",
    eventsTitle: "Eventi",
    outputsTitle: "File generati",
    errorsTitle: "Errori",
    warningsTitle: "Avvisi",
    cancelConfirm: "Annullare il job? Le pagine già tradotte sono salvate.",
    cancelled: "Job annullato",
    retryStarted: "Retry avviato",
    cancelFailed: "Annullamento fallito",
    retryFailed: "Retry fallito",
  },
  // ---- Toast titles ----
  toast: {
    success: "Successo",
    error: "Errore",
    info: "Info",
    warning: "Attenzione",
  },
} as const;

export type TranslationDictionary = typeof ITALIAN_DICTIONARY;

/** Same shape as ``ITALIAN_DICTIONARY`` but with each leaf widened from
 * its literal type to ``string`` — so the English dictionary can hold
 * different strings while still being structurally enforced. */
type DictionaryShape<T> = {
  [K in keyof T]: T[K] extends string ? string : DictionaryShape<T[K]>;
};

const ENGLISH_DICTIONARY: DictionaryShape<TranslationDictionary> = {
  nav: {
    skipToContent: "Skip to main content",
    primaryAriaLabel: "Main navigation",
    sections: "Sections",
    home: "Library",
    add: "Add manga",
    library: "All chapters",
    activity: "Activity",
    settings: "Settings",
  },
  common: {
    loading: "Loading…",
    ready: "Ready",
    save: "Save",
    cancel: "Cancel",
    confirm: "Confirm",
    close: "Close",
    retry: "Retry",
    delete: "Delete",
    open: "Open",
    edit: "Edit",
    yes: "Yes",
    no: "No",
    back: "Back",
    unsavedChanges: "Unsaved changes",
    presentBadge: "present",
    absentBadge: "missing",
    unknown: "?",
  },
  proxy: {
    label: "LiteLLM",
    running: "running",
    unhealthy: "unhealthy",
    stopped: "stopped",
    mitrLabel: "MITR",
    mitrConfigured: "configured",
    mitrMissing: "missing",
    modelLabel: "model",
    title: "LiteLLM proxy",
    statusUp: "up",
    statusUnhealthy: "started (unhealthy)",
    statusDown: "down",
    portLabel: "Port",
    baseUrlLabel: "Base URL",
    restart: "Restart",
    stop: "Stop",
    start: "Start",
    restartHint:
      "Stop + Start: forces the proxy to re-read the current environment variables.",
    restartedSuccess: "LiteLLM restarted",
    restartedHealthcheckFailed: "Restarted, healthcheck failed",
    restartFailed: "Restart failed",
    started: "LiteLLM started",
    stopped_toast: "LiteLLM stopped",
    startFailed: "Start failed",
    stopFailed: "Stop failed",
  },
  banner: {
    batchInProgress: "Batch in progress · {done}/{total} chapters",
    jobInProgress: "Job in progress · phase {phase}",
    open: "open →",
    failedSuffix: "{count} failed",
  },
  settings: {
    title: "Settings",
    subtitle:
      "Providers, default model, runtime and diagnostics. All in one place.",
    sectionKeys: "Provider API keys",
    sectionRuntime: "Runtime",
    modelsCard: {
      title: "Models & fallback",
      description:
        "Primary model: used when a job doesn't specify an override. If its quota runs out mid-run, msrt automatically switches to the preferred model of another provider you have a key for.",
      primaryLabel: "Primary model",
      fallbackTitle: "Per-provider fallback",
      saveSuccess: "Models updated",
      saveError: "Save failed",
      customSuffix: "(custom)",
      perMTokSuffix: "/MTok",
    },
    autoCover: {
      title: "Automatic cover-art retrieval",
      description:
        "Each library series automatically gets the best cover available, in this order: MangaDex → AniList → local composite from the scans → AI-generated. Disable this to use the gradient placeholder instead.",
      enabled: "Active",
      disabled: "Disabled",
      enabledHint:
        "Library cards show the official or generated cover.",
      disabledHint:
        "All cards show the gradient placeholder with initials.",
      toggleAria: "Automatic cover retrieval",
      enabledSuccess: "Cover retrieval enabled",
      disabledSuccess: "Cover retrieval disabled",
    },
    language: {
      title: "Interface language",
      description:
        "Choose the language for the app's UI text. The preference is saved and persists across sessions.",
      italian: "Italiano",
      english: "English",
      saved: "Language updated",
      saveError: "Language switch failed",
    },
    apiKey: {
      newLabel: "New API key",
      whereToFind: "Where to find it:",
      saveButton: "Save",
      removeButton: "Remove",
      removeAriaLabel: "Remove {provider} key",
      testButton: "Test ({model})",
      testAriaLabel: "Test the {provider} key ({model})",
      testHint: "Real mini-call to {model} (~< $0.001)",
      testOk: "Test {provider} OK ({model})",
      testFailed: "Test {provider} failed",
      latency: "Latency {ms} ms.",
      removeConfirm:
        "Remove the {key} key? This deletes it from both the keychain and the .env file.",
      saved: "{provider} key saved",
      savedKeychain: "Stored in the macOS keychain.",
      savedDotenv: "Stored in .env (keychain unavailable).",
      removed: "{provider} key removed",
      saveFailed: "Save failed",
      removeFailed: "Removal failed",
    },
    info: {
      portLabel: "Port",
      baseUrlLabel: "Base URL",
      mitr: "MITR",
      binPath: "Binary path",
      cache: "Cache",
      directory: "Directory",
      notConfigured: "not configured",
    },
    diagnostics: {
      title: "Diagnostics",
      description:
        "Redacted snapshot: keys only as present/absent flags, doctor report, and the last 20 jobs. Attach to issues.",
      download: "Download diagnostics",
      generating: "Generating…",
      success: "Diagnostics downloaded",
      error: "Diagnostics download failed",
    },
    speed: {
      ultra: "ultra-fast",
      fast: "fast",
      standard: "standard",
      reasoning: "slow (deep reasoning)",
    },
  },
  add: {
    title: "Add manga",
    subtitle:
      "Paste a chapter or series URL. Covers, titles, and batch planning are reconstructed by msrt.",
    urlLabel: "Chapter or series URL",
    urlPlaceholder: "https://mangafire.to/manga/...",
    detectButton: "Analyze link",
    analyzing: "Analyzing…",
    invalidUrl: "Invalid URL",
    detectError: "Could not analyze the link",
    advancedToggle: "Advanced options",
    optionsTitle: "Options",
    formatLabel: "Output format",
    rangeLabel: "Chapter range",
    rangePlaceholder: "e.g. 1-10",
    chaptersLabel: "Specific chapters",
    chaptersPlaceholder: "e.g. 1, 3, 5-7",
    limitLabel: "Limit",
    skipExistingLabel: "Skip already-present chapters",
    continueOnErrorLabel: "Continue on error",
    autoGlossaryLabel: "Auto glossary",
    rendererLabel: "Renderer",
    submitButton: "Start",
    submitting: "Submitting…",
    submitSuccess: "Job created",
    submitError: "Job creation failed",
  },
  dashboard: {
    title: "Library",
    subtitle: "Translated series and recovered scans, grouped by title.",
    empty: "Library is empty. Add a manga to get started.",
    addFirst: "Add manga",
    chapterCount: "{count} chapters",
    chapterCountSingular: "1 chapter",
    lastUpdated: "Updated {date}",
    seriesCard: {
      open: "Open",
    },
  },
  library: {
    title: "All chapters",
    subtitle:
      "Every translated chapter, filterable by series and sortable by date.",
    empty: "No chapters yet. Start a job from the Add page.",
    filterPlaceholder: "Filter by series or chapter…",
    sortNewest: "Newest first",
    sortOldest: "Oldest first",
    actions: {
      open: "Open",
      reveal: "Reveal in Finder",
      delete: "Delete",
      retry: "Retry",
    },
    chapterLabel: "ch. {number}",
  },
  logs: {
    title: "Activity",
    subtitle: "Recent jobs and their status. Click for details.",
    empty: "No activity yet. Start a job to see logs here.",
    columns: {
      kind: "Kind",
      status: "Status",
      progress: "Progress",
      created: "Created",
      finished: "Finished",
    },
  },
  job: {
    headerLabel: "Job",
    title: "Job {id}",
    backToLibrary: "← Back to library",
    cancelButton: "Cancel job",
    retryFailedButton: "Retry failed",
    statusLabel: "Status",
    phaseLabel: "Phase",
    chaptersLabel: "Chapters",
    progressLabel: "Progress",
    startedAt: "Started",
    finishedAt: "Finished",
    eventsTitle: "Events",
    outputsTitle: "Output files",
    errorsTitle: "Errors",
    warningsTitle: "Warnings",
    cancelConfirm:
      "Cancel the job? Pages already translated are kept on disk.",
    cancelled: "Job cancelled",
    retryStarted: "Retry started",
    cancelFailed: "Cancel failed",
    retryFailed: "Retry failed",
  },
  toast: {
    success: "Success",
    error: "Error",
    info: "Info",
    warning: "Warning",
  },
};

const DICTIONARIES: Record<Language, DictionaryShape<TranslationDictionary>> = {
  it: ITALIAN_DICTIONARY,
  en: ENGLISH_DICTIONARY,
};

/** Dot-notation key into the translation dictionary, e.g.
 * ``"settings.title"`` or ``"add.urlPlaceholder"``. The type is derived
 * from the Italian dictionary, so any English-only key would be a
 * compile error. */
type Path<T, P extends string = ""> = {
  [K in keyof T & string]: T[K] extends string
    ? `${P}${K}`
    : Path<T[K], `${P}${K}.`>;
}[keyof T & string];

export type TranslationKey = Path<TranslationDictionary>;

function resolvePath(
  dict: DictionaryShape<TranslationDictionary>,
  key: string,
): string | undefined {
  const segments = key.split(".");
  let cursor: unknown = dict;
  for (const segment of segments) {
    if (cursor && typeof cursor === "object" && segment in (cursor as object)) {
      cursor = (cursor as Record<string, unknown>)[segment];
    } else {
      return undefined;
    }
  }
  return typeof cursor === "string" ? cursor : undefined;
}

/** Substitute ``{name}`` placeholders. Numbers are coerced via String(). */
function interpolate(
  template: string,
  params: Record<string, string | number> | undefined,
): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (match, name: string) => {
    const value = params[name];
    return value === undefined ? match : String(value);
  });
}

interface LanguageContextValue {
  language: Language;
  setLanguage: (next: Language) => Promise<void>;
  /** Translate ``key`` and substitute ``{placeholder}`` tokens. Falls
   * back to the Italian copy and then to the literal key, so a missing
   * translation never blanks the UI. */
  t: (key: TranslationKey, params?: Record<string, string | number>) => string;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

function readInitialLanguage(): Language {
  try {
    const stored = window.localStorage.getItem(LOCAL_STORAGE_KEY);
    if (stored === "it" || stored === "en") return stored;
  } catch {
    // localStorage unavailable (private mode etc.) — fall through.
  }
  return "it";
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(readInitialLanguage);

  // On mount, sync with the backend's persisted preference. The
  // backend's value wins because it's the cross-session source of
  // truth (.env), but we don't block first paint on it.
  useEffect(() => {
    let cancelled = false;
    api
      .settings()
      .then((data) => {
        if (cancelled) return;
        const remote = data.ui_language;
        if ((remote === "it" || remote === "en") && remote !== language) {
          setLanguageState(remote);
          try {
            window.localStorage.setItem(LOCAL_STORAGE_KEY, remote);
          } catch {
            // ignore storage errors
          }
        }
      })
      .catch(() => {
        // Backend unreachable on first paint — keep localStorage.
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const setLanguage = useCallback(async (next: Language) => {
    setLanguageState(next);
    try {
      window.localStorage.setItem(LOCAL_STORAGE_KEY, next);
    } catch {
      // ignore
    }
    try {
      await api.setUiLanguage(next);
    } catch {
      // Best-effort: the choice is already in localStorage so the UI
      // stays consistent in this session even if the backend save
      // failed (e.g. .env not writable).
    }
  }, []);

  const value = useMemo<LanguageContextValue>(() => {
    const dict = DICTIONARIES[language];
    return {
      language,
      setLanguage,
      t: (key, params) => {
        const candidate = resolvePath(dict, key) ?? resolvePath(DICTIONARIES.it, key);
        if (candidate === undefined) return key;
        return interpolate(candidate, params);
      },
    };
  }, [language, setLanguage]);

  return createElement(LanguageContext.Provider, { value }, children);
}

/** Access the active language and translate keys. Must be called from
 * within a ``<LanguageProvider>``. */
export function useT(): LanguageContextValue {
  const ctx = useContext(LanguageContext);
  if (!ctx) {
    throw new Error("useT must be used within a <LanguageProvider>");
  }
  return ctx;
}
