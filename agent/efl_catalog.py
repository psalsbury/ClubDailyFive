"""Club identities; league membership is sourced, never copied from the prototype."""
import csv, io, json, pathlib
from source_utils import fetch
LEAGUES={'E0':'premier-league','E1':'championship','E2':'league-one','E3':'league-two'}
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
Wrexham|Wrexham|Wrexham AFC|Wrexham A.F.C.
AFC Wimbledon|AFC Wimbledon|AFC Wimbledon|AFC Wimbledon
Barnsley|Barnsley|Barnsley FC|Barnsley F.C.
Blackpool|Blackpool|Blackpool FC|Blackpool F.C.
Bradford|Bradford City|Bradford City|Bradford City A.F.C.
Bromley|Bromley|Bromley FC|Bromley F.C.
Burton|Burton Albion|Burton Albion|Burton Albion F.C.
Cambridge|Cambridge United|Cambridge United|Cambridge United F.C.
Doncaster|Doncaster Rovers|Doncaster Rovers|Doncaster Rovers F.C.
Huddersfield|Huddersfield Town|Huddersfield Town|Huddersfield Town A.F.C.
Leicester|Leicester City|Leicester City|Leicester City F.C.
Leyton Orient|Leyton Orient|Leyton Orient|Leyton Orient F.C.
Luton|Luton Town|Luton Town|Luton Town F.C.
Mansfield|Mansfield Town|Mansfield Town|Mansfield Town F.C.
Milton Keynes Dons|Milton Keynes Dons|Milton Keynes Dons|Milton Keynes Dons F.C.
Notts County|Notts County|Notts County|Notts County F.C.
Oxford|Oxford United|Oxford United|Oxford United F.C.
Peterboro|Peterborough United|Peterborough United|Peterborough United F.C.
Plymouth|Plymouth Argyle|Plymouth Argyle|Plymouth Argyle F.C.
Reading|Reading|Reading FC|Reading F.C.
Sheffield Weds|Sheffield Wednesday|Sheffield Wednesday|Sheffield Wednesday F.C.
Stevenage|Stevenage|Stevenage FC|Stevenage F.C.
Stockport|Stockport County|Stockport County|Stockport County F.C.
Wigan|Wigan Athletic|Wigan Athletic|Wigan Athletic F.C.
Wycombe|Wycombe Wanderers|Wycombe Wanderers|Wycombe Wanderers F.C.
Accrington|Accrington Stanley|Accrington Stanley|Accrington Stanley F.C.
Barnet|Barnet|Barnet FC|Barnet F.C.
Bristol Rvs|Bristol Rovers|Bristol Rovers|Bristol Rovers F.C.
Cheltenham|Cheltenham Town|Cheltenham Town|Cheltenham Town F.C.
Chesterfield|Chesterfield|Chesterfield FC|Chesterfield F.C.
Colchester|Colchester United|Colchester United|Colchester United F.C.
Crawley Town|Crawley Town|Crawley Town|Crawley Town F.C.
Crewe|Crewe Alexandra|Crewe Alexandra|Crewe Alexandra F.C.
Exeter|Exeter City|Exeter City|Exeter City F.C.
Fleetwood Town|Fleetwood Town|Fleetwood Town|Fleetwood Town F.C.
Gillingham|Gillingham|Gillingham FC|Gillingham F.C.
Grimsby|Grimsby Town|Grimsby Town|Grimsby Town F.C.
Newport County|Newport County|Newport County|Newport County A.F.C.
Northampton|Northampton Town|Northampton Town|Northampton Town F.C.
Oldham|Oldham Athletic|Oldham Athletic|Oldham Athletic A.F.C.
Port Vale|Port Vale|Port Vale FC|Port Vale F.C.
Rochdale|Rochdale|Rochdale AFC|Rochdale A.F.C.
Rotherham|Rotherham United|Rotherham United|Rotherham United F.C.
Salford|Salford City|Salford City|Salford City F.C.
Shrewsbury|Shrewsbury Town|Shrewsbury Town|Shrewsbury Town F.C.
Swindon|Swindon Town|Swindon Town|Swindon Town F.C.
Tranmere|Tranmere Rovers|Tranmere Rovers|Tranmere Rovers F.C.
Walsall|Walsall|Walsall FC|Walsall F.C.
York|York City|York City|York City F.C.'''

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
    if len({m['slug'] for m in members})!=92:raise ValueError('Duplicate memberships')
    return members
