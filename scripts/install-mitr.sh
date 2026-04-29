#!/usr/bin/env bash
# Convenience installer for manga-image-translator (MITR).
#
# This script intentionally installs MITR outside the msrt virtual environment.
# MITR is GPL-3.0 and remains an external runtime dependency; msrt does not
# import or redistribute it.
#
# Usage:
#   ./scripts/install-mitr.sh
#   ./scripts/install-mitr.sh --prefix "$HOME/tools/mitr"
#   ./scripts/install-mitr.sh --dry-run

set -euo pipefail

PREFIX="${HOME}/tools/mitr"
PACKAGE="manga-image-translator"
DRY_RUN=0

usage() {
  cat <<'EOF'
Convenience installer for manga-image-translator (MITR).

This script intentionally installs MITR outside the msrt virtual environment.
MITR is GPL-3.0 and remains an external runtime dependency; msrt does not
import or redistribute it.

Usage:
  ./scripts/install-mitr.sh
  ./scripts/install-mitr.sh --prefix "$HOME/tools/mitr"
  ./scripts/install-mitr.sh --dry-run

Options:
  --prefix PATH   Install MITR venv under PATH (default: $HOME/tools/mitr)
  --package SPEC  Package spec to install (default: manga-image-translator)
  --dry-run       Print commands without executing them
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix)
      if [[ $# -lt 2 ]]; then
        echo "--prefix requires a value" >&2
        exit 2
      fi
      PREFIX="$2"
      shift 2
      ;;
    --package)
      if [[ $# -lt 2 ]]; then
        echo "--package requires a value" >&2
        exit 2
      fi
      PACKAGE="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

PYTHON_BIN="${PREFIX}/.venv/bin/python"
MITR_BIN_PATH="${PYTHON_BIN} -m manga_translator"

run() {
  echo "+ $*"
  if [[ "${DRY_RUN}" -eq 0 ]]; then
    "$@"
  fi
}

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found. Install uv first: https://docs.astral.sh/uv/" >&2
  exit 1
fi

echo "Installing MITR external runtime"
echo "  target:  ${PREFIX}"
echo "  package: ${PACKAGE}"
echo

run mkdir -p "${PREFIX}"
run uv venv "${PREFIX}/.venv"
run uv pip install --python "${PYTHON_BIN}" "${PACKAGE}"

echo
echo "Verification command:"
echo "  ${MITR_BIN_PATH} --help"
if [[ "${DRY_RUN}" -eq 0 ]]; then
  "${PYTHON_BIN}" -m manga_translator --help >/dev/null
  echo "  OK"
fi

echo
echo "Add this to .env:"
echo "  MITR_BIN_PATH=\"${MITR_BIN_PATH}\""
echo
echo "Then run:"
echo "  msrt doctor --model sonnet"
