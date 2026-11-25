#!/usr/bin/env python3
import json, re, os, sys, time, datetime, urllib.request, urllib.parse

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUT_FILE = os.path.join(R, 'state', 'last_portal_sweep.txt')
OUT = os.path.join(R, 'state', 'sweep', 'portal_cands.json')
UTC = datetime.timezone.utc

WORKDAY = [
    ('Nvidia', 'nvidia', 'wd5', 'NVIDIAExternalCareerSite', 'nvidia.wd5.myworkdayjobs.com'),
    ('Salesforce', 'salesforce', 'wd12', 'External_Career_Site', 'salesforce.wd12.myworkdayjobs.com'),
    ('Intel', 'intel', 'wd1', 'External', 'intel.wd1.myworkdayjobs.com'),
    ('Arrowstreet', 'arrowstreetcapital', 'wd5', 'Campus_Careers', 'arrowstreetcapital.wd5.myworkdayjobs.com'),
    ('G-Research', 'gresearch', 'wd103', 'G-Research', 'gresearch.wd103.myworkdayjobs.com'),
    ('Capital One', 'capitalone', 'wd12', 'Capital_One', 'capitalone.wd12.myworkdayjobs.com'),
    ('Mastercard', 'mastercard', 'wd1', 'Campus', 'mastercard.wd1.myworkdayjobs.com'),
    ('Mastercard', 'mastercard', 'wd1', 'CorporateCareers', 'mastercard.wd1.myworkdayjobs.com'),
]
OPEN_PORTALS = {'www.deshaw.com', 'explore.jobs.netflix.net', 'career.mlp.com', 'jobs.uber.com', 'www.rentec.com'}
AMAZON_QUERIES = ['software development engineer', 'software engineer university', 'sde 2027']
WORKDAY_QUERIES = ['new college grad software', 'new college graduate software engineer', 'software engineer intern 2027']

NEWGRAD = re.compile(r'\b(I|1)\b|university|grad|2027|entry|associate|development program|early career|campus|new college|intern', re.I)
BAD = re.compile(r'senior|\bsr\b|principal|\blead\b|manager|director|architect|\bII\b|\bIII\b|hardware|asic|fpga|verification|\bqa\b|quality assurance|test engineer|sales|support', re.I)
SOFT = re.compile(r'data scien|data analyst|analytics engineer|security analyst|soc analyst|software|developer|engineer|machine learning|\bml\b|\bai\b', re.I)
US = re.compile(r'\bUS\b|United States|, (WA|CA|NY|IL|TX|MA|VA|PA|AZ|CO)\b', re.I)

from sweep_out import parse_ts, cutoff, save_cutoff, ssl_ctx, focus_ok, title_term_ok, show

CUT, START, dry, args = cutoff(CUT_FILE, datetime.timedelta(days=7))
CTX = ssl_ctx()

