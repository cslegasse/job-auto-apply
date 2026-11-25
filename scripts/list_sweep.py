#!/usr/bin/env python3
import json, re, os, sys, time, datetime, subprocess, http.cookiejar, urllib.request, urllib.parse

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUT_FILE = os.path.join(R, 'state', 'last_list_sweep.txt')
OUT = os.path.join(R, 'state', 'sweep', 'list_cands.json')
SLUGS = os.path.join(R, 'data', 'slug-candidates.txt')
UTC = datetime.timezone.utc
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/128 Safari/537.36'

SEEN_FILE = os.path.join(R, 'state', 'list_seen.json')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sweep_out import parse_ts, cutoff, save_cutoff, ssl_ctx, focus_ok, term_ok, title_term_ok, show

# Markdown lists. speedyapply links straight to the company's ATS. Zapply links go through a
# zapply.jobs redirect whose slug names the real req (greenhouse-<org>-<id>, ashby-<org>-<uuid>,
# lever-<org>-<uuid>), so we rebuild the company's own ATS URL and never send the user through zapply.
SPEEDY = [('speedyapply SWE', 'speedyapply/2026-SWE-College-Jobs'), ('speedyapply AI', 'speedyapply/2026-AI-College-Jobs')]
ZAPPLY = ('Zapply', 'zapplyjobs/New-Grad-Jobs-2027')
ZAPPLY_SECTIONS = re.compile(r'Software Engineering|Data, AI|Security Engineering|Hardware & Systems', re.I)
SIMPLIFY = [('Simplify new-grad', 'SimplifyJobs/New-Grad-Positions'), ('Simplify intern', 'SimplifyJobs/Summer2027-Internships')]
CONSIDER = [
    ('a16z', 'portfoliojobs.a16z.com', 'andreessen-horowitz'),
    ('Sequoia', 'jobs.sequoiacap.com', 'sequoia-capital'),
    ('Lightspeed', 'jobs.lsvp.com', 'lightspeed'),
    ('Kleiner Perkins', 'jobs.kleinerperkins.com', 'kleiner-perkins'),
    ('GV', 'jobs.gv.com', 'gv'),
    ('Bessemer', 'jobs.bvp.com', 'bessemer-ventures'),
]

S = json.load(open(os.path.join(R, 'config', 'settings.json')))
T, E = S['targets'], S['eligibility']
MAX_YEARS = T.get('max_years_experience_required', 1)
FLOOR = T.get('min_annual_comp_usd', 0)

BAD = re.compile(r'senior|\bsr\b|staff|principal|\blead\b|manager|director|head of|architect|\bII\b|\bIII\b|\bIV\b|sales|account exec|recruit|marketing|support|legal|counsel|finance|accountant|designer'
                 r'|solutions? engineer|value engineer|\bgtm\b|\bit engineer|customer|optical|electrical|solar|mechanical|hardware|design verification|\bpcb\b|\brf\b|ph\.?d|technician|test equipment|\[template\]', re.I)
SOFT = re.compile(r'data scien|data analyst|analytics engineer|security analyst|soc analyst|software|developer|engineer|machine learning|\bml\b|\bai\b|research|quant|infrastructure|platform|backend|full.?stack|forward.?deployed', re.I)
LOC_RULES = {
    'San Francisco Bay Area': r'San Francisco|\bSF\b|Bay Area|Palo Alto|Mountain View|Menlo Park|Redwood City|San Mateo|Sunnyvale|Santa Clara|San Jose|Oakland|Berkeley|Cupertino|Foster City|Emeryville|Burlingame|San Bruno',
    'New York': r'New York|\bNYC\b|Brooklyn|Manhattan',
    'Boston': r'Boston|Cambridge, MA|Somerville|Waltham|Burlington, MA|(?-i:,\s*MA\b)',
    'Chicago': r'Chicago',
    'Seattle': r'Seattle|Bellevue|Redmond|Kirkland',
    'Virginia': r'Virginia|Richmond|Arlington|Reston|McLean|Herndon|Tysons|Fairfax|Chantilly|Alexandria|Ashburn|Sterling|Vienna|Falls Church|Glen Allen|Henrico|(?-i:\bVA\b)',
    'Pittsburgh': r'Pittsburgh|Pennsylvania|(?-i:\bPA\b)',
    'Anywhere in US': r'United States|\bUSA?\b|(?-i:,\s*(AL|AK|AZ|AR|CA|CO|CT|DE|DC|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)\b)',
    'Remote (US)': r'Remote.{0,20}(US|U\.S\.|United States|USA)|(US|USA|United States).{0,5}Remote|^Remote$',
}
LOC = re.compile('|'.join(LOC_RULES[l] for l in T.get('locations', []) if l in LOC_RULES), re.I)

