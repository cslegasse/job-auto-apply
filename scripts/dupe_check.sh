#!/bin/bash
set -uo pipefail
cd "$(dirname "$0")/.."
[ $# -ge 1 ] || { echo "usage: $0 \"<Company Name>\" [req-or-job-id]" >&2; exit 2; }
NAME="$1"; REQ="${2:-}"
MAXL="${DUPE_MAX_LINES:-12}"
hit=0
sec () { printf '\n=== %s ===\n' "$1"; }
show () {
  local out n
  out="$(grep "$@" 2>/dev/null)"
  [ -n "$out" ] || return 1
  n=$(printf '%s\n' "$out" | wc -l)
  printf '%s\n' "$out" | head -n "$MAXL" | cut -c1-300
  [ "$n" -gt "$MAXL" ] && echo "... $((n - MAXL)) more lines"
  return 0
}

TRACKER="$(python3 scripts/run_config.py --get run.interview_tracker_path 2>/dev/null)"
if [ -n "$TRACKER" ] && [ -f "$TRACKER" ]; then
  FIRST="${NAME%% *}"
  PAT="$NAME"; [ ${#FIRST} -ge 4 ] && PAT="$FIRST"
  sec "INTERVIEW TRACKER — grep \"$PAT\""
  if show -in -- "$PAT" "$TRACKER"; then
    echo
    echo "★★★ \"$NAME\" is in your interview tracker. HARD SKIP. Do not open a tab, do not count, do not ask."
    exit 3
  fi
  echo "(not in tracker)"
elif [ -n "$TRACKER" ]; then
  echo "WARNING: run.interview_tracker_path is set but the file is missing: $TRACKER" >&2
fi

sec "logs/applications-log.md + logs/archive/ (incl. queue-done.md)"
show -rin -- "$NAME" logs/applications-log.md logs/archive/ && hit=1

sec "data/queue.md (pending and needs-human rows)"
show -in -- "$NAME" data/queue.md && hit=1

sec "state/status.md"
show -in -- "$NAME" state/status.md && hit=1

sec "data/boards.md + data/ats-field-notes.md — 'AT THE CAP' verdicts, limits, reset dates"
show -in -- "$NAME" data/boards.md data/ats-field-notes.md && hit=1

DASH="$(echo "$NAME" | tr ' ' '-')"; JOIN="$(echo "$NAME" | tr -d ' ')"
sec "applications/ + screenshots/ filenames"
{ ls applications; ls screenshots; } 2>/dev/null | show -i -e "$DASH" -e "$JOIN" && hit=1

if [ -n "$REQ" ]; then
  sec "req/job id \"$REQ\""
  show -rin --exclude-dir=sweep --exclude=queue.md -- "$REQ" logs/ data/ state/ applications/ && hit=1
fi

printf '\n'
if [ "$hit" -eq 1 ]; then
  echo "★ HITS FOUND for \"$NAME\". Count prior applications, match the role TITLE and the req id,"
  echo "  and look for any 'AT THE CAP' / 'spent' / 'one role only' verdict before applying."
  exit 1
fi
echo "No record of \"$NAME\" anywhere. Clean."
