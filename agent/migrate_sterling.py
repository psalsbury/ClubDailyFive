#!/usr/bin/env python3
"""Convert existing questions in place; preserve IDs, answers, usage and rounds."""
import argparse, datetime as dt, json, sqlite3
from pathlib import Path
from sterling import sterling_question, assert_sterling
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--apply",action="store_true")
    parser.add_argument("--db",default="/var/lib/predictioncomp/clubquiz.sqlite")
    args=parser.parse_args()
    con=sqlite3.connect(args.db,timeout=60); con.row_factory=sqlite3.Row
    rows=[dict(r) for r in con.execute("select * from questions")]
    changes=[]
    for row in rows:
        new=sterling_question(row)
        if new!=row: changes.append((row,new))
    print(json.dumps({"questions":len(rows),"converted":len(changes),"samples":[{"question":n["question_text"],"options":json.loads(n["options_json"]),"explanation":n["explanation"]} for _,n in changes[:2]]},ensure_ascii=False))
    if not args.apply or not changes:return
    folder=Path("/var/backups/predictioncomp-question-db"); folder.mkdir(parents=True,exist_ok=True)
    backup=folder/("before-sterling-"+dt.datetime.now().strftime("%Y%m%d-%H%M%S")+".sqlite")
    with sqlite3.connect(backup) as dest:con.backup(dest)
    with con:
        con.execute("begin immediate")
        current=[dict(r) for r in con.execute("select * from questions")]
        if current!=rows:raise RuntimeError("Questions changed during preparation; retry")
        rounds=[tuple(r) for r in con.execute("select * from daily_questions order by club_id,quiz_date,position")]
        usage=[tuple(r) for r in con.execute("select id,correct_index,use_count,last_used_date from questions order by id")]
        con.execute("create table if not exists sterling_conversion_audit(question_id integer primary key, original_json text not null, converted_at text not null)")
        for old,new in changes:
            con.execute("insert into sterling_conversion_audit values(?,?,?)",(old["id"],json.dumps(old,ensure_ascii=False),dt.datetime.now(dt.timezone.utc).isoformat()))
            con.execute("update questions set question_text=?,options_json=?,explanation=?,content_hash=? where id=?",(new["question_text"],new["options_json"],new["explanation"],new["content_hash"],old["id"]))
        for row in con.execute("select * from questions"):assert_sterling(dict(row))
        assert rounds==[tuple(r) for r in con.execute("select * from daily_questions order by club_id,quiz_date,position")]
        assert usage==[tuple(r) for r in con.execute("select id,correct_index,use_count,last_used_date from questions order by id")]
        assert con.execute("pragma integrity_check").fetchone()[0]=="ok"
    print(f"Updated {len(changes)} questions; answer positions, usage and daily rounds preserved. Backup: {backup}")
if __name__=="__main__":main()
