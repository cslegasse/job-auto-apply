
import html
import json
import re
import sys
import urllib.request

UA = {'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json'}
FREE = {'LongText', 'textarea', 'String', 'input_text', 'text'}
STANDARD = re.compile(r'^(name|first name|last name|full name|email|phone|resume|resume/cv|cover letter|linkedin.*|'
                      r'website|github.*|portfolio.*|current company|current location|location|preferred first name)$', re.I)

ASHBY_Q = ('query ApiJobPosting($organizationHostedJobsPageName: String!, $jobPostingId: String!) { '
           'jobPosting(organizationHostedJobsPageName: $organizationHostedJobsPageName, jobPostingId: $jobPostingId) '
           '{ title applicationForm { sections { fieldEntries { ... on FormFieldEntry { field isRequired } } } } } }')


def fetch(url, data=None):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data else None, headers=UA)
    return urllib.request.urlopen(req, timeout=20).read().decode('utf-8', 'replace')


def ashby(org, jid):
    d = json.loads(fetch('https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobPosting',
                         {'operationName': 'ApiJobPosting', 'query': ASHBY_Q,
                          'variables': {'organizationHostedJobsPageName': org, 'jobPostingId': jid}}))
    p = d['data']['jobPosting']
    rows = []
    for s in p['applicationForm']['sections']:
        for e in s['fieldEntries']:
            f = e.get('field') or {}
            opts = [v.get('label') for v in f.get('selectableValues') or []]
            rows.append((e.get('isRequired'), f.get('type'), f.get('title'), opts))
    return p['title'], rows


def greenhouse(org, jid):
    d = json.loads(fetch(f'https://boards-api.greenhouse.io/v1/boards/{org}/jobs/{jid}?questions=true'))
    rows = []
    for q in (d.get('questions') or []) + (d.get('location_questions') or []):
        f = (q.get('fields') or [{}])[0]
        opts = [v.get('label') for v in f.get('values') or []]
        rows.append((q.get('required'), f.get('type'), q.get('label'), opts))
    for block in (d.get('compliance') or []) + (d.get('demographic_questions') or {}).get('questions', []):
        for q in block.get('questions', [block]):
            rows.append((q.get('required'), 'eeo', q.get('label') or q.get('description', '')[:60], []))
    return d.get('title'), rows


def lever(org, jid):
    page = fetch(f'https://jobs.lever.co/{org}/{jid}/apply')
    rows = [(True, 'std', lab, []) for lab in ('Resume/CV', 'Full name', 'Email', 'Phone')]
    for raw in re.findall(r'name="cards\[[^"]+\]\[baseTemplate\]"\s+value="([^"]+)"|'
                          r'value="([^"]+)"\s+name="cards\[[^"]+\]\[baseTemplate\]"', page):
        card = json.loads(html.unescape(raw[0] or raw[1]))
        for f in card.get('fields', []):
            opts = [o.get('text') for o in f.get('options') or []]
            rows.append((f.get('required'), f.get('type'), f.get('text'), opts))
    title = re.search(r'<h2>([^<]+)</h2>', page)
    return (html.unescape(title.group(1)) if title else '?'), rows


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    url = sys.argv[1] if len(sys.argv) > 1 else ''
    m_a = re.search(r'jobs\.ashbyhq\.com/([^/?#]+)/([0-9a-f-]{36})', url, re.I)
    m_g = re.search(r'greenhouse\.io/(?:embed/job_app\?for=)?([\w-]+)(?:/jobs/|&token=)(\d+)', url)
    m_l = re.search(r'jobs\.lever\.co/([^/]+)/([0-9a-f-]{36})', url)
    try:
        if m_a:
            title, rows = ashby(*m_a.groups())
        elif m_g:
            title, rows = greenhouse(*m_g.groups())
        elif m_l:
            title, rows = lever(*m_l.groups())
        else:
            print('unsupported URL: use form_text.js in the browser'); return 2
    except Exception as e:
        print(f'endpoint failed ({e}): use form_text.js in the browser'); return 2
    print(f'# {title}  ({len(rows)} fields)')
    free = 0
    for req, typ, label, opts in rows:
        label = re.sub(r'\s+', ' ', label or '').strip()
        mark = 'REQ' if req else 'opt'
        if req and typ in FREE and not STANDARD.match(label):
            mark, free = 'FREE', free + 1
        o = f"  [{' / '.join(x for x in opts[:6] if x)}{' ...' if len(opts) > 6 else ''}]" if opts else ''
        print(f'{mark:4} {typ or "?":10} {label[:160]}{o}')
    print(f'# {free} required free-text question(s): each needs a preset or fact in answers.md')
    return 0


if __name__ == '__main__':
    sys.exit(main())
