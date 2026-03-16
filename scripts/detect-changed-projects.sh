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
# Output: one project name per line (the directory name under projects/)
# Returns exit code 1 if no projects changed (useful for conditional CI steps).

set -euo pipefail

BEFORE="${1:-}"
AFTER="${2:-HEAD}"

if [[ -z "${BEFORE}" ]]; then
  echo "Usage: $0 <before-sha> [<after-sha>]" >&2
  exit 1
fi

# When BEFORE is the null SHA (first push to a branch), diff against the
# merge base with the default branch instead.
NULL_SHA="0000000000000000000000000000000000000000"
if [[ "${BEFORE}" == "${NULL_SHA}" ]]; then
  DEFAULT_BRANCH="${CI_DEFAULT_BRANCH:-main}"
  BEFORE="$(git merge-base "${DEFAULT_BRANCH}" "${AFTER}" 2>/dev/null || echo "${AFTER}^")"
fi

CHANGED="$(git diff --name-only "${BEFORE}" "${AFTER}" 2>/dev/null \
  | grep '^projects/' \
  | cut -d/ -f2 \
  | sort -u)"

if [[ -z "${CHANGED}" ]]; then
  exit 1
fi

echo "${CHANGED}"
