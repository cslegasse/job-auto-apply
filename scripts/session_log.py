#!/usr/bin/env python3
"""Per-session cost log for run.sh.

  session_log.py add <type> <row> <outcome> <start_epoch> <result.json | ->
      ('-' = no session started, e.g. a pre-gate skip)
      Append one row to logs/sessions.tsv from a `claude -p --output-format json` result,
      and print the session's `result` text to stdout (what `claude -p` used to print).
  session_log.py report
      Print logs/sessions.tsv as an aligned table.

Token fields stay separate (fresh input, 5m/1h cache writes, cache reads, output). The
weighted_usd column prices them per model from PRICES (USD per million tokens, from
https://platform.claude.com/docs/en/about-claude/pricing, read 2026-11-25). cli_usd is the
CLI's own total_cost_usd, kept as a cross-check.
"""
import json
import os
import sys
import time

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(R, 'logs', 'sessions.tsv')

# model id prefix -> (input, 5m write, 1h write, cache read, output) USD / MTok
PRICES = {
    'claude-opus-5-5': (4.00, 5.00, 8.00, 0.20, 20.00),
    'claude-sonnet-5-5': (2.00, 2.50, 4.00, 0.10, 10.00),
}

COLS = ['ts', 'type', 'outcome', 'wall_s', 'api_s', 'turns', 'models',
        'input', 'cache_write_5m', 'cache_write_1h', 'cache_read', 'output', 'thinking',
        'weighted_usd', 'cli_usd', 'is_error', 'row']


def price(model, mu):
    p = next((v for k, v in PRICES.items() if model.startswith(k)), None)
    if p is None:
        return None
    toks = (mu.get('inputTokens', 0), mu.get('cacheCreationEphemeral5mInputTokens', 0),
            mu.get('cacheCreationEphemeral1hInputTokens', 0), mu.get('cacheReadInputTokens', 0),
            mu.get('outputTokens', 0))
    return sum(t * r for t, r in zip(toks, p)) / 1e6


def add(kind, row, outcome, start, path):
    if path == '-':  # no session was started (pre-gate skip): zero tokens by construction
        d = {'is_error': False, 'result': ''}
    else:
        try:
            with open(path, encoding='utf-8') as f:
                d = json.load(f)
        except (OSError, ValueError) as e:
            d = {'is_error': True, 'result': f'(no JSON result: {e})'}
    mu = d.get('modelUsage') or {}
    tot = {k: 0 for k in ('inputTokens', 'cacheCreationEphemeral5mInputTokens',
                          'cacheCreationEphemeral1hInputTokens', 'cacheReadInputTokens',
                          'outputTokens', 'thinkingTokens')}
    usd = 0.0
    for model, u in mu.items():
        for k in tot:
            tot[k] += u.get(k, 0)
        c = price(model, u)
        usd = None if (usd is None or c is None) else usd + c
    vals = [time.strftime('%Y-%m-%d %H:%M:%S'), kind, outcome,
            str(int(time.time()) - int(start)), str(round(d.get('duration_api_ms', 0) / 1000)),
            str(d.get('num_turns', '')), ','.join(mu) or '-',
            *(str(tot[k]) for k in tot),
            'unpriced' if usd is None else f'{usd:.4f}',
            f"{d.get('total_cost_usd', 0):.4f}", str(d.get('is_error', '')),
            row.replace('\t', ' ')]
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    new = not os.path.exists(LOG)
    with open(LOG, 'a', encoding='utf-8') as f:
        if new:
            f.write('\t'.join(COLS) + '\n')
        f.write('\t'.join(vals) + '\n')
    print(d.get('result', ''))


def report():
    with open(LOG, encoding='utf-8') as f:
        rows = [l.rstrip('\n').split('\t') for l in f if l.strip()]
    w = [max(len(r[i]) if i < len(r) else 0 for r in rows) for i in range(len(rows[0]) - 1)]
    for r in rows:
        print('  '.join(c.ljust(w[i]) for i, c in enumerate(r[:-1])), ' ', r[-1][:80])


if __name__ == '__main__':
    if sys.argv[1:2] == ['add'] and len(sys.argv) == 7:
        add(*sys.argv[2:])
    elif sys.argv[1:2] == ['report']:
        report()
    else:
        sys.exit(__doc__)
