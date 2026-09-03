#!/usr/bin/env bash
# scripts/sync-agy-cli.sh — Sync or verify agy_cli Python files between REPO and LIVE.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/../agy_cli" && pwd)"
LIVE_DIR="${HOME}/.config/bridge/agy_cli"

if [[ "${1:-}" == "--check" ]]; then
    if [[ ! -d "${LIVE_DIR}" ]]; then
        echo "ERROR: Live directory ${LIVE_DIR} does not exist." >&2
        exit 1
    fi
    drift=0
    for f in "${REPO_DIR}"/*.py; do
        b="$(basename "$f")"
        if [[ ! -f "${LIVE_DIR}/${b}" ]]; then
            echo "DRIFT: ${b} missing in LIVE directory" >&2
            drift=1
        elif ! cmp -s "$f" "${LIVE_DIR}/${b}"; then
            echo "DRIFT: ${b} differs between REPO and LIVE" >&2
            diff -u "$f" "${LIVE_DIR}/${b}" || true
            drift=1
        fi
    done
    for f in "${LIVE_DIR}"/*.py; do
        b="$(basename "$f")"
        if [[ ! -f "${REPO_DIR}/${b}" ]]; then
            echo "DRIFT: ${b} exists in LIVE but missing in REPO" >&2
            drift=1
        fi
    done
    if [[ $drift -ne 0 ]]; then
        echo "FAIL: Drift detected between ${REPO_DIR} and ${LIVE_DIR}." >&2
        exit 1
    fi
    echo "OK: All agy_cli *.py files are byte-identical between REPO and LIVE."
    exit 0
fi

echo "Installing agy_cli Python files from REPO -> LIVE (${LIVE_DIR})..."
mkdir -p "${LIVE_DIR}"
cp -f "${REPO_DIR}"/*.py "${LIVE_DIR}/"
echo "Sync complete."
