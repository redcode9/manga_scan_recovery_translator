# Stato Avanzamento Lavori — `msrt`

Documento vivo del progetto. Aggiornato in occasione di:
- chiusura di un task significativo
- blocker incontrato (con descrizione e workaround)
- decisione tecnica presa che cambia il piano (anche piccola)
- risultato di una verifica (manuale o automatica)

Non aggiornato per micro-cambi di stato (es. "ora sto debuggando"). Il piano ufficiale resta in `~/.claude/plans/dobbiamo-costruire-un-estrattore-synthetic-sundae.md`. Questo file riflette **lo stato reale** dell'implementazione e devia dal piano quando emergono cose nuove.

**Non viene cancellato** finché il progetto non è completato (raggiunti tutti gli obiettivi MVP + v0.3 minimo per uso reale).

---

## Decisioni prese

| Data | Decisione | Motivazione |
|---|---|---|
| 2026-04-29 | Lingue: EN → IT priorità | Esempio dell'utente è `mangafire.to/.../en/` |
| 2026-04-29 | Architettura: wrap di MITR come **dipendenza esterna**, non fork né import | MITR è GPL-3.0; il wrapper resta MIT e mantiene una separazione esplicita dal motore esterno |
| 2026-04-29 | Provider LLM multi-provider via LiteLLM proxy | Anthropic + OpenAI + Google intercambiabili senza patch upstream |
| 2026-04-29 | Default model: GPT-5.5 (alias `gpt`) | Switch da Sonnet durante setup wizard: prima coppia chiave/modello disponibile sulla macchina dell'utente; Claude resta supportato via `--model sonnet`. |
| 2026-04-29 | Default formato: CBZ (`translate`/`package`), PDF (`run-local`/`run`) | CBZ è standard archivio manga; PDF è il formato lettura per l'utente finale |
| 2026-04-29 | Naming: motore esterno chiamato `MITR` o `manga-image-translator`, mai "MIT" | Evita ambiguità con la licenza MIT del wrapper |
| 2026-04-29 | MangaDex come adapter pubblico, MangaFire come adapter interno first-class non promosso | MangaDex ha API ufficiale; MangaFire è il sito che l'utente sta effettivamente usando |
| 2026-04-29 | Niente font bundlato: `--font-path` opzionale + `doctor` avvisa | Licenze font incerte (Wild Words, Anime Ace non confermati permissive) |
| 2026-04-29 | Niente smoke test paid in CI; `--paid-smoke` solo opt-in in `doctor` | Costo, fragilità, requisito 3 chiavi |
| 2026-04-29 | RunManifest `msrt-run.json` salvato per ogni esecuzione | Riproducibilità, debug, A/B tra provider |
| 2026-04-29 | LLM locale rimandato a v0.7 via Ollama, modello scelto al momento via benchmark | Lo stato dell'arte locale evolve velocemente, niente hardcoding oggi |
| 2026-04-29 | Nessun remoto GitHub creato per ora | Non serve per v0.1 locale; nome, account/org e visibilità si decidono prima della pubblicazione o collaborazione esterna |
| 2026-04-29 | Rimossi URL GitHub placeholder dal metadata package | Evita metadata PyPI/packaging puntati a un repository non ancora creato |
| 2026-04-29 | `--lang-target` deve pilotare anche il target MITR | Evita CLI ingannevole: il flag non deve finire solo nel manifest/metadata |
| 2026-04-29 | Primo E2E reale su OpenAI (`--model gpt`) | L'utente ha confermato che il prossimo test end-to-end userà API OpenAI; `gpt` punta a `gpt-5.5` |
| 2026-04-29 | Fallback URL automatico: adapter/download diretto → euristiche DOM → browser capture | L'obiettivo reale è `msrt run <URL>` senza scelte manuali; se non si riesce a scaricare la scan raw, il tool prova a catturare la scan visibile dal browser e poi continua con la pipeline locale |
| 2026-04-29 | Browser capture non bypassa blocchi umani | Se compaiono login, Turnstile, captcha o verifica manuale, il tool mette in pausa, lascia completare l'utente nel browser e riprende quando la scan è visibile; niente stealth/bypass |

---

## Task

### v0.0 — Bootstrap repository ✅ COMPLETATO 2026-04-29
- [x] `git init` + struttura cartelle (`docs/`, `configs/`, `src/msrt/{translate,package,scrape,utils}`, `tests/{unit,integration,fixtures}`, `scripts/`, `.github/workflows/`)
- [x] `pyproject.toml` con uv + hatchling, deps minime (typer, pydantic v2, pydantic-settings, rich, structlog, httpx, pyyaml) + extras (scrape: playwright; package-pdf: img2pdf, pillow; hyphenation: pyphen). Dev: pytest, ruff, mypy strict.
- [x] `LICENSE` (MIT) e `NOTICE` con elenco licenze upstream (manga-image-translator GPL-3.0, LiteLLM MIT, Playwright Apache-2.0, Pyphen LGPL/MPL, ecc.)
- [x] `README.md` con disclaimer prudente, claim "best-effort", obiettivi finali separati, tabella alias `--model`, sezione font OFL consigliati
- [x] `docs/PROGRESS.md` (questo file)
- [x] `docs/UNOFFICIAL_ADAPTERS.md` (placeholder per MangaFire v0.3)
- [x] `docs/PROVIDER_NOTES.md` (Chat Completions vs Responses API, glossary workaround, tabella alias)
- [x] `.env.example` (Anthropic + OpenAI + Google + LITELLM_PORT + MITR_BIN_PATH) e `.gitignore` (Python, venv, output, fixture immagini protette)
- [x] CI `.github/workflows/ci.yml` (matrix Python 3.11/3.12, ruff lint + format check, mypy strict, pytest, NO rete, NO chiamate paid)
- [x] `scripts/bootstrap.sh` (eseguibile, `uv sync` + istruzioni manuali per install MITR in venv dedicato)
- [x] Placeholder `src/msrt/cli.py` (Typer app) + `__init__.py` di tutti i package
- [x] Test smoke `tests/test_smoke.py` (3 test, tutti passano)
- [x] **Primo commit `chore: bootstrap repository (v0.0)`** — hash `afc7aaa`, 21 files, 1483 inserzioni
- [x] Review v0.0: rimossi metadata URL GitHub prematuri, aggiunti `.gitkeep` per tracciare cartelle vuote previste dal piano, formulazione licenza resa più prudente

**Verifica qualità locale (post-commit)**:
- `uv sync --all-extras --dev`: OK
- `uv run ruff check src tests`: All checks passed
- `uv run ruff format --check src tests`: 9 files already formatted
- `uv run mypy src/msrt`: Success: no issues found in 7 source files
- `uv run pytest -q`: 3 passed in 0.04s

**Review successiva (2026-04-29)**:
- `git status --short`: pulito prima della review
- `git log --oneline --decorate --stat -5`: 2 commit su `main`
- `uv run ruff check src tests`: All checks passed
- `uv run ruff format --check src tests`: 9 files already formatted
- `uv run mypy src/msrt`: Success: no issues found in 7 source files
- `uv run pytest -q`: 3 passed in 0.01s

### v0.1 — Motore end-to-end con input locale (MVP)

1. [ ] Pin versione MITR + verifica flag reali (`--help`, `config-help`)
   - 2026-04-29: MITR non installato nel Python globale né nel venv msrt (`No module named manga_translator`). Decisione: implementare `doctor` e wrapper con errore chiaro; pin/verifica reale resta **bloccato** finché MITR non viene installato in venv dedicato.
