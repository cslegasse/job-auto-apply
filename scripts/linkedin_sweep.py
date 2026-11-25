#!/usr/bin/env python3
import datetime, html, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sweep_out import focus_ok

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUT_FILE = os.path.join(R, 'state', 'last_linkedin_sweep.txt')
OUT = os.path.join(R, 'state', 'sweep', 'linkedin_cands.json')
UTC = datetime.timezone.utc
DEADLINE = 420
LOCATIONS = {
    'Virginia': 'Virginia, United States',
    'Pittsburgh': 'Pittsburgh, Pennsylvania, United States',
    'New York': 'New York, United States',
    'Seattle': 'Seattle, Washington, United States',
    'San Francisco Bay Area': 'San Francisco Bay Area',
    'Chicago': 'Chicago, Illinois, United States',
}
QUERY = ('("new grad" OR "entry level" OR "entry-level" OR "new graduate" OR associate OR junior) '
         '("software engineer" OR "software developer" OR "full stack developer" OR "backend developer" OR '
         '"frontend developer" OR "application developer" OR "IT developer" OR "AI engineer" OR '
         '"machine learning engineer" OR "ML engineer" OR "data engineer" OR "systems engineer" OR "QA engineer" OR '
         '"test engineer" OR "web developer" OR programmer)')
SOFT_TITLE = re.compile(r'security analyst|soc analyst|security engineer|analytics engineer|data analyst|forward.?deploy|deployed (?:\w+ )?engineer|software|developer|programmer|full.?stack|front.?end|back.?end|\bweb\b|application|\bapps?\b|data (?:engineer|scientist)|machine learning|\bml\b|\bai\b|robotics|\bqa\b|sdet|\btest(?:ing)? engineer|systems engineer|devops|automation engineer|\bit developer|systems analyst|technical solutions|applications? analyst|implementation (?:engineer|analyst)', re.I)
def skip_title_re(terms):
    return re.compile('|'.join(r'\b' + re.escape(t) + r'\b' for t in terms), re.I) if terms else None
YEARS = re.compile(r'(?<!\d)(\d{1,2})(?!\d)\s*\+?\s*(?:-|to|–)?\s*\d{0,2}\s*\+?\s*years?\b(?!\s*(?:of age|old))[^.]{0,60}?experience', re.I)
ANY_CLEARANCE = re.compile(r'security clearance|TS/SCI|top secret|secret clearance|clearance (?:is )?required|(?:obtain|eligible for)[^.;]{0,30}clearance|polygraph', re.I)
ACTIVE_CLEARANCE = re.compile(r'(active|current|must (?:hold|have|possess))[^;:]{0,40}?(clearance|TS\s*(?:/|and|&)\s*SCI|top secret)', re.I)
UA = {'User-Agent': 'Mozilla/5.0'}

def text_of(page):
    return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', page)))

def req_years(t):
    for m in YEARS.finditer(t):
        if int(m.group(1)) < 20: return int(m.group(1))
    return None

def needs_active_clearance(t):
    return bool(ACTIVE_CLEARANCE.search(t))

def mentions_clearance(t):
    t = re.sub(r'(?:security )?clearance (?:type|status|level)?:?\s*(?:none|not required)[^.]*', '', t, flags=re.I)
    return bool(ANY_CLEARANCE.search(t))

def get(url):
    for wait in (10, 30, 60, None):
        try: return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20).read().decode('utf-8', 'ignore')
        except urllib.error.HTTPError as e:
            if e.code != 429 or wait is None: raise
            time.sleep(wait)

def selftest():
    assert req_years('BS with 4+ years’ industry experience') == 4
    assert req_years('0-1 years of hands-on experience in scripting') == 0
    assert req_years('3+ years of non-internship professional software development experience 1+ years of Object Oriented Design experience') == 3
    assert req_years('Raytheon brings more than 100 years of experience. a minimum of 2 years of prior relevant experience') == 2
    assert req_years('Bachelor degree. Experience with Java.') is None
    assert req_years("Are 18 years of age or older Bachelor's degree or equivalent Experience with at least one language") is None
    assert needs_active_clearance('This position requires an active U.S. Top Secret Security Clearance')
    assert needs_active_clearance('Bachelor’s Degree Active TS and SCI eligible')
    assert needs_active_clearance('must hold an active government Secret security clearance')
    assert needs_active_clearance('Active TS/SCI security clearance.')
    assert not needs_active_clearance('Ability to obtain a Secret clearance')
    assert not needs_active_clearance('obtain and maintain a security clearance at the TS/SCI level')
    assert not needs_active_clearance('Must have experience with TS and React')
    assert not needs_active_clearance('must have experience with secret management in Vault')
    assert not needs_active_clearance('Current students with TypeScript (TS) skills')
    assert mentions_clearance('Ability to obtain a Secret clearance')
    assert mentions_clearance('must be able to obtain and maintain a security clearance')
    assert not mentions_clearance('Security Clearance Type: None/Not Required Security Clearance Status: Not Required')
    assert not mentions_clearance('Experience with secret management in Vault and AWS')
    for title in ('Software Engineer, Entry Level', 'Engineer - AI Delivery (high-potential program)', 'Full Stack Developer', 'Junior Web Developer', 'QA Engineer', 'Entry-Level Technical Solutions Engineer', 'Systems Analyst - Intermediate', 'Application Analyst I'):
        assert SOFT_TITLE.search(title), title
    for title in ('Operations Engineer', 'Early Career Field Service Engineer, Power & Water Solutions', 'Tele-Infectious Disease', 'Licensing Engineer (early career)', 'Mechanical Design Engineer', 'IT Support Specialist - Level 1', 'Payroll, Benefits & Expenses Coordinator'):
        assert not SOFT_TITLE.search(title), title
    sk = skip_title_re(['cloud', 'aws', 'azure'])
    for title in ('AWS Cloud Infrastructure Experienced Associate', 'Cloud Engineer I', 'Junior Azure Developer'):
        assert sk.search(title), title
    assert not sk.search('Software Engineer, Payments') and skip_title_re([]) is None
    print('selftest ok')