def get(u, data=None, retry=True):
    req = urllib.request.Request(u, data=json.dumps(data).encode() if data is not None else None,
                                 headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json', 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=25, context=CTX) as r: return json.load(r)
    except urllib.error.HTTPError as e:
        if retry and (e.code == 429 or e.code >= 500):
            time.sleep(5); return get(u, data, retry=False)
        print(f'  ! HTTPError {e.code} on {u[:80]}', file=sys.stderr); return None
    except Exception as e:
        print(f'  ! {type(e).__name__} on {u[:80]}', file=sys.stderr); return None

SEEN_FILE = os.path.join(R, 'state', 'sweep', 'portal_seen.json')
try: SEEN = json.load(open(SEEN_FILE))
except Exception: SEEN = {}
def get_text(u):
    req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/128 Safari/537.36'})
    try:
        with urllib.request.urlopen(req, timeout=25, context=CTX) as r: return r.read().decode('utf-8', 'ignore')
    except Exception as e:
        print(f'  ! {type(e).__name__} on {u[:80]}', file=sys.stderr); return ''
def new_id(portal, jid):
    s = SEEN.setdefault(portal, [])
    if jid in s: return False
    s.append(jid); return True

try:
    signed = set(json.load(open(os.path.join(R, 'config', 'settings.json'))).get('channels', {}).get('signed_in_portals', []))
except Exception: signed = set()

rows = []

seen = set()
for q in AMAZON_QUERIES:
    for offset in (0, 100, 200):
        u = ('https://www.amazon.jobs/en/search.json?' + urllib.parse.urlencode({'base_query': q, 'country[]': 'USA',
             'result_limit': 100, 'offset': offset, 'sort': 'recent', 'category[]': 'software-development'}))
        d = get(u)
        if not d or not d.get('jobs'): break
        stop = False
        for j in d['jobs']:
            try: posted = datetime.datetime.strptime(j.get('posted_date', ''), '%B %d, %Y').replace(tzinfo=UTC)
            except Exception: continue
            if posted < CUT: stop = True; continue
            if j['id_icims'] in seen: continue
            seen.add(j['id_icims'])
            t = j.get('title', '')
            if NEWGRAD.search(t) and not BAD.search(t) and US.search(j.get('location', '') or ''):
                rows.append(['Amazon', 'amazon.jobs', posted.isoformat()[:10], t, j.get('location', ''), 'https://www.amazon.jobs' + j.get('job_path', '')])
        if stop: break
        time.sleep(1)

REL = re.compile(r'Posted (Today|Yesterday|(\d+)\+? Days? Ago)', re.I)
def wd_date(s):
    m = REL.search(s or '')
    if not m: return None
    if m.group(1).lower() == 'today': days = 0
    elif m.group(1).lower() == 'yesterday': days = 1
    else: days = int(m.group(2))
    return START - datetime.timedelta(days=days)
for label, tenant, wd, site, host in WORKDAY:
    seen = set()
    for q in WORKDAY_QUERIES:
        for offset in (0, 20, 40):
            d = get(f'https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs', {'appliedFacets': {}, 'limit': 20, 'offset': offset, 'searchText': q})
            if not d or not d.get('jobPostings'): break
            for j in d['jobPostings']:
                posted = wd_date(j.get('postedOn'))
                if not posted or posted < CUT: continue
                path = j.get('externalPath', '')
                if path in seen: continue
                seen.add(path)
                t = j.get('title', ''); loc = j.get('locationsText', '') or ''
                if NEWGRAD.search(t) and not BAD.search(t) and SOFT.search(t) and (US.search(loc) or ('Locations' in loc and path.startswith('/job/US'))):
                    rows.append([label, host, posted.isoformat()[:10], t, loc, f'https://{tenant}.{wd}.myworkdayjobs.com/en-US/{site}{path}'])
            time.sleep(1)

import html as _html
GOOGLE_QUERIES = ['"software engineer" "university graduate"', '"software engineer" "early career"', '"software engineer" "new grad"']
for q in GOOGLE_QUERIES:
    u = 'https://www.google.com/about/careers/applications/jobs/results/?' + urllib.parse.urlencode({'q': q, 'location': 'United States', 'sort_by': 'date'})
    page = get_text(u)
    for c in re.split(r'<li class="lLd3Je"', page)[1:]:
        jid = re.search(r"ssk='\d+:(\d+)'", c); title = re.search(r'<h3 class="QJPWVe">([^<]+)</h3>', c)
        if not jid or not title: continue
        tt = _html.unescape(title.group(1)); loc = '; '.join(_html.unescape(re.sub(r'<[^>]+>', '', s)) for s in re.findall(r'<span class="r0wTof">(.*?)</span>', c))
        if NEWGRAD.search(tt) and not BAD.search(tt) and new_id('google', jid.group(1)):
            rows.append(['Google', 'www.google.com', 'new', tt, loc or 'United States', f'https://www.google.com/about/careers/applications/jobs/results/{jid.group(1)}'])
    time.sleep(1)

page = get_text('https://www.deshaw.com/careers/choose-your-path/campus-candidates')
for m in re.finditer(r'"id":(\d+),"displayName":"([^"]+)","jobUrl":"([^"]+)"', page):
    jid, tt, slug = m.group(1), _html.unescape(m.group(2)), m.group(3)
    tail = page[m.end():m.end() + 6000]
    offices = ', '.join(re.findall(r'"name":"([^"]+)"', tail.split('"header"')[0])) if '"office"' in tail else ''
    nxt = tail.find('"displayName"'); seg = tail[:nxt] if nxt > 0 else tail
    js = re.search(r'"jobSeekerCategoriesString":"([^"]*)"', seg)
    campus = bool(js and 'Student' in js.group(1))
    if campus and re.search(r'software|developer|engineer', tt, re.I) and not re.search(r'intern|ph\.?d|senior|lead|london|all positions', tt, re.I) and (not offices or 'New York' in offices):
        if new_id('deshaw', jid):
            rows.append(['D. E. Shaw', 'www.deshaw.com', 'new', tt, offices or 'New York', f'https://www.deshaw.com/careers/{slug.lower()}'])

page = get_text('https://careers.twosigma.com/careers/InternshipsAndEarlyCareers')
for u, slug, jid in sorted(set(re.findall(r'href="(https://careers\.twosigma\.com/careers/JobDetail/([^"/]+)/(\d+))"', page))):
    tt = slug.replace('-', ' ')
    if re.search(r'software|engineer|developer', tt, re.I) and not re.search(r'intern|hardware|ph ?d', tt, re.I) and re.search(r'united states', tt, re.I):
        if new_id('twosigma', jid):
            rows.append(['Two Sigma', 'careers.twosigma.com', 'new', tt, 'see title', u])

US_STATES = re.compile(r'United States|\bUSA?\b|California|Washington|New York|Texas|Massachusetts|Illinois|Oregon|Colorado|Georgia|North Carolina|Virginia|Pennsylvania|Arizona|Florida|Remote', re.I)
def keep(t, loc):
    return NEWGRAD.search(t) and not BAD.search(t) and SOFT.search(t) and (US.search(loc or '') or US_STATES.search(loc or ''))
def ts_date(ts):
    try: return datetime.datetime.fromtimestamp(int(ts), UTC)
    except Exception: return None

for label, host, domain in [('Microsoft', 'apply.careers.microsoft.com', 'microsoft.com'), ('Qualcomm', 'careers.qualcomm.com', 'qualcomm.com')]:
    for q in ['university', 'intern', 'college graduate', 'new grad']:
        d = get(f'https://{host}/api/pcsx/search?' + urllib.parse.urlencode({'domain': domain, 'query': q, 'location': 'United States', 'start': 0}))
        for p in ((d or {}).get('data') or {}).get('positions') or []:
            posted = ts_date(p.get('postedTs')); loc = '; '.join(p.get('locations') or [])
            if posted and posted >= CUT and keep(p.get('name', ''), loc) and new_id(label.lower(), str(p['id'])):
                rows.append([label, host, posted.isoformat()[:10], p['name'].lstrip('#'), loc, f"https://{host}{p.get('positionUrl') or '/careers/job/' + str(p['id'])}"])
        time.sleep(3)

for label, host, domain in [('Netflix', 'explore.jobs.netflix.net', 'netflix.com'), ('Millennium', 'career.mlp.com', 'mlp.com')]:
    d = get(f'https://{host}/api/apply/v2/jobs?' + urllib.parse.urlencode({'domain': domain, 'query': 'software engineer', 'location': 'United States', 'num': 100, 'sort_by': 'timestamp'}))
    for p in (d or {}).get('positions') or []:
        posted = ts_date(p.get('t_create')); t = p.get('name', ''); loc = p.get('location', '')
        ok = keep(t, loc) if label == 'Netflix' else (re.search(r'software|developer', t, re.I) and not BAD.search(t) and US.search(loc))
        if posted and posted >= CUT and ok and new_id(label.lower(), str(p['id'])):
            rows.append([label, host, posted.isoformat()[:10], t, loc, f'https://{host}/careers/apply?pid={p["id"]}&domain={domain}'])

for q in ['software engineer new college grad', 'software engineer intern', 'software engineer university']:
    d = get('https://careers.amd.com/api/jobs?' + urllib.parse.urlencode({'keywords': q, 'location': 'United States', 'limit': 50, 'sortBy': 'posted_date', 'descending': 'true'}))
    for j in (d or {}).get('jobs') or []:
        j = j.get('data', {}); posted = parse_ts(re.sub(r'([+-]\d\d)(\d\d)$', r'\1:\2', j.get('posted_date', '') or ''))
        if posted and posted >= CUT and keep(j.get('title', ''), j.get('full_location', '')) and new_id('amd', str(j.get('req_id'))):
            rows.append(['AMD', 'careers-amd.icims.com', posted.isoformat()[:10], j['title'], j.get('full_location', ''), f"https://careers.amd.com/careers-home/jobs/{j['req_id']}"])
    time.sleep(1)

for q in ['software engineer', 'new grad', 'intern']:
    u = ('https://iaziqy.fa.ocs.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions?onlyData=true&expand=requisitionList'
         f'&finder=findReqs;siteNumber=UberCareers,keyword=%22{urllib.parse.quote(q)}%22,limit=50,sortBy=POSTING_DATES_DESC')
    d = get(u)
    for x in (((d or {}).get('items') or [{}])[0].get('requisitionList') or []):
        posted = parse_ts((x.get('PostedDate') or '') + 'T00:00:00Z')
        if posted and posted >= CUT and keep(x.get('Title', ''), x.get('PrimaryLocation', '')) and new_id('uber', str(x['Id'])):
            rows.append(['Uber', 'jobs.uber.com', posted.isoformat()[:10], x['Title'], x.get('PrimaryLocation', ''), f"https://jobs.uber.com/en/jobs/{x['Id']}/"])
    time.sleep(1)

for team in ['internships-STDNT-INTRN']:
    page = get_text('https://jobs.apple.com/en-us/search?' + urllib.parse.urlencode({'team': team, 'sort': 'newest', 'location': 'united-states-USA'}))
    for jid, slug in sorted(set(re.findall(r'details/([0-9A-Z-]+)/([a-z0-9-]+)', page))):
        tt = slug.replace('-', ' ')
        if NEWGRAD.search(tt) and not BAD.search(tt) and SOFT.search(tt) and new_id('apple', jid):
            rows.append(['Apple', 'jobs.apple.com', 'new', tt, 'United States', f'https://jobs.apple.com/en-us/details/{jid}/{slug}'])
    time.sleep(1)

for q in ['software engineer', 'internship', '2027']:
    page = get_text('https://bloomberg.avature.net/careers/SearchJobs/' + urllib.parse.quote(q) + '?listFilterMode=1&jobRecordsPerPage=50')
    for slug, jid in sorted(set(re.findall(r'JobDetail/([^"/?]+)/(\d+)', page))):
        tt = slug.replace('-', ' ')
        if NEWGRAD.search(tt) and not BAD.search(tt) and SOFT.search(tt) and not re.search(r'london|singapore|tokyo|hong kong|frankfurt', tt, re.I) and new_id('bloomberg', jid):
            rows.append(['Bloomberg', 'bloomberg.avature.net', 'new', tt, 'see posting', f'https://bloomberg.avature.net/careers/JobDetail/{slug}/{jid}'])
    time.sleep(1)

page = get_text('https://www.rentec.com/Careers.action?jobs=true')
for pos in sorted(set(re.findall(r'selectedPosition=([A-Za-z]+)', page))):
    tt = re.sub(r'(?<!^)([A-Z])', r' \1', pos).title()
    if re.search(r'programmer|engineer', tt, re.I) and not re.search(r'network|security|systems|devops|data center', tt, re.I) and new_id('rentec', pos):
        rows.append(['Renaissance', 'www.rentec.com', 'new', tt, 'East Setauket / New York', f'https://www.rentec.com/Careers.action?jobs=true&selectedPosition={pos}'])

dropped = [r for r in rows if not title_term_ok(r[3])]
rows = [r for r in rows if title_term_ok(r[3]) and focus_ok(r[3])]

os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(rows, open(OUT, 'w'))
print(f'cutoff {CUT.isoformat()[:16]}Z  candidates {len(rows)} ({len(dropped)} dropped: season outside the start window)  signed-in portals: {sorted(signed) or "none"}')
ok_hosts = signed | OPEN_PORTALS
agent = [r for r in rows if r[1] in ok_hosts]; alex = [r for r in rows if r[1] not in ok_hosts]
if agent:
    print('--- AGENT MAY APPLY (signed-in portal, or a no-account portal in OPEN_PORTALS):')
    show(['\t'.join(r) for r in sorted(agent)], os.path.join(os.path.dirname(OUT), 'portal_agent.tsv'))
show(['\t'.join(r) for r in sorted(alex)], os.path.join(os.path.dirname(OUT), 'portal_by_hand.tsv'), head=0)
print(f'--- FOR YOU, BY HAND: {len(alex)} rows in state/sweep/portal_by_hand.tsv (scripts/end_run.py copies them into the run summary)')
if not dry:
    json.dump(SEEN, open(SEEN_FILE, 'w'))
    save_cutoff(CUT_FILE, START)