2. [x] Modelli `Bubble`, `Page`, `Chapter`, `TranslationJob`, `RunManifest` in `src/msrt/models.py`
3. [x] Config (`pydantic-settings`) e logging (`structlog` + `rich`)
4. [x] LiteLLM proxy multi-provider, `configs/litellm.yaml`, `configs/translator-prompt.yaml` con prompt EN→IT manga-aware + glossary embedded
5. [x] `msrt doctor` (default + placeholder esplicito `--paid-smoke`)
6. [x] `TranslationEngine` ABC + `SubprocessEngine` MITR (subprocess pronto, verifica reale bloccata da MITR mancante)
7. [x] CLI metadati manuali (`--series`, `--chapter`, `--title`, `--lang-source`, `--lang-target`) su `run-local`, `translate` e `package`
8. [x] `package/naming.py` natural sort + warning ambiguità
9. [x] Packaging CBZ (ComicInfo.xml `LanguageISO=it`) + PDF (img2pdf)
10. [x] RunManifest `msrt-run.json` model + writer
11. [x] CLI `msrt run-local` end-to-end con progress bar `rich.Progress` (3 fasi: collect → translate → package)
12. [x] CLI `msrt translate` splittato da `run-local` (solo MITR, niente packaging) con progress bar a 2 fasi (collect → translate)
13. [x] `pipeline.run_local` / `translate_only` accettano `engine_factory` (DI) e `on_phase` callback
14. [x] Test E2E con `MockTranslationEngine` che simula MITR copiando le immagini → coperto run_local + translate_only senza dipendere da MITR installato
15. [ ] Test E2E **reale** su fixture proprietaria con MITR installato — bloccato finché MITR non è installato e LiteLLM proxy attivo

**Verifica qualità locale v0.1 (2026-04-29, dopo split translate + progress bar + mock E2E)**:
- `uv run ruff check src tests`: All checks passed
- `uv run ruff format --check src tests`: 23 files already formatted
- `uv run mypy src/msrt`: Success: no issues found in 18 source files
- `uv run pytest -q`: 9 passed in 0.20s
- `uv run msrt --help`: 6 sotto-comandi listati (`version`, `doctor`, `package`, `translate`, `run-local`, `server`)
- `uv run msrt translate --help`: tutti i flag previsti presenti (incluso `--glossary` e `--no-gpu`)
- Smoke `msrt doctor --model sonnet` (precedente): exit 1 atteso, segnala mancanza chiave + MITR + LiteLLM. Comportamento corretto in ambiente senza setup completo.

**Review v0.1 successiva (2026-04-29)**:
- Corretto bug: `--lang-target` ora viene mappato a `TranslationJob.target_lang` e usato dal comando subprocess MITR (`it`/`ITA`/`italiano` → `ITA`; codici a 3 lettere passano uppercase; codici non supportati falliscono con errore chiaro).
- Corretto edge case: directory senza immagini supportate fallisce subito prima di invocare MITR.
- Corretto naming: `msrt package` usa lo stesso slug robusto di `run-local`, invece di comporre path con `series` grezzo; slash e caratteri non alfanumerici non creano sottocartelle accidentali.
- Aggiunti test per target lang MITR, directory vuote e manifest su errore.
- `uv run ruff check src tests`: All checks passed
- `uv run ruff format --check src tests`: 24 files already formatted
- `uv run mypy src/msrt`: Success: no issues found in 18 source files
- `uv run pytest -q`: 14 passed in 0.52s
- `uv run msrt --help`: 6 sotto-comandi listati
- `uv run msrt doctor --model sonnet`: exit 1 atteso in ambiente non configurato

### v0.1.x — Ambiente runtime LiteLLM (subprocess locale + Docker riferimento)

Obiettivo: rendere `msrt server up/down/status` operativo in modo che il primo E2E reale richieda solo l'install di MITR. Docker non è installato sulla macchina di Piero → scelta nativa via subprocess.

- [x] `pyproject.toml`: aggiunto `[project.optional-dependencies] runtime = ["litellm[proxy]>=1.55"]`. `uv sync --all-extras --dev` ora installa litellm 1.83.14 nel venv di msrt (`.venv/bin/litellm`).
- [x] `src/msrt/server.py` con `start_litellm`/`stop_litellm`/`litellm_status`/`find_litellm_binary`. PID file in `~/.cache/msrt/litellm.pid`, log file in `~/.cache/msrt/litellm.log`. SIGTERM con fallback SIGKILL su stop. Idempotente su `up` se già running. Healthcheck con timeout configurabile (default 15s).
- [x] CLI `msrt server up|down|status` reali (sostituiscono il precedente placeholder). `up` accetta `--config` e `--wait`. Errori esplicitati con `LiteLLMUnavailableError` quando il binary non c'è.
- [x] `msrt doctor` esteso con check `litellm-bin` (path risolto) + `litellm` (status del proxy + healthcheck reale).
- [x] `docker-compose.yml` come **riferimento opzionale** per chi preferisce Docker (Linux/NVIDIA o isolamento). Documentato che `msrt server up` resta la via consigliata su macOS/MPS.
- [x] `scripts/bootstrap.sh` aggiornato con istruzioni native+docker per il proxy.
- [x] `tests/test_server.py` (12 test): binary non trovato, status senza/con PID file stale, idempotenza su already-running, stop SIGTERM, ricerca binary venv-first con fallback PATH, path file PID/log.
- [x] Review runtime: `server.start_litellm` ora chiude il log handle lato parent dopo lo spawn del subprocess.
- [x] `scripts/install-mitr.sh`: convenience installer opt-in per creare il venv MITR esterno, installare `manga-image-translator` e stampare il valore `MITR_BIN_PATH` da copiare in `.env`. Supporta `--prefix`, `--package`, `--dry-run`, `--help`.
- [x] README, `.env.example` e `scripts/bootstrap.sh` aggiornati con flusso runtime v0.1.x reale e path MITR da venv dedicato.

**Verifica qualità (2026-04-29 dopo v0.1.x)**:
- `uv run ruff check src tests`: All checks passed
- `uv run ruff format --check src tests`: 26 files formatted
- `uv run mypy src/msrt`: Success: no issues found in 19 source files
- `uv run pytest -q`: 26 passed in 0.29s

**Review runtime + MITR installer (2026-04-29)**:
- `bash -n scripts/install-mitr.sh`: OK
- `./scripts/install-mitr.sh --help`: OK
- `./scripts/install-mitr.sh --dry-run --prefix /tmp/msrt-mitr-dry`: OK, nessuna installazione eseguita
- `uv run ruff check src tests`: All checks passed
- `uv run ruff format --check src tests`: 26 files already formatted
- `uv run mypy src/msrt`: Success: no issues found in 19 source files
- `uv run pytest -q`: 26 passed in 0.15s

**Smoke reali (2026-04-29)** sulla macchina dell'utente:
- `uv run msrt server up --wait 25` → `LiteLLM up & healthy PID 56054: ...http://localhost:4000/health`.
- `curl http://localhost:4000/health` → HTTP 200.
- `uv run msrt server status` → identico a sopra.
- `uv run msrt doctor --model sonnet` → `litellm-bin` ok (path .venv/bin/litellm), `litellm` ok (PID 56054), restanti check riportano correttamente lo stato (model fail per ANTHROPIC_API_KEY mancante, mitr fail per MITR non installato).
- `uv run msrt server down` → `LiteLLM fermato.`
- `uv run msrt server status` → exit 1 + `LiteLLM non in esecuzione (no .../litellm.pid)`.

→ Lo stack runtime è ora completo. Il primo E2E reale richiede solo: install MITR in venv dedicato + `ANTHROPIC_API_KEY` in `.env` + cartella di immagini.

### v0.1.x — Predisposizione E2E OpenAI

Decisione: il prossimo E2E reale userà OpenAI, non Anthropic. Quindi il percorso consigliato diventa `--model gpt` con `OPENAI_API_KEY`.

