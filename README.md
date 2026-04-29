# Manga Scan Recovery Translator (`msrt`)

CLI Python che, partendo da una cartella di immagini manga (MVP) o da un URL di capitolo (estensioni successive), produce un archivio leggibile (CBZ o PDF) con il testo tradotto da inglese a italiano.

> ⚠️ **Stato del progetto: in sviluppo (v0.2.b).** Questo repository è un wrapper attorno a [`manga-image-translator`](https://github.com/zyddnys/manga-image-translator) (MITR), che resta una **dipendenza esterna** installata e mantenuta dall'utente.

## Cosa fa (e cosa non fa)

**Cosa fa oggi (v0.2.b)**:
- pipeline locale `msrt run-local` validata end-to-end su capitoli reali (50 pagine in ~24 min su Mac MPS): traduzione EN→IT con MITR + LiteLLM proxy + auto-glossary di serie via LLM (cache persistente in `~/.cache/msrt/glossaries/`);
- comando `msrt fetch <URL> --i-own-rights` scarica un capitolo da MangaDex (API ufficiale, At-Home server) in una cartella locale pronta per `run-local`;
- impacchetta cartelle di immagini in CBZ (con `ComicInfo.xml`) o PDF;
- proxy LiteLLM locale con `msrt server up|down|status` e diagnostica con `msrt doctor`;
- subapp `msrt glossary {build,show,list,path,forget}` per ispezionare il cache di serie.

**Cosa farà nelle prossime release**:
- v0.2c: comando `msrt run <URL>` che combina `fetch` + `run-local` in un singolo passo.
- v0.3+: adapter aggiuntivi best-effort (vedi [`docs/UNOFFICIAL_ADAPTERS.md`](docs/UNOFFICIAL_ADAPTERS.md)), fallback automatico con browser capture quando il download diretto non funziona, generic scraper euristico, fallback con vision LLM, post-processing custom per preservazione font/colore piena, supporto LLM locali via Ollama.

**Cosa NON fa**:
- Non promette di funzionare su "qualsiasi sito": estrazione **best-effort** con adapter ufficiali e fallback.
- Non bundla il motore di traduzione, i font o i modelli: vanno installati separatamente.
- Non aggira protezioni anti-bot: usa user-agent dichiarato e rispetta rate-limit/`robots.txt` dove applicabile. Se un fallback browser incontra login/captcha/Turnstile, il tool può attendere l'intervento manuale dell'utente, ma non prova a bypassarlo.

## Prerequisiti

- macOS o Linux (Apple Silicon supportato via MPS).
- Python 3.11 o 3.12.
- [`uv`](https://docs.astral.sh/uv/) per gestione ambiente.
- [`manga-image-translator`](https://github.com/zyddnys/manga-image-translator) installato in un venv dedicato (è GPL-3.0, vedi `NOTICE`).
- Almeno una API key tra Anthropic / OpenAI / Google (vedi `.env.example`).

## Installazione

**Setup guidato (consigliato)**:

```bash
git clone <repo-url>
cd manga_scan_recovery_translator
./scripts/setup.sh
```

`setup.sh` esegue `uv sync --all-extras --dev` e poi avvia `msrt setup`, un wizard interattivo che:

1. verifica i prerequisiti (uv, versione Python, spazio disco);
2. crea `.env` (copiato da `.env.example` se manca);
3. ti fa scegliere il provider LLM (OpenAI / Anthropic / Google), salva `MSRT_MODEL` e la chiave in `.env`;
4. installa MITR in un venv esterno (`~/tools/mitr` di default) chiamando `scripts/install-mitr.sh`;
5. avvia il proxy LiteLLM con `msrt server up`;
6. opzionalmente esegue `--paid-smoke` per validare la chiave con una chiamata reale (chiede conferma esplicita).

Il wizard è idempotente: se una chiave o `MITR_BIN_PATH` esistono già, chiede prima di sovrascrivere. Per CI o reinstall scriptato:

```bash
./scripts/setup.sh -- --yes --no-server      # accetta default; non avvia il proxy
OPENAI_API_KEY=... ./scripts/setup.sh -- --yes --paid-smoke  # non interattivo + smoke reale
msrt setup --no-install-mitr                 # se MITR è già installato
```

`--yes` non chiede la chiave in prompt: per uso non interattivo passa la chiave
via ambiente o scrivila prima in `.env`. Se `--paid-smoke` fallisce, il comando
esce con codice non zero.

**Setup manuale** (se preferisci controllare ogni passo):

```bash
git clone <repo-url>
cd manga_scan_recovery_translator
uv sync --all-extras --dev
cp .env.example .env  # popola le chiavi
./scripts/install-mitr.sh
# aggiungi a .env il MITR_BIN_PATH stampato e la chiave provider
msrt server up
msrt doctor --model gpt
```

## Utilizzo

```bash
# Tradurre una cartella di immagini → CBZ
msrt translate ./pages --series "Test" --chapter 1 --out ./out

# One-shot: traduci e produci PDF
msrt run-local ./pages --format pdf --series "Test" --chapter 1

# Verifica prerequisiti (usa MSRT_MODEL se --model è omesso)
msrt doctor

# Avvia LiteLLM proxy locale
msrt server up

# Preflight OpenAI reale (opt-in, consuma pochi token; usa MSRT_MODEL=gpt)
msrt doctor --paid-smoke

# Primo E2E consigliato con OpenAI
msrt run-local ./pages --format pdf --series "Test" --chapter 1
```

## Provider LLM

Il flag `--model` accetta alias multi-provider, configurati in `configs/litellm.yaml`:

| Alias | Provider | Modello (default) |
|---|---|---|
| `sonnet` | Anthropic | claude-sonnet-4-6 |
| `opus` | Anthropic | claude-opus-4-7 |
| `gpt` (default setup) | OpenAI | gpt-5.5 |
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
