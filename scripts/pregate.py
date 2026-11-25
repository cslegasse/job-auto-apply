#!/usr/bin/env python3
import glob
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(R, 'logs', 'applications-log.md')
ENTRY = re.compile(r'^(?:- |#+ )\[(\d{4}-\d\d-\d\d)[^\]]*\] (.+?) — (.+?) — ([A-Z][A-Z ]+)')


def cfg(key, default):
    try:
        out = subprocess.run([sys.executable, os.path.join(R, 'scripts', 'run_config.py'), '--get', key],
                             capture_output=True, text=True, timeout=30).stdout.strip()
        return out or default
    except Exception:
        return default


def req_id(url):
    for pat in (r'jobs\.ashbyhq\.com/[^/?#]+/([0-9a-f-]{36})', r'jobs\.lever\.co/[^/]+/([0-9a-f-]{36})',
                r'greenhouse\.io/.*?(?:/jobs/|token=)(\d+)', r'gh_jid=(\d+)'):
        m = re.search(pat, url, re.I)
        if m:
            return m.group(1)
    return None


def submitted_entries():
    files = [LOG] + sorted(glob.glob(os.path.join(R, 'logs', 'archive', 'applications-log-*.md')))
    out = []
    for f in files:
        try:
            lines = open(f, encoding='utf-8').read().split('\n')
        except OSError:
            continue
        cur = None
        for line in lines:
            m = ENTRY.match(line)
            if m:
                if cur:
                    out.append(cur)
                cur = None
                if m.group(4).strip().startswith('SUBMITTED'):
                    cur = [m.group(1), m.group(2).strip(), m.group(3).strip(), line]
            elif cur is not None:
                if line.startswith(('- [', '#')):
                    out.append(cur); cur = None
                else:
                    cur[3] += '\n' + line
        if cur:
            out.append(cur)
    return out


def text(s):
    s = html.unescape(html.unescape(s or ''))
    s = re.sub(r'<(br|/p|/li|/h\d|/div)[^>]*>', '\n', s, flags=re.I)
    s = re.sub(r'<[^>]+>', '', s)
    return re.sub(r'\n\s*\n+', '\n', re.sub(r'[ \t\xa0]+', ' ', s)).strip()


