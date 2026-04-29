# Manga Scan Recovery Translator (`msrt`)

CLI Python che, partendo da una cartella di immagini manga (MVP) o da un URL di capitolo (estensioni successive), produce un archivio leggibile (CBZ o PDF) con il testo tradotto da inglese a italiano.

> ⚠️ **Stato del progetto: in sviluppo (v0.1.x).** Questo repository è un wrapper attorno a [`manga-image-translator`](https://github.com/zyddnys/manga-image-translator) (MITR), che resta una **dipendenza esterna** installata e mantenuta dall'utente.

## Cosa fa (e cosa non fa)

**Cosa fa oggi (v0.1.x)**:
- impacchetta cartelle di immagini in CBZ/PDF;
- gestisce il proxy LiteLLM locale con `msrt server up|down|status`;
- esegue diagnostica con `msrt doctor`;
- espone `translate` e `run-local` per la pipeline locale, pronte per MITR installato esternamente.

**Cosa farà nelle prossime release**:
- v0.1: input = cartella locale di immagini → traduzione EN→IT → CBZ/PDF (un PDF per capitolo). Il layout viene preservato in modalità "best-effort" tramite il renderer di MITR.
- v0.2: download da [MangaDex](https://mangadex.org) tramite API ufficiale.
- v0.3+: adapter aggiuntivi best-effort (vedi [`docs/UNOFFICIAL_ADAPTERS.md`](docs/UNOFFICIAL_ADAPTERS.md)), generic scraper euristico, fallback con vision LLM, post-processing custom per preservazione font/colore piena, supporto LLM locali via Ollama.

**Cosa NON fa**:
- Non promette di funzionare su "qualsiasi sito": estrazione **best-effort** con adapter ufficiali e fallback.
- Non bundla il motore di traduzione, i font o i modelli: vanno installati separatamente.
- Non aggira protezioni anti-bot: usa user-agent dichiarato e rispetta rate-limit/`robots.txt` dove applicabile.

## Prerequisiti

- macOS o Linux (Apple Silicon supportato via MPS).
- Python 3.11 o 3.12.
- [`uv`](https://docs.astral.sh/uv/) per gestione ambiente.
- [`manga-image-translator`](https://github.com/zyddnys/manga-image-translator) installato in un venv dedicato (è GPL-3.0, vedi `NOTICE`).
- Almeno una API key tra Anthropic / OpenAI / Google (vedi `.env.example`).

## Installazione

```bash
git clone <repo-url>
cd manga_scan_recovery_translator
cp .env.example .env  # popola le chiavi
uv sync --all-extras --dev
./scripts/bootstrap.sh
./scripts/install-mitr.sh
```

Poi aggiungi a `.env` il valore `MITR_BIN_PATH` stampato da `scripts/install-mitr.sh` e la chiave OpenAI:

```bash
OPENAI_API_KEY=...
```

## Utilizzo

```bash
# Tradurre una cartella di immagini → CBZ
msrt translate ./pages --series "Test" --chapter 1 --out ./out

# One-shot: traduci e produci PDF
msrt run-local ./pages --format pdf --series "Test" --chapter 1

# Verifica prerequisiti
msrt doctor

# Avvia LiteLLM proxy locale
msrt server up

# Preflight OpenAI reale (opt-in, consuma pochi token)
msrt doctor --model gpt --paid-smoke

# Primo E2E consigliato con OpenAI
msrt run-local ./pages --format pdf --model gpt --series "Test" --chapter 1
```

## Provider LLM

Il flag `--model` accetta alias multi-provider, configurati in `configs/litellm.yaml`:

| Alias | Provider | Modello (default) |
|---|---|---|
| `sonnet` (default) | Anthropic | claude-sonnet-4-6 |
| `opus` | Anthropic | claude-opus-4-7 |
| `gpt` | OpenAI | gpt-5.5 |
| `gpt-mini` | OpenAI | gpt-5-mini |
| `gemini-pro` | Google | gemini-2.5-pro |
| `gemini-flash` | Google | gemini-2.5-flash |

Si possono aggiungere alias custom modificando `configs/litellm.yaml`.

Il prossimo E2E reale del progetto usa OpenAI (`--model gpt`). L'alias `gpt`
punta a `gpt-5.5`, che i documenti OpenAI indicano come modello latest al
2026-04-29. L'integrazione passa da LiteLLM e dall'endpoint Chat Completions
compatibile richiesto da MITR.

## Font

`msrt` non distribuisce font. Il flag `--font-path` è opzionale; se non specificato il motore usa il proprio default. Per qualità migliore, fornite un font a licenza permissiva, ad esempio:
- [Noto Sans](https://fonts.google.com/noto/specimen/Noto+Sans) — OFL
- [Comic Neue](https://comicneue.com/) — OFL
- [Open Sans](https://fonts.google.com/specimen/Open+Sans) — OFL

`msrt doctor` segnala suggerimenti se il font non è impostato.

## Disclaimer

Lo scraping di contenuti protetti da copyright può violare i Termini di Servizio del sito o le leggi locali sul diritto d'autore. **Lei è responsabile** di assicurarsi di avere il diritto di scaricare e tradurre i contenuti. Il flag `--i-own-rights` è un guardrail UX, non una tutela legale.

## Licenze

- `msrt` (questo repository): **MIT** (vedi `LICENSE`).
- `manga-image-translator`: **GPL-3.0**, NON incluso in questo repo.
- Altre dipendenze: vedi `NOTICE`.

## Contributi

Progetto in sviluppo iniziale. Vedere [`docs/PROGRESS.md`](docs/PROGRESS.md) per lo stato avanzamento lavori.
