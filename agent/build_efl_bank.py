#!/usr/bin/env python3
"""Additive EFL catalogue and bank import. No deletion of rounds or usage history.

Sources: completed Football-Data match CSVs, Wikipedia club infoboxes,
and sourced Transfermarkt player profiles. Unclear facts are not published.
"""
import argparse,collections,csv,datetime as dt,gzip,hashlib,html,io,json,os,pathlib,random,re,sqlite3,urllib.parse,urllib.request
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo
from source_utils import clean,fetch,infobox
from efl_catalog import membership
from generate_questions import ALIASES,pdate,scoreopts,numopts,season_start,scode
BASE=pathlib.Path('/var/lib/clubdailyfive');CACHE=BASE/'efl-cache';UK=ZoneInfo('Europe/London')

def options(answer,wrong,key):
    items=[str(answer),*dict.fromkeys(str(v) for v in wrong if str(v)!=str(answer))][:4]
    if len(items)!=4:raise ValueError('Insufficient distinct distractors')
    random.Random(key).shuffle(items);return items,items.index(str(answer))

def add(con,cid,text,answer,wrong,key,source,label,date=None):
    opts,index=options(answer,wrong,key)
    if str(answer).lower() in text.lower() and len(str(answer))>3:raise ValueError('Answer leaked in question')
    con.execute('''INSERT OR IGNORE INTO questions(club_id,question_text,options_json,correct_index,explanation,source_url,source_label,content_hash,semantic_key,status,question_kind,fact_date)
    VALUES(?,?,?,?,?,?,?,?,?,'reviewed','history',?)''',(cid,text,json.dumps(opts,ensure_ascii=False),index,f'{answer}. {text}',source,label,hashlib.sha256((text+'|'+key).encode()).hexdigest(),key,date))

def metadata(member):
    url='https://en.wikipedia.org/wiki/'+urllib.parse.quote(member['wiki'].replace(' ','_'))
    raw=fetch(url,CACHE/'wiki',days=30);box=infobox(raw);facts={}
    for k,label in [('Full name','full_name'),('Nickname','nickname'),('Nickname(s)','nickname'),('Ground','ground')]:
        if k in box:
            value=clean(box[k]);facts[label]=re.sub(r'\s*\(.*?\)','',value).strip()
    if 'Founded' in box:
        date=re.search(r'\b(?:18|19|20)\d{2}\b',clean(box['Founded']))
        if date:facts['founded']=date[0]
    first=re.search(r'<table\b[^>]*class="[^"]*infobox[^>]*>(.*?)</table>',raw,re.S)
    image=None
    if first:
        for src in re.findall(r'<img\b[^>]*src="([^"]+)"',first[1]):
            if not any(x in src for x in ('Kit_','kit_','Flag_','Football_kit')):
                image=html.unescape(src);break
    if image and image.startswith('//'):image='https:'+image
    return {**member,'facts':facts,'club_source':url,'crest_source':image}