- [x] Alias `gpt` già presente in `configs/litellm.yaml`: `openai/gpt-5.5`.
- [x] `MODEL_ALIASES` già risolve `gpt` → provider `openai`, model ID `gpt-5.5`, env `OPENAI_API_KEY`.
- [x] `msrt doctor --model gpt` verifica `OPENAI_API_KEY`.
- [x] `msrt doctor --model gpt --paid-smoke` ora esegue una chiamata reale minima via LiteLLM `/v1/chat/completions`, lo stesso percorso compatibile OpenAI usato da MITR.
- [x] README e `.env.example` aggiornati con flusso OpenAI-first.

**Verifica OpenAI preflight (2026-04-29)**:
- `uv run ruff check src tests`: All checks passed
- `uv run ruff format --check src tests`: 27 files already formatted
- `uv run mypy src/msrt`: Success: no issues found in 19 source files
- `uv run pytest -q`: 28 passed in 0.24s
- `uv run msrt doctor --model gpt`: exit 1 atteso in ambiente non configurato; segnala correttamente `OPENAI_API_KEY` mancante, MITR mancante, LiteLLM non avviato, e `litellm-bin` OK.

**Prossimo E2E consigliato**:
1. `./scripts/install-mitr.sh`
2. Copiare in `.env` il `MITR_BIN_PATH="..."` stampato dallo script.
3. Impostare `OPENAI_API_KEY=...` in `.env`.
4. `msrt server up`
5. `msrt doctor --paid-smoke` (`MSRT_MODEL=gpt` viene letto da `.env`)
6. `msrt run-local <DIR_IMG> --format pdf --series "<SERIE>" --chapter "<N>"`

### v0.1.x — Setup wizard (`msrt setup` + `scripts/setup.sh`)

Obiettivo: ridurre l'onboarding da "checklist manuale" a "un comando + qualche conferma". Il wizard guida le decisioni che restavano manuali (provider, chiavi, install MITR, avvio proxy, paid smoke).

- [x] `src/msrt/setup.py`: `load_env`/`save_env` (parsing via python-dotenv, preserva commenti, quoting double-quote con escape per spazi/`$`/`#`/quote/CRLF), `PROVIDER_CATALOG` (OpenAI consigliato per il prossimo E2E, poi Anthropic, Google), `run_setup()` orchestra prereqs → .env → provider → API key → MITR → server → paid smoke → next steps.
- [x] Il provider scelto salva `MSRT_MODEL` in `.env`; `doctor`, `translate` e `run-local` lo usano quando `--model` è omesso.
- [x] `msrt server up` passa al subprocess LiteLLM anche le chiavi lette da `.env`, non solo `os.environ`, così una chiave appena inserita nel wizard è subito visibile al proxy.
- [x] CLI `msrt setup` con flag `--yes`, `--no-install-mitr`, `--no-server`, `--paid-smoke`, `--project-root` (per test).
- [x] `scripts/setup.sh` come entrypoint: `uv sync --all-extras --dev` + `uv run msrt setup`. Forwarda flag dopo `--`.
- [x] Idempotente: chiavi e `MITR_BIN_PATH` esistenti richiedono conferma esplicita prima della sostituzione; `--yes` mantiene i valori esistenti.
- [x] README rinnovato: setup guidato (un comando) come metodo consigliato; setup manuale documentato come alternativa.
- [x] Test (`tests/test_setup.py`): round-trip `.env`, preservazione commenti, quoting valori speciali, alias del catalogo coerenti con `MODEL_ALIASES`, smoke `run_setup` con `--yes`, idempotenza `MSRT_MODEL`, export env in-process, fail-fast quando `uv` manca, exit code non-zero se `--paid-smoke` fallisce.

**Verifica qualità (2026-04-29 dopo setup wizard)**:
- `uv run ruff check src tests`: All checks passed
- `uv run ruff format --check src tests`: 28 files formatted
- `uv run mypy src/msrt`: Success: no issues found in 20 source files
- `uv run pytest -q`: 40 passed in 0.16s

**Review setup wizard (2026-04-29)**:
- Corretto flusso env → subprocess: le chiavi lette/scritte da `.env` vengono propagate al processo corrente e poi al subprocess LiteLLM.
- Corretto default modello: il wizard salva `MSRT_MODEL=gpt` e `doctor`/`translate`/`run-local` usano `MSRT_MODEL` quando `--model` è omesso.
- Corretto idempotenza: se `.env` contiene già `MSRT_MODEL` valido, `msrt setup --yes` lo mantiene invece di forzare OpenAI.
- Corretto `--paid-smoke`: se la chiamata reale al provider fallisce, `msrt setup --paid-smoke` esce con codice non-zero; `--yes --paid-smoke` è non interattivo e richiede chiave già presente in env/`.env`.
- Aggiornati next steps: dopo setup si può usare `msrt doctor` e `msrt run-local ...` senza ripetere `--model gpt`.
- `.venv/bin/ruff check src tests`: All checks passed
- `.venv/bin/ruff format --check src tests`: 29 files already formatted
- `.venv/bin/mypy src/msrt`: Success: no issues found in 20 source files
- `.venv/bin/pytest -q`: 44 passed in 0.24s

**Smoke CLI (2026-04-29)**:
- `uv run msrt --help`: 7 sotto-comandi listati (`version`, `doctor`, `package`, `translate`, `run-local`, `setup`, `server`).
- `uv run msrt setup --help`: tutti i flag presenti, descrizioni in italiano.
- `.venv/bin/msrt setup --yes --no-install-mitr --no-server --project-root /tmp/...`: crea `.env` da template con `MSRT_MODEL=gpt`, sceglie OpenAI di default, salta install/server, stampa next steps coerenti. Exit 0.

→ L'onboarding adesso è `git clone + ./scripts/setup.sh`. L'E2E reale resta dipendente solo dall'effettivo install di MITR + chiave provider.

### v0.1.x — Diagnostica primo E2E (2026-04-29)

Tentativo reale del wizard sulla macchina dell'utente. Trovati 3 problemi e fixati.

**Problema A: install MITR fallito** — `uv pip install manga-image-translator` ritornava `package not found`. Causa: MITR **non è pubblicato su PyPI** sotto quel nome; va installato dal repo Git.

Fix in `scripts/install-mitr.sh`:
- clone del repo `https://github.com/zyddnys/manga-image-translator.git` in `<prefix>/repo` (idempotente: se già clonato fa fetch+checkout+reset).
- nuovi flag `--git-url` e `--git-ref` (default `main`), `--python` (default `3.11`).
- `uv pip install -r <repo>/requirements.txt` per le dipendenze runtime.
- `uv pip install <repo>` per il package stesso (definisce `python -m manga_translator`).

**Problema B: Python 3.12 incompatibile** — il venv MITR usava il Python di sistema (3.12.13), ma il `pyproject.toml` di MITR pinna `requires-python = ">=3.10, <3.12"`.

Fix: il venv ora viene creato con `uv venv --python 3.11 <prefix>/.venv`. uv scarica automaticamente CPython 3.11 se non disponibile.

**Problema C: timeout LiteLLM al primo boot** — `start_litellm` con `wait_seconds=15-20s` è troppo stretto: il primo boot del proxy carica il config, registra i model, fa varie inizializzazioni. Il proxy era effettivamente up a 25-30s ma il wizard segnalava "non healthy".

Fix:
- `start_litellm.wait_seconds` default da 15.0 a **45.0** (`src/msrt/server.py`).
- `_maybe_start_server` in setup wizard da 20.0 a **45.0**.
- `check_litellm_health.timeout` da 2.0 a **5.0**.

Verifica post-fix: `curl http://localhost:4000/health` HTTP 200 con il proxy ancora running dal primo tentativo dell'utente. Test 44/44 pass. `install-mitr.sh --dry-run --prefix /tmp/mitr-dryrun` stampa i nuovi comandi corretti.

