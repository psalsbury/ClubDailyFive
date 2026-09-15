import argparse,datetime,sqlite3,json
from pathlib import Path
from generate_questions import DB,BACKUPS
from display_dates import format_question

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
 con=sqlite3.connect('file:'+DB+'?mode='+('rw' if args.apply else 'ro'),uri=True,timeout=30);con.row_factory=sqlite3.Row
 changes=[]
 for row in con.execute('SELECT * FROM questions'):
  new=format_question(row)
  if row['question_text']!=new['question_text'] or row['explanation']!=new['explanation'] or json.loads(row['options_json'])!=json.loads(new['options_json']):
   changes.append((new['question_text'],new['options_json'],new['explanation'],new['content_hash'],row['id']))
 print('Question records requiring display formatting:',len(changes))
 if args.apply and changes:
  backup=Path(BACKUPS)/('before-display-dates-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.sqlite')
  with sqlite3.connect(backup) as dest:con.backup(dest)
  with con:con.executemany('UPDATE questions SET question_text=?,options_json=?,explanation=?,content_hash=? WHERE id=?',changes)
  assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
  print('Applied; backup:',backup)
if __name__=='__main__':main()