def performances(members):
    wanted={m['team']:m['slug'] for m in members if 'team' in m};players=collections.defaultdict(lambda:collections.Counter());pids=set()
    with open('/var/lib/clubdailyfive/player-sources/performances.csv',newline='',encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            slug=wanted.get(r['team_name']);match=re.match(r'(\d{2})/',r['season_name'])
            if not slug or not match or (2000+int(match[1]) if int(match[1])<50 else 1900+int(match[1]))<2016:continue
            count=int(float(r['nb_on_pitch'] or 0));players[slug][r['player_id']]+=count;pids.add(r['player_id'])
    profiles={}
    with open('/var/lib/clubdailyfive/player-sources/profiles.csv',newline='',encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            if r['player_id'] in pids:profiles[r['player_id']]=r
    return players,profiles

def scoring(members,profiles,year):
    team_to_slug={m['team']:m['slug'] for m in members if 'team' in m};stats=collections.defaultdict(lambda:collections.Counter())
    with open('/var/lib/clubdailyfive/player-sources/performances.csv',encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            slug=team_to_slug.get(r['team_name']);match=re.match(r'(\d{2})/',r['season_name'])
            if not slug or not match or r['competition_id'] not in ('GB1','GB2','GB3','GB4','GB5'):continue
            y=int(match[1])+2000
            if year-3<=y<year:stats[(slug,y)][r['player_id']]+=int(float(r['goals'] or 0))
    return stats

def appearance_facts(members,year):
    teams={m['team']:m['slug'] for m in members if 'team' in m};out=collections.defaultdict(list);seen=set()
    with open('/var/lib/clubdailyfive/player-sources/performances.csv',encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            slug=teams.get(r['team_name']);match=re.fullmatch(r'(\d{2})/(\d{2})',r['season_name'])
            if not slug or not match or r['competition_id'] not in ('GB1','GB2','GB3','GB4','GB5'):continue
            y=2000+int(match[1]);n=int(float(r['nb_on_pitch'] or 0));key=(slug,y,r['player_id'],r['competition_id'])
            if year-6<=y<year and 20<=n<=46 and key not in seen:
                out[slug].append((r,y,n));seen.add(key)
    return out

def cup_facts(members,year):
    wanted={m['team']:m['slug'] for m in members if 'team' in m};out=collections.defaultdict(list)
    path=BASE/'transfermarkt-data/games.csv.gz'
    if not path.exists():return out
    with gzip.open(path,'rt',encoding='utf-8') as f:
        for r in csv.DictReader(f):
            if r['competition_id']!='FAC' or not (year-4<=int(r['season'])<year):continue
            for key in ('home_club_name','away_club_name'):
                slug=wanted.get(r[key])
                if not slug:continue
                own=int(r['home_club_goals'] if key=='home_club_name' else r['away_club_goals']);opp=int(r['away_club_goals'] if key=='home_club_name' else r['home_club_goals'])
                if own<opp and 'round' in r['round'].lower() or own<opp and r['round'] in ('Quarter-Finals','Semi-Finals','Final'):
                    out[slug].append(r)
    return out

def history(members,year):
    aliases={**ALIASES,**{m['alias']:m['slug'] for m in members}}
    out=collections.defaultdict(list)
    for y in range(year-6,year):
        for div in ('E0','E1','E2','E3','EC'):
            url=f'https://www.football-data.co.uk/mmz4281/{scode(y)}/{div}.csv'
            try:raw=fetch(url,CACHE/'matches',days=365)
            except Exception as e:print('HISTORY SOURCE UNAVAILABLE',url,type(e).__name__);continue
            for row in csv.DictReader(io.StringIO(raw)):
                if not all(row.get(k) for k in ('Date','HomeTeam','AwayTeam','FTHG','FTAG')):continue
                date=pdate(row['Date'])
                if not date:continue
                for field in ('HomeTeam','AwayTeam'):
                    slug=aliases.get(row[field])
                    if not slug:continue
                    home=field=='HomeTeam';gf=int(row['FTHG'] if home else row['FTAG']);ga=int(row['FTAG'] if home else row['FTHG'])
                    out[slug].append({'row':row,'year':y,'div':div,'date':date.isoformat(),'source':url,'home':home,'gf':gf,'ga':ga,'opponent':row['AwayTeam'] if home else row['HomeTeam']})
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--refresh',action='store_true');a=ap.parse_args()
    year=season_start(dt.datetime.now(UK).date());con=sqlite3.connect(os.getenv('QUIZ_DB',str(BASE/'clubquiz.sqlite')),timeout=60)
    con.execute('PRAGMA foreign_keys=ON');columns={r[1] for r in con.execute('pragma table_info(clubs)')}
    if 'league' not in columns:con.execute("ALTER TABLE clubs ADD COLUMN league TEXT NOT NULL DEFAULT 'premier-league'")
    members=membership(year,CACHE/'membership',ALIASES)
    for m in members:
        if 'name' in m:con.execute("INSERT INTO clubs(slug,name,accent,active,league) VALUES(?,?,'#ffcc33',1,?) ON CONFLICT(slug) DO UPDATE SET league=excluded.league,name=excluded.name",(m['slug'],m['name'],m['league']))
        else:con.execute('UPDATE clubs SET league=? WHERE slug=?',(m['league'],m['slug']))
    con.commit();efl=[m for m in members if 'team' in m]
    file=BASE/'efl-clubs.json'
    if file.exists() and not a.refresh:meta={m['slug']:m for m in json.loads(file.read_text())}
    else:meta={}
    def load(m):
        try:return metadata(m)
        except Exception as e:print('CLUB FACTS UNAVAILABLE',m['slug'],str(e));return {**m,'facts':{}}
    missing=[m for m in efl if m['slug'] not in meta]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for m in pool.map(load,missing):meta[m['slug']]=m
    members=[{**meta.get(m['slug'],{}),**m} for m in members];temp=file.with_suffix('.tmp');temp.write_text(json.dumps(members,ensure_ascii=False,indent=2));temp.replace(file)
    for m in members:
        if not m.get('crest_source'):continue
        path=pathlib.Path('/var/www/clubdailyfive.com/public_html/assets/crests')/(m['slug']+'.png')
        if not path.exists():
            try:
                payload=urllib.request.urlopen(urllib.request.Request(m['crest_source'],headers={'User-Agent':'Mozilla/5.0'}),timeout=20).read()
                if not payload.startswith(b'\x89PNG'):raise ValueError('Expected PNG thumbnail')
                path.write_bytes(payload)
            except Exception as e:print('CREST UNAVAILABLE',m['slug'],str(e));continue
        con.execute('update clubs set logo_path=? where slug=?',('/assets/crests/'+path.name,m['slug']))
    con.commit();player_counts,profiles=performances(members);past=history(members,year);scorers=scoring(members,profiles,year);cups=cup_facts(members,year);appearances=appearance_facts(members,year)
    # Snapshot a useful source record for review, independent of a live player import.
    (BASE/'efl-source-profiles.json').write_text(json.dumps({'counts':{s:dict(v) for s,v in player_counts.items()},'profiles':profiles},ensure_ascii=False))
    for m in members:
        if m['league']=='premier-league':continue
        cid=con.execute('select id from clubs where slug=?',(m['slug'],)).fetchone()[0];name=m['name'];slug=m['slug'];facts=m.get('facts',{})
        for fact,wording in [('founded',f'In which year was {name} founded?'),('nickname',f'Which nickname is associated with {name}?'),('ground',f'Which ground is home to {name}?'),('full_name',f'What is the full official name of {name}?')]:
            answer=facts.get(fact)
            if not answer:continue
            wrong=[c['facts'][fact] for c in meta.values() if c.get('facts',{}).get(fact) and c['facts'][fact]!=answer]
            try:add(con,cid,wording,answer,wrong,f'generic|{slug}|{fact}|source-1',m['club_source'],'Wikipedia club profile')
            except ValueError as e:print('SKIP FACT',slug,fact,e)
        for pid,count in player_counts[slug].most_common(20):
            p=profiles.get(pid,{});country=p.get('country_of_birth');player=re.sub(r' \(\d+\)$','',p.get('player_name',''))
            if count<25 or not country or not player:continue
            key=f'generic|{slug}|player-birth|{pid}';src=f'https://www.transfermarkt.com/{p["player_slug"]}/profil/spieler/{pid}'
            add(con,cid,f'In which country was {name} player {player} born?',country,['England','Scotland','Wales','France','Spain','Nigeria','Brazil','Australia'],key,src,'Transfermarkt player profile')
            if con.execute("select count(*) from questions where club_id=? and semantic_key like 'generic|%'",(cid,)).fetchone()[0]>=12:break
        candidates=collections.defaultdict(list)
        def queue(typ,text,answer,wrong,suffix,source,date=None):candidates[typ].append((text,answer,wrong,f'v4bank|efl|{typ}|{slug}|{suffix}',source,'Football-Data.co.uk historical records',date))
        grouped=collections.defaultdict(list)
        for game in past[slug]:
            grouped[(game['year'],game['div'])].append(game);gf=game['gf'];ga=game['ga'];date=game['date'];opponent=game['opponent'];venue='at home to' if game['home'] else 'away to';d=dt.date.fromisoformat(date);display=f'{d.day} {d:%B %Y}'
            opts=[f'{gf+1}-{ga}',f'{gf}-{ga+1}',f'{max(0,gf-1)}-{ga}',f'{gf}-{max(0,ga-1)}',f'{gf+2}-{ga}',f'{gf}-{ga+2}']
            queue('match_score',f'What was the score for {name} in their league match {venue} {opponent} on {display}?',f'{gf}-{ga}',opts,date+'|score',game['source'],date)
            for colour in ('yellow',):  # single-match red-card counts are almost always 0: no real question
                field=('HY' if game['home'] else 'AY') if colour=='yellow' else ('HR' if game['home'] else 'AR');value=game['row'].get(field)
                if value is None or value=='':continue
                n=int(value);queue('discipline',f'How many {colour} cards did {name} receive against {opponent} on {display}?',n,[max(0,n-1),n+1,n+2,n+3],date+'|'+colour,game['source'],date)
        for (y,div),games in grouped.items():
            games.sort(key=lambda g:g['date']);label=f'{y}-{str(y+1)[-2:]}';total=len(games)
            if total not in (38,46):continue  # No incomplete historical season aggregates.
            for result,typ in [('wins','W'),('draws','D'),('losses','L')]:
                results=['W' if g['gf']>g['ga'] else 'D' if g['gf']==g['ga'] else 'L' for g in games];n=results.count(typ)
                queue('season_record',f'How many league {result} did {name} record in the {label} season?',n,[v for v in (n-3,n-2,n-1,n+1,n+2,n+3,n+4,n+5) if 0<=v<=total],f'{label}|{result}',games[0]['source'])
                longest=max((len(list(items)) for k,items in __import__('itertools').groupby(results) if k==typ),default=0)
                if (result=='wins' and longest<=3) or longest<1:continue
                queue('runs',f'What was {name}’s longest continuous run of league {result} in {label}?',longest,[max(0,longest-1),longest+1,longest+2,longest+3],f'{label}|run-{result}',games[0]['source'])
        for (y,div),games in grouped.items():
            stats=scorers.get((slug,y),{});leaders=sorted(stats.items(),key=lambda p:p[1],reverse=True)
            # Reject partial scoring coverage rather than inventing a leading scorer.
            totalgoals=sum(g['gf'] for g in games)
            if len(games) not in (38,46) or not leaders or sum(stats.values())!=totalgoals:continue
            for rank in (0,1):
                if len(leaders)<=rank+1 or leaders[rank][1]<=0 or leaders[rank][1]==leaders[rank+1][1] or rank and leaders[rank][1]==leaders[rank-1][1]:continue
                pid,n=leaders[rank];profile=profiles.get(pid)
                if not profile:continue
                player=re.sub(r' \(\d+\)$','',profile['player_name']);wrong=[re.sub(r' \(\d+\)$','',profiles[p]['player_name']) for p,_ in leaders if p!=pid and p in profiles]
                if len(set(wrong))<3:continue
                queue('player_scoring',f'Who was {name}’s {"leading" if rank==0 else "second-highest"} league goalscorer in {y}-{str(y+1)[-2:]}?',player,wrong,f'{y}|scorer-{rank}',f'https://www.transfermarkt.com/{slug}/leistungsdaten/verein/'+str(next((p['current_club_id'] for p in profiles.values() if p['current_club_name']==m['team']),'')))
        for g in cups[slug]:
            y=int(g['season']);date=g['date'];roundname=g['round']
            queue('cups',f'At which round were {name} knocked out of the FA Cup in {y}-{str(y+1)[-2:]}?',roundname,['First Round','Second Round','Third Round','Fourth Round','Fifth Round','Quarter-Finals','Semi-Finals','Final'],f'{y}|fac-exit',g['url'],date)
        for pid,count in player_counts[slug].most_common(50):
            p=profiles.get(pid,{})
            if count<25 or not p.get('date_of_birth'):continue
            try:birthyear=dt.date.fromisoformat(p['date_of_birth']).year
            except ValueError:continue
            player=re.sub(r' \(\d+\)$','',p['player_name'])
            candidates['player_biography'].append((f'In which year was {name} player {player} born?',birthyear,[birthyear-4,birthyear-2,birthyear+2,birthyear+4],f'v4bank|efl|player_biography|{slug}|birth-{pid}',f'https://www.transfermarkt.com/{p["player_slug"]}/profil/spieler/{pid}','Transfermarkt player profile',None))
        for r,y,n in appearances[slug]:
            p=profiles.get(r['player_id'])
            if not p:continue
            player=re.sub(r' \(\d+\)$','',p['player_name']);label=f'{y}-{str(y+1)[-2:]}'
            url=f'https://www.transfermarkt.com/{p["player_slug"]}/leistungsdatendetails/spieler/{r["player_id"]}/saison/{y}/verein/{r["team_id"]}/wettbewerb/{r["competition_id"]}'
            candidates['player_appearances'].append((f'How many {r["competition_name"]} appearances did {player} make for {name} in {label}?',n,[v for v in (n-3,n-2,n-1,n+1,n+2,n+3) if 0<=v<=46],f'v4bank|efl|player_appearances|{slug}|{y}-{r["player_id"]}',url,'Transfermarkt season appearance records',None))
        # Source facts get separate identities, not hundreds of wording variants.
        rows=[];groups={k:sorted(v,key=lambda r:hashlib.sha256(r[3].encode()).hexdigest()) for k,v in candidates.items()}
        while any(groups.values()) and len(rows)<330:
            for group in groups.values():
                if group and len(rows)<330:rows.append(group.pop())
        for text,answer,wrong,key,source,label,date in rows:
            try:add(con,cid,text,answer,wrong,key,source,label,date)
            except ValueError as e:print('REJECT',slug,key,e)
        con.commit();count=con.execute("select count(*) from questions where club_id=? and status='reviewed'",(cid,)).fetchone()[0];print('BANK',slug,count,flush=True)
    print('INTEGRITY',con.execute('pragma integrity_check').fetchone()[0]);con.close()

if __name__=='__main__':main()