CUT, START, dry, args = cutoff(CUT_FILE, datetime.timedelta(days=3))
CTX = ssl_ctx()
def fetch(u, data=None, headers=None, opener=None):
    req = urllib.request.Request(u, data=json.dumps(data).encode() if data is not None else None,
                                 headers={'User-Agent': UA, **({'Content-Type': 'application/json'} if data is not None else {}), **(headers or {})})
    try:
        with (opener.open(req, timeout=30) if opener else urllib.request.urlopen(req, timeout=30, context=CTX)) as r:
            return r.read().decode('utf-8', 'ignore')
    except Exception as e:
        print(f'  ! {type(e).__name__} on {u[:80]}', file=sys.stderr); return ''

def norm(c): return re.sub(r'[^a-z0-9]', '', (c or '').lower())
blocked = {norm(c) for c in T.get('skip_companies', [])}
try:
    tr = subprocess.run([sys.executable, os.path.join(R, 'scripts', 'tracker_companies.py')], capture_output=True, text=True, timeout=60)
    blocked |= {norm(l) for l in tr.stdout.splitlines() if l.strip()}
except Exception: pass
def is_blocked(company):
    n = norm(company)
    return any(b and (n == b or n.startswith(b) or b.startswith(n)) for b in blocked)


rows, slugs_seen = [], set()
ATS_SLUG = re.compile(r'(?:job-boards|boards)(?:\.eu)?\.greenhouse\.io/([A-Za-z0-9_-]+)|jobs\.ashbyhq\.com/([A-Za-z0-9._-]+)|jobs\.lever\.co/([A-Za-z0-9._-]+)')
def harvest(url):
    m = ATS_SLUG.search(url or '')
    if m: slugs_seen.add(next(g for g in m.groups() if g))
def clean(url): return re.sub(r'[?&](utm_[^&]+|lever-source[^&]*|gh_src=[^&]+|ref=[^&]+)', '', url or '').rstrip('?&')

for label, repo in SIMPLIFY:
    try: listings = json.loads(fetch(f'https://raw.githubusercontent.com/{repo}/dev/.github/scripts/listings.json') or '[]')
    except Exception: listings = []
    if not listings: print(f'  ! {label}: empty feed', file=sys.stderr)
    for x in listings:
        if not x.get('active') or not x.get('is_visible', True): continue
        posted = datetime.datetime.fromtimestamp(x.get('date_posted', 0), UTC)
        if posted < CUT: continue
        url, t, co, locs = x.get('url', ''), x.get('title', ''), x.get('company_name', ''), '; '.join(x.get('locations') or [])
        harvest(url)
        sp = x.get('sponsorship', '') or ''
        if E.get('needs_visa_sponsorship') and re.search(r'does not offer|citizenship', sp, re.I): continue
        if not E.get('us_person_only_roles_ok', True) and re.search(r'citizenship', sp, re.I): continue
        degrees = x.get('degrees') or []
        if degrees and not any('bachelor' in d.lower() for d in degrees): continue
        if not SOFT.search(t) or BAD.search(t) or not focus_ok(t) or not LOC.search(locs) or is_blocked(co): continue
        if ('intern' in label and not term_ok(x.get('terms'))) or not title_term_ok(t): continue
        rows.append([label, co, posted.isoformat()[:10], t, locs[:80], '' if sp == 'Other' else sp, '', clean(url)])

try: SEEN = set(json.load(open(SEEN_FILE)))
except Exception: SEEN = set()
NEW_SEEN = set()
TAG = re.compile(r'<[^>]+>')
def k_dollars(s):
    m = re.findall(r'\$\s*([\d.]+)\s*([kK])?', s or '')
    return [float(v) * (1000 if k else 1) for v, k in m]
