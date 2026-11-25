#!/usr/bin/env python3
USAGE = """  queue_row.py next             first pending "- [ ]" row (exit 1 if none)
  queue_row.py status "<row>"   current marker of that row: " ", x, ~, -, or ? if gone
  queue_row.py mark "<row or URL>" <x|~|-> "<reason>"   set that row's marker, append the reason
  queue_row.py prompt "<row>"   prompts/apply_one.md filled in ($RUN_CONFIG used if set)
"""
import os, re, sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Q = os.path.join(R, 'data', 'queue.md')
ROW = re.compile(r'^(\s*- \[)(.)(\] )(.*)$')


def urls(text):
    return [u.rstrip('.,;)>') for u in re.findall(r'https?://\S+', text)]


def lines():
    return open(Q, encoding='utf-8').read().split('\n')


def find(row):
    u = urls(row)
    k = u[0] if u else None
    for i, l in enumerate(lines()):
        m = ROW.match(l)
        if m and ((k and k in urls(m.group(4))) or m.group(4).strip() == row.strip()):
            return i, m
    return None, None


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == 'next':
        for l in lines():
            m = ROW.match(l)
            if m and m.group(2) == ' ':
                print(m.group(4)); return 0
        return 1
    if cmd == 'status':
        _, m = find(args[0])
        print(m.group(2) if m else '?'); return 0
    if cmd == 'mark':
        if len(args) < 2: print(USAGE); return 2
        mk, reason = args[1], args[2] if len(args) > 2 else ''
        if mk not in ('x', '~', '-'): print('marker must be x, ~ or -'); return 2
        ls = lines(); i, m = find(args[0])
        if m is None: return 1
        label = {'x': 'SUBMITTED', '~': 'NEEDS HUMAN', '-': 'SKIP'}[mk]
        ls[i] = f'{m.group(1)}{mk}{m.group(3)}{m.group(4)}' + (f' {label}: {reason}' if reason else '')
        open(Q, 'w', encoding='utf-8').write('\n'.join(ls)); return 0
    if cmd == 'prompt':
        t = open(os.path.join(R, 'prompts', 'apply_one.md'), encoding='utf-8').read()
        cfg = os.environ.get('RUN_CONFIG') or 'Run python3 scripts/run_config.py and obey its output.'
        print(t.replace('{{ROW}}', args[0]).replace('{{RUN_CONFIG}}', cfg)); return 0
    print(USAGE); return 2


if __name__ == '__main__':
    sys.exit(main())
