#!/usr/bin/env bash
# generate.sh — local Docker-based KiBot generation
#
# Usage:
#   ./scripts/generate.sh <project-path> <stage> [kibot-extra-args]
#
#   project-path  Path to the project directory, e.g. projects/example
#                 For single-project repos: .
#   stage         draft | review | release
#
# Environment variables:
#   KIBOT_IMAGE          Docker image to use (default: ghcr.io/inti-cern/kibot:dev)
#   KIBASE_PROJECTS_DIR  Override projects dir (default: projects; use . for single-project)
#
# Examples:
#   ./scripts/generate.sh projects/example draft
#   ./scripts/generate.sh projects/example review
#   ./scripts/generate.sh . release                  # single-project repo
#   ./scripts/generate.sh projects/example review -e KIRI_BASE=abc123

set -euo pipefail

KIBOT_IMAGE="${KIBOT_IMAGE:-ghcr.io/inti-cern/kibot:dev}"

# ── argument validation ─────────────────────────────────────────────────────
if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <project-path> <stage> [kibot-extra-args...]" >&2
  echo "  stage: draft | review | release" >&2
  exit 1
fi

PROJECT_PATH="${1%/}"
STAGE="$2"
shift 2
EXTRA_ARGS=("$@")

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KIBOT_CONFIG="/kibase/kibot/${STAGE}.yaml"
PROJECT_DIR_ABS="${REPO_ROOT}/${PROJECT_PATH}"
KICAD_DIR_ABS="${PROJECT_DIR_ABS}/kicad"

# ── validation ──────────────────────────────────────────────────────────────
if [[ ! -d "${PROJECT_DIR_ABS}" ]]; then
  echo "Error: project directory not found: ${PROJECT_DIR_ABS}" >&2
  exit 1
fi

if [[ ! "${STAGE}" =~ ^(draft|review|release)$ ]]; then
  echo "Error: stage must be one of: draft, review, release" >&2
  exit 1
fi

if [[ ! -d "${KICAD_DIR_ABS}" ]]; then
  echo "Error: kicad/ subdirectory not found in ${PROJECT_DIR_ABS}" >&2
  echo "  Expected: ${KICAD_DIR_ABS}" >&2
  exit 1
fi

# Find the .kicad_pro file inside kicad/
KICAD_PRO="$(find "${KICAD_DIR_ABS}" -maxdepth 1 -name '*.kicad_pro' | head -n1)"
if [[ -z "${KICAD_PRO}" ]]; then
  echo "Error: no .kicad_pro file found in ${KICAD_DIR_ABS}" >&2
  exit 1
fi
KICAD_PRO_FILE="$(basename "${KICAD_PRO}")"
PROJECT_NAME="${KICAD_PRO_FILE%.kicad_pro}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " kibase generate"
echo "  project : ${PROJECT_PATH}"
echo "  kicad/  : ${PROJECT_PATH}/kicad/${KICAD_PRO_FILE}"
echo "  stage   : ${STAGE}"
echo "  image   : ${KIBOT_IMAGE}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── pull image if not present ────────────────────────────────────────────────
if ! docker image inspect "${KIBOT_IMAGE}" &>/dev/null; then
  echo "Pulling ${KIBOT_IMAGE} ..."
  docker pull "${KIBOT_IMAGE}"
fi

# ── run KiBot ────────────────────────────────────────────────────────────────
mkdir -p "${PROJECT_DIR_ABS}/output"

docker run --rm \
  --user "$(id -u):$(id -g)" \
  --volume "${REPO_ROOT}:/kibase:ro" \
  --volume "${PROJECT_DIR_ABS}/output:/kibase/${PROJECT_PATH}/output" \
  --workdir "/kibase/${PROJECT_PATH}/kicad" \
  "${KIBOT_IMAGE}" \
  kibot \
    --board-file "/kibase/${PROJECT_PATH}/kicad/${PROJECT_NAME}.kicad_pcb" \
    --schematic "/kibase/${PROJECT_PATH}/kicad/${PROJECT_NAME}.kicad_sch" \
    --config "${KIBOT_CONFIG}" \
    --out-dir "/kibase/${PROJECT_PATH}/output" \
    "${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}"

echo ""
echo "Done. Output in: ${PROJECT_DIR_ABS}/output/"
