#!/usr/bin/env python3
import json, re, sys

LINK = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")

def names(text):
    seen, out = set(), []
    for m in LINK.finditer(text):
        n = m.group(1).strip()
        if n and n.lower() not in seen:
            seen.add(n.lower()); out.append(n)
    return out

def main():
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        path = json.load(open("config/settings.json")).get("run", {}).get("interview_tracker_path", "")
    if not path:
        return 0
    try:
        text = open(path, encoding="utf-8").read()
    except OSError as e:
        print(f"ERROR: interview tracker unreadable: {path} ({e})", file=sys.stderr)
        return 1
    for n in names(text):
        print(n)
    return 0

if __name__ == "__main__":
    sys.exit(main())
