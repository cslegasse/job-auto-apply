#!/usr/bin/env python3
import email, email.header, email.utils, getpass, html, imaplib, json, os, re, ssl, subprocess, sys, time, datetime

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(R, 'state', 'broker.jsonl')
IS_WIN = os.name == 'nt'
# Windows: the Gmail app password lives in this file, encrypted with DPAPI (only this Windows user
# can decrypt it). Written by `code_broker.py store`, which the USER runs in their own terminal.
SECRET = os.path.join(R, 'state', 'broker_secret.bin')
DEFAULTS = {'gmail_account': '', 'signup_email_pattern': '', 'keychain_service': 'jobapply-gmail-imap'}

def cfg():
    try: s = json.load(open(os.path.join(R, 'config', 'settings.json'))).get('broker', {})
    except Exception: s = {}
    return {k: s.get(k) or v for k, v in DEFAULTS.items()}

def out(status, code=0, **kw):
    print(json.dumps(dict(status=status, **kw)))
    sys.exit(code)

def log(**kw):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    kw['ts'] = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    with open(LOG, 'a') as f: f.write(json.dumps(kw) + '\n')

if IS_WIN:
    import ctypes
    from ctypes import wintypes

    class _Blob(ctypes.Structure):
        _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_char))]

    def dpapi(data, protect):
        crypt32, k32 = ctypes.WinDLL('crypt32'), ctypes.WinDLL('kernel32')
        k32.LocalFree.argtypes = [ctypes.c_void_p]
        buf = ctypes.create_string_buffer(data, len(data))
        src, dst = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), _Blob()
        fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
        if not fn(ctypes.byref(src), None, None, None, None, 0x1, ctypes.byref(dst)): return None
        try: return ctypes.string_at(dst.pbData, dst.cbData)
        finally: k32.LocalFree(ctypes.cast(dst.pbData, ctypes.c_void_p))

    def _win32():
        u32, k32 = ctypes.WinDLL('user32'), ctypes.WinDLL('kernel32')
        k32.GlobalAlloc.argtypes, k32.GlobalAlloc.restype = [wintypes.UINT, ctypes.c_size_t], wintypes.HGLOBAL
        k32.GlobalLock.argtypes, k32.GlobalLock.restype = [wintypes.HGLOBAL], ctypes.c_void_p
        k32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        u32.OpenClipboard.argtypes = [wintypes.HWND]
        u32.SetClipboardData.argtypes, u32.SetClipboardData.restype = [wintypes.UINT, wintypes.HANDLE], wintypes.HANDLE
        u32.RegisterClipboardFormatW.argtypes, u32.RegisterClipboardFormatW.restype = [wintypes.LPCWSTR], wintypes.UINT
        u32.GetClipboardSequenceNumber.restype = wintypes.DWORD
        return u32, k32

    def _open(u32):
        for _ in range(20):
            if u32.OpenClipboard(None): return True
            time.sleep(0.1)
        return False

    def win_clip_set(value):
        u32, k32 = _win32()
        def put(fmt, raw):
            h = k32.GlobalAlloc(0x0002, len(raw))  # GMEM_MOVEABLE
            ctypes.memmove(k32.GlobalLock(h), raw, len(raw)); k32.GlobalUnlock(h)
            if not u32.SetClipboardData(fmt, h): raise OSError('SetClipboardData failed')
        if not _open(u32): raise OSError('clipboard busy')
        try:
            u32.EmptyClipboard()
            put(13, (value + '\0').encode('utf-16-le'))  # CF_UNICODETEXT
            # Keep the code out of Win+V history, cloud clipboard and clipboard monitors.
            put(u32.RegisterClipboardFormatW('ExcludeClipboardContentFromMonitorProcessing'), b'\0')
            put(u32.RegisterClipboardFormatW('CanIncludeInClipboardHistory'), b'\0\0\0\0')
            put(u32.RegisterClipboardFormatW('CanUploadToCloudClipboard'), b'\0\0\0\0')
        finally: u32.CloseClipboard()
        return u32.GetClipboardSequenceNumber()

    def win_clip_clear_later(hold, seq):
        time.sleep(hold)
        u32, _ = _win32()
        if u32.GetClipboardSequenceNumber() == seq and _open(u32):
            u32.EmptyClipboard(); u32.CloseClipboard()

