"""Small source adapters. Keep evidence; reject missing or ambiguous facts."""
import datetime as dt, hashlib, html, json, pathlib, re, urllib.request, urllib.error, time, threading
_request_lock=threading.Lock()
_next_request=0.0
_requests=0
_blocked=False

def clean(raw):
    raw=re.sub(r'<sup\b[^>]*>.*?</sup>','',raw,flags=re.S|re.I)
    return re.sub(r'\s+',' ',html.unescape(re.sub('<[^>]*>',' ',raw))).strip()

def fetch(url, cache, days=7):
    path=pathlib.Path(cache)/hashlib.sha256(url.encode()).hexdigest();path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and dt.datetime.now().timestamp()-path.stat().st_mtime<days*86400:
        return path.read_text()
    request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; ClubDailyFive/3.0; admin@clubdailyfive.com)'})
    global _next_request,_requests,_blocked
    if 'en.wikipedia.org' in url:
        with _request_lock:
            if _blocked or _requests>=100:raise RuntimeError('Research budget reached; resume at next scheduled run')
            time.sleep(max(0,_next_request-time.monotonic()));_next_request=time.monotonic()+1.2;_requests+=1
    try:raw=urllib.request.urlopen(request,timeout=20).read().decode('utf-8-sig','replace')
    except urllib.error.HTTPError as e:
        if e.code==429:_blocked=True
        raise
    if len(raw)<100:raise ValueError('Empty source: '+url)
    path.write_text(raw);return raw

def infobox(raw):
    match=re.search(r'<table\b[^>]*class="[^"]*infobox[^>]*>(.*?)</table>',raw,re.S)
    if not match:return {}
    out={}
    for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>',match[1],re.S):
        h=re.search(r'<th\b[^>]*>(.*?)</th>',row,re.S);d=re.search(r'<td\b[^>]*>(.*?)</td>',row,re.S)
        if h and d:out[clean(h[1])]=d[1]
    return out

def broad_position(text):
    """No inferred default. Mixed broad roles require review, not guessing."""
    text=text.lower().replace('–','-').replace('‐','-')
    groups=set()
    if re.search(r'goalkeeper|\bkeeper\b',text):groups.add('Goalkeeper')
    if re.search(r'defender|centre.back|center.back|full.back|wing.back|left.back|right.back',text):groups.add('Defender')
    if re.search(r'midfield|\bplaymaker\b',text):groups.add('Midfielder')
    if re.search(r'forward|striker|winger|centre.forward|center.forward|\battack\b',text):groups.add('Forward')
    return next(iter(groups)) if len(groups)==1 else None

RANK={'Goalkeeper':0,'Defender':1,'Midfielder':2,'Forward':3}
