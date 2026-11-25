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
# Cost: only the Chrome MCP server (stable cached prefix), and no interactive startup skills.
HEADLESS_NOTE="Headless run.sh session: no human is present. Do not invoke the caveman-mode or grill-me skills; keep replies to one line."
# project,local drops user plugins/hooks/MCP but also the user's model + effort, so pin those.
# --tools is variadic: the prompt must come before these flags.
CLAUDE_FLAGS=(--no-session-persistence --dangerously-skip-permissions --strict-mcp-config
  --setting-sources project,local
  --tools Bash,Read,Write,Edit,Grep,Glob,Skill,ToolSearch,Monitor,TaskStop
  --append-system-prompt "$HEADLESS_NOTE" --output-format json)
# Model and effort per session type; judge a change by cost per submit in logs/sessions.tsv.
SOURCE_FLAGS=(--model opus --effort medium)
# --max-turns is accepted by CLI 2.1.332 though --help omits it. Past submit sessions: p99 48, max 51.
APPLY_FLAGS=(--model opus --effort medium --max-turns 60)
# Sourcing runs only when the queue is low: fewer pending rows than run.queue_floor (default 2 x MAX).
QUEUE_FLOOR="$(cfg run.queue_floor $((MAX * 2)))"
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
PENDING="$(grep -c '^- \[ \]' data/queue.md 2>/dev/null || true)"
if [ "$(cfg run.queue_only False)" = "True" ]; then
  :
elif [ "${PENDING:-0}" -ge "$QUEUE_FLOOR" ]; then
  echo "Sourcing skipped: $PENDING pending rows >= queue floor $QUEUE_FLOOR."
else
  rm -f state/sweep/portal_by_hand.tsv
  mkdir -p state
  SOURCE_PROMPT="Sourcing pass for the job application run in $(pwd). Fresh session: derive state from repository files. Do NOT open a browser and do NOT apply to anything; a separate session per queue row does the applying.

Load the source-jobs skill and follow it. CLAUDE.md is already in context; do not Read it.

RUN CONFIG (the target gate): ${SETTINGS_PROMPT}

Queue at most $((MAX * 3)) rows. Add one status line to state/status.md only if you learned something new about a board. Then stop."
  start=$(date +%s)
  "$CLAUDE_BIN" -p "$SOURCE_PROMPT" "${CLAUDE_FLAGS[@]}" "${SOURCE_FLAGS[@]}" > state/session.json || true
  python3 scripts/session_log.py add source "-" done "$start" state/session.json || true
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
  start=$(date +%s)
  # Deterministic gates first: a row that fails one never starts a session.
  PGRC=0; PG="$(python3 scripts/pregate.py "$ROW")" || PGRC=$?
  if [ "$PGRC" -eq 10 ]; then
    echo "$PG"
    python3 scripts/queue_row.py mark "$ROW" - "${PG#pre-gate: } (pre-gate)" || true
    python3 scripts/session_log.py add pregate "$ROW" - "$start" - || true
    printf '%s\t%s\n' "-" "$ROW" >> "$ROWS_FILE"
    continue
  fi
  APPLY_PROMPT="$(python3 scripts/queue_row.py prompt "$ROW")"
  "$CLAUDE_BIN" -p "$APPLY_PROMPT" --chrome "${CLAUDE_FLAGS[@]}" "${APPLY_FLAGS[@]}" > state/session.json || true
  LOGMARK="$(python3 scripts/queue_row.py status "$ROW" || echo '?')"
  [ "$LOGMARK" = " " ] && LOGMARK=unmarked
  LOGTYPE=apply; [ "$LOGMARK" = "-" ] && LOGTYPE=skip
  python3 scripts/session_log.py add "$LOGTYPE" "$ROW" "$LOGMARK" "$start" state/session.json || true
  if [ -f state/chrome_down ]; then
    echo "Chrome not connected: $(cat state/chrome_down). Stopping; row left pending." >&2
    break
  fi
  MARK="$(python3 scripts/queue_row.py status "$ROW")"
  if [ "$MARK" = " " ] && grep -q '"subtype": *"error_max_turns"' state/session.json 2>/dev/null; then
    # Turn cap hit mid-form: the tab may still be open and the form part-filled. A human checks it.
    python3 - "$ROW" <<'PY' || true
import re, sys, time
row = sys.argv[1]; p = [x.strip() for x in row.split(' | ')]
url = (re.findall(r'https?://\S+', row) or ['-'])[0]
with open('logs/applications-log.md', 'a', encoding='utf-8') as f:
    f.write(f"- [{time.strftime('%Y-%m-%d %H:%M')}] {p[0]} — {p[1] if len(p) > 1 else '?'} — NEEDS HUMAN — "
            f"{url} — turn cap hit; tab may be left open in the Claude tab group, submit status unknown, check it\n")
PY
    python3 scripts/queue_row.py mark "$ROW" '~' "turn cap hit (--max-turns); check the open tab" || true
    MARK="~"
  elif [ "$MARK" = " " ]; then
    python3 scripts/queue_row.py mark "$ROW" - "apply session ended without setting a status; check logs" || true
    MARK="-"
  fi
  printf '%s\t%s\n' "$MARK" "$ROW" >> "$ROWS_FILE"
  [ "$MARK" = "x" ] && submitted=$((submitted + 1))
done

# Phase 3: summary on top of the log and state/status.md, archive the log and finished queue rows.
python3 scripts/end_run.py "$ROWS_FILE"
rm -f "$ROWS_FILE"