def app_password(c):
    if IS_WIN:
        try: raw = open(SECRET, 'rb').read()
        except OSError: return None
        pw = dpapi(raw, False)
        return pw.decode() if pw else None
    r = subprocess.run(['security', 'find-generic-password', '-s', c['keychain_service'], '-a', c['gmail_account'], '-w'],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None

def imap_login(c):
    if not c['gmail_account']: out('setup_error', 3, detail='settings.json broker.gmail_account is empty')
    pw = app_password(c)
    if not pw: out('setup_error', 3, detail=(f'no {SECRET}; the user runs `python scripts/code_broker.py store` in their own terminal' if IS_WIN
                                            else f'no Keychain item service={c["keychain_service"]} account={c["gmail_account"]}'))
    ctx = ssl.create_default_context(cafile='/etc/ssl/cert.pem') if os.path.exists('/etc/ssl/cert.pem') else ssl.create_default_context()
    try: M = imaplib.IMAP4_SSL('imap.gmail.com', 993, ssl_context=ctx)
    except (OSError, ssl.SSLError) as e: out('setup_error', 3, detail=f'cannot reach imap.gmail.com: {type(e).__name__}')
    try: M.login(c['gmail_account'], pw)
    except imaplib.IMAP4.error: out('setup_error', 3, detail='IMAP login refused (wrong app password, or IMAP off)')
    finally: del pw
    return M

def mailboxes(M):
    typ, rows = M.list()
    found = []
    for row in rows or []:
        s = row.decode(errors='replace')
        if '\\All' in s or '\\Junk' in s:
            found.append(s.rsplit(' "/" ', 1)[-1])
    return found or ['INBOX']

KEY = re.compile(r'code|passcode|verification|verify|one[- ]time|\botp\b|\bpin\b', re.I)
# Greenhouse codes are 8 mixed-case letters/digits; others are 4-8 chars, often 6 digits.
CAND = re.compile(r'(?<![\w#/.@-])([A-Za-z0-9]{4,8})(?![\w/@-])')

def text_of(msg):
    subj = str(email.header.make_header(email.header.decode_header(msg.get('Subject', ''))))
    plain, htm = [], []
    for part in msg.walk():
        ct = part.get_content_type()
        if ct not in ('text/plain', 'text/html') or part.get_filename(): continue
        try: body = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='replace')
        except Exception: continue
        (plain if ct == 'text/plain' else htm).append(body)
    body = '\n'.join(plain) if plain else re.sub(r'<[^>]+>', ' ', re.sub(r'(?is)<(style|script).*?</\1>', ' ', '\n'.join(htm)))
    return subj + '\n' + html.unescape(body)

def extract(text):
    near = set()
    for k in KEY.finditer(text):
        window = text[max(0, k.start() - 60): k.end() + 120]
        near.update(m for m in CAND.findall(window) if re.search(r'\d', m) and not re.fullmatch(r'(19|20)\d\d', m))
    six = {m for m in near if re.fullmatch(r'\d{6}', m)}
    eight = {m for m in near if len(m) == 8 and re.search(r'[A-Za-z]', m)}
    pool = six or eight or near
    if len(pool) == 1: return next(iter(pool)), 'ok'
    return None, ('ambiguous' if pool else 'no_code')

def dkim_ok(msg, domain):
    # Trust only Gmail's own verdict. Gmail prepends its Authentication-Results header, so it is the
    # topmost one; any further down were written by the sender and can claim dkim=pass for anyone.
    ars = msg.get_all('Authentication-Results') or []
    ar = ars[0] if ars else ''
    if not re.match(r'\s*mx\.google\.com\s*;', ar, re.I): return False
    for m in re.finditer(r'dkim=pass[^;]*?header\.(?:i|d)=@?([\w.-]+)', ar, re.I):
        d = m.group(1).lower()
        if d == domain or d.endswith('.' + domain): return True
    return False

JXA_SET = '''ObjC.import("AppKit");function run(){var d=$.NSFileHandle.fileHandleWithStandardInput.readDataToEndOfFile;
var s=$.NSString.alloc.initWithDataEncoding(d,$.NSUTF8StringEncoding);var p=$.NSPasteboard.generalPasteboard;p.clearContents;
p.setStringForType(s,"public.utf8-plain-text");p.setStringForType($(""),"org.nspasteboard.ConcealedType");
p.setStringForType($(""),"org.nspasteboard.TransientType");return p.changeCount;}'''
JXA_CLEAR = '''ObjC.import("AppKit");function run(a){var p=$.NSPasteboard.generalPasteboard;
if(p.changeCount==parseInt(a[0])){p.clearContents;return "cleared"}return "untouched"}'''

