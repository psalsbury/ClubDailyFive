#!/usr/bin/env python3
"""Source-backed EFL player discovery and promotion, plus position evidence audit.

Never estimates a debut date from 1 July or defaults a missing position.
Uncertain facts stay in a review queue. Existing validated players are retained.
"""
import argparse,collections,csv,datetime as dt,html,json,os,pathlib,re,sqlite3,unicodedata,urllib.parse
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo
from source_utils import clean,fetch,infobox,broad_position,RANK
BASE=pathlib.Path('/var/lib/clubdailyfive');UK=ZoneInfo('Europe/London');DB=str(BASE/'player-wordle/game.sqlite3')
def normalized(s):return re.sub('[^a-z0-9]','',unicodedata.normalize('NFKD',s.lower()).encode('ascii','ignore').decode())
def stamp():return dt.datetime.now(dt.timezone.utc).isoformat()

def protection(c):
    c.executescript('''CREATE TABLE IF NOT EXISTS position_overrides(player_id INTEGER PRIMARY KEY REFERENCES players(id),position TEXT NOT NULL,position_rank INTEGER NOT NULL,source_url TEXT NOT NULL,reason TEXT NOT NULL,reviewed_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS position_reviews(player_id INTEGER PRIMARY KEY REFERENCES players(id),stored_position TEXT NOT NULL,source_position TEXT,source_url TEXT NOT NULL,status TEXT NOT NULL,evidence TEXT,checked_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS efl_player_research(club_id INTEGER NOT NULL,player_name TEXT NOT NULL,profile_id TEXT NOT NULL,status TEXT NOT NULL,reason TEXT,source_url TEXT,evidence_json TEXT,checked_at TEXT NOT NULL,PRIMARY KEY(club_id,player_name));
    CREATE TRIGGER IF NOT EXISTS preserve_reviewed_position AFTER UPDATE OF position,position_rank ON players
    WHEN EXISTS(SELECT 1 FROM position_overrides o WHERE o.player_id=NEW.id AND (NEW.position!=o.position OR NEW.position_rank!=o.position_rank))
    BEGIN UPDATE players SET position=(SELECT position FROM position_overrides WHERE player_id=NEW.id),position_rank=(SELECT position_rank FROM position_overrides WHERE player_id=NEW.id) WHERE id=NEW.id; END;''')

def protect(c,pid,position,source,reason):
    c.execute('INSERT INTO position_overrides VALUES(?,?,?,?,?,?) ON CONFLICT(player_id) DO UPDATE SET position=excluded.position,position_rank=excluded.position_rank,source_url=excluded.source_url,reason=excluded.reason,reviewed_at=excluded.reviewed_at',(pid,position,RANK[position],source,reason,stamp()))
    c.execute('UPDATE players SET position=?,position_rank=? WHERE id=?',(position,RANK[position],pid))

def audit_hull(c):
    url='https://tigerbase.hullcity.com/tigers-players.php?select_col=pos';raw=fetch(url,BASE/'efl-cache/hull',days=7);records={}
    for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>',raw,re.S):
        cells=[clean(v) for v in re.findall(r'<td\b[^>]*>(.*?)</td>',row,re.S)]
        for n,cell in enumerate(cells):
            if cell in {'GK','DF','MD','FW'} and n>=3:
                name=cells[n-3]+' '+cells[n-2];records[normalized(name)]={'GK':'Goalkeeper','DF':'Defender','MD':'Midfielder','FW':'Forward'}[cell]
    cid=c.execute("select id from clubs where slug='hull'").fetchone()[0];matched=changed=0
    for pid,name,position in c.execute('select id,name,position from players where club_id=?',(cid,)).fetchall():
        pos=records.get(normalized(name))
        if not pos:continue
        matched+=1;changed+=pos!=position;protect(c,pid,pos,url,'Hull City historical archive: prominent position while at Hull')
    c.commit();print('HULL POSITIONS matched',matched,'corrected',changed,flush=True)
    row=c.execute("select id,position from players where club_id=? and name='Markus Henriksen'",(cid,)).fetchone()
    if row and row[1]!='Midfielder':raise RuntimeError('Henriksen source match failed; do not guess')

def wiki_player(name):
    url='https://en.wikipedia.org/wiki/'+urllib.parse.quote(name.replace(' ','_'))
    raw=fetch(url,BASE/'efl-cache/players',days=30)
    if 'Senior career' not in raw or not (infobox(raw).get('Position(s)') or infobox(raw).get('Position')): # A disambiguation page is not a source.
        other=url+'_(footballer)';raw=fetch(other,BASE/'efl-cache/players',days=30);url=other
    return url,raw