**Conseguenze sul piano**: il wizard E2E adesso può andare a buon fine in un solo passaggio. L'utente fa `rm -rf ~/tools/mitr && ./scripts/install-mitr.sh` e il flow continua.

### v0.1.y — Primo E2E reale completato (2026-04-29)

Eseguito il primo E2E reale `msrt run-local` su 3 pagine di Wistoria capitolo 44 (scan salvate manualmente da browser, scraping URL rimandato a v0.2/v0.3 per blocchi di rete su MangaDex e Cloudflare su MangaFire). Pipeline funziona end-to-end e produce `out/wistoria-44-it.pdf`. Durante il debug sono emerse decisioni tecniche significative sul wrapping di MITR.

**Pin commit MITR**: `3abfc47` (giugno 2025, pre-rust). La `main` ha `import rusty_manga_image_translator` hard-coded che fallisce su macos-arm64 (wheel corrotto). Il commit pre-rust gira pulito. Salvato in `scripts/install-mitr.sh` come `GIT_REF` di default? → no, default resta `main` ma è documentato come override consigliato. **Da decidere**: se pinnare `3abfc47` come default. Per ora workaround: passare `--git-ref 3abfc47` a `install-mitr.sh`.

**Struttura CLI MITR scoperta**: la documentazione del piano è obsoleta. La forma corretta è:

```
manga_translator [TOP-LEVEL flags] {local|ws|shared|config-help} [SUBCOMMAND flags]
```

- Top-level (prima del subcommand): `--use-gpu`, `--font-path`, `--pre-dict`, `--post-dict`, `--attempts`, `--ignore-errors`, `--model-dir`, `--kernel-size`, `--context-size`.
- Subcommand `local`: `-i`, `-o`, `-f`, `--overwrite`, `--skip-no-text`, `--use-mtpe`, `--save-text|--load-text|--save-text-file`, `--prep-manual`, `--save-quality`, `--config-file`.
- **Non esistono come flag CLI**: `--translator`, `--target-lang`, `--gpt-config`, `--manga2eng`. Questi vanno tutti dentro `--config-file <path.json>`.
- `--save-text` e `--save-text-file` sono mutualmente esclusive (mutually-exclusive group).

**Translator per OpenAI-compatible endpoint**: `custom_openai`, non `chatgpt`. Il translator `chatgpt` parla con `api.openai.com` direttamente e usa `chatgpt-4o-latest` di default; non funziona via LiteLLM. `custom_openai` legge da env vars **`CUSTOM_OPENAI_API_BASE`**, **`CUSTOM_OPENAI_API_KEY`**, **`CUSTOM_OPENAI_MODEL`** (non `OPENAI_*`).

**Formato `--config-file`**: JSON con struttura nested:

```json
{
  "translator": {
    "translator": "custom_openai",
    "target_lang": "ITA",
    "gpt_config": "/abs/path/to/configs/mitr-gpt-config.yaml"
  },
  "detector": {
    "box_threshold": 0.5,
    "text_threshold": 0.3,
    "det_rotate": true,
    "det_auto_rotate": true
  }
}
```

MITR rifiuta config-file senza estensione `.json`/`.yaml` (errore `Unsupported configuration file format`); process substitution `<(echo …)` non funziona, deve essere un file vero.

**`gpt_config` YAML (OmegaConf)**: file separato letto via `OmegaConf.load`. Parametri rilevanti al root:
- `temperature: 1` — **richiesto da GPT-5.5**, che rifiuta qualsiasi valore diverso da 1 con HTTP 400 `Unsupported value: 'temperature' does not support 0.5`. Il default MITR è 0.5 e crasha (poi cade in `UnboundLocalError` nella gestione errore di `chatgpt.py:451`). `drop_params: true` di LiteLLM non aiuta perché `temperature` è un param valido, è solo il valore a essere fuori range.
- `chat_system_template` — system prompt con placeholder `{to_lang}`.

**Tweak detector per testo italico/stilizzato**: con i default (`box_threshold=0.7`, `text_threshold=0.5`, no rotation) il detector dbconvnext salta testo italico (esempio reale: caption "SHE'S THE ONE WHO'S BEEN" non rilevata). Fix: thresholds 0.5/0.3 + `det_rotate=true` + `det_auto_rotate=true`. Trade-off: qualche falso positivo in più (sfondi tramati riconosciuti come testo).

