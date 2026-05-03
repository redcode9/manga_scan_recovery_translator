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
| 2026-04-30 | MangaFire primario = reader-network, browser-capture solo fallback | E2E reale chapter 51: il reader espone gli URL pagina in `/ajax/read/chapter/<id>`; intercettare quella risposta è più stabile e qualitativo dello screenshot |
| 2026-04-30 | Typesetting bubble-aware | Dentro una bubble il testo tradotto deve usare il font massimo che rientra nel poligono/bbox; fuori bubble deve rispettare la dimensione/stile originale per SFX, didascalie e testo ambientale |
| 2026-05-02 | UI desktop/web pianificata come v0.4 | L'utente vuole un'esperienza MacBook autoconfigurante e semplice, ma la UI deve restare un layer sopra backend/pipeline `msrt`, non una riscrittura del motore |

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

**Pin commit MITR**: `3abfc47` (giugno 2025, pre-rust). La `main` ha `import rusty_manga_image_translator` hard-coded che fallisce su macos-arm64 (wheel corrotto). Il commit pre-rust gira pulito. In v0.3f è diventato il `GIT_REF` di default in `scripts/install-mitr.sh`; `--git-ref main` resta opt-in per seguire upstream.

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
- ✅ Pinning `GIT_REF` MITR a `3abfc47`: chiuso in v0.3f.
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

### v0.2b.1 — Code review hardening (2026-04-29)

Code review post v0.2b ha trovato 4 punti, tutti chiusi prima di iniziare v0.2c.

**Alta — fetch cross-chapter pollution**: `download_pages` promuoveva i nuovi file in `output_dir` ma non rimuoveva quelli vecchi. Sequenza tipica: fetch capitolo 50-pagine in `out/fetch/`, poi fetch di un capitolo da 3 pagine nella stessa dir → restavano `004.png ... 050.png` del primo capitolo. Bug strutturalmente identico a quello di v0.1.z su `translated-pages`, ma sul lato fetch.

Fix: nuovo helper `_purge_canonical_pages(output_dir)` invocato **dopo** il successo dello staging e **prima** della rename atomica. Pulisce solo i file matching `^\d{3,}\.(png|jpe?g|webp|gif|avif|bin)$` (case-insensitive); user file (`cover.jpg`) e `msrt-run.json` sopravvivono. Test regressivo: pre-popolo `output_dir` con 5 file canonical + 2 file user, eseguo fetch da 2 pagine, verifico che resti solo `001.png` + `002.png` + i 2 file user.

**Media — `_api_get` non wrappa errori httpx**: `httpx.ConnectError`, `httpx.ReadTimeout`, `httpx.SSLError` sfuggivano alla cattura `except FetchError` del CLI e venivano stampate come traceback grezzo. Esposizione concreta: la rete dell'utente con SSL intercept su `api.mangadex.org` mostrava una traceback mostro invece di un messaggio utile.

Fix: `_api_get` ora cattura `httpx.HTTPError` (base class che copre tutti i sotto-errori di rete httpx) e re-raise come `FetchError("MangaDex API non raggiungibile … Verifica connettività, DNS o eventuali intercept SSL aziendali")`. Test: 2 nuovi (`ConnectError` con simulato cert verify failed, `ReadTimeout`) → entrambi diventano `FetchError`.

**Media/Bassa — feed paging mancante**: `_first_chapter_for_manga` legge solo i primi 100 capitoli del feed. Se un manga ha 200+ capitoli con i primi 100 tutti `externalUrl`, l'errore era generico ("Tutti i capitoli sono externalUrl"). Senza paging completo, l'utente non sapeva se è la lista completa o solo una pagina.

Fix: ora il messaggio di errore include esplicitamente il conteggio (`Il feed ha 250 capitoli ma sto leggendo solo i primi 100; passa un URL /chapter/<UUID> specifico per saltare la selezione automatica`). Paging completo del feed è rimandato (richiede selezione capitolo, fuori scope v0.2). Test: fixture con `total: 250` e tutti `externalUrl` → errore con hint chapter-URL.

**Bassa/docs — README obsoleto**: il header diceva "v0.1.x in sviluppo" e descriveva v0.2 come futuro. Aggiornato a "v0.2.b" + lista capabilities reali (run-local validato 50 pagine, auto-glossary, fetch MangaDex, glossary subapp).

**Quality gate (2026-04-29)**: ruff/format/mypy strict clean, **137 test pass** (era 133, +4 nuovi su purge canonical / httpx wrapping / feed truncated hint / regression download promote-cleanup).

### v0.2c — `msrt run <URL>` orchestratore (2026-04-29)

Comando `msrt run <URL>` introdotto come pura orchestrazione di `fetch` + `run-local`. Nessuna nuova logica di scraping: l'adapter resolution e il download passano per `scraper_for_url(url, site=…)` + `scraper.fetch(...)` esattamente come `msrt fetch`, poi i metadata di `FetchResult` (series, chapter_number, chapter_title) alimentano direttamente `run_local`.

**Fetch staging** (per evitare cartelle "fragili" se il run è interrotto):
1. Fetch in `out/.msrt-fetch/<site>/_pending-<8 hex>` (nome univoco per concorrenza).
2. Quando `FetchResult` ritorna con metadata, `shutil.move` verso `out/.msrt-fetch/<site>/<series-slug>/<chapter-slug>/`. Se la dir finale esiste già (re-run), viene rimossa prima.
3. `run_local` riceve la dir finale come input, niente è in `out/` direttamente.
4. Se `fetch` fallisce con `FetchError` o `NotImplementedError`, lo staging dir viene cancellato e MITR **non parte**.
5. Se `run_local` fallisce, la dir di fetch resta su disco con messaggio chiaro: l'utente può ri-tentare la traduzione senza riscaricare.

**Manifest URL pipeline** (`src/msrt/models.py`):
- Nuovo `ManifestFetch` (strategy, source_url, output_dir, page_count, warnings).
- `RunManifest.fetch: ManifestFetch | None` (popolato solo da `msrt run`, `None` da `msrt run-local`).
- `build_manifest` e `run_local` accettano nuovi keyword opzionali `input_type`, `input_url`, `fetch_metadata`. Default `"local"`/None per backwards-compat con `run-local`.
- `pipeline._slugify` esposto come `slugify` per consentire al CLI di costruire il path canonico senza duplicare la logica.

**CLI** (`src/msrt/cli.py`):
- `@app.command() def run(url, *, out, format=pdf, model, font_path, glossary, auto_glossary, pre_dict, lang_source, lang_target, no_gpu, site, i_own_rights)`.
- Default `--format pdf` (UX finale: utente vuole leggere subito).
- `--i-own-rights` obbligatorio (stesso guardrail di `fetch`); senza, exit 1 con messaggio diretto.
- Errori discriminati per chiarezza utente: `FetchError → exit 1`, `NotImplementedError → exit 2`, errore traduzione → exit 1 + path fetch dir.