def career(raw):
    section=raw.split('Senior career',1)[-1].split('International career',1)[0].split('Managerial career',1)[0].split('</table>',1)[0]
    out=[]
    for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>',section,re.S):
        h=re.search(r'<th\b[^>]*>(.*?)</th>',row,re.S);cells=re.findall(r'<td\b[^>]*>(.*?)</td>',row,re.S)
        if not h or not cells or not re.match(r'(?:18|19|20)\d{2}',clean(h[1])):continue
        years=re.findall(r'(?:18|19|20)\d{2}',clean(h[1]));team=re.sub(r'\(loan\)|→','',clean(cells[0])).strip()
        out.append((int(years[0]),team))
    return out

def debut(raw,member,first_year):
    aliases={member['name'].lower(),member['team'].lower(),member['name'].lower().removesuffix(' city').removesuffix(' town').removesuffix(' united')}
    heading='';dates=[]
    for chunk in re.findall(r'<h[234]\b[^>]*>.*?</h[234]>|<p\b[^>]*>.*?</p>',raw,re.S):
        text=clean(chunk)
        if chunk.startswith('<h'):heading=text.lower();continue
        if 'debut' not in text.lower():continue
        if not any(a in text.lower() or a in heading for a in aliases if len(a)>3):continue
        for sentence in re.split(r'(?<=[.!?])\s+',text):
            low=sentence.lower()
            if 'debut' not in low or any(s in low for s in ('league debut','international','under-','next day','following day','friendly','second debut','second spell')):continue
            if any(a in heading for a in aliases): pass
            elif not any(a in low for a in aliases if len(a)>3):continue
            # Require a full date in the debut sentence itself, not a nearby transfer date.
            found=re.findall(r'\b(\d{1,2} (?:January|February|March|April|May|June|July|August|September|October|November|December) (?:19|20)\d{2})\b',sentence)
            if len(found)!=1:continue
            date=dt.datetime.strptime(found[0],'%d %B %Y').date()
            if date.year not in (first_year,first_year+1) or date>dt.datetime.now(UK).date():continue
            dates.append((date,sentence))
    if not dates:return None,None
    return min(dates,key=lambda x:x[0])