def main():
    sys.stdout.reconfigure(encoding='utf-8')  # the PARTIAL marker is a star; Windows consoles default to cp1252
    args = sys.argv[1:]
    if '--selftest' in args: return selftest()
    S = json.load(open(os.path.join(R, 'config', 'settings.json')))
    T = S['targets']
    skip = [c.lower() for c in T.get('skip_companies', [])]
    skip_any_clearance = T.get('skip_any_clearance', False)
    query = T.get('linkedin_query') or QUERY
    skip_title = skip_title_re(T.get('skip_title_terms', []))
    t0, ok = time.time(), True
    now = datetime.datetime.now(UTC)
    if '--hours' in args:
        since, advance = now - datetime.timedelta(hours=float(args[args.index('--hours') + 1])), False
    elif os.path.exists(CUT_FILE):
        since, advance = datetime.datetime.fromisoformat(open(CUT_FILE).read().strip().replace('Z', '+00:00')), True
    else:
        since, advance = now - datetime.timedelta(hours=24), True
    window = max(3600, int((now - since).total_seconds()))
    locs = [(l, LOCATIONS[l]) for l in T.get('locations', []) if l in LOCATIONS]
    print(f'window {window // 3600}h  locations {[l for l, _ in locs]}')

    cards = {}
    for label, loc in locs:
        for start in range(0, 250, 25):
            if time.time() - t0 > DEADLINE: ok = False; break
            q = urllib.parse.urlencode({'keywords': query, 'location': loc, 'f_TPR': f'r{window}', 'sortBy': 'DD', 'start': start})
            try: page = get('https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?' + q)
            except Exception as e: print('search error', label, start, e); ok = False; break
            got = 0
            for card in page.split('<li>')[1:]:
                g = lambda p: html.unescape(re.sub(r'\s+', ' ', (re.search(p, card, re.S) or [None, ''])[1])).strip()
                jid = g(r'jobPosting:(\d+)')
                if not jid: continue
                got += 1
                if jid not in cards:
                    cards[jid] = dict(id=jid, title=g(r'base-search-card__title">(.*?)<'), company=g(r'base-search-card__subtitle">.*?>(.*?)<'),
                                      location=g(r'job-search-card__location">(.*?)<'), posted=g(r'datetime="(.*?)"'),
                                      ago=g(r'<time[^>]*>(.*?)</time>'), area=label)
            time.sleep(2)
            if got < 10: break

    rows = []
    for c in cards.values():
        if not SOFT_TITLE.search(c['title']) or not focus_ok(c['title']) or (skip_title and skip_title.search(c['title'])) or any(s in c['company'].lower() for s in skip): continue
        if time.time() - t0 > DEADLINE: ok = False; break
        try: page = get(f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{c['id']}")
        except Exception as e: print('detail error', c['id'], e); continue
        t = text_of(page)
        time.sleep(3)
        yrs = req_years(t)
        if needs_active_clearance(t): continue
        if skip_any_clearance and mentions_clearance(t): continue
        pay = re.search(r'\$\s?[\d,]{5,}(?:\.\d+)?\s*(?:-|to|–)\s*\$?\s?[\d,]{5,}', t)
        c.update(years='?' if yrs is None else yrs, pay=pay.group(0) if pay else '',
                 apply='company-site' if 'offsite-apply' in page else 'easy-apply',
                 url=f"https://www.linkedin.com/jobs/view/{c['id']}")
        rows.append(c)

    rows.sort(key=lambda c: (c['apply'] != 'company-site', c['area'], c['posted']), reverse=False)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(rows, open(OUT, 'w'), indent=1)
    print(f'{len(cards)} cards, {len(rows)} after software-title and clearance filters  {time.time() - t0:.0f}s'
          + ('' if ok else '  ★ PARTIAL (deadline or search errors); cutoff NOT advanced'))
    from sweep_out import show
    show(['\t'.join(str(c[k]) for k in ('area', 'ago', 'company', 'title', 'location', 'years', 'pay', 'apply', 'url')) for c in rows],
         os.path.splitext(OUT)[0] + '.tsv')
    if advance and ok:
        open(CUT_FILE, 'w').write(now.isoformat(timespec='minutes').replace('+00:00', 'Z') + '\n')

if __name__ == '__main__':
    main()
