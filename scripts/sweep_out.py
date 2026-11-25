import datetime, json, os, re, ssl, sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UTC = datetime.timezone.utc
HEAD = int(os.environ.get('SWEEP_HEAD', '30'))

try:
    SETTINGS = json.load(open(os.path.join(R, 'config', 'settings.json'), encoding='utf-8'))
except Exception:
    SETTINGS = {}


def show(lines, path, head=HEAD):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + ('\n' if lines else ''))
    for l in lines[:head]:
        print(l)
    if len(lines) > head:
        print(f'... {len(lines) - head} more rows in {path} (grep it; do not cat it)')


def parse_ts(s):
    try:
        d = datetime.datetime.fromisoformat(s.strip().replace('Z', '+00:00'))
        return d if d.tzinfo else d.replace(tzinfo=UTC)
    except Exception:
        return None


def cutoff(cut_file, default):
    args = sys.argv[1:]
    since = args[args.index('--since') + 1] if '--since' in args else None
    start = datetime.datetime.now(UTC)
    if since:
        raw = since
    elif os.path.exists(cut_file):
        raw = open(cut_file).read()
    else:
        return start - default, start, '--dry' in args, args
    cut = parse_ts(raw)
    if not cut:
        sys.exit(f'bad cutoff (want ISO UTC like 2026-09-15T04:00Z): {raw!r}')
    return cut.astimezone(UTC), start, '--dry' in args, args


def save_cutoff(cut_file, when):
    with open(cut_file, 'w') as f:
        f.write(when.isoformat(timespec='minutes').replace('+00:00', 'Z') + '\n')


def ssl_ctx():
    try:
        import certifi
        cafiles = [certifi.where()]
    except Exception:
        cafiles = []
    for cafile in cafiles + ['/etc/ssl/cert.pem']:
        if os.path.exists(cafile):
            try:
                return ssl.create_default_context(cafile=cafile)
            except Exception:
                pass
    return ssl.create_default_context()


_FOCUS = (SETTINGS.get('targets') or {}).get('title_focus') or ''
FOCUS = re.compile(_FOCUS, re.I) if _FOCUS else None


def focus_ok(title):
    return not FOCUS or bool(FOCUS.search(title or ''))


SEASON = {'winter': 1, 'spring': 1, 'summer': 5, 'fall': 8, 'autumn': 8}
SEASON_RE = re.compile(r'(winter|spring|summer|fall|autumn)\s*(\d{4})', re.I)


def _ym(s):
    m = re.match(r'(\d{4})-(\d{2})', s or '')
    return (int(m.group(1)), int(m.group(2))) if m else None


_E = SETTINGS.get('eligibility') or {}
WIN = (_ym(_E.get('earliest_start')), _ym(_E.get('latest_start')))


def term_ok(terms):
    if not terms or not all(WIN):
        return True
    for t in terms:
        m = SEASON_RE.search(t)
        if not m:
            return True
        if WIN[0] <= (int(m.group(2)), SEASON[m.group(1).lower()]) <= WIN[1]:
            return True
    return False


def title_term_ok(title):
    m = SEASON_RE.search(title or '')
    return term_ok([m.group(0)]) if m else True