def research(member,profile,count,history):
    name=re.sub(r' \(\d+\)$','',profile['player_name']);url,raw=wiki_player(name);box=infobox(raw)
    position=broad_position(clean(box.get('Position(s)',box.get('Position',''))))
    profilepos=broad_position(profile.get('position',''))
    if not position or position!=profilepos:return {'status':'review','reason':'Position sources ambiguous or disagree','source':url,'position':position,'name':name}
    rows=career(raw);match=[i for i,(_,team) in enumerate(rows) if normalized(team)==normalized(member['name']) or normalized(team)==normalized(member['team'].removesuffix(' FC').removesuffix(' AFC'))]
    if not match:return {'status':'review','reason':'Cannot verify senior club career','source':url,'name':name}
    start=match[0];first=rows[start][0]
    if first<dt.datetime.now(UK).year-10:return {'status':'review','reason':'Historical eligibility needs additional evidence','source':url,'name':name}
    date,evidence=debut(raw,member,first)
    if not date:return {'status':'review','reason':'Exact competitive debut date not sourced','source':url,'name':name}
    dob=dt.date.fromisoformat(profile['date_of_birth']);age=date.year-dob.year-((date.month,date.day)<(dob.month,dob.day))
    if not 15<=age<=45:return {'status':'review','reason':'Debut age outside valid range','source':url,'name':name}
    countries=re.split(r'\s{2,}|\s*/\s*|,',profile.get('citizenship',''));nationality=countries[0].strip()
    if len(countries)!=1:return {'status':'review','reason':'Multiple citizenships require football nationality evidence','source':url,'name':name}
    from player_country import continent
    cont=continent(nationality)
    if cont=='Other':return {'status':'review','reason':'Unmapped nationality','source':url,'name':name}
    prior=len({normalized(team) for y,team in rows[:start] if y<=date.year and normalized(team)!=normalized(member['name'])})
    return {'status':'approved','reason':'Complete independently sourced career and debut evidence','name':name,'position':position,'source':url,'evidence':evidence,'debut_date':date.isoformat(),'debut_age':age,'debut_year':date.year,'prior_clubs':prior,'nationality':nationality,'continent':cont,'appearances':count}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--limit',type=int,default=2);ap.add_argument('--audit',action='store_true');a=ap.parse_args()
    c=sqlite3.connect(os.getenv('WORDLE_DB',DB),timeout=60);c.execute('pragma foreign_keys=on');protection(c);audit_hull(c)
    members=json.loads((BASE/'efl-clubs.json').read_text());data=json.loads((BASE/'efl-source-profiles.json').read_text())
    # Fairly visit clubs with the smallest approved bank first.
    sizes={slug:n for slug,n in c.execute('select c.slug,count(p.id) from clubs c left join players p on p.club_id=c.id group by c.id')}
    members.sort(key=lambda m:(sizes.get(m['slug'],0),m['name'] if 'name' in m else m['slug']))
    tasks=[]
    for m in members:
        if m['league']=='premier-league' or a.limit<=0:continue
        c.execute('INSERT INTO clubs(slug,name,active) VALUES(?,?,1) ON CONFLICT(slug) DO UPDATE SET name=excluded.name',(m['slug'],m['name']));cid=c.execute('select id from clubs where slug=?',(m['slug'],)).fetchone()[0]
        counts=sorted(data['counts'].get(m['slug'],{}).items(),key=lambda p:p[1],reverse=True)
        existing={r[0] for r in c.execute("select player_name from efl_player_research where club_id=? and reason not like 'HTTPError:%429%' and reason not like 'RuntimeError: Research budget%'",(cid,))}
        for pid,count in counts:
            p=data['profiles'].get(pid)
            if count<25 or not p or not p.get('date_of_birth'):continue
            name=re.sub(r' \(\d+\)$','',p['player_name'])
            if name in existing:continue
            tasks.append((m,p,count,cid,pid))
            if sum(t[3]==cid for t in tasks)>=a.limit:break
    c.commit()
    def worker(t):
        m,p,count,cid,pid=t
        try:return t,research(m,p,count,None)
        except Exception as e:return t,{'status':'review','name':re.sub(r' \(\d+\)$','',p['player_name']),'reason':type(e).__name__+': '+str(e),'source':''}
    approved=0;seen=0
    with ThreadPoolExecutor(max_workers=6) as pool:
        for t,r in pool.map(worker,tasks):
            m,p,count,cid,pid=t;now=stamp();c.execute('INSERT OR REPLACE INTO efl_player_research VALUES(?,?,?,?,?,?,?,?)',(cid,r['name'],pid,r['status'],r['reason'],r['source'],json.dumps(r,ensure_ascii=False),now))
            c.execute('INSERT INTO player_candidates(club_id,name,discovered_at,source_url,status) VALUES(?,?,?,?,?) ON CONFLICT(club_id,name) DO UPDATE SET status=excluded.status,source_url=excluded.source_url',(cid,r['name'],now,r['source'],r['status']))
            if r['status']=='approved':
                c.execute('''INSERT INTO players(club_id,name,debut_age,position,position_rank,nationality,continent,appearances,prior_clubs,source_url,source_updated_at,debut_year)
                 VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(club_id,name) DO NOTHING''',(cid,r['name'],r['debut_age'],r['position'],RANK[r['position']],r['nationality'],r['continent'],r['appearances'],r['prior_clubs'],r['source'],now,r['debut_year']))
                player=c.execute('select id from players where club_id=? and name=?',(cid,r['name'])).fetchone()[0];protect(c,player,r['position'],r['source'],'Verified prominent role; ambiguous mixed roles excluded');approved+=1
            seen+=1
            if seen%50==0:c.commit();print('PLAYER RESEARCH',seen,'approved',approved,flush=True)
    c.commit();print('PLAYER RESEARCH COMPLETE',seen,'approved',approved)
    if a.audit:
        # Cross-check existing roles without silently applying disputed changes.
        records=c.execute("select p.id,p.name,p.position from players p left join position_reviews r on r.player_id=p.id where r.player_id is null or (r.source_position is null and r.source_url='' and r.checked_at < ?) order by coalesce(r.checked_at,'') limit 100",((dt.datetime.now(dt.timezone.utc)-dt.timedelta(hours=20)).isoformat(),)).fetchall()
        def review(row):
            pid,name,position=row
            try:
                url,raw=wiki_player(name);box=infobox(raw);evidence=clean(box.get('Position(s)',box.get('Position','')));pos=broad_position(evidence)
                return (pid,position,pos,url,'confirmed' if pos==position else 'review',evidence,stamp())
            except Exception as e:return (pid,position,None,'','review',str(e),stamp())
        with ThreadPoolExecutor(max_workers=6) as pool:
            for r in pool.map(review,records):c.execute('INSERT OR REPLACE INTO position_reviews VALUES(?,?,?,?,?,?,?)',r)
        c.commit();print('POSITION AUDIT',len(records),'checked; remaining queued for next run')
    c.execute('insert into agent_runs(ran_at,status,details) values(?,?,?)',(stamp(),'efl-research',f'Candidates checked={seen}; approved={approved}; disputed or incomplete records held for review'))
    c.commit();print('INTEGRITY',c.execute('pragma integrity_check').fetchone()[0])

if __name__=='__main__':main()
