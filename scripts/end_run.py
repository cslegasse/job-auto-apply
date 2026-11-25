#!/usr/bin/env python3
"""End of run: summary, then archive the applications log and leave an empty one.

  end_run.py [rows_file]

rows_file (written by run.sh) has one "<marker>\t<row>" line per queue row this run touched.
With it, a summary block goes on top of the log and of state/status.md. Without it (interactive
runs), the log is archived as is: write the summary at its top first.
The log then moves to logs/archive/applications-log-<stamp>.md and logs/applications-log.md is
reset to its header, so the next run starts from an empty file. Finished queue rows ([x], [-]) move
from data/queue.md to logs/archive/queue-done.md so the queue every session reads stays small.
dupe_check.sh greps the archive.
"""
import datetime, os, re, sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(R, 'logs', 'applications-log.md')
ARCH = os.path.join(R, 'logs', 'archive')
STATUS = os.path.join(R, 'state', 'status.md')
BY_HAND = os.path.join(R, 'state', 'sweep', 'portal_by_hand.tsv')
QUEUE = os.path.join(R, 'data', 'queue.md')
DONE = re.compile(r'^\s*- \[[x-]\] ')
HEADER = ('# Applications log\n\n'
          'One line per application; full Q&A lives in applications/<company>-<role>.md.\n'
          'Earlier runs: logs/archive/ (scripts/dupe_check.sh searches it).\n')
NAMES = {'x': 'Submitted', '~': 'NEEDS HUMAN', '-': 'Skipped', ' ': 'Untouched'}


def read(p):
    try: return open(p, encoding='utf-8').read()
    except FileNotFoundError: return ''


def summary(rows_file, now):
    rows = [l.rstrip('\n').split('\t', 1) for l in open(rows_file, encoding='utf-8') if '\t' in l]
    out = [f'## Run summary {now:%Y-%m-%d %H:%M}']
    for mk in ('x', '~', '-', ' '):
        hit = [r for m, r in rows if m == mk]
        if hit:
            out.append(f'- {NAMES[mk]} ({len(hit)}):')
            out += [f'  - {r}' for r in hit]
    hand = [l for l in read(BY_HAND).splitlines() if l.strip()]
    if hand:
        out.append(f'- FOR YOU, BY HAND ({len(hand)}):')
        out += [f'  - {l}' for l in hand]
    return '\n'.join(out) + '\n'


def prepend(path, block, title):
    body = read(path)
    if body.startswith(title):
        head, _, rest = body.partition('\n')
        body = head + '\n\n' + block + '\n' + rest.lstrip('\n')
    else:
        body = block + '\n' + body
    open(path, 'w', encoding='utf-8').write(body)


def prune_queue(now):
    keep, done, in_done = [], [], False
    for l in read(QUEUE).split('\n'):
        if DONE.match(l):
            in_done = True
        elif not (in_done and l[:1] in (' ', '\t') and l.strip()):
            in_done = False   # indented lines right after a finished row belong to it
        (done if in_done else keep).append(l)
    if not done:
        return
    os.makedirs(ARCH, exist_ok=True)
    with open(os.path.join(ARCH, 'queue-done.md'), 'a', encoding='utf-8') as f:
        f.write(f'\n## Archived {now:%Y-%m-%d %H:%M}\n' + '\n'.join(done) + '\n')
    open(QUEUE, 'w', encoding='utf-8').write('\n'.join(keep))
    print(f'moved {len(done)} finished queue rows -> logs/archive/queue-done.md')


def main():
    now = datetime.datetime.now()
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        block = summary(sys.argv[1], now)
        prepend(LOG, block, '# Applications log')
        prepend(STATUS, block, '# Run status')
    log = read(LOG)
    if log.strip() and log.strip() != HEADER.strip():
        os.makedirs(ARCH, exist_ok=True)
        dest = os.path.join(ARCH, f'applications-log-{now:%Y-%m-%d-%H%M%S}.md')
        os.replace(LOG, dest)
        print('archived log ->', os.path.relpath(dest, R))
    open(LOG, 'w', encoding='utf-8').write(HEADER)
    print('logs/applications-log.md reset')
    prune_queue(now)


if __name__ == '__main__':
    main()