def keep(t, co, locs):
    return SOFT.search(t) and not BAD.search(t) and focus_ok(t) and LOC.search(locs) and not is_blocked(co) and title_term_ok(t)

for label, repo in SPEEDY:
    md = fetch(f'https://raw.githubusercontent.com/{repo}/master/NEW_GRAD_USA.md')
    if not md: print(f'  ! {label}: empty feed', file=sys.stderr); continue
    cols = []
    for line in md.splitlines():
        if not line.startswith('|'): continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if cells and cells[0] == 'Company': cols = cells; continue
        if not cols or not line.startswith('| <a') or len(cells) != len(cols): continue
        c = dict(zip(cols, cells))
        url = clean((re.search(r'href="([^"]+)"', c.get('Posting', '')) or [None, ''])[1])
        age = re.match(r'(\d+)d', c.get('Age', ''))
        if not url or not age: continue
        posted = (START - datetime.timedelta(days=int(age.group(1)))).replace(hour=0, minute=0, second=0, microsecond=0)
        if posted < CUT.replace(hour=0, minute=0, second=0, microsecond=0) or url in SEEN: continue
        NEW_SEEN.add(url); harvest(url)
        co, t, locs, sal = TAG.sub('', c.get('Company', '')), TAG.sub('', c.get('Position', '')), TAG.sub('', c.get('Location', '')), c.get('Salary', '')
        if not keep(t, co, locs): continue
        if '/yr' in sal and FLOOR and max(k_dollars(sal) or [FLOOR]) < FLOOR: continue
        rows.append([label, co, posted.isoformat()[:10], t, locs[:80], '', sal, url])

ZP_ROW = re.compile(r'^\| \*\*(?P<co>.+?)\*\* \| (?P<t>[^|]+) \| (?P<loc>[^|]*) \| (?P<age>[^|]*) \| [^|]* \| \[<img[^]]*\]\((?P<u>https://zapply\.jobs/l/d/[^)?]+)')
ZP_ATS = [
    (re.compile(r'greenhouse-(.+)-(\d{6,})$'), 'https://job-boards.greenhouse.io/{0}/jobs/{1}'),
    (re.compile(r'ashby-(.+)-([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$'), 'https://jobs.ashbyhq.com/{0}/{1}'),
    (re.compile(r'lever-(.+)-([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$'), 'https://jobs.lever.co/{0}/{1}'),
]
ZP_FOREIGN = re.compile(r'Canada|Toronto|Vancouver|Montreal|Ontario|London|United Kingdom|\bUK\b|India|Bengaluru|Bangalore|Hyderabad|Pune|Mexico|Brazil|Germany|Berlin|France|Paris|Ireland|Dublin|Poland|Israel|Singapore|Japan|China|Australia|Netherlands|Amsterdam|Spain|Philippines', re.I)
ZP_UNIT = {'m': 1 / 1440, 'h': 1 / 24, 'd': 1, 'w': 7, 'mo': 30}
def zp_ats(u):
    slug = u.rstrip('/').rsplit('/', 1)[-1]
    for rx, fmt in ZP_ATS:
        m = rx.match(slug)
        if m: return fmt.format(*m.groups())
    return None  # Workday, Oracle, iCIMS, Amazon, Apple...: account portals, out of scope
label, repo = ZAPPLY
md = fetch(f'https://raw.githubusercontent.com/{repo}/main/README.md')
if not md: print(f'  ! {label}: empty feed', file=sys.stderr)
section, zp_portal = '', 0
for line in md.splitlines():
    if '<summary>' in line: section = line; continue
    m = ZP_ROW.match(line)
    if not m or not ZAPPLY_SECTIONS.search(section): continue
    age = re.match(r'(\d+)(mo|m|h|d|w)\b', m.group('age').strip())
    if not age: continue
    posted = START - datetime.timedelta(days=int(age.group(1)) * ZP_UNIT[age.group(2)])
    if posted < CUT: continue
    url = zp_ats(m.group('u'))
    if not url: zp_portal += 1; continue
    if url in SEEN: continue
    NEW_SEEN.add(url); harvest(url)
    co, t, locs = m.group('co').strip(), m.group('t').strip(), m.group('loc').strip()
    if re.search(r'\bremote\b', t + ' ' + locs, re.I) and not re.search(r'remote', locs, re.I): locs += '; Remote'
    # Zapply is a US list but writes "California - San Francisco"; tag it US unless it names a foreign place.
    us = '' if ZP_FOREIGN.search(locs) else '; United States'
    if not re.search(r'intern|co-?op', t, re.I) and keep(t, co, locs + us):
        rows.append([label, co, posted.isoformat()[:10], t, locs[:80], '', '', url])