def posting(url):
    def get(u):
        return json.loads(urllib.request.urlopen(
            urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'}), timeout=20).read())
    try:
        m = re.search(r'jobs\.ashbyhq\.com/([^/?#]+)/([0-9a-f-]{36})', url, re.I)
        if m:
            d = get(f'https://api.ashbyhq.com/posting-api/job-board/{m.group(1)}?includeCompensation=true')
            j = next((j for j in d.get('jobs', []) if j.get('id', '').lower() == m.group(2).lower()), None)
            if not j:
                return 'closed', {}
            comp = (j.get('compensation') or {}).get('compensationTierSummary')
            return 'live', {'title': j.get('title'), 'location': j.get('location'), 'compensation': comp,
                            'workplace': j.get('workplaceType'), 'description': text(j.get('descriptionHtml'))
                            or j.get('descriptionPlain')}
        m = re.search(r'greenhouse\.io/(?:embed/job_app\?for=)?([\w-]+)(?:/jobs/|&token=)(\d+)', url)
        if m:
            j = get(f'https://boards-api.greenhouse.io/v1/boards/{m.group(1)}/jobs/{m.group(2)}?pay_transparency=true')
            pay = [f"{p.get('title') or ''} {p.get('min_cents', 0) // 100}-{p.get('max_cents', 0) // 100} "
                   f"{p.get('currency_type') or ''}".strip() for p in j.get('pay_input_ranges') or []]
            return 'live', {'title': j.get('title'), 'location': (j.get('location') or {}).get('name'),
                            'compensation': '; '.join(pay) or None, 'description': text(j.get('content'))}
        m = re.search(r'jobs\.lever\.co/([^/]+)/([0-9a-f-]{36})', url)
        if m:
            j = get(f'https://api.lever.co/v0/postings/{m.group(1)}/{m.group(2)}')
            lists = '\n'.join(f"{x.get('text')}\n{text(x.get('content'))}" for x in j.get('lists') or [])
            sal = j.get('salaryRange') or {}
            return 'live', {'title': j.get('text'), 'location': (j.get('categories') or {}).get('location'),
                            'compensation': f"{sal.get('min')}-{sal.get('max')} {sal.get('currency')} "
                                            f"{sal.get('interval')}" if sal else None,
                            'workplace': j.get('workplaceType'),
                            'description': '\n'.join(filter(None, [j.get('descriptionPlain'), lists,
                                                                   j.get('additionalPlain')]))}
    except urllib.error.HTTPError as e:
        return ('closed' if e.code == 404 else 'unknown'), {}
    except Exception:
        return 'unknown', {}
    return 'unknown', {}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    row = sys.argv[1]
    parts = [p.strip() for p in row.split(' | ')]
    company = parts[0]
    role = parts[1] if len(parts) > 1 else '?'
    urls = [u.rstrip('.,;)>') for u in re.findall(r'https?://\S+', row)]
    url = urls[0] if urls else ''
    rid = req_id(url) if url else None
    reason = None
    found = {'row': row, 'company': company, 'role': role, 'url': url, 'req_id': rid, 'checks': {}}
    chk = found['checks']

    dc = subprocess.run(['bash', os.path.join(R, 'scripts', 'dupe_check.sh'), company] + ([rid] if rid else []),
                        capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=R)
    found['dupe_check'] = {'exit': dc.returncode, 'output': dc.stdout.strip()[-3000:]}
    if dc.returncode == 3:
        reason = 'company is in the interview tracker (dupe_check exit 3)'
    chk['interview_tracker'] = 'hit' if reason else 'pass'

    subs = submitted_entries() if not reason else []
    mine = [e for e in subs if e[1].lower() == company.lower()]
    if not reason and rid:
        hit = next((e for e in subs if rid in {req_id(u) for u in re.findall(r'https?://\S+', e[3])}), None)
        if hit:
            reason = f'same req {rid} already SUBMITTED {hit[0]}'
        chk['same_req'] = 'hit' if hit else 'pass'
    if not reason:
        cap = int(cfg('run.max_applications_per_company_lifetime', '2'))
        roles = {' '.join(re.sub(r'\([^)]*\)', ' ', e[2]).lower().split()) for e in mine}
        if len(roles) >= cap:
            reason = f'lifetime cap reached ({len(roles)} of {cap} for {company})'
        chk['lifetime_cap'] = f'{len(roles)} of {cap} (exact name)'
    if not reason and cfg('run.same_day_company_freeze', 'True') == 'True':
        today = time.strftime('%Y-%m-%d')
        if any(e[0] == today for e in mine):
            reason = f'same-day freeze: {company} already SUBMITTED today'
        chk['same_day_freeze'] = 'hit' if reason else 'pass (exact name)'
    if not reason and url:
        status, data = posting(url)
        chk['posting'] = status
        found['posting'] = data
        if status == 'closed':
            reason = 'posting closed (ATS API)'
    if not reason and url:
        fs = subprocess.run([sys.executable, os.path.join(R, 'scripts', 'form_schema.py'), url],
                            capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=R)
        found['form_schema'] = {'exit': fs.returncode, 'output': fs.stdout.strip()}

    found['verdict'] = f'SKIP: {reason}' if reason else 'pass'
    os.makedirs(os.path.join(R, 'state'), exist_ok=True)
    with open(os.path.join(R, 'state', 'pregate.json'), 'w', encoding='utf-8') as f:
        json.dump(found, f, indent=1, ensure_ascii=False)
    if not reason:
        return 0
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(f"- [{time.strftime('%Y-%m-%d %H:%M')}] {company} — {role} — SKIPPED — "
                f"{url or '-'} — pre-gate: {reason}\n")
    print(f'pre-gate: {reason}')
    return 10


if __name__ == '__main__':
    sys.exit(main())