def to_clipboard(value, hold):
    if IS_WIN:
        try: seq = win_clip_set(value)
        except OSError as e: out('clipboard_error', 3, detail=str(e)[:200])
        flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        subprocess.Popen([sys.executable, os.path.abspath(__file__), '_clear', str(hold), str(seq)], creationflags=flags,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
        return
    r = subprocess.run(['osascript', '-l', 'JavaScript', '-e', JXA_SET], input=value, capture_output=True, text=True)
    if r.returncode != 0: out('clipboard_error', 3, detail=r.stderr.strip()[:200])
    n = r.stdout.strip()
    subprocess.Popen(['/bin/sh', '-c', 'sleep "$1"; osascript -l JavaScript -e "$2" "$3"', 'sh', str(hold), JXA_CLEAR, n],
                     start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def arg(name, default=None):
    a = sys.argv
    return a[a.index(name) + 1] if name in a and a.index(name) + 1 < len(a) else default

def cmd_fetch(c):
    to = arg('--to')
    if not to and arg('--tag'):
        if '{tag}' not in c['signup_email_pattern']: out('setup_error', 3, detail='broker.signup_email_pattern needs {tag}')
        to = c['signup_email_pattern'].replace('{tag}', arg('--tag'))
    frms = [d.strip().lower().lstrip('@') for d in (arg('--from') or '').split(',') if d.strip()]
    frm, since = ','.join(frms), arg('--since')
    if not (to and frm and since): out('usage', 3, detail='need --to or --tag, --from DOMAIN, --since EPOCH')
    since, wait, hold = float(since), int(arg('--wait', '300')), int(arg('--hold', '20'))
    days = max(1, int((time.time() - since) // 86400) + 1)
    query = f'to:{to} ' + (f'from:{frm}' if len(frms) == 1 else '{' + ' '.join('from:' + d for d in frms) + '}') + f' newer_than:{days}d'
    M = imap_login(c)
    boxes, deadline, last = mailboxes(M), time.time() + wait, 'no_message'
    while True:
        best = None
        for box in boxes:
            if M.select(box, readonly=True)[0] != 'OK': continue
            typ, data = M.uid('SEARCH', 'X-GM-RAW', '"' + query.replace('"', '') + '"')
            for uid in (data[0].split() if typ == 'OK' and data and data[0] else [])[-10:]:
                typ, parts = M.uid('FETCH', uid, '(INTERNALDATE BODY.PEEK[])')
                if typ != 'OK' or not parts or not isinstance(parts[0], tuple): continue
                t = imaplib.Internaldate2tuple(parts[0][0])
                ts = time.mktime(t) if t else 0
                if ts >= since - 30 and (best is None or ts > best[0]):
                    best = (ts, email.message_from_bytes(parts[0][1]))
        if best:
            ts, msg = best
            sender = email.utils.parseaddr(msg.get('From', ''))[1].lower()
            received = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            if not any((sender.endswith('@' + d) or sender.endswith('.' + d)) and dkim_ok(msg, d) for d in frms):
                log(cmd='fetch', to=to, sender_domain=frm, status='unverified_sender', received=received)
                out('unverified_sender', 2, received=received, detail='From or DKIM does not match --from; not used')
            code, why = extract(text_of(msg))
            if code:
                to_clipboard(code, hold); del code
                log(cmd='fetch', to=to, sender_domain=frm, status='ready', received=received)
                out('ready', 0, received=received, hold_s=hold, next=f'click the code field, press {"ctrl" if IS_WIN else "cmd"}+v, click confirm; never read the field back')
            if why == 'ambiguous':
                log(cmd='fetch', to=to, sender_domain=frm, status='ambiguous', received=received)
                out('ambiguous', 2, received=received, detail='several candidate codes; NEEDS HUMAN')
            last = why
        if time.time() >= deadline: break
        time.sleep(10)
    log(cmd='fetch', to=to, sender_domain=frm, status=last)
    out(last, 1, waited_s=wait)

def cmd_store(c):
    if not IS_WIN: out('usage', 3, detail='macOS: use `security add-generic-password -s jobapply-gmail-imap -a <gmail> -w`')
    if not sys.stdin.isatty(): out('usage', 3, detail='run this yourself in Windows Terminal, not through the agent')
    pw = getpass.getpass(f'Gmail app password for {c["gmail_account"] or "(set broker.gmail_account first)"} (hidden): ').replace(' ', '')
    if not pw: out('usage', 3, detail='empty password')
    blob = dpapi(pw.encode(), True); del pw
    if not blob: out('setup_error', 3, detail='DPAPI encrypt failed')
    os.makedirs(os.path.dirname(SECRET), exist_ok=True)
    open(SECRET, 'wb').write(blob)
    out('stored', 0, file=SECRET, next='python scripts/code_broker.py check')

def cmd_check(c):
    M = imap_login(c)
    boxes = mailboxes(M); M.logout()
    out('ok', 0, account=c['gmail_account'], mailboxes=boxes, signup_email_pattern=c['signup_email_pattern'] or None)

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == '_clear' and IS_WIN:
        win_clip_clear_later(int(sys.argv[2]), int(sys.argv[3])); return
    if cmd == 'selftest':
        to_clipboard('BROKER-TEST-4821', int(arg('--hold', '20')))
        out('ready', 0, hold_s=int(arg('--hold', '20')), detail='dummy value BROKER-TEST-4821 on clipboard; paste it to test')
    c = cfg()
    if cmd == 'store': cmd_store(c)
    if cmd == 'check': cmd_check(c)
    if cmd == 'fetch': cmd_fetch(c)
    out('usage', 3, detail=['code_broker.py check', 'code_broker.py fetch --to EMAIL --from DOMAIN --since EPOCH [--wait 300] [--hold 20]', 'code_broker.py fetch --tag TAG --from DOMAIN --since EPOCH', 'code_broker.py selftest', 'code_broker.py store   (Windows; the user runs it)'])

if __name__ == '__main__':
    main()
