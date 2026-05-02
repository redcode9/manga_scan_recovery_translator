# Desktop UI Plan — `msrt`

Stato: pianificazione approvata, non implementata in questa tranche.

Obiettivo: creare una UI locale, bella ma operativa, che renda `msrt` usabile su
MacBook senza terminale. L'utente deve poter configurare l'ambiente, incollare un
URL o scegliere una cartella, vedere dry-run/capitoli, lanciare traduzione,
seguire progress e aprire PDF/CBZ prodotti.

La UI non deve duplicare logica di scraping, traduzione, packaging o setup. Deve
orchestrare il backend Python esistente e mostrare stato/progress in modo chiaro.

## Decisione Stack

Scelta raccomandata: **Tauri + Vite + React/TypeScript + backend locale Python**.

Motivazioni:
- app desktop leggera e naturale su macOS;
- Vite/React permette una UI moderna, veloce e facilmente affidabile a un team
  frontend;
- Tauri è più leggero di Electron e mantiene una distribuzione desktop pulita;
- il backend Python riusa `msrt` senza duplicare logica nel frontend;
- la UI può nascere prima come web app locale e poi essere impacchettata con
  Tauri.

Alternative valutate:
- **Vite web puro + FastAPI**: più semplice, ma l'utente deve aprire browser e
  gestire un server locale; meno rifinito come esperienza Mac.
- **Electron + Vite**: maturo e semplice per process management, ma più pesante.
- **SwiftUI nativa**: ottima su macOS, ma meno diretta da integrare col backend
  Python e meno portabile.

## Principi UX

- Prima schermata = prodotto operativo, non landing page.
- L'utente non deve conoscere i comandi CLI.
- Ogni azione lunga ha progress, log e stato recuperabile.
- Opzioni avanzate sono disponibili, ma non visibili di default.
- Le API key non appaiono mai nei log né nel frontend dopo il salvataggio.
- I batch lunghi devono essere pianificabili prima dell'esecuzione.
- La UI deve poter riprendere dopo crash o chiusura leggendo manifest/cache.

Stile consigliato:
- operativo, denso ma leggibile, da utility professionale macOS;
- palette neutra chiara/scura con accenti blu/verde per stato e azioni;
- card solo per elementi ripetuti o pannelli funzionali, non layout decorativo;
- icone Lucide per azioni comuni;
- tabelle/lista virtualizzata per capitoli e job;
- supporto tastiera, focus ring visibili, contrasto AA.

## Layout Applicazione

Navigazione laterale compatta:
- **Dashboard**
- **Nuovo Job**
- **Batch**
- **Libreria**
- **Impostazioni**
- **Log**

Header globale:
- stato LiteLLM (`running`, `stopped`, `unhealthy`);
- modello attivo;
- stato MITR;
- spazio cache;
- ultimo errore critico se presente.

## Schermate

### Dashboard

Mostra:
- stato ambiente: `doctor`, MITR, LiteLLM, provider, GPU/CPU;
- job in corso con progress sintetico;
- ultimi output prodotti;
- azioni rapide: `Nuovo URL`, `Cartella locale`, `Dry-run batch`, `Apri libreria`.

La dashboard deve essere usabile anche al primo avvio: se mancano prerequisiti,
mostra CTA diretta al setup wizard.

### Setup Wizard

Percorso guidato:
1. Verifica prerequisiti (`uv`, Python, spazio disco, Playwright, MITR).
2. Selezione provider LLM: OpenAI default, Anthropic/Google opzionali.
3. Inserimento API key con input mascherato.
4. Salvataggio credenziali: preferenza macOS Keychain; fallback `.env`.
5. Install/verify MITR.
6. Avvio/verifica LiteLLM.
7. Test opzionale paid smoke.
8. Esito finale con stato verde/giallo/rosso e next action.

Il wizard deve essere idempotente: se una configurazione esiste, chiede conferma
prima di sostituirla.

### Nuovo Job

Input:
- URL capitolo/serie oppure cartella locale;
- formato: PDF default, CBZ, both;
- modello: default `gpt`, scelta alias;
- renderer: `custom-postprocess` default, `mitr-manga2eng` per confronto;
- output directory;
- toggle `I own rights`;
- opzioni avanzate collassate: font path, pre-dict, no-gpu, no-auto-glossary,
  site adapter.

Comportamento:
- se URL supporta lista capitoli, suggerisce `Dry-run batch`;
- se URL singolo, propone `Esegui capitolo`;
- se cartella locale, usa pipeline `run-local`.

### Batch Planner

Usato per `--all-chapters`.

Mostra:
- elenco capitoli con numero, titolo, URL, stato output esistente;
- checkbox per includere/escludere capitoli;
- selezione rapida: tutti, mancanti, range, da N a M;
- stima pagine se disponibile;
- stima tempo/costo solo quando dati sufficienti, marcata come approssimativa;
- opzioni `skip existing`, `continue on error`, formato, modello.

