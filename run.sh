#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
export PYTHONUTF8=1 
LOCK_DIR=".hourly-run.lock"

if [ $# -ge 1 ] && ! [ "$1" -ge 0 ] 2>/dev/null; then
  echo "Usage: ./run.sh [max_applications]   (a non-negative integer; omit to use config/settings.json)" >&2
  exit 2
fi

for f in config/settings.json config/profile.json config/answers.md; do
  [ -f "$f" ] || { echo "ERROR: $f is missing. Open Claude Code in this folder to run first-time setup." >&2; exit 1; }
done

if [ -x "$HOME/.local/bin/claude" ]; then
  CLAUDE_BIN="$HOME/.local/bin/claude"
elif command -v claude >/dev/null 2>&1; then
  CLAUDE_BIN="$(command -v claude)"
else
  echo "ERROR: claude binary not found (checked ~/.local/bin/claude and PATH)." >&2
  exit 127
fi

cfg() { python3 scripts/run_config.py --get "$@"; }

TRACKER_PATH="$(cfg run.interview_tracker_path)"
if [ -n "$TRACKER_PATH" ] && [ ! -r "$TRACKER_PATH" ]; then
  echo "ERROR: run.interview_tracker_path is set but not readable: $TRACKER_PATH" >&2
  echo "       Fix the path in config/settings.json and rerun. Nothing was applied." >&2
  exit 1
fi

MAX="${1:-$(cfg run.max_applications_per_run 3)}"
SETTINGS_PROMPT="$(python3 scripts/run_config.py "$MAX")"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  stale_pid="$(cat "$LOCK_DIR/pid" 2>/dev/null || true)"
  if [ -n "$stale_pid" ] && kill -0 "$stale_pid" 2>/dev/null; then
    printf 'Another run (pid %s) is active. Skipping this trigger.\n' "$stale_pid"
    exit 0
  fi
  printf 'Removing stale lock (pid %s no longer running).\n' "${stale_pid:-unknown}"
  rm -rf "$LOCK_DIR"
  mkdir "$LOCK_DIR" || { printf 'Could not acquire lock. Skipping.\n'; exit 0; }
fi
echo "$$" > "$LOCK_DIR/pid"
trap 'rm -rf "$LOCK_DIR" 2>/dev/null || true' EXIT

# Phase 1: sourcing in its own session, no browser. It only adds vetted [ ] rows to data/queue.md.
if [ "$(cfg run.queue_only False)" != "True" ]; then
  rm -f state/sweep/portal_by_hand.tsv
  SOURCE_PROMPT="Sourcing pass for the job application run in $(pwd). Fresh session: derive state from repository files. Do NOT open a browser and do NOT apply to anything; a separate session per queue row does the applying.

Load the source-jobs skill and follow it. CLAUDE.md is already in context; do not Read it.

RUN CONFIG (the target gate): ${SETTINGS_PROMPT}

Queue at most $((MAX * 3)) rows. Add one status line to state/status.md only if you learned something new about a board. Then stop."
  "$CLAUDE_BIN" -p --no-session-persistence --dangerously-skip-permissions "$SOURCE_PROMPT" || true
fi

# Phase 2: one fresh session per queue row, so context never carries earlier applications.
RUN_ID="$(date +%Y%m%d-%H%M%S)"
ROWS_FILE="state/run-$RUN_ID.rows"
mkdir -p state
: > "$ROWS_FILE"
rm -f state/chrome_down
export RUN_CONFIG="$SETTINGS_PROMPT"
submitted=0
while [ "$submitted" -lt "$MAX" ]; do
  ROW="$(python3 scripts/queue_row.py next)" || break
  APPLY_PROMPT="$(python3 scripts/queue_row.py prompt "$ROW")"
  "$CLAUDE_BIN" -p --chrome --no-session-persistence --dangerously-skip-permissions "$APPLY_PROMPT" || true
  if [ -f state/chrome_down ]; then
    echo "Chrome not connected: $(cat state/chrome_down). Stopping; row left pending." >&2
    break
  fi
  MARK="$(python3 scripts/queue_row.py status "$ROW")"
  if [ "$MARK" = " " ]; then
    python3 scripts/queue_row.py mark "$ROW" - "apply session ended without setting a status; check logs" || true
    MARK="-"
  fi
  printf '%s\t%s\n' "$MARK" "$ROW" >> "$ROWS_FILE"
  [ "$MARK" = "x" ] && submitted=$((submitted + 1))
done

# Phase 3: summary on top of the log and state/status.md, archive the log and finished queue rows.
python3 scripts/end_run.py "$ROWS_FILE"
rm -f "$ROWS_FILE"
