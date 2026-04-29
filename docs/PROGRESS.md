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
| 2026-04-29 | Default model: Claude Sonnet 4.6 | Bilanciamento qualità/costo per traduzione manga |
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

### v0.2+ — vedi piano
*(da pianificare dopo l'E2E reale)*

---

## Verifiche

- 2026-04-29: test automatici v0.1 passano (`ruff`, `ruff format --check`, `mypy strict`, `pytest`).
- 2026-04-29: smoke CLI `msrt --help` OK.
- 2026-04-29: smoke `msrt doctor --model sonnet` fallisce correttamente perché mancano prerequisiti runtime reali.
- 2026-04-29: smoke E2E ambiente runtime — `msrt server up` avvia LiteLLM (PID 56054), `curl /health` 200, `msrt server status` rileva up healthy, `msrt server down` lo ferma. PID file gestito correttamente.

---

## Problemi & workaround

- MITR non installato: pin versione, verifica flag reali e E2E reale restano bloccati. Workaround attuale: test con `MockTranslationEngine` + `doctor` esplicito sui prerequisiti mancanti. Mitigazione aggiunta: `scripts/install-mitr.sh` per install opt-in in venv esterno.
- LiteLLM non avviato e chiave OpenAI assente in ambiente locale: smoke paid/E2E reale rimandati.

---

## TODO emersi durante l'implementazione

Nessuno ancora.
