"""Add recorded dates to existing high-scoring opponent wording in place."""
import argparse
import datetime as dt
import hashlib
import sqlite3
from pathlib import Path
from generate_questions import DB, BACKUPS
from question_dates import dated_opponent_question


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    con=sqlite3.connect('file:'+DB+'?mode='+('rw' if args.apply else 'ro'),uri=True,timeout=30)
    con.row_factory=sqlite3.Row
    changes=[]
    for row in con.execute('SELECT * FROM questions'):
        text=dated_opponent_question(row['question_text'],row['fact_date'])
        if text!=row['question_text']:
            changes.append((text,hashlib.sha256((row['semantic_key']+'|'+text).encode()).hexdigest(),row['id']))
    print('Questions needing dates:',len(changes))
    if args.apply and changes:
        Path(BACKUPS).mkdir(parents=True,exist_ok=True)
        backup=Path(BACKUPS)/('before-question-dates-'+dt.datetime.now().strftime('%Y%m%d-%H%M%S')+'.sqlite')
        with sqlite3.connect(backup) as target:con.backup(target)
        with con:
            con.executemany('UPDATE questions SET question_text=?,content_hash=? WHERE id=?',changes)
        assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        print('Updated; backup:',backup)


if __name__=='__main__':main()