if zp_portal: print(f'  {label}: {zp_portal} rows on account portals (Workday/Oracle/etc.) skipped', file=sys.stderr)

for label, host, board in CONSIDER:
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), urllib.request.HTTPSHandler(context=CTX))
    page = fetch(f'https://{host}/jobs', opener=op)
    tok = re.search(r'"csrfToken":"([^"]+)"', page)
    if not tok: print(f'  ! {label}: no CSRF token', file=sys.stderr); continue
    seq, pages = None, 0
    while pages < 20:
        body = {'meta': {'size': 100, **({'sequence': seq} if seq else {})}, 'board': {'id': board, 'isParent': True}, 'query': {}, 'grouped': False}
        raw = fetch(f'https://{host}/api-boards/search-jobs', body, {'x-csrf-token': tok.group(1)}, op)
        try: d = json.loads(raw)
        except Exception: break
        jobs = d.get('jobs') or []
        if not jobs: break
        old = 0
        for j in jobs:
            posted = parse_ts(j.get('timeStamp', ''))
            if not posted or posted < CUT: old += 1; continue
            url, t, co = j.get('applyUrl') or j.get('url', ''), j.get('title', ''), j.get('companyName', '')
            harvest(url)
            locs = '; '.join(j.get('locations') or [])
            if j.get('remote') and re.search(r'United States|\bUSA?\b|North America', json.dumps([j.get('regions'), j.get('normalizedLocations')])):
                locs += '; Remote (US)'
            yrs = j.get('minYearsExp')
            sal = j.get('salary') or {}
            mx = sal.get('maxValue') if (sal.get('period') or {}).get('value') == 'year' else None
            if yrs is not None and yrs > MAX_YEARS: continue
            if not SOFT.search(t) or BAD.search(t) or not focus_ok(t) or not LOC.search(locs) or is_blocked(co) or not title_term_ok(t): continue
            if mx and FLOOR and mx < FLOOR and not re.search(r'intern', t, re.I): continue
            band = f"${sal.get('minValue', 0) // 1000}K-${mx // 1000}K" if mx else ''
            rows.append([label, co, posted.isoformat()[:10], t, locs[:80], '', band, clean(url)])
        if old == len(jobs): break
        seq = (d.get('meta') or {}).get('sequence'); pages += 1
        if not seq: break
        time.sleep(1)

seen, uniq = set(), []
for r in sorted(rows, key=lambda r: r[2], reverse=True):
    k = r[7].split('?')[0].rstrip('/').lower()
    if k in seen: continue
    seen.add(k); uniq.append(r)

known = set()
for f in (SLUGS, os.path.join(R, 'data', 'boards.md')):
    try: known |= set(re.findall(r'[A-Za-z0-9._-]+', open(f).read()))
    except Exception: pass
new_slugs = sorted(s for s in slugs_seen if s not in known)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(uniq, open(OUT, 'w'))
print(f'cutoff {CUT.isoformat()[:16]}Z  candidates {len(uniq)}  new ATS slugs {len(new_slugs)}  '
      f'(columns: source, company, posted, title, location, sponsorship, band, url)')
print('--- JUDGE EACH AGAINST targets.prestige_note, THEN APPLY THE USUAL DUPLICATE AND ELIGIBILITY CHECKS.')
show(['\t'.join(r) for r in uniq], os.path.splitext(OUT)[0] + '.tsv')
if not dry:
    json.dump(sorted(SEEN | NEW_SEEN), open(SEEN_FILE, 'w'))
    if new_slugs:
        with open(SLUGS, 'a') as f: f.write('\n'.join(new_slugs) + '\n')
    save_cutoff(CUT_FILE, START)
