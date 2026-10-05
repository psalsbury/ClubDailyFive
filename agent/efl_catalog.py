"""Club identities; league membership is sourced, never copied from the prototype."""
import csv, io, json, pathlib
from source_utils import fetch
LEAGUES={'E0':'premier-league','E1':'championship'}
# Football-Data alias, display name, Transfermarkt team name, Wikipedia page.
DATA='''Birmingham|Birmingham City|Birmingham City|Birmingham City F.C.
Blackburn|Blackburn Rovers|Blackburn Rovers|Blackburn Rovers F.C.
Bolton|Bolton Wanderers|Bolton Wanderers|Bolton Wanderers F.C.
Bristol City|Bristol City|Bristol City|Bristol City F.C.
Burnley|Burnley|Burnley FC|Burnley F.C.
Cardiff|Cardiff City|Cardiff City|Cardiff City F.C.
Charlton|Charlton Athletic|Charlton Athletic|Charlton Athletic F.C.
Derby|Derby County|Derby County|Derby County F.C.
Lincoln|Lincoln City|Lincoln City|Lincoln City F.C.
Middlesbrough|Middlesbrough|Middlesbrough FC|Middlesbrough F.C.
Millwall|Millwall|Millwall FC|Millwall F.C.
Norwich|Norwich City|Norwich City|Norwich City F.C.
Portsmouth|Portsmouth|Portsmouth FC|Portsmouth F.C.
Preston|Preston North End|Preston North End|Preston North End F.C.
QPR|Queens Park Rangers|Queens Park Rangers|Queens Park Rangers F.C.
Sheffield United|Sheffield United|Sheffield United|Sheffield United F.C.
Southampton|Southampton|Southampton FC|Southampton F.C.
Stoke|Stoke City|Stoke City|Stoke City F.C.
Swansea|Swansea City|Swansea City|Swansea City A.F.C.
Watford|Watford|Watford FC|Watford F.C.
West Brom|West Bromwich Albion|West Bromwich Albion|West Bromwich Albion F.C.
West Ham|West Ham United|West Ham United|West Ham United F.C.
Wolves|Wolverhampton Wanderers|Wolverhampton Wanderers|Wolverhampton Wanderers F.C.
Wrexham|Wrexham|Wrexham AFC|Wrexham A.F.C.'''

def identities():
    return {a:{'alias':a,'name':n,'slug':n.lower().replace(' ','-'),'team':t,'wiki':w} for a,n,t,w in (r.split('|') for r in DATA.splitlines())}

def membership(year, cache, pl_aliases):
    catalog=identities();members=[]
    for div,league in LEAGUES.items():
        url=f'https://www.football-data.co.uk/mmz4281/{str(year)[-2:]}{str(year+1)[-2:]}/{div}.csv'
        rows=list(csv.DictReader(io.StringIO(fetch(url,cache,days=1))))
        names=sorted({r[k] for r in rows for k in ('HomeTeam','AwayTeam') if r.get(k)})
        if len(names)!=(20 if div=='E0' else 24):raise ValueError('Incomplete league membership: '+div)
        for name in names:
            if div=='E0':
                if name not in pl_aliases:raise ValueError('Unmapped Premier League club: '+name)
                members.append({'alias':name,'slug':pl_aliases[name],'league':league,'membership_source':url,'season':year})
            else:
                if name not in catalog:raise ValueError('Unmapped EFL club: '+name)
                members.append({**catalog[name],'league':league,'membership_source':url,'season':year})
    if len({m['slug'] for m in members})!=44:raise ValueError('Duplicate memberships')
    return members
