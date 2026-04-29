#!/usr/bin/env bash
# msrt — first-run guided setup.
#
# What it does:
#   1) uv sync --all-extras --dev (installs msrt + runtime extras incl. litellm)
#   2) uv run msrt setup (interactive wizard)
#
# All flags after "--" are forwarded to `msrt setup`. Examples:
#
#   ./scripts/setup.sh                    # full interactive setup
#   ./scripts/setup.sh -- --yes           # accept all defaults (CI / scripted)
#   ./scripts/setup.sh -- --no-install-mitr --no-server --paid-smoke
#
# Notes:
#   - MITR is installed in a separate venv (default ~/tools/mitr) by
#     scripts/install-mitr.sh. msrt never imports MITR; see NOTICE for the
#     GPL-3.0 boundary.
#   - The wizard is idempotent: running it twice keeps existing keys unless
#     you confirm a replacement.

set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found. Install uv first: https://docs.astral.sh/uv/" >&2
  exit 1
fi

echo "▶ Sync dipendenze msrt (uv sync --all-extras --dev)..."
uv sync --all-extras --dev

# Strip a single leading "--" so users can write `setup.sh -- --yes`.
if [[ "${1:-}" == "--" ]]; then
  shift
fi

echo
echo "▶ Avvio wizard interattivo (uv run msrt setup $*)..."
exec uv run msrt setup "$@"
