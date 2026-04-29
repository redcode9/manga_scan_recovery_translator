#!/usr/bin/env bash
# Bootstrap script per msrt — esegue setup iniziale dell'ambiente.
#
# Uso:
#   ./scripts/bootstrap.sh

set -euo pipefail

cd "$(dirname "$0")/.."

echo "▶ Sync dipendenze msrt (uv sync)..."
uv sync --all-extras --dev

echo
echo "✅ msrt installato in venv locale."
echo
echo "─────────────────────────────────────────────────────────────────"
echo "PROSSIMI PASSI (manuali, non automatizzati per mantenere separate le licenze):"
echo "─────────────────────────────────────────────────────────────────"
echo
echo "1) Installa manga-image-translator (MITR) in un VENV DEDICATO."
echo "   MITR è GPL-3.0; tienilo separato dal venv di msrt."
echo
echo "     mkdir -p \"\$HOME/tools/mitr\" && cd \"\$HOME/tools/mitr\""
echo "     uv venv && source .venv/bin/activate"
echo "     uv pip install manga-image-translator"
echo "     # oppure clona: git clone https://github.com/zyddnys/manga-image-translator"
echo
echo "   Verifica:"
echo "     python -m manga_translator --help"
echo
echo "   Imposta MITR_BIN_PATH nel tuo .env."
echo
echo "2) Copia .env.example in .env e popola almeno una API key LLM."
echo "     cp .env.example .env"
echo
echo "3) Avvia LiteLLM proxy (usato da MITR come backend OpenAI-compatible)."
echo "     # docker compose up litellm     (consigliato)"
echo "     # opzioni di config in configs/litellm.yaml (sarà disponibile da v0.1)"
echo
echo "4) Verifica setup (disponibile da v0.1):"
echo "     msrt doctor"
echo
echo "─────────────────────────────────────────────────────────────────"
echo "msrt è in v0.0 (bootstrap). Le funzionalità arrivano da v0.1."
echo "─────────────────────────────────────────────────────────────────"
