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
echo "3) Avvia LiteLLM proxy (necessario per la traduzione)."
echo "   Due opzioni equivalenti:"
echo "     a) Native (consigliato su macOS, no Docker richiesto):"
echo "          msrt server up      # avvia subprocess locale via 'litellm'"
echo "          msrt server status  # PID + healthcheck"
echo "          msrt server down    # SIGTERM con fallback SIGKILL"
echo "        Richiede l'extra runtime: lo abbiamo appena installato con uv sync --all-extras."
echo "     b) Docker:"
echo "          docker compose up -d litellm"
echo "        Vedi docker-compose.yml. Niente MPS in container su Mac."
echo
echo "4) Verifica setup:"
echo "     msrt doctor                # check senza chiamate paid"
echo "     msrt doctor --paid-smoke   # opt-in: una piccola chiamata reale al provider"
echo
echo "─────────────────────────────────────────────────────────────────"
echo "Pipeline locale disponibile (v0.1)."
echo "Adapter MangaDex / MangaFire arrivano in v0.2 / v0.3."
echo "─────────────────────────────────────────────────────────────────"