**Correzione artefatti OCR**: l'OCR di MITR (Model48pxOCR) compatta tokens (`MAKINGEMMA` invece di `MAKING EMMA`, `WHOSBEEN` invece di `WHO'S BEEN`, `ICAN` invece di `I CAN`). Il LLM non capisce automaticamente che vanno splittati. Fix nel system prompt (`configs/mitr-gpt-config.yaml`): istruzioni esplicite con esempi reali per separare i tokens prima di tradurre. **Limite residuo**: artefatti come `MAKINGIEMMA` (la `I` di "MAKING" bleed nella "EMMA") restano ambigui anche per il LLM senza glossary di serie. La risoluzione completa è il **two-pass `--save-text`/`--load-text`** (pianificato v0.6) + glossary di serie (v0.1 carry-over).

**Code paths aggiornati**:
- `src/msrt/translate/engine.py:_command()` — top-level flags prima di `local`.
- `src/msrt/translate/engine.py:_mitr_config()` — JSON nested, gpt_config absolute path, detector tweaks.
- `src/msrt/translate/engine.py:_environment()` — `CUSTOM_OPENAI_*` (non `OPENAI_*`).
- `src/msrt/translate/engine.py:translate()` — temp file `.json` per config-file (non process substitution).
- `src/msrt/cli.py:run_local_command` + `translate` — flag `--pre-dict` per OCR corrections opzionali.
- `src/msrt/models.py:TranslationJob` — campo `pre_dict_path: Path | None`.
- `configs/mitr-gpt-config.yaml` — nuovo file, `temperature: 1` + system prompt con istruzioni OCR.

**Carry-over v0.1 → v0.2**:
- ~~Glossary di serie non cablata~~ → chiuso. v0.1.z l'ha cablata al prompt; v0.1.aa l'ha automatizzata con build via LLM + cache persistente in `~/.cache/msrt/glossaries/`.
- Pinning MITR a `3abfc47`: decidere se settarlo come default in `install-mitr.sh` o lasciare la flag override.
- Test automatico per `engine._command()` aggiornato (la nuova struttura merita coverage).

### v0.1.z — Bug cross-chapter packaging + glossary cablata (2026-04-29)

Tentativo di run su un capitolo diverso (Wistoria Capitolo 50, 50 pagine, manualmente scaricate) ha rivelato due bug strutturali da chiudere prima di passare a v0.2.

**Bug A — packager raccoglie file vecchi**: `out/translated-pages/` non veniva pulita tra le run. Quando MITR non scriveva i nuovi file (per qualsiasi motivo: errore silenzioso, troppe pagine, modello non installato), `package_pdf`/`package_cbz` scansionavano la directory e raccoglievano i file della run precedente. Il PDF di Capitolo 50 conteneva quindi i contenuti tradotti di Capitolo 44, con `errors: []` nel manifest perché il packager si limitava a controllare "lista non vuota". Bug critico per UX.

Fix:
- `pipeline.reset_translated_dir(translated_dir)` invocata all'inizio di `run_local`/`translate_only` per cancellare i file (preservando subdir per safety).
- `package_pdf(files: list[Path], …)` e `package_cbz(files: list[Path], chapter, …)` ora **accettano una lista esplicita di file**, non più una directory da scansionare. Il caller fornisce la sequenza ordinata.
- `pipeline._collect_translated_files(chapter, translated_dir)` costruisce la lista da `chapter.pages` cercando ogni pagina per nome in `translated_dir`. Se manca anche solo una pagina, solleva `ValueError("MITR non ha prodotto N pagine attese su M: …")` con sample dei file mancanti — il packager non parte, l'utente vede errore chiaro.
- CLI `msrt package <DIR>` aggiornata: scannerizza la directory di input e passa la lista esplicita ai packager (comportamento utente invariato).

**Bug B — glossary mai iniettata**: `glossary.py` aveva `load_glossary`/`format_glossary`/`inject_glossary` ma non era cablata. `--glossary` era no-op. La placeholder `{glossary}` nel template di `translator-prompt.yaml` non veniva mai sostituita.

Fix:
- `TranslationJob` campo nuovo `gpt_config_path: Path | None`.
- `glossary.build_gpt_config_with_glossary(base_config, entries, target_dir)` legge la base YAML come testo, fa `replace("{glossary}", formatted)` (preservando `{to_lang}` per la sostituzione successiva di MITR), scrive un file temporaneo `.yaml` e ritorna il path.
- `pipeline._prepare_gpt_config(job, …)` invocata dopo `model_copy(target_lang)`: se `job.glossary_path` è valorizzata e contiene voci, costruisce il temp file e ritorna un `job` con `gpt_config_path` settato. Cleanup nel `finally` di `run_local`/`translate_only`.
- `SubprocessEngine._mitr_config()` usa `job.gpt_config_path` se presente, altrimenti il default `configs/mitr-gpt-config.yaml`.
- `mitr-gpt-config.yaml` aggiornato con sezione "Series glossary (apply when applicable…)" e placeholder `{glossary}`. Quando il glossary è vuoto/assente la placeholder diventa `(none — no series-specific terminology)`.

**Test aggiunti**:
- `test_pipeline.py::test_run_local_does_not_leak_pages_from_previous_chapter` — regressione per bug A (due run consecutive su out_dir condivisa, verifica che il secondo run non abbia residui del primo).
- `test_pipeline.py::test_run_local_raises_when_engine_drops_pages` — engine che traduce solo 1 pagina su 3, deve fallire con messaggio chiaro invece di pacchettare.
- `test_pipeline.py::test_reset_translated_dir_*` — rimozione file + creazione idempotente.
- `test_pipeline.py::test_run_local_uses_glossary_path_in_job` — verifica che il `CapturingEngine` riceva un job con `gpt_config_path` valido contenente le voci formattate, e che la pipeline cancelli il temp file alla fine.
- `test_glossary.py` — nuovo file con 6 test: load TSV/CSV, formattazione vuota, preservazione `{to_lang}`, build con/senza voci.
- `test_engine.py` — riscritto per la nuova firma `_command(in, out, text_out, cfg_path, job)`; verifica struttura top-level/subcommand, override `gpt_config_path`, default path.
- `test_package.py` — firme aggiornate, `package_pdf([])`/`package_cbz([])` rifiutati con `ValueError("lista vuota")`.

**Quality gate post-fix (2026-04-29)**:
- `uv run ruff check src tests`: All checks passed
- `uv run ruff format --check src tests`: 30 files already formatted
- `uv run mypy src/msrt`: Success in 20 source files
- `uv run pytest -q`: **61 passed** (up from 44)

**Carry-over chiusi**:
- ✅ Glossary cablata al prompt (era TODO esplicito).
- ✅ Test unit per `SubprocessEngine._command()` con la nuova struttura.
- ⏳ Pinning `GIT_REF` MITR a `3abfc47`: ancora da decidere.
- ⏳ `docs/PROVIDER_NOTES.md` con vincolo `temperature=1` GPT-5.5: ancora da scrivere.

### v0.1.aa — Auto-glossary via LLM (2026-04-29)

Direzione presa: il glossario di serie deve essere zero-friction per l'utente. Niente file da creare a mano. Implementato Livello A del piano (prefetch via LLM con cache persistente). Livello B (augmentation incrementale dal testo OCR del capitolo) rimandato a v0.6 dove convive col two-pass.

**Flusso utente**:
1. `msrt run-local <DIR> --series "Wistoria" …` lancia tutto. Se in cache `~/.cache/msrt/glossaries/wistoria.tsv` non esiste, il pipeline:
   - Logga "Glossario per 'Wistoria' non in cache. Lo costruisco con il modello 'gpt' (1 chiamata LLM)…"
   - POST a LiteLLM `/v1/chat/completions` con un system prompt strutturato che chiede TSV `EN<tab>IT` di nomi propri/luoghi/terminologia (max 30 voci).
   - Parsa la risposta (tollerante a Markdown fences, numbering, tabelle pipe, separatore `=>`).
   - Salva in cache.
2. Tutti i run successivi su Wistoria (qualsiasi capitolo) leggono dalla cache → 0 chiamate extra.
3. Il glossario alimenta la placeholder `{glossary}` in `mitr-gpt-config.yaml`, viene reso in un YAML temporaneo per ogni run e passato al `custom_openai` via `gpt_config`.

**Override e opt-out**:
- `--glossary <path>` esplicito → override completo (no auto-build).
- `--no-auto-glossary` → niente glossario, no chiamata LLM.
- `msrt glossary build "<series>" [--model X] [--force]` → build manuale opt-in (debug/manutenzione).
- `msrt glossary show/list/path/forget` → ispezione del cache.

**Failure handling**: se la build LLM fallisce (proxy down, modello non risponde, hallucination senza voci parsabili), il pipeline logga warning e continua **senza glossary** invece di abortire. Quality check sul lato chiamata: error chiaro se LiteLLM non raggiungibile, HTTP error con snippet della risposta, parsing failure con risposta grezza in messaggio.

**File toccati**:
- `src/msrt/translate/glossary_builder.py` (nuovo) — `build_glossary_via_llm`, `parse_glossary_tsv` (tollerante), `cached_glossary_path`, `save_glossary`, `slugify_series`. ~200 righe.
- `src/msrt/translate/glossary.py` — aggiunto `load_or_build_glossary` (orchestratore cache hit / cache miss).
- `src/msrt/models.py` — `TranslationJob.auto_glossary: bool = True`.
- `src/msrt/pipeline.py` — `_prepare_gpt_config` ora orchestra glossary_path → cached → auto-build → none. Nuovo callback `on_log` per messaggi pipeline (separato da `on_phase` per il progress bar).
- `src/msrt/cli.py` — flag `--auto-glossary/--no-auto-glossary` in `translate` e `run-local`. Subapp Typer `glossary` con `build/show/list/path/forget`. `_log_callback` usa `progress.console.print` per non mangiarsi le righe sotto lo spinner.
- `configs/mitr-gpt-config.yaml` — placeholder `{glossary}` già presente da v0.1.z; quando il glossary è vuoto/(none) la sostituzione produce un marker esplicito.

**Test aggiunti (83 totali pass, era 61)**:
- `test_glossary_builder.py` — 13 test: slugify, cached path, parse di vari formati TSV (pulito, markdown fences, numbering, pipe tables, arrow), save/load roundtrip, build success, HTTP error, parsing error, proxy unreachable, cache hit/miss, force rebuild.
- `test_pipeline.py` — 3 nuovi test: auto-build su cache miss (mock httpx, verifica TSV reso nel gpt_config che arriva all'engine), opt-out con `auto_glossary=False`, fallback graceful quando build solleva.
- `test_smoke.py` — 4 nuovi test: `glossary --help`, `glossary path` (con HOME monkey-patched), `glossary show` (missing series), `glossary list` (cache vuota).

**Quality gate (2026-04-29)**:
- `ruff check`: All checks passed
- `ruff format --check`: 32 files clean
- `mypy src/msrt`: Success in 21 source files
- `pytest -q`: **83 passed** (era 61)

**Limiti noti — onestà**:
- Hallucinations: il LLM può inventare nomi plausibili per serie obscure o post-cutoff. Il file TSV è editabile manualmente (`msrt glossary show`/edit con `$EDITOR`), e la cache è persistente.
- Per serie nicchia il LLM può rispondere con due campi vuoti (per design — il prompt lo istruisce a farlo se non sa la serie); in quel caso `parse_glossary_tsv` ritorna 0 voci → `GlossaryBuildError("non ha prodotto voci")` → fallback senza glossary.
- 100% accuracy non è raggiungibile col solo prefetch. Il vero salto qualità arriva con il **two-pass v0.6** dove il LLM vede tutto il testo OCR del capitolo e può augmentare il glossary in-context.

**Carry-over chiusi**:
- ✅ Glossary completamente cablato (era TODO esplicito).
- ✅ Auto-build di default → utente non deve fare nulla.

### v0.1.ab — Hotfix YAML block-scalar (2026-04-29)

Test su Capitolo 50 di Wistoria (50 pagine) ha esposto due bug nascosti dal cablaggio v0.1.aa.

**Bug 1 — placeholder `{glossary}` sopravvive quando entries è vuoto**: il pipeline ritornava `gpt_config_path = None` quando `_prepare_gpt_config` non aveva voci da iniettare (auto_glossary=False, build fail, override path con file vuoto). MITR riceveva quindi il file `mitr-gpt-config.yaml` raw che contiene `{glossary}` non sostituito. Quando MITR invoca `template.format(to_lang=…)` per il prompt, Python solleva `KeyError: 'glossary'` su ogni pagina. MITR esce con returncode 0 (errori per pagina sono solo log warning), il pipeline non vede `TranslationError`, e `_collect_translated_files` reporta correttamente "MITR non ha prodotto N pagine" — ma con sintomo confuso.

Fix: `_prepare_gpt_config` ora **sempre** rende un temp YAML (anche con entries={} → marker "(none)"). MITR non vede mai più la placeholder cruda. Test di regressione: `test_run_local_never_leaves_unsubstituted_glossary_placeholder` (CapturingEngine assert `"{glossary}" not in text`).

**Bug 2 — sostituzione multi-riga rompe il block scalar YAML**: `inject_glossary` faceva `str.replace("{glossary}", formatted)` con `formatted` come stringa multi-riga. Ma il `chat_system_template` è un YAML block scalar `|` con indent 2. Sostituendo `{glossary}` con `- Emma => Emma\n- Will => Will\n…`, solo la prima riga ereditava l'indentazione del placeholder; le successive iniziavano a colonna 0. OmegaConf legge questo come "block scalar terminato" e poi vede `-` dove si aspetta una nuova chiave del mapping → `yaml.parser.ParserError: while parsing a block mapping, expected <block end>, but found '-'`.

Fix: `inject_glossary` ora processa il template line-by-line; quando trova `{glossary}` con prefisso whitespace puro, ri-indenta tutte le righe della sostituzione con lo stesso prefisso. Test di regressione: `test_inject_glossary_preserves_block_scalar_indentation` parsa il rendered con `yaml.safe_load` per garantire validità sintattica (e verifica che `{to_lang}` sopravviva untouched per la sostituzione successiva di MITR).

**Diagnostica aggiunta**: ora il pipeline scrive sempre `out/.msrt-tmp/mitr.log` con stdout+stderr di MITR, e `_collect_translated_files` include il path nel messaggio di errore (`"…Vedi il log MITR in <path>"`). Ha fatto risparmiare un giro di debug per identificare il bug 2 — il log mostrava direttamente il `ParserError` con riferimento alla riga incriminata.

**File toccati**:
- `src/msrt/pipeline.py` — `_prepare_gpt_config` rende sempre il temp; `_collect_translated_files` accetta `log_dir`; nuovo helper `_write_mitr_log`; `run_local` cattura `TranslationResult` e scrive log.
- `src/msrt/translate/glossary.py` — `inject_glossary` preserva indent.
- `tests/test_glossary.py` — nuovo test indent + parse YAML reso.
- `tests/test_pipeline.py` — 2 test aggiornati al nuovo comportamento (gpt_config sempre non-None) + 1 nuovo test regressione su placeholder leakage.

**Quality gate (2026-04-29)**: ruff/format/mypy clean, **85 test pass** (era 83).

### v0.1.ac — Code review fixes (2026-04-29)

Code review post v0.1.aa ha trovato 5 punti, tutti chiusi.

**Alta — `translate_only` poteva dare falso successo**: il path `run_local` validava già con `_collect_translated_files`, ma `translate_only` no. Se MITR exit 0 dropping pagine (silenzio storico di MITR), `translate_only` salvava il manifest dichiarando successo. Fix: stesso pattern di `run_local` — `_write_mitr_log` su `out/.msrt-tmp/mitr.log` e `_collect_translated_files(chapter, translated_dir, log_dir=…)` come asserzione finale. Test: `test_translate_only_raises_when_engine_drops_pages`.

**Media — auto-glossary su `--series` di default**: la CLI defaultava a "Untitled Series", `_prepare_gpt_config` valutava `if series:` e partiva in auto-build. Risultato: chiamata LLM inutile + `~/.cache/msrt/glossaries/untitled-series.tsv` polluto. Fix: nuovo helper `_series_is_meaningful(series)` che skippa "untitled series", "untitled", "" (case-insensitive). Skip viene loggato all'utente per visibilità. Test: `test_run_local_skips_auto_glossary_for_default_series_title`.

**Media — `--pre-dict` mancava su `msrt translate`**: c'era solo su `run-local`. Asimmetria che bloccava chi usa `translate` per produrre solo le pagine tradotte. Fix: aggiunto `--pre-dict` con stessa semantica e descrizione. Test: `test_cli_translate_help_exposes_pre_dict`.

**Bassa — parser pipe-table inghiottiva header/separator Markdown**: tabelle tipo `| Source | Target |\n| --- | --- |\n| Emma | Emma |` finivano col salvare `Source => Target` e `--- => ---` come voci. Fix: `_MD_TABLE_SEPARATOR_RE` per droppare righe di solo `[ -:|*]`, e `_MD_TABLE_HEADER_TOKENS` per droppare header con synonyms tipici (Source/Target/English/Italian/Term/Name/...). Test: 3 nuovi (`...skips_markdown_table_headers_and_separators`, `...drops_bare_dash_separator_line`, `...drops_alternative_header_synonyms`).

**Bassa/docs — note PROGRESS.md obsolete**: aggiornato il default modello (Sonnet → GPT-5.5 con motivazione setup-wizard), rimossi i TODO già chiusi (glossary cablato, test engine).

**Quality gate (2026-04-29)**: ruff/format/mypy clean, **91 test pass** (era 85).

### v0.1.ad — Verifica E2E su capitolo lungo (2026-04-29 22:09)

`uv run msrt run-local ~/Desktop/Wistoria/Capitolo_50 --format pdf --series "Wistoria" --chapter "50" --title "Capitolo 50"` su 50 pagine PNG ad alta risoluzione (1034×1470, ~2.5 MB ciascuna): **completato in 24 min**.

- Auto-glossary cache hit (no chiamata LLM extra dopo il primo build di v0.1.aa).
- 50/50 pagine tradotte e renderizzate.
- `out/wistoria-50-it.pdf` prodotto, ~114 MB (2.3 MB/pagina, coerente con risoluzione input).
- Tutti i fix v0.1.z/aa/ab/ac validati end-to-end: cleanup translated-pages, validazione output, glossary iniettata, indent YAML preservato, `<|N|>` formato istruito.

**Throughput osservato**: ~28 sec/pagina su MPS Mac (model loading una tantum + ~25s/pagina di OCR + LLM call + inpainting + render). Plausibile collo di bottiglia: chiamata sequenziale al LLM (1 batch per pagina, no concurrency).

**Ottimizzazioni candidate per v0.6 / future**: `HttpEngine` (server MITR persistente, salta model loading ad ogni run); batching multi-pagina al LLM; `--attempts`/`--ignore-errors` di MITR esposti via CLI per non bloccare l'intero run su una pagina problematica.

### v0.2a — URL pipeline foundation (2026-04-29) ✅

Code review interno ha suggerito di partire dal "binario" comune URL → cartella locale **prima** di scrivere qualsiasi adapter site-specifico, così MangaDex / MangaFire / generic / browser-capture diventano strategie diverse dello stesso flusso. Implementato il bridge URL → folder; `msrt fetch` non traduce, produce solo le pagine, pronte per `msrt run-local`.

**Moduli creati**:
- `src/msrt/scrape/base.py` — `ChapterScraper` ABC + dataclasses `FetchedPage`, `FetchResult`, `FetchError`. Contratto: `matches(url) -> bool` + `async fetch(url, output_dir) -> FetchResult`. Naming on-disk obbligatorio `001.png`/`002.jpg` per natural sort downstream.
- `src/msrt/scrape/registry.py` — registry module-level + decorator `@register`. `scraper_for_url(url, site="auto")` con import lazy degli adapter (evita circular). Errori puliti con lista degli adapter registrati quando il match fallisce.
- `src/msrt/scrape/downloader.py` — `download_pages` async (`httpx.AsyncClient`), concurrency soft-limit con `asyncio.Semaphore`, retry esponenziale 1/2/4/8s su {408,425,429,500,502,503,504}, naming `001.png` da Content-Type → URL ext → `.bin` fallback. Helper `find_duplicate_pages` (warning per pagine con sha256 identico). Parametro `transport` per `httpx.MockTransport` nei test → zero rete in CI.
- `src/msrt/scrape/adapters/mangadex.py` — skeleton: riconosce `mangadex.org/{chapter,title}/<UUID>` e varianti `www`/`canary.mangadex.dev`. `fetch()` solleva `NotImplementedError("…v0.2b")` con messaggio chiaro. Auto-registrazione via `@register` al primo import del package adapters.
- `src/msrt/cli.py` — nuovo comando `msrt fetch <URL> [--out DIR] [--site auto|mangadex]`. Risolve adapter, esegue `asyncio.run(scraper.fetch(...))`, stampa percorso + warnings, suggerisce il prossimo passo (`msrt run-local …`). Exit codes: 0 success, 1 errore generico, 2 adapter not-yet-implemented.

**Test (16 nuovi, totale 116 pass)**:
- `tests/test_scrape_registry.py` — auto routing, `--site` override, FetchError per URL/site sconosciuto, idempotenza `@register`.
- `tests/test_scrape_downloader.py` — 8 test contro `httpx.MockTransport`: naming, fallback Content-Type/URL/`.bin`, retry su 429 con backoff istantaneo, fail su 404 non-retryable, ordering stabile, dedup, input vuoto.
- `tests/test_scrape_mangadex.py` — match parametrizzati su URL valide e fuori dominio; skeleton solleva NotImplementedError; URL malformata → FetchError.
- `tests/test_smoke.py` — fetch help, exit 1 su URL non supportato, exit 2 su skeleton MangaDex.

**Quality gate (2026-04-29)**: ruff/format/mypy strict clean, **116 test pass** (era 91).

### v0.2a.1 — Code review hardening (2026-04-29)

Code review post v0.2a ha trovato 6 punti, tutti chiusi.

**Media — HTTP 200 con body non-immagine veniva accettato come pagina valida**: un sito che restituisce HTML "you must log in" con status 200 produceva un finto `001.bin` su disco e il fetch risultava success. Run-local poi non trovava immagini valide e l'utente non capiva dove fosse il problema.

Fix: `_validated_extension()` valida l'**ordine giusto** — magic bytes (PNG/JPEG/WebP/GIF/AVIF authoritativi) → Content-Type `image/*` mappato → URL extension solo se Content-Type è `image/*`. Tutto il resto solleva `DownloadError("non immagine, ...")` non-retryable, con snippet del body per debug. Test: rifiuto su HTML 200, su body vuoto con Content-Type image, accettazione di vere PNG/JPG/WebP prodotte da Pillow.

**Media — concurrency ≠ rate limit per host**: il "rate limit" precedente era solo concurrency (max N download in flight). Per MangaDex (che chiede ≤5 req/s) e per il posizionamento pubblico del progetto, serviva un limite reale.

Fix: nuovo parametro `min_delay_per_host` su `download_pages`. Implementazione `_HostRateLimiter` con `asyncio.Lock` per host (richieste a host A non bloccano richieste a host B), `loop.time()` per timestamp dell'ultima richiesta, sleep prima di ogni acquire se la quota non è ancora trascorsa. Default 0 → no-op back-compat. Test: 3 richieste sullo stesso host con `min_delay_per_host=0.05` hanno deltas ≥ 0.04s; 3 host diversi non si bloccano a vicenda.

**Media — output parziale su failure**: `asyncio.gather()` può raise dopo che alcune task hanno già scritto file. Senza un fetch atomico, l'utente trovava `out/` con metà capitolo dentro e nessuna chiara indicazione di errore.

Fix: download in `output_dir/.staging/`, promozione atomica (rename file → `output_dir/`) **solo se ogni pagina ha avuto successo**. Su fallimento, lo staging dir resta per ispezione ma `output_dir` non viene mai polluta. Test: failure su pagina 2 → no file in canonical output, error sollevato.

**Bassa/Media — `msrt fetch` senza guardrail diritti**: `msrt run` avrà `--i-own-rights` ma `fetch` no, asimmetria. Allineato.

Fix: `--i-own-rights` aggiunto a `fetch`. Senza il flag, errore chiaro che ricorda all'utente "guardrail UX, non tutela legale; la responsabilità resta tua". Test: fetch senza flag → exit 1; con flag + URL non supportato → exit 1; con flag + MangaDex skeleton → exit 2.

**Bassa — registry test pollution**: `test_register_decorator_is_idempotent` registrava `Dummy` nel registry globale `_REGISTRY` senza ripristinarlo. Oggi non rompe; potrebbe rendere flaky qualsiasi test futuro che inserisce dummy adapters.

Fix: `tests/conftest.py` con fixture autouse `_isolate_scrape_registry` che snapshota e ripristina `_REGISTRY` per ogni test.

**Bassa — regex MangaDex troppo permissiva**: `_UUID_RE.search(path)` matchava qualsiasi path che contenesse un UUID, inclusi `/follows/<uuid>` o tracking parameters. Inoltre case-sensitive, mentre i link copiati possono avere UUID maiuscolo.

Fix: `_CHAPTER_OR_TITLE_RE` ancorata su `^/(?:chapter|title)/<UUID>(?:/...)?$`, `re.IGNORECASE`. Test: rifiuto di `/follows/<uuid>` e `/random/path/<uuid>`; accettazione di UUID uppercase.

**Quality gate (2026-04-29)**: ruff/format/mypy strict clean, **123 test pass** (era 116, +7 nuovi su validation, rate-limit, atomic, regex tightening, rights flag).

### v0.2a.2 — Magic-bytes only validation (2026-04-29)

Code review post v0.2a.1 ha trovato un buco residuo nella validazione: `_validated_extension("image/png", url, b"<html>...")` ritornava ancora `.png`. Caso d'uso reale: server CDN che serve una pagina di errore/login con header `image/png`. Il file di v0.2a.1 era già rifiutato per HTML con Content-Type `text/html`, ma non quando il server *mente* sull'header. Il bug si era spostato di livello senza sparire.

Fix: `_validated_extension` ora **richiede magic bytes** validi e basta. Content-Type e URL extension sono ignorati (mantenuti nei parametri solo per stabilità API). Se un format esotico senza magic byte signature emerge in futuro (image/svg+xml, image/x-icon), va aggiunto esplicitamente in `_detect_image_magic`.

Eliminate anche le costanti `_CONTENT_TYPE_TO_EXT` / `_KNOWN_IMAGE_EXTS`, ora morte. Il path attraverso il validator è ora una sola riga: `body → magic detection → ext or None`.

**Test di regressione**:
- `test_download_pages_rejects_html_body_with_image_content_type` — header `image/png` + body HTML → `DownloadError("non immagine")`, niente file scritto
- `test_download_pages_rejects_json_body_with_image_content_type` — header `image/jpeg` + JSON envelope di errore → idem

**Quality gate (2026-04-29)**: ruff/format/mypy strict clean, **125 test pass** (era 123, +2 nuovi).

### v0.2 — URL pipeline foundation + MangaDex pubblico

Obiettivo: introdurre `msrt fetch <URL>` e `msrt run <URL>` con una pipeline URL reale, mantenendo MangaDex come adapter pubblico e testabile via fixture anche quando la rete MangaDex sulla macchina utente è bloccata.

- [x] `src/msrt/scrape/base.py`: `ChapterScraper` ABC + modelli/risultati fetch separati dal dominio `Chapter` usato dalla pipeline locale. (v0.2a)
- [x] `src/msrt/scrape/registry.py`: routing URL → adapter (`mangadex`, fallback `generic`, futuro `mangafire`) con errore chiaro se nessun adapter supporta il dominio. (v0.2a)
- [x] `src/msrt/scrape/downloader.py`: async httpx, rate-limit per host, retry con backoff, dedup sha256, cache/resume in `~/.cache/msrt/<host>/<series>/<chapter>/`. (v0.2a — manca `cache/resume` per host, da aggiungere in v0.2b)
- [x] CLI `msrt fetch <URL>`: fetch → cartella locale. (v0.2a)
- [ ] Adapter MangaDex ufficiale: resolver per URL `title`/`chapter`/ID, feed capitoli, At-Home endpoint, gestione `externalUrl` con skip + warning. (v0.2b)
- [ ] CLI `msrt run <URL>`: fetch + `run-local` esistente in un comando. (v0.2c)
- [ ] RunManifest per URL: `input.type=url`, source URL, strategy usata (`mangadex-api`), cache dir, errori fetch. (v0.2b/c)
- [ ] Test fixture JSON MangaDex; niente rete in CI. (v0.2b)

### v0.3 — MangaFire + fallback browser capture automatico

Obiettivo pratico: `msrt run https://mangafire.to/read/...` deve tentare tutto automaticamente e arrivare a una cartella immagini utilizzabile dalla pipeline locale quando il sito lo consente.

Strategia a cascata per ogni URL:
1. Adapter dedicato/download diretto: estrazione URL immagini raw, qualità massima.
2. Generic DOM heuristics: immagini grandi nel reader (`img`, `picture`, lazy `data-src`, sequenze).
3. Browser capture automatico: Playwright apre il reader, identifica la scan visibile e salva screenshot/crop dell'elemento scan, non dell'intera finestra.

Decisioni browser capture:
- [ ] Fallback automatico: l'utente non deve scegliere `--fallback browser`; parte quando direct/generic falliscono o producono pagine incomplete.
- [ ] Pausa manuale consentita: se il browser mostra login, Turnstile/captcha o blocco umano, `msrt` apre/lascia il browser in attesa e chiede all'utente di completare la verifica, poi riprende appena una scan valida è rilevata.
- [ ] Nessun bypass: no stealth, no token forging, no aggiramento di Turnstile/Cloudflare. Se dopo intervento umano la scan non è visibile, fallisce con messaggio chiaro.
- [ ] Cattura scan-only: escludere header/sidebar/sfondi; usare screenshot dell'elemento o crop calcolato dal bounding box della pagina manga.
- [ ] Qualità: preferire immagine raw se disponibile; per screenshot usare viewport alto, `deviceScaleFactor` configurabile e validazione dimensioni minime. Loggare warning se la capture è troppo piccola per OCR affidabile.
- [ ] Navigazione pagine: supportare reader paginato e long-strip; rilevare numero pagine quando esposto dalla UI, altrimenti fermarsi su fine capitolo/duplicato hash.
- [ ] Manifest: registrare `strategy=browser-capture`, viewport, device scale factor, numero pagine catturate, eventuale `manual_intervention=true`.
- [ ] Test: fixture HTML/screenshot sintetici per crop scan-only; E2E manuale su MangaFire chapter Wistoria quando disponibile.

---

## Verifiche

- 2026-04-29: test automatici v0.1 passano (`ruff`, `ruff format --check`, `mypy strict`, `pytest`).
- 2026-04-29: smoke CLI `msrt --help` OK.
- 2026-04-29: smoke `msrt doctor --model sonnet` fallisce correttamente perché mancano prerequisiti runtime reali.
- 2026-04-29: smoke E2E ambiente runtime — `msrt server up` avvia LiteLLM (PID 56054), `curl /health` 200, `msrt server status` rileva up healthy, `msrt server down` lo ferma. PID file gestito correttamente.
- 2026-04-29: **primo E2E reale** — `msrt run-local ~/Desktop/Wistoria/Capitolo_44 --format pdf --series "Wistoria" --chapter "44"` produce `out/wistoria-44-it.pdf` in 2:08 su 3 pagine. 23+ regioni di testo rilevate per pagina, traduzioni IT corrette eccetto artefatti OCR su nomi propri compatti (Emma → IEMMA). Con detector tweaks + system prompt aggiornato la copertura del testo italico migliora sensibilmente.

---

## Problemi & workaround

- ~~MITR non installato~~ → installato via `scripts/install-mitr.sh --git-ref 3abfc47` in `~/tools/mitr/.venv` (Python 3.11).
- ~~LiteLLM non avviato~~ → up via `msrt server up`, healthcheck OK su `gpt|gpt-5|gpt-mini` (Anthropic e Gemini unhealthy perché chiavi non in env, atteso).
- **Scraping URL bloccato sulla macchina utente**: `api.mangadex.org` con SSL intercept (filtro DNS/proxy aziendale o ISP), `mangafire.to` con Cloudflare Turnstile + vrf token. Workaround attuale: input locale (`run-local`) con scan salvate manualmente. Sblocco: v0.2 testabile contro fixture JSON salvata; v0.3 (MangaFire) richiederà soluzione separata per Turnstile.
- **Fallback browser capture deciso**: quando raw download/generic extraction falliscono ma il reader è visibile nel browser, `msrt` potrà catturare automaticamente le scan come immagini locali e proseguire con la pipeline. Se serve verifica umana, il tool mette in pausa e aspetta l'intervento utente, senza bypass.
- **OCR artifacts su nomi compatti**: limite di Model48pxOCR. Mitigazione parziale via system prompt; soluzione completa con two-pass v0.6 + series glossary.

---

## TODO emersi durante l'implementazione

- ~~Cablare `glossary.py` al prompt~~ → chiuso in v0.1.z, automatizzato in v0.1.aa con auto-build.
- ~~Test unit per `SubprocessEngine._command()` con la nuova struttura~~ → chiuso in v0.1.z (`tests/test_engine.py` riscritto).
- Decidere default `GIT_REF` in `install-mitr.sh`: `main` (latest, può rompersi) vs `3abfc47` (stabile, può invecchiare).
- Formalizzare e implementare `browser-capture` come fallback automatico di `msrt run <URL>` dopo v0.2 foundation.
- Documentare in `docs/PROVIDER_NOTES.md` il vincolo `temperature=1` di GPT-5.5 e il workaround via `gpt_config` YAML.
