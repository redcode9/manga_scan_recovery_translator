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

### v0.2+ — vedi piano
*(da pianificare dopo v0.1)*

---

## Verifiche

Nessuna ancora.

---

## Problemi & workaround

Nessuno ancora.

---

## TODO emersi durante l'implementazione

Nessuno ancora.
