#!/usr/bin/env bash
# detect-changed-projects.sh — list project directories that changed
# between two git SHAs.
#
# Usage (CI):
#   ./scripts/detect-changed-projects.sh $CI_COMMIT_BEFORE_SHA $CI_COMMIT_SHA
#
# Usage (local, compare working tree to HEAD):
#   ./scripts/detect-changed-projects.sh HEAD
#
# Environment variables:
#   KIBASE_PROJECTS_DIR   Directory containing projects (default: projects)
#                         Set to "." for single-project repos — always outputs
#                         the project name found in kicad/*.kicad_pro.
#
# Output: one project name per line
# Exit code 1 if no projects changed

set -euo pipefail

PROJECTS_DIR="${KIBASE_PROJECTS_DIR:-projects}"
BEFORE="${1:-}"
AFTER="${2:-HEAD}"

if [[ -z "${BEFORE}" ]]; then
  echo "Usage: $0 <before-sha> [<after-sha>]" >&2
  exit 1
fi

NULL_SHA="0000000000000000000000000000000000000000"
if [[ "${BEFORE}" == "${NULL_SHA}" ]]; then
  DEFAULT_BRANCH="${CI_DEFAULT_BRANCH:-main}"
  BEFORE="$(git merge-base "${DEFAULT_BRANCH}" "${AFTER}" 2>/dev/null || echo "${AFTER}^")"
fi

# Single-project mode: repo root is the project
if [[ "${PROJECTS_DIR}" == "." ]]; then
  # Check if any relevant files changed (kicad/ subdir or root project files)
  CHANGED="$(git diff --name-only "${BEFORE}" "${AFTER}" 2>/dev/null \
    | grep -E '^(kicad/|design/|simulation/)' || true)"
  if [[ -z "${CHANGED}" ]]; then
    exit 1
  fi
  # Project name comes from the .kicad_pro filename
  KICAD_PRO="$(find kicad/ -maxdepth 1 -name '*.kicad_pro' 2>/dev/null | head -n1)"
  if [[ -z "${KICAD_PRO}" ]]; then
    echo "Error: no .kicad_pro found in kicad/" >&2
    exit 1
  fi
  basename "${KICAD_PRO}" .kicad_pro
  exit 0
fi

# Monorepo mode
CHANGED="$(git diff --name-only "${BEFORE}" "${AFTER}" 2>/dev/null \
  | grep "^${PROJECTS_DIR}/" \
  | cut -d/ -f2 \
  | sort -u)"

if [[ -z "${CHANGED}" ]]; then
  exit 1
fi

echo "${CHANGED}"