Azioni:
- `Dry run`: lista e valida senza scaricare/tradurre;
- `Avvia batch`: crea job batch;
- `Salva piano`: opzionale, salva JSON del piano per ripresa futura.

Per batch grandi, default consigliato: esecuzione sequenziale, non parallela,
per rispettare rate limit e contenere uso LLM/GPU.

### Job Progress

Vista live di un job singolo o batch.

Fasi:
- setup/preflight;
- fetch;
- auto-glossary;
- translate/MITR;
- postprocess;
- package;
- done/error.

Elementi:
- progress bar globale;
- progress per capitolo;
- log streaming filtrabile (`info`, `warn`, `error`, `debug`);
- comando equivalente CLI copiabile;
- output appena prodotti;
- pulsanti: pausa futura, stop, retry failed, apri output, apri log.

Stop deve terminare processi figli in modo pulito quando possibile e marcare il
job come interrotto.

### Libreria

Mostra output locali:
- PDF/CBZ prodotti;
- serie/capitolo/titolo;
- data esecuzione;
- modello/provider;
- strategia fetch;
- errori o warning;
- link al manifest `msrt-run.json`;
- apri PDF, apri cartella, ritenta capitolo, elimina output.

Fonte dati: manifest e output in `out/`, cache in `~/.cache/msrt/`.

### Impostazioni

Sezioni:
- provider e modello default;
- API key status (presente/non presente, mai valore chiaro);
- MITR path/versione;
- LiteLLM port/config;
- Playwright/browser;
- cache/output dir;
- font consigliato/path;
- advanced diagnostics.

Azioni:
- avvia/ferma LiteLLM;
- esegui doctor;
- paid smoke esplicito;
- pulizia cache controllata;
- esporta diagnostics bundle senza credenziali.

## Backend Locale

Struttura proposta:

```text
src/msrt/ui_server/
  app.py              # FastAPI locale, bind 127.0.0.1
  jobs.py             # job queue + lifecycle
  events.py           # SSE/WebSocket event stream
  settings_api.py     # setup/env/provider/font/MITR checks
  commands.py         # bridge verso pipeline Python esistente
  library.py          # lettura manifest/output/cache
  schemas.py          # pydantic request/response/event models
```

La UI desktop avvia il backend locale come processo figlio oppure importa il
server dal venv del progetto. Per MVP UI, preferire processo figlio per isolare
dipendenze e semplificare restart.

Bind: `127.0.0.1` soltanto. Niente esposizione LAN.

## Frontend

Struttura proposta:

```text
apps/desktop/
  package.json
  vite.config.ts
  tsconfig.json
  src/
    main.tsx
    app/
      App.tsx
      routes.tsx
      stores/
    components/
      AppShell.tsx
      StatusPill.tsx
      JobProgress.tsx
      ChapterTable.tsx
      LogViewer.tsx
      ProviderSelector.tsx
      FilePicker.tsx
    pages/
      Dashboard.tsx
      SetupWizard.tsx
      NewJob.tsx
      BatchPlanner.tsx
      Library.tsx
      Settings.tsx
      Logs.tsx
    lib/
      api.ts
      events.ts
      format.ts
      paths.ts
  src-tauri/
    tauri.conf.json
    capabilities/
```

Design system:
- React + TypeScript;
- Tailwind o CSS modules;
- Radix/shadcn primitives ammessi per dialog, tabs, select, tooltip;
- Lucide icons;
- TanStack Query per API state;
- Zustand o Redux Toolkit solo se serve stato complesso;
- TanStack Table + virtualization per lista capitoli/output.

## Contratto API

Endpoint minimi:

```text
GET  /api/health
GET  /api/doctor
POST /api/setup
GET  /api/settings
PUT  /api/settings
POST /api/server/up
POST /api/server/down

POST /api/chapters/dry-run
POST /api/jobs
GET  /api/jobs
GET  /api/jobs/{id}
POST /api/jobs/{id}/cancel
POST /api/jobs/{id}/retry
GET  /api/jobs/{id}/events

GET  /api/library
GET  /api/library/{manifest_id}
POST /api/open-path
```

`/api/jobs/{id}/events` può essere SSE per semplicità. WebSocket è accettabile
se il team preferisce, ma SSE è sufficiente per progress/log monodirezionale.

## Eventi Progress

Schema indicativo:

```json
{"type":"job_started","job_id":"...","kind":"url_batch"}
{"type":"phase","job_id":"...","chapter":"51","phase":"fetch","message":"Scarico pagine"}
{"type":"progress","job_id":"...","current":12,"total":45,"unit":"pages"}
{"type":"log","job_id":"...","level":"info","message":"Auto-glossary cache hit"}
{"type":"output","job_id":"...","path":"out/wistoria-51-it.pdf"}
{"type":"warning","job_id":"...","message":"1 pagina richiede browser capture"}
{"type":"error","job_id":"...","message":"MITR non ha prodotto 2 pagine"}
{"type":"job_finished","job_id":"...","status":"success"}
```

