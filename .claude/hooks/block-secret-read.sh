#!/bin/bash
input=$(cat)
block() {
  echo "Blocked by .claude/hooks/block-secret-read.sh: the agent never reads the Keychain, clipboard or vault directly. Use scripts/code_broker.py." >&2
  exit 2
}
if printf '%s' "$input" | grep -Eqi 'find-(generic|internet)-password|dump-keychain|export-keychain|pbpaste|generalPasteboard|NSPasteboard|stringForType|get the clipboard|clipboard info|Get-Clipboard|Clipboard\]::Get|GetClipboardData|clip\.exe -o|broker_secret|CryptUnprotect|Unprotect\(|BW_SESSION|\bbw (get|export|unlock|list)\b|\bop (read|item get)\b'; then
  block
fi
# code_broker.py may only run as a program (fetch/check/selftest print no secret). Importing it, or
# loading it with runpy/importlib/exec, reaches app_password() and puts the Gmail password in context.
if printf '%s' "$input" | grep -Eq 'code_broker'; then
  rest=$(printf '%s' "$input" | sed -E 's#scripts[/\\]+code_broker\.py##g')
  if printf '%s' "$rest" | grep -Eq 'code_broker' \
    || printf '%s' "$input" | grep -Eqi 'runpy|importlib|exec\(|execfile|SourceFileLoader|spec_from_file|compile\('; then
    block
  fi
fi
exit 0
