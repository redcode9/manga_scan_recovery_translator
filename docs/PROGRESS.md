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
| 2026-04-29 | Architettura: wrap di MITR come **dipendenza esterna**, non fork né import | MITR è GPL-3.0; il wrapper resta MIT senza contagio licenza |
| 2026-04-29 | Provider LLM multi-provider via LiteLLM proxy | Anthropic + OpenAI + Google intercambiabili senza patch upstream |
| 2026-04-29 | Default model: Claude Sonnet 4.6 | Bilanciamento qualità/costo per traduzione manga |
| 2026-04-29 | Default formato: CBZ (`translate`/`package`), PDF (`run-local`/`run`) | CBZ è standard archivio manga; PDF è il formato lettura per l'utente finale |
| 2026-04-29 | Naming: motore esterno chiamato `MITR` o `manga-image-translator`, mai "MIT" | Evita ambiguità con la licenza MIT del wrapper |
| 2026-04-29 | MangaDex come adapter pubblico, MangaFire come adapter interno first-class non promosso | MangaDex ha API ufficiale; MangaFire è il sito che l'utente sta effettivamente usando |
| 2026-04-29 | Niente font bundlato: `--font-path` opzionale + `doctor` avvisa | Licenze font incerte (Wild Words, Anime Ace non confermati permissive) |
| 2026-04-29 | Niente smoke test paid in CI; `--paid-smoke` solo opt-in in `doctor` | Costo, fragilità, requisito 3 chiavi |
| 2026-04-29 | RunManifest `msrt-run.json` salvato per ogni esecuzione | Riproducibilità, debug, A/B tra provider |
| 2026-04-29 | LLM locale rimandato a v0.7 via Ollama, modello scelto al momento via benchmark | Lo stato dell'arte locale evolve velocemente, niente hardcoding oggi |

---

## Task

### v0.0 — Bootstrap repository
- [x] **2026-04-29** `git init` + struttura cartelle (`docs/`, `configs/`, `src/msrt/{translate,package,scrape,utils}`, `tests/{unit,integration,fixtures}`, `scripts/`, `.github/workflows/`)
- [ ] `pyproject.toml` con uv + hatchling, deps minime, scripts entry, tool config (ruff/mypy/pytest)
- [ ] `LICENSE` (MIT) e `NOTICE` (rimando GPL upstream)
- [ ] `README.md` con disclaimer prudente
- [ ] `docs/PROGRESS.md` (questo file)
- [ ] `docs/UNOFFICIAL_ADAPTERS.md` e `docs/PROVIDER_NOTES.md`
- [ ] `.env.example` e `.gitignore`
- [ ] CI minima `.github/workflows/ci.yml` (lint + scheletro test, no rete)
- [ ] `scripts/bootstrap.sh`
- [ ] Primo commit `chore: bootstrap repository (v0.0)`

### v0.1 — Motore end-to-end con input locale (MVP)
*(da iniziare dopo v0.0)*

1. Pin versione MITR + verifica flag reali (`--help`, `config-help`)
2. Modelli `Bubble`, `Page`, `Chapter`, `TranslationJob`, `RunManifest` in `src/msrt/models.py`
3. Config (`pydantic-settings`) e logging (`structlog` + `rich`)
4. LiteLLM proxy multi-provider, `configs/litellm.yaml`, `configs/translator-prompt.yaml` con prompt EN→IT manga-aware + glossary embedded
5. `msrt doctor` (default + `--paid-smoke`)
6. `TranslationEngine` ABC + `SubprocessEngine` MITR
7. CLI metadati manuali (`--series`, `--chapter`, `--title`, `--lang-source`, `--lang-target`)
8. `package/naming.py` natural sort + warning ambiguità
9. Packaging CBZ (ComicInfo.xml `LanguageISO=it`) + PDF (img2pdf)
10. RunManifest `msrt-run.json`
11. CLI `msrt run-local` end-to-end con progress bar
12. Test E2E manuale su fixture proprietaria

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