Il backend deve generare eventi direttamente dalla pipeline Python, non parsare
il rendering Rich della CLI.

## Job Model

Campi minimi:
- `id`;
- `kind`: `local`, `url`, `url_batch`;
- `status`: `queued`, `running`, `succeeded`, `failed`, `cancelled`;
- `input_url` o `input_dir`;
- `output_dir`;
- `format`;
- `model`;
- `renderer`;
- `chapters_total`, `chapters_done`, `chapters_failed`;
- `current_phase`;
- `created_at`, `started_at`, `finished_at`;
- `output_files`;
- `manifest_paths`;
- `errors`, `warnings`.

Persistenza:
- SQLite locale consigliato per job history;
- manifest `msrt-run.json` resta fonte di verità per output prodotti;
- log job in `~/.cache/msrt/ui/jobs/<job_id>/`.

## Sicurezza E Credenziali

- API key mai inviate al frontend in chiaro.
- Preferire `keyring`/macOS Keychain per salvataggio credenziali.
- Fallback `.env` esplicito e segnalato come meno sicuro.
- Diagnostics/export deve redigere token e path sensibili quando richiesto.
- Log backend deve filtrare pattern comuni: chiavi provider, token `Bearer`,
  e assegnazioni env come `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`.
- Conferma `i-own-rights` resta obbligatoria per URL e batch.

## Mapping UI → CLI/Pipeline

La UI deve poter mostrare il comando equivalente per debug:

```bash
msrt run <URL> --site mangafire --all-chapters --format pdf --model gpt --i-own-rights
msrt run <URL> --site mangafire --all-chapters --dry-run --i-own-rights
msrt run-local <DIR> --format pdf --series "<SERIES>" --chapter "<N>"
msrt doctor --model gpt
msrt server up
```

Internamente, il backend deve chiamare funzioni Python dove possibile
(`run_local`, scraper, setup, doctor), non shellare comandi se esiste già
un'API interna stabile. Shell/subprocess resta accettabile per MITR e LiteLLM,
come oggi.

## Error Handling

Errori attesi da trattare come stati UI, non traceback:
- MITR mancante;
- LiteLLM non running/unhealthy;
- API key mancante;
- provider paid smoke fallito;
- URL non supportato;
- lista capitoli non disponibile;
- fetch parziale;
- MITR exit code non zero;
- MITR exit zero ma pagine mancanti;
- browser capture richiede intervento manuale;
- spazio disco insufficiente;
- batch interrotto dall'utente.

Ogni errore deve mostrare:
- cosa è successo;
- quale step era in corso;
- cosa può fare l'utente;
- path log/manifest utile.

## Roadmap UI

### v0.4a — Backend UI Foundation

- FastAPI locale;
- job queue single-worker;
- SSE events;
- wrapper `doctor`, `server up/down`, dry-run capitoli;
- libreria manifest/output;
- test backend zero-rete.

### v0.4b — Web UI MVP

- Vite React app;
- dashboard;
- setup wizard base;
- nuovo job URL/cartella;
- batch dry-run planner;
- job progress live;
- library minima.

### v0.4c — Tauri Mac App

- wrapper desktop;
- avvio/stop backend;
- file/directory picker nativo;
- open PDF/folder nativo;
- app icon, signing/notarization plan.

### v0.4d — Full Setup Autoconfigurante

- keychain integration;
- install/check MITR;
- Playwright install/check;
- provider selection;
- paid smoke opt-in;
- diagnostics bundle redatto.

### v0.4e — Polish E Rilascio Interno

- dark/light mode;
- empty states;
- retry failed chapters;
- batch resume;
- performance su 70+ capitoli;
- packaging release `.dmg` o `.zip`.

## Acceptance Criteria

La v0.4 è considerata pronta quando:
- un utente su MacBook clona/apre l'app e completa setup senza terminale;
- può incollare un URL MangaFire, fare dry-run e vedere i 70 capitoli;
- può selezionare 1-3 capitoli e produrre PDF;
- può lanciare batch con skip existing e vedere progress per capitolo;
- può aprire PDF/output/log dalla UI;
- può diagnosticare provider/MITR/LiteLLM da UI;
- nessuna credenziale compare in log, manifest, network response o UI state;
- chiudere e riaprire la UI mostra job/output esistenti.

## Vincoli Per Il Team

- Non riscrivere scraper/traduzione/package in TypeScript.
- Non salvare API key nel localStorage.
- Non bypassare login/captcha/Turnstile.
- Non lanciare batch globale senza dry-run o conferma esplicita.
- Non introdurre chiamate paid in background senza consenso.
- Non committare output manga, credenziali, cache o log reali.
