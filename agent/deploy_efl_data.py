#!/usr/bin/env python3
"""Add prepared EFL data without replacing live databases or existing rounds."""
import datetime as dt,pathlib,sqlite3
from collect_efl_players import protection,protect

BASE=pathlib.Path('/var/lib/clubdailyfive')
def connect(path):
    c=sqlite3.connect(path,timeout=60);c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on');return c
def backup(c,name):
    folder=BASE/'efl-deployment-backups';folder.mkdir(exist_ok=True)
    with sqlite3.connect(folder/(name+'-'+dt.datetime.now().strftime('%Y%m%d-%H%M%S')+'.sqlite')) as b:c.backup(b)
def insert(c,table,row,omit=()):
    row={k:v for k,v in dict(row).items() if k not in omit};keys=list(row)
    c.execute('INSERT OR IGNORE INTO '+table+'('+','.join(keys)+') VALUES('+','.join('?' for _ in keys)+')',list(row.values()))
def main():
    q=connect(BASE/'clubquiz.sqlite');s=connect(BASE/'clubquiz-efl-staging.sqlite');backup(q,'quiz')
    original=[tuple(r) for r in q.execute('select * from daily_questions order by club_id,quiz_date,position')]
    if 'league' not in {r[1] for r in q.execute('pragma table_info(clubs)')}:q.execute("alter table clubs add column league TEXT NOT NULL DEFAULT 'premier-league'")
    with q:
        for r in s.execute('select * from clubs'):
            insert(q,'clubs',r,('id',))
            q.execute('update clubs set league=?,logo_path=coalesce(?,logo_path) where slug=?',(r['league'],r['logo_path'],r['slug']))
        ids={r['id']:q.execute('select id from clubs where slug=?',(r['slug'],)).fetchone()[0] for r in s.execute('select id,slug from clubs')}
        for r in s.execute("select q.* from questions q join clubs c on c.id=q.club_id where c.league!='premier-league'"):
            row=dict(r);row['club_id']=ids[row['club_id']];insert(q,'questions',row,('id',))
    assert original==[tuple(r) for r in q.execute('select * from daily_questions order by club_id,quiz_date,position')]
    print('QUIZ',dict(q.execute('select league,count(*) from clubs group by league')),'questions',q.execute('select count(*) from questions').fetchone()[0])
    w=connect(BASE/'player-wordle/game.sqlite3');t=connect(BASE/'player-wordle/efl-staging.sqlite3');backup(w,'wordle');protection(w)
    original_games=[tuple(r) for r in w.execute('select * from daily_game order by game_date,club_id')]
    original_players=w.execute('select count(*) from players').fetchone()[0]
    with w:
        for r in t.execute('select * from clubs'):insert(w,'clubs',r,('id',))
        clubs={r['id']:w.execute('select id from clubs where slug=?',(r['slug'],)).fetchone()[0] for r in t.execute('select id,slug from clubs')}
        players={}
        for r in t.execute('select * from players'):
            row=dict(r);row['club_id']=clubs[row['club_id']];insert(w,'players',row,('id',))
            players[r['id']]=w.execute('select id from players where club_id=? and name=?',(row['club_id'],row['name'])).fetchone()[0]
        for table in ('efl_player_research','player_candidates'):
            for r in t.execute('select * from '+table):
                row=dict(r);row['club_id']=clubs[row['club_id']];insert(w,table,row,('id',))
        for r in t.execute('select * from position_reviews'):
            row=dict(r);row['player_id']=players[row['player_id']];insert(w,'position_reviews',row)
        changed=0
        for r in t.execute('select * from position_overrides'):
            pid=players[r['player_id']];before=w.execute('select position from players where id=?',(pid,)).fetchone()[0]
            protect(w,pid,r['position'],r['source_url'],r['reason']);changed+=before!=r['position']
    assert original_games==[tuple(r) for r in w.execute('select * from daily_game order by game_date,club_id')]
    row=w.execute("select p.id,p.position,p.position_rank from players p join clubs c on c.id=p.club_id where c.slug='hull' and p.name='Markus Henriksen'").fetchone();assert row and tuple(row)[1:]==('Midfielder',2)
    w.execute('savepoint protection_test');w.execute("update players set position='Defender',position_rank=1 where id=?",(row['id'],));assert tuple(w.execute('select position,position_rank from players where id=?',(row['id'],)).fetchone())==('Midfielder',2);w.execute('rollback to protection_test');w.execute('release protection_test')
    print('WORDLE added',w.execute('select count(*) from players').fetchone()[0]-original_players,'positions corrected',changed,'Henriksen protected')
    for c in (q,w):assert c.execute('pragma integrity_check').fetchone()[0]=='ok';assert not c.execute('pragma foreign_key_check').fetchall()
    print('Existing rounds and mystery players preserved; both databases valid')
if __name__=='__main__':main()