**Test** (`tests/test_cli_run.py`, 7 nuovi):
- `test_run_url_without_rights_flag_exits_one` — guardrail.
- `test_run_unsupported_url_exits_one` — registry rifiuta URL ignoto, MITR non parte.
- `test_run_orchestrates_fetch_then_local_pipeline` — fake scraper + run_local stub: verifica che `image_dir` sia `out/.msrt-fetch/fakemd/fake-series/42/`, che metadata e `fetch_metadata` siano propagati a `run_local`, niente staging dir residua.
- `test_run_aborts_when_fetch_fails` — `FetchError` interrompe prima di `run_local`.
- `test_run_keeps_fetch_dir_when_translation_fails` — fetch ok + `run_local` raise → exit 1 ma fetch dir intatta per ri-tentare.
- `test_run_cleans_pending_dir_when_fetch_raises_not_implemented` — staging dir viene cancellata su exit 2.
- `test_run_help_lists_url_orchestration_flags` — smoke help.

I test usano un `_FakeMangaDexLikeScraper` registrato via `monkeypatch.setattr("msrt.cli.scraper_for_url", …)` e `monkeypatch.setattr("msrt.cli.run_local", stub)` per controllare il flow senza toccare rete o MITR.

**Quality gate (2026-04-29)**: ruff/format/mypy strict clean, **144 test pass** (era 137, +7 nuovi).

### v0.3a/v0.3b/v0.3c — MangaFire browser-capture foundation (2026-04-29)

Implementato il primo blocco v0.3: non ancora validato E2E live su MangaFire reale, ma integrato nel
codice con test offline e nessuna chiamata rete in CI.

**v0.3a hardening**:
- `msrt run` ora cattura anche eccezioni inattese durante il fetch stage, ripulisce `_pending-*` e
  mostra `Errore fetch inatteso` invece di lasciare traceback grezzo. Questo è importante per adapter
  browser-backed, dove Playwright può sollevare errori non incapsulati.
- README aggiornato da v0.2.b a v0.3-dev e documenta `msrt run <URL>` come capability reale.

**v0.3b browser capture core** (`src/msrt/scrape/browser_capture.py`):
- Nuovo `BrowserCaptureEngine` con import lazy di Playwright: MangaDex/local non richiedono Playwright
  a import time.
- Nessun bypass: user-agent dichiarato, nessun plugin stealth, nessun token forging/captcha solving.
  Se il testo pagina contiene segnali di login/captcha/Turnstile/Cloudflare, il browser resta aperto
  e il tool aspetta che l'utente completi manualmente; se una scan non diventa visibile entro timeout,
  `FetchError` chiaro.
- Candidate scan detector su `img, canvas`: filtra per dimensione minima/aspect ratio, preferisce la
  pagina manga più grande, ignora asset piccoli/sidebar.
- Capture path: tenta raw download via browser context (`page.request`, quindi con cookie/sessione del
  browser) e fallback a screenshot dell'elemento scan. I byte vengono validati con la stessa allowlist
  magic-bytes del downloader.
- Navigazione paginata iniziale: prova click su controlli "next" e fallback `ArrowRight`; stop su
  duplicato hash, page count `Page N/M`, o impossibilità di avanzare.

**v0.3c MangaFire adapter** (`src/msrt/scrape/adapters/mangafire.py`):
- `MangaFireScraper.matches()` riconosce `mangafire.to/read/<slug>/<lang>/chapter-<N>` e varianti
  senza chapter esplicito.
- `fetch()` delega a `BrowserCaptureEngine`, converte le pagine catturate in `FetchedPage`, estrae
  metadata base da URL (`series`, `chapter_number`) e ritorna `FetchResult(strategy="mangafire-browser-capture")`.
- `FetchResult` e `ManifestFetch` ora hanno campi opzionali per metadata browser capture:
  `capture_mode`, `viewport`, `device_scale_factor`, `manual_intervention`.

**Test offline aggiunti**:
- `tests/test_browser_capture.py`: parsing `Page 1/45`, challenge detection, candidate selection,
  scrittura bytes con magic-byte validation.
- `tests/test_scrape_mangafire.py`: matching URL, registry routing, fetch con capture engine finto,
  propagazione warnings/manual intervention/viewport, errore capture.
- `tests/test_cli_run.py`: regression per cleanup `_pending-*` quando il fetch stage solleva
  eccezioni inattese.

**Da validare manualmente**:
- E2E su `https://mangafire.to/read/wistoria-wand-and-swordd.02n57/en/chapter-44`.
- Se il DOM corrente richiede selettori/navigazione specifici, patch mirata su `BrowserCaptureEngine`
  o su `MangaFireScraper` senza cambiare la pipeline `run-local`.

### v0.3d — MangaFire reader-network + E2E reale chapter 51 (2026-04-30)

Il primo tentativo live con browser-capture puro su
`https://mangafire.to/read/wistoria-wand-and-swordd.02n57/en/chapter-51` ha
fallito: il reader caricava per un attimo e poi navigava alla home, lasciando
`Nessun elemento scan valido trovato nel reader`. La diagnostica di rete ha
mostrato che il sito emette comunque due XHR utili prima del redirect:

1. `/ajax/read/<hid>/chapter/<lang>?vrf=...` → lista capitoli e `data-id`
   del capitolo selezionato.
2. `/ajax/read/chapter/<chapter_id>?vrf=...` → payload JSON con
   `result.images`, cioè la lista ordinata degli URL pagina.

Decisione implementativa:
- `MangaFireScraper` prova prima `MangaFireReaderResolver`: apre il reader con
  Playwright, non ricostruisce né forza token `vrf`, ma aspetta la risposta
  pubblica emessa dal sito stesso e legge `result.images`.
- Gli URL vengono scaricati dal downloader condiviso con `Referer`, user-agent
  dichiarato, magic-byte validation e `min_delay_per_host=0.2`.
- Se `reader-network` fallisce, resta il fallback automatico
  `BrowserCaptureEngine` già implementato.
- Fix race: leggere `response.text()` dentro l'handler `response` appena arriva,
  perché dopo la navigazione alla home Playwright può perdere il body e sollevare
  `Protocol error (Network.getResponseBody): No resource with given identifier found`.

Verifica reale:
- `msrt fetch ...chapter-51 --site mangafire --out out/e2e-mangafire-51-fetch`
  → 45 JPEG scaricati, 0 duplicati SHA, dimensioni plausibili (`001.jpg`
  960x1378, `045.jpg` 1920x1378).
- `msrt run ...chapter-51 --site mangafire --out out/e2e-mangafire-51-run
  --format pdf --model gpt --i-own-rights --no-gpu`
  → completato in 22:19, output
  `out/e2e-mangafire-51-run/wistoria-wand-and-swordd-51-it.pdf` (42 MB).
- Manifest: `input.type=url`, `page_count=45`,
  `fetch.strategy=mangafire-reader-network`, `capture_mode=browser-network`,
  `manual_intervention=false`, `errors=[]`.

Quality observation:
- La pagina 001 tradotta conferma un problema qualitativo già visto nel
  capitolo 50: alcune bubble usano un font troppo piccolo rispetto allo spazio
  disponibile. Nuovo requisito per il postprocess custom: bubble text =
  massimo font che rientra nel poligono/bbox; non-bubble text = preserva scala
  originale.

### v0.3e — MangaFire all-chapters + bubble-aware bridge (2026-05-02)

