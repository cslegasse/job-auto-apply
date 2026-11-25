#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.."

REPO="$(pwd -P)"
TAG="# job-auto-apply:$REPO"
FREQ="$(python3 -c "import json;print(json.load(open('config/settings.json')).get('schedule',{}).get('frequency','manual'))" 2>/dev/null)"

case "$FREQ" in
  hourly)        SPEC="0 * * * *" ;;
  every-2-hours) SPEC="0 */2 * * *" ;;
  every-3-hours) SPEC="0 */3 * * *" ;;
  every-6-hours) SPEC="0 */6 * * *" ;;
  daily)         SPEC="0 9 * * *" ;;
  weekdays)      SPEC="0 9 * * 1-5" ;;
  *)             SPEC="" ;;
esac

without_ours() { crontab -l 2>/dev/null | grep -vF "$TAG"; }

case "${1:-status}" in
  install)
    [ -z "$SPEC" ] && { echo "schedule.frequency is '$FREQ'. Set it in config/settings.json first."; exit 0; }
    line="$SPEC cd \"$REPO\" && /bin/bash scripts/scheduled_run.sh $TAG"
    ( without_ours; echo "$line" ) | crontab -
    echo "Installed cron entry ($FREQ):"
    echo "  $line"
    echo "Log: $REPO/logs/scheduled-run.log"
    ;;
  uninstall)
    without_ours | crontab -
    echo "Removed the cron entry for this folder (if there was one)."
    ;;
  status)
    echo "Frequency: $FREQ  (config/settings.json -> schedule.frequency)"
    crontab -l 2>/dev/null | grep -F "$TAG" || echo "Not scheduled."
    ;;
  *) echo "Usage: $0 [install|uninstall|status]"; exit 1 ;;
esac
