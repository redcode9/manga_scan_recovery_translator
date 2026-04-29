#!/usr/bin/env bash
# Convenience installer for manga-image-translator (MITR).
#
# MITR is not published on PyPI under its package name. We clone the upstream
# Git repository and install its requirements + the package itself into a
# dedicated venv. The venv is pinned to Python 3.11 because MITR's pyproject
# requires Python >=3.10, <3.12.
#
# This script intentionally installs MITR outside the msrt virtual environment.
# MITR is GPL-3.0 and remains an external runtime dependency; msrt does not
# import or redistribute it.
#
# Usage:
#   ./scripts/install-mitr.sh
#   ./scripts/install-mitr.sh --prefix "$HOME/tools/mitr"
#   ./scripts/install-mitr.sh --git-ref main
#   ./scripts/install-mitr.sh --dry-run

set -euo pipefail

PREFIX="${HOME}/tools/mitr"
GIT_URL="https://github.com/zyddnys/manga-image-translator.git"
GIT_REF="main"
PYTHON_VERSION="3.11"
DRY_RUN=0
WITH_RUSTY=0  # rusty-manga-image-translator wheel bug noto su macos-arm64; opt-in

usage() {
  cat <<'EOF'
Convenience installer for manga-image-translator (MITR).

MITR is GPL-3.0 and remains an external runtime dependency; msrt does not
import or redistribute it. The venv is pinned to Python 3.11 because MITR's
pyproject.toml requires Python >=3.10, <3.12.

Usage:
  ./scripts/install-mitr.sh
  ./scripts/install-mitr.sh --prefix "$HOME/tools/mitr"
  ./scripts/install-mitr.sh --git-ref v1.2.3
  ./scripts/install-mitr.sh --dry-run

Options:
  --prefix PATH       Install MITR venv + repo under PATH (default: $HOME/tools/mitr)
  --git-url URL       Git repository URL (default: zyddnys/manga-image-translator)
  --git-ref REF       Git ref/branch/tag to checkout (default: main)
  --python VERSION    Python version for the MITR venv (default: 3.11)
  --with-rusty        Include rusty-manga-image-translator (opt-in;
                      currently has a corrupted wheel on macos-arm64).
  --dry-run           Print commands without executing them
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
    --git-url)
      if [[ $# -lt 2 ]]; then
        echo "--git-url requires a value" >&2
        exit 2
      fi
      GIT_URL="$2"
      shift 2
      ;;
    --git-ref)
      if [[ $# -lt 2 ]]; then
        echo "--git-ref requires a value" >&2
        exit 2
      fi
      GIT_REF="$2"
      shift 2
      ;;
    --python)
      if [[ $# -lt 2 ]]; then
        echo "--python requires a value" >&2
        exit 2
      fi
      PYTHON_VERSION="$2"
      shift 2
      ;;
    --with-rusty)
      WITH_RUSTY=1
      shift
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

REPO_DIR="${PREFIX}/repo"
VENV_DIR="${PREFIX}/.venv"
PYTHON_BIN="${VENV_DIR}/bin/python"
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
if ! command -v git >/dev/null 2>&1; then
  echo "git not found. Install git first." >&2
  exit 1
fi

echo "Installing MITR external runtime"
echo "  prefix:  ${PREFIX}"
echo "  repo:    ${REPO_DIR}"
echo "  git:     ${GIT_URL}@${GIT_REF}"
echo "  python:  ${PYTHON_VERSION}"
echo

run mkdir -p "${PREFIX}"

if [[ ! -d "${REPO_DIR}/.git" ]]; then
  # Clone full (no --depth) perché GitHub non permette fetch shallow di
  # commit hash arbitrari (allowReachableSHA1InWant=false).
  run git clone "${GIT_URL}" "${REPO_DIR}"
fi
echo "Sync repo a ${GIT_REF}"
run git -C "${REPO_DIR}" fetch origin
run git -C "${REPO_DIR}" checkout --detach "${GIT_REF}"

CURRENT_PYTHON_VER="$("${PYTHON_BIN}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "missing")"
if [[ "${CURRENT_PYTHON_VER}" == "${PYTHON_VERSION}" ]]; then
  echo "Venv già presente con Python ${PYTHON_VERSION}, riuso"
else
  echo "Venv assente o con Python ${CURRENT_PYTHON_VER}; creo Python ${PYTHON_VERSION}"
  run uv venv --clear --python "${PYTHON_VERSION}" "${VENV_DIR}"
fi

REQ_FILE="${REPO_DIR}/requirements.txt"
if [[ "${WITH_RUSTY}" -eq 0 ]]; then
  FILTERED_REQ="$(mktemp -t mitr-req.XXXXXX)"
  trap 'rm -f "${FILTERED_REQ}"' EXIT
  echo "Filtro rusty-manga-image-translator (wheel rotto su macos-arm64; usa --with-rusty per includerlo)"
  if [[ "${DRY_RUN}" -eq 0 ]]; then
    grep -vE "^(--extra-index-url.*manga-image-translator-rust|rusty-manga-image-translator)" \
      "${REQ_FILE}" > "${FILTERED_REQ}"
  fi
  REQ_FILE="${FILTERED_REQ}"
fi
run uv pip install --python "${PYTHON_BIN}" --index-strategy unsafe-best-match -r "${REQ_FILE}"
# Editable install: il pyproject.toml di MITR non configura package discovery,
# quindi un install "normale" pubblica solo __init__.py e i sub-package
# (manga_translator.utils, ...) non vengono trovati. Editable mappa
# direttamente al repo, dove tutti i sub-package esistono.
run uv pip install --python "${PYTHON_BIN}" -e "${REPO_DIR}"

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
echo "  msrt doctor"