Decisione prodotto: l'utente vuole passare un URL di un manga e ottenere tutti
i PDF dei capitoli disponibili, non lanciare manualmente un comando per ogni
capitolo. Per MangaFire la struttura URL è stabile (`/read/<slug>/<lang>/chapter-N`)
e il reader espone già l'indice capitoli nella risposta `/ajax/read/<hid>/chapter/<lang>`.

Implementazione:
- `ChapterScraper.list_chapters(url)` diventa parte del contratto opzionale
  degli adapter; default = `FetchError("non supporta --all-chapters")`.
- `MangaFireScraper.list_chapters()` usa `MangaFireReaderResolver` per osservare
  la normale risposta reader con la lista capitoli, estrae link da HTML,
  supporta attributi con doppi apici/singoli apici e ricava `chapter_number`
  anche dall'href se `data-number` manca.
- `msrt run <URL> --all-chapters --i-own-rights` esegue batch sequenziale:
  lista capitoli → per ogni capitolo `_run_url_once()` → fetch cache in
  `out/.msrt-fetch/<site>/<series>/<chapter>/` → `run_local` → PDF/CBZ.
- `--skip-existing` è attivo di default: se il PDF/CBZ atteso è già presente,
  il capitolo viene saltato. `--continue-on-error` è attivo di default per
  evitare che un singolo capitolo rotto fermi un batch lungo.
- Manifest e cache restano per-capitolo; non c'è ancora un manifest batch
  aggregato. Per ora il riepilogo CLI elenca completati/saltati/falliti.

Postprocess bubble-aware:
- Aggiunto `src/msrt/translate/postprocess.py` come bridge image-level prima
  del postprocess strutturato v0.6: rileva componenti bianche chiuse che
  sembrano bubble, trova il testo scuro interno, lo scala fino a occupare più
  spazio disponibile e lascia invariato il testo fuori bubble.
- `--renderer custom-postprocess` è ora il default dei comandi CLI orientati
  all'utente (`translate`, `run-local`, `run`). Per debug o confronto si può
  usare `--renderer mitr-manga2eng` per ottenere l'output puro MITR.
- Limite noto: essendo image-level, non conosce polygon/mask/testo originale.
  Funziona come miglioramento pragmatico sulle bubble bianche standard; la
  preservazione piena font/colore/rotazione resta il target v0.6 con JSON MITR
  o two-pass.

Quality gate:
- `uv run ruff check .` OK
- `uv run ruff format --check .` OK
- `uv run mypy src/msrt` OK (`28 source files`)
- `uv run pytest -q` OK (`165 passed`)

### v0.3f — Batch safety: chapter selectors + postprocess hardening (2026-05-02)

Pre-requisito v0.4: la UI futura dovrà costruire batch controllati ("primi 2", "range 50-51", "solo 51.1") senza inventarsi logica sua. Tre selettori ora vivono nella CLI come primitive testabili e isolate dal resto del flusso.

**Nuovi flag su `msrt run --all-chapters`** (pure orchestrazione, niente cambi di scraping):
- `--range "50-51"` — range numerico inclusivo. Capitoli non-numerici (`extra`, `omake`) vengono saltati dal filtro range.
- `--chapters "50,51,51.1"` — lista esplicita per match esatto su `chapter_number`. Unico modo di prendere decimali singoli senza sweepare i vicini.
- `--limit N` — primi N **dopo** range/chapters. Combinabile.

Tutti e tre richiedono `--all-chapters` esplicito; senza, exit 1 con messaggio "richiedono --all-chapters" così l'utente non pensa di aver fatto qualcosa che non ha fatto. Compatibili con `--dry-run`: il listing mostra solo i capitoli filtrati e include `selezionati N di M` per visibilità immediata.

**Nuovo modulo** `src/msrt/scrape/selection.py` — funzioni pure `parse_chapter_range`, `parse_chapter_list`, `select_chapters`. Niente I/O, niente asyncio: testabili senza CLI in mezzo. Errori parser tradotti in `ValueError` con messaggi user-readable; il CLI li intercetta e diventa exit 1 prima del fetch.

