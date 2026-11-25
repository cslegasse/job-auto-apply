#!/usr/bin/env bash
set -uo pipefail

cd "$(dirname "$0")/.."
mkdir -p logs

{
  printf '\n=== Scheduled run: %s ===\n' "$(date '+%Y-%m-%d %H:%M:%S %Z')"
  ./run.sh
  status=$?
  printf '=== Session exited with status %s ===\n' "$status"
} >> logs/scheduled-run.log 2>&1

exit "$status"
