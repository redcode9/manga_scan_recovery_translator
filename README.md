# Manga Scan Recovery Translator (msrt)

A tool that translates entire manga from English to Italian while
keeping the original speech-bubble layout intact. Works either from a
folder of scans already on your Mac, or directly from a series URL on
MangaDex or MangaFire, and produces one PDF (or CBZ) per chapter that
opens in any reader.

The interface is a small local web app that runs in your browser: you
paste a series URL, the tool downloads the chapters, translates the
bubbles with an LLM provider you choose (Anthropic, OpenAI or Google), and
shows you a Netflix-style library of covers where you can see at a
glance what you have and what is missing.

It runs on Mac and Linux only. Nothing of this is in the cloud — the
whole pipeline lives on your machine. The only data that leaves the
computer are the translation calls to the LLM provider you picked, and
(when enabled) the cover-art lookups against public manga catalogues.

> Note: msrt is a wrapper around
> [manga-image-translator](https://github.com/zyddnys/manga-image-translator)
> ("MITR" for short), which is a separate GPL-3.0 project and has to be
> installed alongside. The `scripts/install-mitr.sh` script does that
> for you during setup.

## What you need before starting

Even if you are not technical, you only need to gather these once:

1. **A Mac (Apple Silicon or Intel) or a Linux machine.** Windows is
   not tested and not officially supported.
2. **Python 3.11 or 3.12.** Recent macOS ships with one already; if
   yours does not, install it via
   [Homebrew](https://brew.sh/): `brew install python@3.12`.
3. **uv**, a fast modern Python environment manager.
   One-time install:
   `curl -LsSf https://astral.sh/uv/install.sh | sh`.
4. **An LLM provider API key** — at least one of OpenAI, Anthropic or
   Google. OpenAI is the recommended path; you can create the key at
   <https://platform.openai.com/api-keys>. Translating a full manga
   typically costs a few cents.
5. **About 4 GB of free disk space** (MITR models, scans, translated
   pages). Final PDFs land in the project's `out/` directory.

No accounts to create, no cloud, no logins: everything stays local.

## Step-by-step install

Open a Terminal (on Mac: ⌘+Space, type "Terminal", press enter) and
paste the blocks below one at a time.

```bash
# 1. Get the project
git clone https://github.com/redcode9/manga_scan_recovery_translator.git
cd manga_scan_recovery_translator

# 2. Run the guided setup
./scripts/setup.sh
```

The setup will ask a few questions:

- "Which provider do you want to use?" — press `1` for OpenAI
  (recommended), or pick the one whose key you already have.
- "Paste your API key." — paste the key you created on the provider's
  portal. On macOS the key is stored in the system keychain, never in
  plain text.
- "Install MITR?" — answer yes the first time. The script downloads
  and configures it under `~/tools/mitr` without touching the rest of
  the system.
- "Start the LiteLLM proxy?" — yes; it is the local component that
  talks to the LLM on your behalf.

When the setup finishes, the environment is ready.

## How to use it

The simplest way is the web app:

```bash
uv run msrt ui
```

This builds the interface if needed, starts the local server at
`http://127.0.0.1:4001` and opens the browser. From there:

1. **Add a manga.** In the left menu click "Aggiungi manga", paste the
   URL of the series (a MangaDex or MangaFire page), confirm you have
   the right to translate it, and press "Avvia batch".
2. **Watch the progress.** You land on the job page with two progress
   bars: one for the current chapter (page X of Y) and one for the
   manga as a whole (chapters done over chapters available on the
   source).
3. **Library.** Going back to the home shows a Netflix-style grid of
   every manga you have translated. Each cover is fetched
   automatically from MangaDex or AniList; if the series exists in
   neither, msrt synthesises one from the actual scanned pages, and as
   a last resort (opt-in) lets the AI generate a manga-styled cover.
4. **Recover missing chapters.** If a chapter failed mid-batch (CDN
   hiccup, a transient page error), the series card surfaces a
   "Recupera mancanti" button to re-run only those. When new chapters
   appear on the source, "Continua dal prossimo" shows up too.

## Quick start without the UI (command line)

If you prefer the CLI, here is the minimum you need:

```bash
# Translate a folder of images into a PDF
uv run msrt run-local ./scan-folder --format pdf --series "My Manga" --chapter 1

# Translate a whole series from URL
uv run msrt run https://mangafire.to/read/<slug>/en/chapter-0 \
  --all-chapters --i-own-rights --format pdf

# Start / stop the LiteLLM proxy (the UI does this for you)
uv run msrt server up
uv run msrt server down

# Diagnostics
uv run msrt doctor
```

Every command accepts `--help` for the full reference.

## Configuration

Everything you need lives in two places:

- `.env` in the project root, with the keys and the default model.
  Created automatically on first setup.
- The web app (`uv run msrt ui` → "Impostazioni") lets you swap
  providers, rotate keys, toggle the automatic cover retrieval, and
  download a redacted diagnostics bundle (handy when filing an issue).

Environment variables the program reads:

| Variable | What it does |
|---|---|
| `MSRT_MODEL` | Default model alias (`gpt`, `sonnet`, `opus`, `gemini-pro`, `gemini-flash`, `gpt-mini`). |
| `OPENAI_API_KEY` | OpenAI key. |
| `ANTHROPIC_API_KEY` | Anthropic API key. |
| `GEMINI_API_KEY` | Google Gemini key. |
| `MITR_BIN_PATH` | How to invoke manga-image-translator. The setup writes this. |
| `LITELLM_PORT` | LiteLLM proxy port (default 4000). |
| `MSRT_AUTO_COVER` | `0` or `1`. Disables the automatic cover lookup. |
| `MSRT_HOME` | Override project root (useful when running `msrt` from outside the folder). |

## How it works, in two paragraphs

When you add a series from URL, msrt talks to the site's official API
(MangaDex) or observes the reader without forging anything (MangaFire)
to obtain the page URLs. It downloads them with a polite HTTP client
(rate limit, retry on 5xx, validation that the response is actually an
image). It then invokes MITR as an external process to handle OCR,
inpainting and rendering, and uses the LiteLLM proxy to call your
chosen LLM for translating the bubbles. The result is one PDF (or CBZ)
per chapter, with Italian text inside the original bubbles.

The translation model is the one you pick (OpenAI, Anthropic, Google):
a 20-page chapter usually costs a fraction of a cent, but check the
provider's pricing page for the exact figure. msrt does not store the
translation: every call is isolated, the processed pages stay in your
local `out/` folder and that is it.

## Troubleshooting

**"msrt: command not found"** — Prefix with `uv run` (e.g.
`uv run msrt ui`). To use the bare command, activate the venv first:
`source .venv/bin/activate`.

**"LiteLLM stopped" badge in the top bar** — The LLM proxy is not
running. Click "Avvia LiteLLM" on the dashboard, or run
`uv run msrt server up` from a terminal. It takes a few seconds the
first time.

**"MITR: mancante" badge in the top bar** — The translation engine
was not installed. Run `./scripts/install-mitr.sh` and follow the
prompts.

**A translation has been running for an hour and is not finished** —
Big chapters take time: typical speed is roughly one minute per page
on Apple Silicon Macs with MPS. The job page shows in real time how
many pages have been rendered; if it is genuinely stuck, the banner
warns you after 15 minutes without progress.

**A series shows no cover in the library** — If you find one without a
poster, it means the series is not in MangaDex / AniList and you have
not enabled AI generation. Open "Impostazioni" → "Recupero automatico
copertine" → on. With an OpenAI key configured the missing covers get
generated too (~$0.011 per image, only once per series, then cached).

**A chapter failed during the batch** — The series card carries a
"Recupera mancanti" button that re-runs only the broken chapters. The
system already does up to three automatic retries with backoff, but if
the source returns errors for several minutes you may need to wait and
retry by hand later.

## Known limitations

- Compact-font character names (e.g. "Emma" being read as "IEMMA") are
  still a known OCR artefact; the auto-built series glossary mitigates
  it but a full fix needs a two-pass OCR (in roadmap).
- The MangaFire adapter is best-effort: we do not reconstruct anti-bot
  tokens, we observe the reader as a normal browser would. If the site
  changes layout, msrt falls back to browser capture; if even that
  fails it stops and asks you to step in instead of bypassing
  anything.
- The Tauri desktop wrapper is scaffold only: today msrt runs as a web
  app served by its own Python backend. A standalone binary will come
  later.

## Disclaimer

Downloading and translating copyrighted content may violate the
terms of service of the source site or the copyright laws of your
country. You are responsible for ensuring you have the right to do
it: the `--i-own-rights` flag is a reminder in the UI, not legal
shielding.

## License

The msrt code is MIT (see [`LICENSE`](LICENSE)).

manga-image-translator is a separate GPL-3.0 project: it is not
included in this repository, you install it on the side. Details on
all third-party dependencies live in [`NOTICE`](NOTICE).