**Postprocess bubble-aware — guard anti-falsi-positivi** (`src/msrt/translate/postprocess.py`):
- Aspect-ratio guard: bubble plausibili hanno `0.30 ≤ width/height ≤ 3.50`. Strisce orizzontali (banner, bordi che hanno superato l'edge check) e gutter verticali sono ora rifiutati.
- Fill-ratio guard: `area / (bbox_w * bbox_h) ≥ 0.55`. Forme complesse white tipo SFX-starburst, cluster sparso di pixel uniti da spilloni, hanno fill-ratio basso e sarebbero un cattivo target per blind-scaling.
- Calcolo del fill-ratio in spazio downscaled (consistente con `area`), così il valore non dipende dal `downscale=4` interno.

**Pin MITR `GIT_REF` di default a `3abfc47`** (`scripts/install-mitr.sh`):
- Fino a ieri il default era `main`. Su macOS arm64 le commit recenti tirano dentro `rusty_manga_image_translator` (wheel rotto) e `main` ha un import hard di quel modulo.
- Il commit `3abfc47` (giugno 2025, pre-rust) è quello che ha fatto girare l'E2E reale di Wistoria. Pinnarlo come default rende il primo `setup.sh` riproducibile.
- `--git-ref main` resta disponibile come opt-in upstream-tracking quando MITR avrà sistemato il problema rust.

**Test (35 nuovi, totale 201 pass)**:
- `tests/test_scrape_selection.py` — 14 test sui selectors puri: parse range (decimali, whitespace, malformed×7), parse list (basic, whitespace, empty), select_chapters (range filter, non-numeric skip, chapter_list, limit, ordine, combinazioni, error su limit<1, preservazione metadata).
- `tests/test_cli_run_selectors.py` — 9 test CLI: rifiuto guardrail dei tre flag senza `--all-chapters`, rifiuto malformed range, dry-run filter (range, list, limit, range+limit), errore quando i selettori scartano tutto.
- `tests/test_postprocess.py` — 3 nuovi: skip thin horizontal strip (aspect-ratio guard), skip low-fill starburst (fill-ratio guard), no-op on dark page (no white components).

**Quality gate (2026-05-02)**: ruff / format / mypy strict clean, **201 test pass** (era 166).

### v0.4a — Backend UI foundation (2026-05-02)

Primo step del piano UI desktop. Backend FastAPI locale che riusa la pipeline esistente: niente reimplementazione di scraping/translate/package nel server, niente subprocess CLI parsing. Scope ridotto al **backend headless** — Tauri + frontend React arrivano in v0.4b/c.

**Modulo nuovo `src/msrt/ui_server/`** (8 file, ~1800 righe):
- `schemas.py` — Pydantic models per Job, Event, DryRun, Library, Doctor, Settings, ServerAction. ``SettingsView`` espone `has_*_key` booleani, **mai** i valori delle chiavi.
- `events.py` — `EventBroker` per-job con `asyncio.Queue` per subscriber, fan-out senza blocco (drop oldest se piena), close-sentinel cross-thread sicuro.
- `jobs.py` — `JobManager` single-worker FIFO. Persistenza JSON in `~/.cache/msrt/ui/jobs/<id>.json`. Re-loading al boot con auto-fail dei job marcati "running" (worker precedente morto). Strong-ref a fire-and-forget tasks per evitare GC.
- `commands.py` — bridge: `run_local`/`run` chiamati come funzioni Python, `on_phase`/`on_log` callbacks convertiti in Event SSE. Funzioni sync (run_local) wrappate in `asyncio.to_thread` con `run_coroutine_threadsafe` per emit cross-thread.
- `library.py` — scansione `out/*/msrt-run.json`, mapping deterministic `manifest_id` (sha1 path), filtra subdir nascoste (`.msrt-fetch`, `.msrt-tmp`).
- `settings_api.py` — `SettingsView` builder.
- `doctor_api.py` — `build_doctor_report` wraps `run_doctor` con `overall_status` aggregato.
- `app.py` — `create_app()` factory con tutti gli endpoint, lifespan async start/shutdown, dependency injection del `job_runner` per testing.

**Endpoint API** (tutti binding 127.0.0.1):
- `GET /api/health` — version + boot time
- `GET /api/settings` — public-safe (zero key leak verificato in test)
- `GET /api/doctor` — `DoctorReport` strutturato
- `GET /api/server`, `POST /api/server/{up,down}` — lifecycle LiteLLM
- `POST /api/chapters/dry-run` — adapter `list_chapters` + selectors v0.3f
- `POST /api/jobs`, `GET /api/jobs`, `GET /api/jobs/{id}`, `POST /api/jobs/{id}/cancel`
- `GET /api/jobs/{id}/events` — SSE stream via `sse-starlette`
- `GET /api/library`, `GET /api/library/{manifest_id}`
- `POST /api/open-path` — opener nativo (`open` su macOS, `xdg-open` su Linux)

**CLI**: nuovo comando `msrt ui [--host 127.0.0.1] [--port 4001] [--reload]`. Avvia uvicorn contro `msrt.ui_server:create_app` con factory mode. Default 127.0.0.1 — esposizione LAN richiede override esplicito di `--host`.

**Dipendenze**: nuovo extra `[ui]` in `pyproject.toml` con `fastapi>=0.110`, `uvicorn[standard]>=0.30`, `sse-starlette>=2.1`. Già presente in `uv sync --all-extras`.

**Test (15 nuovi, 218 totali)** — `tests/test_ui_server.py`:
- `health` — version + boot time
- `settings` — sentinel API key non appare nel JSON, `has_*_key` booleani consistenti
- `doctor` — checklist non vuota, `overall_status ∈ {ok,warn,fail}`, ogni check ha {name,status,message}
- `library` — manifest popolato → entry corretta con series/chapter/strategy/model_alias
- `dry_run` — fake adapter + selector range, payload con total/selected/site corretti
- `dry_run` — range malformed → 400
- `jobs` — validation rifiuta `url` senza `i_own_rights`, `local` con `input_url`
- `jobs` — lifecycle `succeeded` (poll fino a terminale, output_files popolati)
- `jobs` — lifecycle `failed` (errors popolati con messaggio)
- `jobs` — listing ordinato most-recent-first
- `jobs` — cancel su queued → status `cancelled` (con un job long-running che blocca il worker)
- `jobs` — cancel su id sconosciuto → 409
- `events` — broker fan-out + close sentinel
- `events` — late-subscriber dopo close non resta appeso

**Dipendenze runtime confermate**: `fastapi 0.124.4`, `uvicorn 0.33.0`, `sse-starlette 3.4.1`.

**Quality gate (2026-05-02)**: ruff/format/mypy strict clean (38 source files), **218 test pass** (era 203, +15).

**Note di design — cosa è dentro v0.4a e cosa NO**:
- ✅ JobManager single-worker, persistenza JSON, cancel cooperativo.
- ✅ SSE stream con fan-out e timeout-safe.
- ✅ Bridge pipeline → eventi senza shellare la CLI.
- ❌ Nessun frontend (v0.4b).
- ❌ Nessun Tauri wrapper (v0.4c).
- ❌ Nessuna persistenza SQLite (JSON è OK per single-worker; SQLite arriverà se il volume di job lo richiede).
- ❌ Nessun retry endpoint (esposto in v0.4e con la failed-chapters retry).
- ❌ Nessun Keychain integration (v0.4d).

### v0.2 — URL pipeline foundation + MangaDex pubblico

Obiettivo: introdurre `msrt fetch <URL>` e `msrt run <URL>` con una pipeline URL reale, mantenendo MangaDex come adapter pubblico e testabile via fixture anche quando la rete MangaDex sulla macchina utente è bloccata.

- [x] `src/msrt/scrape/base.py`: `ChapterScraper` ABC + modelli/risultati fetch separati dal dominio `Chapter` usato dalla pipeline locale. (v0.2a)
- [x] `src/msrt/scrape/registry.py`: routing URL → adapter (`mangadex`, fallback `generic`, futuro `mangafire`) con errore chiaro se nessun adapter supporta il dominio. (v0.2a)
- [x] `src/msrt/scrape/downloader.py`: async httpx, rate-limit per host, retry con backoff, dedup sha256, cache/resume in `~/.cache/msrt/<host>/<series>/<chapter>/`. (v0.2a — manca `cache/resume` per host, da aggiungere in v0.2b)
- [x] CLI `msrt fetch <URL>`: fetch → cartella locale. (v0.2a)
- [x] Adapter MangaDex ufficiale: resolver per URL `title`/`chapter`/ID, feed capitoli, At-Home endpoint, gestione `externalUrl` con skip + warning. (v0.2b)
- [x] CLI `msrt run <URL>`: fetch + `run-local` esistente in un comando. (v0.2c)
- [x] RunManifest per URL: `input.type=url`, source URL, strategy usata (`mangadex-api`), cache dir, errori fetch. (v0.2c)
- [x] Test fixture JSON MangaDex; niente rete in CI. (v0.2b)

### v0.2b — MangaDex API completo (2026-04-29)

`MangaDexScraper.fetch()` ora orchestra l'API MangaDex end-to-end. Tutto è esercitato contro fixture JSON via `httpx.MockTransport` — zero rete in CI.

**Flusso implementato**:
1. Parse URL: `^/chapter/<UUID>$` o `^/title/<UUID>(/...)?$` (case-insensitive). Niente match su path che contiene UUID per caso (chiuso in v0.2a.1).
2. Per `/title/<UUID>`: `GET /manga/{id}/feed?translatedLanguage[]=en&order[chapter]=asc&limit=100` → primo entry senza `externalUrl`. Se il feed in inglese è vuoto, retry senza filtro lingua per non fallire su release prima dell'inglese.
3. `GET /chapter/{id}` → `attributes.chapter`, `attributes.title`, `attributes.translatedLanguage`, relazione `manga`. Se `externalUrl` ≠ null → `FetchError("esterno")` chiaro: MangaDex non ospita le immagini.
4. `GET /manga/{manga_id}` → titolo serie. Preferisce `attributes.title.en`; fallback alla prima lingua disponibile (alfabetico per determinismo). Default `"Untitled Series"` se nessun titolo è popolato.
5. `GET /at-home/server/{chapter_id}` → `baseUrl`, `chapter.hash`, `chapter.data` (lista filename ordinata). URL pagina = `{baseUrl}/data/{hash}/{filename}` (full quality, non `dataSaver`).
6. `download_pages(jobs, min_delay_per_host=0.2)` per rispettare la guideline pubblica MangaDex (≤5 req/s). Magic-byte validator già attivo dal v0.2a.2 protegge da soft-fail page con header `image/*`.
7. `find_duplicate_pages` aggiunto a `warnings`; lingua diversa da `en` aggiunge un warning informativo (no errore).
8. Ritorna `FetchResult(strategy="mangadex-api", series, chapter_number, chapter_title, source_url, pages, warnings, output_dir)`.

**Test injection design**: `MangaDexScraper(transport=…)` accetta un transport opzionale che viene usato sia per le chiamate API sia (passato through) a `download_pages`. La signature `fetch(url, output_dir)` resta invariata rispetto alla ABC, niente kwargs di test che leakano in produzione.

**Fixture JSON** (`tests/fixtures/mangadex/`):
- `chapter_normal.json` — chapter 44 di "Wistoria", inglese, no externalUrl, 3 pagine atteso
- `chapter_external.json` — stessa serie ma con `externalUrl` valorizzato
- `manga_wistoria.json` — manga entity con `title.en` + `title.ja`
- `manga_feed.json` — feed con 2 capitoli inglesi
- `manga_feed_empty.json` — feed vuoto, per testare il fallback senza filtro lingua
- `at_home.json` — At-Home response con baseUrl + hash + 3 filename

**10 nuovi test** (`tests/test_scrape_mangadex_fetch.py`):
- `test_fetch_chapter_url_returns_full_result` — fetch completo end-to-end, verifica nomi file `001.png/002.png/003.png`, URL costruiti correttamente con base+hash+filename, warnings vuoti
- `test_fetch_title_url_resolves_first_chapter` — title URL → feed → primo capitolo
- `test_fetch_title_url_falls_back_when_english_feed_empty` — fallback senza filtro lingua quando feed `en` vuoto
- `test_fetch_title_url_raises_when_no_chapters` — entrambi i feed vuoti → FetchError chiaro
- `test_fetch_external_url_chapter_raises_with_clear_message` — externalUrl → FetchError con hint
- `test_fetch_raises_when_at_home_has_no_pages` — At-Home senza filename → FetchError
- `test_fetch_raises_on_api_error_envelope` — `result != "ok"` → FetchError
- `test_fetch_warns_on_non_english_chapter` — capitolo `es` produce warning ma non fallisce
- `test_fetch_propagates_download_failure_as_fetch_error` — DownloadError → FetchError per uniformità del contratto
- `test_pick_series_title_falls_back_to_japanese_when_english_missing` — title.en mancante → primo non-vuoto

Aggiornato `test_scrape_mangadex.py`: rimosso il vecchio test "skeleton raises NotImplementedError" (obsoleto). Rimosso `test_cli_fetch_mangadex_skeleton_exits_two` da `test_smoke.py` per la stessa ragione (ora la fetch è reale e farebbe network reale dal CLI smoke test).

**Quality gate (2026-04-29)**: ruff/format/mypy strict clean, **133 test pass** (era 125, +8 nuovi netti — 10 added, 2 removed obsoleti).

### v0.3 — MangaFire + fallback browser capture automatico

Obiettivo pratico: `msrt run https://mangafire.to/read/...` deve tentare tutto automaticamente e arrivare a una cartella immagini utilizzabile dalla pipeline locale quando il sito lo consente.

Strategia a cascata per ogni URL:
1. Adapter dedicato/download diretto: estrazione URL immagini raw, qualità massima.
2. Generic DOM heuristics: immagini grandi nel reader (`img`, `picture`, lazy `data-src`, sequenze).
3. Browser capture automatico: Playwright apre il reader, identifica la scan visibile e salva screenshot/crop dell'elemento scan, non dell'intera finestra.

Decisioni browser capture:
- [x] Fallback automatico: l'utente non deve scegliere `--fallback browser`; `MangaFireScraper` usa browser capture come strategia interna.
- [x] Pausa manuale consentita: se il browser mostra login, Turnstile/captcha o blocco umano, `msrt` apre/lascia il browser in attesa e chiede all'utente di completare la verifica, poi riprende appena una scan valida è rilevata.
- [x] Nessun bypass: no stealth, no token forging, no aggiramento di Turnstile/Cloudflare. Se dopo intervento umano la scan non è visibile, fallisce con messaggio chiaro.
- [x] Cattura scan-only: escludere header/sidebar/sfondi scegliendo `img/canvas` manga più grande; usare raw browser-context quando disponibile, altrimenti screenshot dell'elemento.
- [x] Qualità: viewport alto, `deviceScaleFactor` configurabile e validazione dimensioni minime. Warning low-res fine-grained da raffinare dopo E2E reale.
- [x] Navigazione pagine: reader paginato iniziale con next controls/ArrowRight; stop su page count o duplicato hash. Long-strip rimandato a patch successiva se emerge dal sito reale.
- [x] Manifest: registrare strategy, viewport, device scale factor, numero pagine catturate, eventuale `manual_intervention=true`.
- [x] Test: test offline su candidate selection/capture metadata; E2E manuale su MangaFire chapter 51 eseguito e riuscito.

### v0.4 — Desktop/Web UI autoconfigurante

Documento di riferimento: [`docs/DESKTOP_UI_PLAN.md`](DESKTOP_UI_PLAN.md).

Obiettivo: rendere `msrt` usabile su MacBook senza terminale. L'utente apre una
app, completa setup guidato, incolla un URL o sceglie una cartella, vede dry-run
e capitoli disponibili, lancia traduzione/batch e segue progress/log/output.

Decisione stack:
- Tauri + Vite + React/TypeScript per la UI desktop/web.
- Backend locale Python (`src/msrt/ui_server/`) sopra le funzioni esistenti.
- Eventi progress via SSE/WebSocket generati dalla pipeline, non parsing del
  rendering Rich della CLI.
- API key mai nel frontend; preferenza macOS Keychain, fallback `.env`.

Roadmap v0.4:
- [x] v0.4a backend UI foundation: FastAPI locale, job queue, eventi, doctor/server/dry-run, library manifest. (2026-05-02)
- [x] v0.4b web UI MVP: scaffolding Vite/React/TS/Tailwind + Dashboard + Library + Settings live, NewJob + BatchPlanner + JobProgress + Logs cablati su SSE/dry-run/jobs. (2026-05-02)
- [x] v0.4c single-command UX: backend serve la SPA buildata + auto-open browser; scaffold Tauri pronto per packaging futuro. (2026-05-02)
- [x] v0.4d setup wizard UI: endpoint backend per save/delete/test/default-model + portachiavi macOS via `keyring` con fallback `.env`, pagina React `SetupWizard` con 3 provider e default model. (2026-05-02)
- [x] v0.4e polish (parziale): retry-failed chapters endpoint + UI, diagnostics bundle redatto + download UI. Dark/light mode + batch resume from manifest rimandati a futuro post-MVP. (2026-05-02)

### v0.4b (parziale) — Web UI scaffolding + Dashboard/Library/Settings (2026-05-02)

Primo iteration step della UI desktop. Frontend isolato in `apps/desktop/`, parla col backend FastAPI di v0.4a tramite proxy Vite (`/api/*` → 127.0.0.1:4001) — niente CORS, niente accoppiamento col tooling Python.

**Stack confermato**:
- React 18 + TypeScript 5 strict
- Vite 5 con `@tailwindcss/vite` (Tailwind v4 senza PostCSS config)
- TanStack Query v5 per cache API
- `react-router-dom` v6 per routing
- `lucide-react` per icone
- `EventSource` nativo dietro hook `useJobEvents`
- npm (non pnpm), come da scelta utente

**Layout**:
```
apps/desktop/
├── package.json, vite.config.ts, tsconfig.json (strict)
├── index.html, .gitignore, README.md
└── src/
    ├── main.tsx                 # QueryClientProvider + RouterProvider
    ├── index.css                # @import "tailwindcss"
    ├── app/routes.tsx           # createBrowserRouter
    ├── components/
    │   ├── AppShell.tsx         # sidebar + header con StatusPill live
    │   └── StatusPill.tsx       # primitiva di stato (5 toni)
    ├── lib/
    │   ├── api.ts               # client tipizzato per ogni endpoint v0.4a
    │   ├── events.ts            # useJobEvents(jobId) → {events, latest, closed}
    │   └── format.ts            # formatTimestamp / formatDuration / pathBasename
    └── pages/
        ├── Dashboard.tsx        # doctor + LiteLLM + quick actions
        ├── Library.tsx          # GET /api/library + open-path
        ├── Settings.tsx         # read-only, mai key values, solo has_*_key
        └── StubPage.tsx         # placeholder con milestone target
```

**Endpoint coperti**:
- `Dashboard` → `/api/health`, `/api/doctor`, `/api/server` (refetch 5s), `/api/settings`. Mutations `serverUp/serverDown` invalidano lo status.
- `Library` → `/api/library` con `out` configurabile. Click "apri" su PDF chiama `/api/open-path` → opener nativo.
- `Settings` → `/api/settings` read-only. **Verifica esplicita**: `KeyPill` mostra solo `presente`/`assente`, mai il valore.

**Pagine stub** (`StubPage` con milestone target): `Nuovo Job` (v0.4b prossimo step), `Batch` (v0.4b prossimo step), `Log` (v0.4e). La voce di menu c'è già, così la nav è completa, ma il contenuto chiarisce che non è ancora cablato.

**Quick start (dev)**:
```bash
# Terminale 1
uv run msrt ui

# Terminale 2
cd apps/desktop && npm install && npm run dev
# Apri http://127.0.0.1:5173
```

**Production-like flow finale** (v0.4c): Tauri shell avvia il backend in background; l'utente vede solo l'app desktop. Per ora dev = due processi.

**Quality gate frontend**:
- `npm run typecheck` (`tsc -b --noEmit`) clean
- `npm run build` clean — `dist/index.html 0.47 kB`, JS 277.85 kB / 87.32 kB gzip, CSS 16.92 kB / 4.20 kB gzip
- Backend: 222 test pass invariati

**Cosa NON è ancora in v0.4b**:
- Form `Nuovo Job` (POST `/api/jobs` con campi locale/url, options, i_own_rights)
- `Batch Planner` con `/api/chapters/dry-run` interattivo + selettori range/chapters/limit
- `JobProgress` live tramite `useJobEvents` (SSE)
- `SetupWizard` guidato (passa a v0.4d con Keychain integration)
- `Logs` page (v0.4e)

Questi entrano nel prossimo iteration step di v0.4b.

### v0.4b — Web UI MVP completa (2026-05-02)

Chiusi gli stub di `Nuovo Job`, `Batch Planner`, `JobProgress` e `Logs` cablandoli sugli endpoint v0.4a:

- `NewJob.tsx`: form con switch `local | url | url_batch`, opzioni avanzate collassabili, guardrail `--i-own-rights` per le rotte URL, `POST /api/jobs` → redirect a `/jobs/:id`.
- `JobProgress.tsx`: live log via `useJobEvents` (SSE), progress bar fasi, lista output con `openPath` per aprire da Finder, mutation di cancel.
- `BatchPlanner.tsx`: dry-run con `range`/`chapters`/`limit`, tabella capitoli con stato `output_exists`, lancio batch dietro `--i-own-rights`.
- `Logs.tsx`: lista job e tail SSE per quello selezionato.

### v0.4c — Single-command UX (2026-05-02)

Obiettivo dichiarato dall'utente: "non deve servire avviare due processi". Soluzione doppia:

1. **Backend serve la SPA buildata**. `app.py` espone `/assets/*` come `StaticFiles` e usa un fallback catch-all che restituisce `index.html` per qualsiasi path non `api/`. La directory di dist viene risolta tramite `MSRT_UI_DIST` (override) o `apps/desktop/dist` (default). Risultato: `msrt ui` da solo serve sia API che frontend a `127.0.0.1:4001`.
2. **`msrt ui` auto-builda + apre il browser**. La CLI ha nuovi flag `--build/--no-build` (default `True`) e `--open/--no-open` (default `True`). Quando il bundle React non esiste o è obsoleto, lancia `npm install` + `npm run build` con stderr passato a video; se manca `npm` o la cartella `apps/desktop`, degrada gracefully e parte il backend in modalità solo-API.
3. **Tauri shell scaffolato per il futuro**. `apps/desktop/src-tauri/` contiene `Cargo.toml` (Tauri 2 + serde), `tauri.conf.json` con `frontendDist: "../dist"` e `devUrl: http://127.0.0.1:5173`, `src/main.rs` con un comando `backend_info` di esempio. La build richiede toolchain Rust che oggi non è disponibile sulla macchina utente; il packaging `.dmg` resta uno step desktop successivo.

Quality gate post-v0.4c: ruff/format clean, mypy strict clean, **225 test backend passano**, `npm run build` clean.

### v0.4d — Setup wizard + portachiavi (2026-05-02)

Le chiavi API e il modello di default ora si configurano dalla UI senza editare `.env` a mano.

**Backend nuovo**:
- `src/msrt/ui_server/secrets.py`: store dei segreti con due backend in priorità (1) `keyring` (macOS Keychain / SecretService Linux / Credential Manager Windows) e (2) `.env` come fallback. Funzioni: `save_secret` / `get_secret` / `delete_secret` / `known_keys` / `hydrate_process_env`. Quando il portachiavi accetta il valore, il `.env` viene bonificato per evitare shadow read; al boot della UI i segreti salvati nel portachiavi vengono reidratati in `os.environ` così LiteLLM continua a ricevere le chiavi dopo un restart. Il modulo onora `MSRT_DISABLE_KEYRING=1` per test e per gli utenti che preferiscono solo `.env`.
- `src/msrt/ui_server/setup_api.py`: schemi Pydantic + handler per i 4 endpoint nuovi. La validazione del nome chiave usa `known_keys()` (whitelist `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY`).
- 4 nuovi endpoint in `app.py`:
  - `POST /api/setup/save-key`     → salva (preferisce keychain, mirror env in-process, ritorna `{name, backend, message}` senza il valore)
  - `POST /api/setup/delete-key`   → cancella da entrambi i backend, `os.environ.pop`
  - `POST /api/setup/test-key`     → mini-chiamata reale al provider via `run_litellm_paid_smoke` (richiede LiteLLM up)
  - `POST /api/setup/default-model`→ scrive `MSRT_MODEL` nel `.env` e nell'env del processo
- `settings_view` riscritto: la presenza di una chiave si calcola da `Settings` + secret store, ritornando solo booleani `has_*_key`. Conseguenza: niente valori segreti nel payload `/api/settings`.

**Frontend nuovo**:
- `apps/desktop/src/pages/SetupWizard.tsx` (`/setup` route): tre `ProviderCard` (Anthropic/OpenAI/Google) ognuna con input password rivelabile, pulsanti `Salva` / `Test` / `Rimuovi`, link al portale del provider, feedback in linea (tone `ok`/`warn`/`fail` a seconda del backend). Quarta card `Default model` con `<select>` su tutti gli alias noti + supporto a custom alias presenti in `.env`. Stato live: dopo ogni mutation invalida `["settings"]` così il pill `presente`/`assente` si aggiorna. Voce di nav `Setup` aggiunta in `AppShell`.
- `Settings.tsx` resta diagnostica/read-only e rimanda a `/setup` per modificare chiavi/modello.
- `lib/api.ts`: tipi `SecretName`/`SecretReportResponse`/`SetupTestResult`/`DefaultModelResponse` + metodi `saveKey` / `deleteKey` / `testModel` / `setDefaultModel`.

**Test**:
- `test_setup_save_key_uses_dotenv_without_leaking_value` — sentinel non appare in nessuna risposta, `.env` viene scritto in tmp_path.
- `test_setup_delete_key_removes_presence_flag`.
- `test_setup_rejects_unknown_key_name` — validazione 400 con messaggio italiano.
- `test_settings_endpoint_does_not_leak_keys` continua a passare anche con la `.env` di progetto piena.

Quality gate post-v0.4d: ruff/format clean, mypy strict clean, **225 test backend passano**, `npm run build` clean.

### v0.4e — Retry failed + diagnostics (2026-05-02)

Polish funzionale dopo che il setup è cablato. Due capability ad alta utilità per l'uso reale del tool.

**Backend nuovo**:
- `POST /api/jobs/{id}/retry-failed`: legge i `Job.errors` di un job `url_batch` (formati come `ch.<numero>: <messaggio>`), estrae i numeri di capitolo distinti e crea un nuovo job batch con `options.chapters_filter` impostato a quei numeri (separati da virgola). `range_filter` e `limit` vengono azzerati così la nuova run rilancia esattamente quei capitoli e nient'altro. Risponde 409 se il job non è batch o se non ci sono fallimenti registrati.
- `GET /api/diagnostics`: snapshot redatto con `msrt_version`, info piattaforma, `settings_view` (presence flag, mai valori), `doctor_report`, percorso del log LiteLLM e ultimi 20 job (id/kind/status/contatori capitoli/errors/warnings). Niente chiavi, niente body grezzi: questo bundle è pensato per essere allegato a un'issue pubblica.

**Frontend nuovo**:
- `JobProgress.tsx`: pulsante "Riprova falliti (N)" visibile solo per batch URL terminali con `chapters_failed > 0`. On click chiama `api.retryFailed(id)` e naviga al job nuovo.
- `Settings.tsx`: card `Diagnostica` con bottone che fetcha `/api/diagnostics` lato client e triggera un download del JSON come `msrt-diagnostics-<timestamp>.json`. Nessun secret nel payload.
- `lib/api.ts`: nuovi metodi `retryFailed(id)` e `diagnostics()`.

**Test**:
- `test_diagnostics_endpoint_returns_redacted_snapshot` — sentinel non appare, presence flags ok.
- `test_retry_failed_chapters_filters_to_failed_numbers` — runner finto popola `errors=["ch.51: …", "ch.52: …"]`; il retry crea un job nuovo con `chapters_filter == "51,52"` e `range_filter/limit` azzerati.
- `test_retry_failed_rejects_non_batch_jobs` — local job → 409.
- `test_retry_failed_rejects_jobs_without_failed_chapters` — batch senza errori → 409.

Quality gate post-v0.4e: ruff/format clean, mypy strict clean, **229 test backend passano**, `npm run build` clean.

### v0.5 — Resilience & UX overhaul (in corso, 2026-05-03)

Trigger: overnight run di Wistoria (URL `…/chapter-0`, `--all-chapters`,
range 0-63 sul reader). Il job ha prodotto 33 PDF su 70 capitoli ed è
stato cancellato manualmente al chapter 33 (job id `d211deae1e2f`).
**Failure root cause** dei 4 errori registrati:

| Capitolo | Tipo | Causa |
|---|---|---|
| 1, 8.1 | race | `Network.getResponseBody: No resource with given identifier found`. `page.on("response", lambda r: asyncio.create_task(handle(r)))` legge il body in async dopo che la pagina è già navigata al sub-capitolo (1 → 1.1, 8 → 8.1). Chromium ha già scartato la risorsa. |
| 8, 15 | CDN 520 | Il reader-network ha esposto gli URL immagine, ma il download da `5w0.mfcdn2.xyz` ha risposto HTTP 520 con body Cloudflare. `_RETRYABLE_STATUSES` in `downloader.py:46` non include 520-524, quindi la prima 520 fa esplodere il capitolo senza retry. |

Il fallback browser-capture è fallito su tutti e 4 perché (a) le pagine
"shell" (chapter-1) non hanno scan in DOM al `domcontentloaded` o (b)
il rendering interno carica gli stessi URL CDN bloccati.

**Pain UX dichiarato**: il job è apparso "stuck al chapter 32" mentre in
realtà MITR stava macinando il chapter 33 (~30 min/capitolo per 45
pagine). La fase `translate` non emette progress per-pagina. Inoltre
la lista capitoli skipped non è visibile in nessuna vista UI; per
risalire ai 4 fallimenti l'utente ha dovuto leggere il JSON del job a
mano.

**Tier A — Resilience scraping** (must-have prima del prossimo overnight):
- [x] A.1 — `mangafire.py:_first_reader_payload` riscritto con `page.expect_response(predicate)`. Il context manager Playwright tiene viva la response finché il body non è letto, eliminando la race indipendentemente da redirect/navigazioni.
- [x] A.2 — `_RETRYABLE_STATUSES` esteso a `{520, 521, 522, 523, 524}` (Cloudflare); backoff esponenziale invariato.
- [x] A.3 — Trim del body HTML negli errori HTTP non retryable: summary tipo `[HTML 12kB]` via `_summarize_error_body`.
- [x] A.4 — Test: `test_download_pages_retries_on_cloudflare_520_then_succeeds`, `test_download_pages_summarises_html_error_body`.

**Tier B — Resilience job-level**:
- [x] B.1 — Retry per-capitolo nel batch tramite `_run_chapter_with_retry` (3 attempts, backoff 5/10/20s capped at 60s, `_RETRYABLE_HINTS` distingue errori network/race da 4xx).
- [x] B.2 — Sub-chapter detection: `MangaFireReaderPages` ora porta `observed_chapter`; `MangaFireScraper.fetch` rietichetta il `chapter_number` quando il reader serve un sub-chapter (1 → 1.1) e aggiunge un warning chiaro. Il manifest e il PDF carry il numero corretto, niente più "PDF ch.1 con contenuto 1.1".
- [x] B.3 — Test: `test_batch_retries_retryable_chapter_failures`, `test_batch_does_not_retry_non_retryable_failures`, `test_mangafire_fetch_relabels_shell_chapter_to_actual_subchapter`.

**Tier C — Osservabilità & UX overhaul**:
- [x] C.1 — Per-page progress nella fase translate via watcher thread che polla `out/translated-pages/` ogni 2s ed emette `Event(type="progress", unit="pages")`.
- [x] C.2 — Tabella capitoli per batch in `JobProgress`: righe per ogni numero esposto da coverage, status pill ridotto da manifest_paths/errors/warnings.
- [x] C.3 — Log feed collassato dietro `<details>` di default per ridurre rumore; truncate body HTML già fatto lato A.3.
- [x] C.4 — Watchdog stall: il page-watcher emette warning SSE se non vede nuove pagine per 15+ min (configurabile via `_STALL_THRESHOLD_SECONDS`).
- [x] C.5 — Dark mode default (Apple/Uber-style) applicato globalmente.
- [x] C.6 — Active batch banner persistente in `AppShell`.
- [x] C.7 — Manga-level progress bar in `JobProgress` (chapters on-disk / available).
- [x] C.8 — `POST /api/chapters/coverage` endpoint.
- [x] C.9 — Gap UX in BatchPlanner: due pannelli "Includere mancanti prima/dopo del range?" con checkbox.

**Tier D — Test discipline**:
- [x] D.1 — Test del relabel sub-chapter (proxy del fix expect_response, copre il path "shell chapter").
- [x] D.2 — Test retry batch (retryable + non-retryable).
- [x] D.3 — Test coverage endpoint con range e output su disco preesistente.

**Tier E — Usability polish (in chiusura per v0.5)**:
- [x] E.1 — Dashboard `SetupStatusHero`: 3-step checklist (chiavi API, LiteLLM, MITR) con CTA inline; quando tutto verde diventa una banner "Tutto pronto" con shortcut a Nuovo job / Batch.
- [x] E.2 — `NewJob` semplificato a 2 modi (locale, URL singolo): la modalità batch è nella pagina dedicata `/batch`, niente più ridondanza fra le due. Header con CTA "Batch su una serie →".
- [x] E.3 — Mode switch a card descrittive con sottotesto invece di pill anonime, così l'utente capisce cosa fa ogni modalità prima di sceglierla.
- [x] E.4 — Quick actions su Dashboard ampliate a 4 (Nuovo Job, Batch, Libreria, Setup) con icone parlanti.

**Decisione operativa**: il job overnight è stato cancellato (status
`cancelled`, `chapters_done=33, chapters_failed=5` — 4 originali + ch.33
ucciso a metà). Procediamo Tier C (UX) → Tier A (resilience) → B → D. La
priorità inversa rispetto al naturale "fixiamo prima i bug" è motivata
dal fatto che senza C.6/C.7/C.9 l'utente non può **vedere** che i fix
funzionano nei prossimi run lunghi.

### v0.4a.1 — Code review backend UI (2026-05-02)

Revisione diretta della codebase dopo il commit `58bce50`.

Finding chiusi:
- `commands._invoke_run_local()` cercava l'event loop dentro il worker thread creato da `asyncio.to_thread()`. Su Python 3.11+ questo rompe i job UI reali con `RuntimeError: There is no current event loop`. Fix: cattura del loop nel coroutine caller e pass esplicito al bridge sync.
- `JobManager._run_one()` rilanciava `asyncio.CancelledError` dopo aver marcato il job come cancellato, spegnendo il worker FIFO. Fix: la cancellazione diventa terminal state del job ma il worker continua col job successivo.
- `url_batch` UI ignorava `options.skip_existing`, a differenza della CLI. Fix: helper `_chapter_outputs_exist()` condiviso nel comportamento, warning SSE e conteggio del capitolo come completato/skipped.
- `DryRunRequest.limit` e `JobOptions.limit` accettavano `0` fino al layer selector. Fix: validazione Pydantic `ge=1`, risposta 422 pulita.
- Metadata URL nel manifest UI non propagavano i campi browser-capture (`capture_mode`, `viewport`, `device_scale_factor`, `manual_intervention`). Fix: parity con CLI `msrt run`.

Test aggiunti:
- `test_default_local_runner_emits_from_worker_thread`
- `test_cancel_running_job_does_not_stop_worker`
- `test_url_batch_job_honours_skip_existing`
- `test_dry_run_rejects_non_positive_limit`

Quality gate locale con binari `.venv/bin`: ruff, format, mypy strict clean; **222 test pass**.

Vincoli:
- Il team UI non deve riscrivere scraping/traduzione/package in TypeScript.
- Batch globale sempre dietro dry-run o conferma esplicita.
- Nessuna credenziale in localStorage, log, manifest o response API.
- Nessun bypass di login/captcha/Turnstile.

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
- **Scraping URL parzialmente bloccato sulla macchina utente**: `api.mangadex.org` resta affetto da SSL intercept (filtro DNS/proxy aziendale o ISP). MangaFire è stato sbloccato in v0.3d tramite reader-network, senza ricostruire token o bypassare challenge.
- **Fallback browser capture deciso**: quando raw download/generic extraction falliscono ma il reader è visibile nel browser, `msrt` potrà catturare automaticamente le scan come immagini locali e proseguire con la pipeline. Se serve verifica umana, il tool mette in pausa e aspetta l'intervento utente, senza bypass.
- ~~MangaFire chapter 51 non scaricabile via browser-capture puro~~ → chiuso in v0.3d con reader-network: osserva la normale risposta `/ajax/read/chapter/<id>` e scarica `result.images`; browser-capture resta fallback.
- **OCR artifacts su nomi compatti**: limite di Model48pxOCR. Mitigazione parziale via system prompt; soluzione completa con two-pass v0.6 + series glossary.
- **Font troppo piccolo nelle bubble**: emerso leggendo il PDF del capitolo 50 e confermato visivamente su chapter 51 pagina 001. Mitigazione v0.3e: postprocess image-level bubble-aware attivo di default. Soluzione completa pianificata: postprocess strutturato v0.6 con polygon/mask/rotation e preservazione scala originale fuori bubble.

---

## TODO emersi durante l'implementazione

- ~~Cablare `glossary.py` al prompt~~ → chiuso in v0.1.z, automatizzato in v0.1.aa con auto-build.
- ~~Test unit per `SubprocessEngine._command()` con la nuova struttura~~ → chiuso in v0.1.z (`tests/test_engine.py` riscritto).
- ~~Decidere default `GIT_REF` in `install-mitr.sh`~~ → chiuso in v0.3f: default `3abfc47`, `--git-ref main` opt-in.
- ~~Formalizzare e implementare `browser-capture` come fallback automatico di `msrt run <URL>` dopo v0.2 foundation~~ → foundation chiusa in v0.3-dev; resta E2E reale MangaFire + raffinamento selettori.
- ~~Implementare mitigazione bubble-aware per testo troppo piccolo~~ → chiuso in v0.3e come bridge image-level. Resta il postprocess typesetting pieno v0.6 basato su polygon/mask/rotation.
- Documentare in `docs/PROVIDER_NOTES.md` il vincolo `temperature=1` di GPT-5.5 e il workaround via `gpt_config` YAML.
