#!/usr/bin/env python3
"""Run a ClubDailyFive background job and email its database change report."""
from __future__ import annotations

import argparse
import datetime as dt
import os
import shutil
import sqlite3
import subprocess
import tempfile
import traceback
from email.message import EmailMessage
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/London")
FROM = "admin@clubdailyfive.com"
TO = "pete@salsbury.co.uk"
SENDMAIL = "/usr/sbin/sendmail"

JOBS = {
    "playerwordle": {
        "label": "Player Wordle agent",
        "db": "/var/lib/clubdailyfive/player-wordle/game.sqlite3",
        "commands": [
            ["/usr/bin/python3", "/opt/clubdailyfive/player-wordle/collector.py"],
            ["/usr/bin/python3", "/opt/clubdailyfive/player-wordle/nightly.py"],
        ],
    },
    "questions": {
        "label": "ClubDailyFive questions agent",
        "db": "/var/lib/clubdailyfive/clubquiz.sqlite",
        "commands": [["/usr/bin/python3", "/opt/predictioncomp/bin/generate_questions.py"]],
    },
}


def backup_database(path: str, destination: str) -> None:
    source = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30)
    target = sqlite3.connect(destination)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()


def rows(db: str, sql: str, args=()):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(sql, args)]
    finally:
        con.close()


def keyed(items, keys):
    return {tuple(item[k] for k in keys): item for item in items}


def format_items(title, items, formatter, limit=80):
    if not items:
        return [f"{title}: none"]
    out = [f"{title}: {len(items)}"]
    for item in items[:limit]:
        out.append(f"  - {formatter(item)}")
    if len(items) > limit:
        out.append(f"  - …and {len(items) - limit} more")
    return out


def player_changes(before: str, after: str):
    sections = []
    queries = {
        "candidates": """SELECT pc.club_id,c.name club,pc.name,pc.status,pc.source_url
                         FROM player_candidates pc JOIN clubs c ON c.id=pc.club_id""",
        "players": """SELECT p.id,p.club_id,c.name club,p.name,p.debut_age,p.debut_year,p.position,
                      p.nationality,p.continent,p.appearances,p.prior_clubs,p.source_url
                      FROM players p JOIN clubs c ON c.id=p.club_id""",
        "games": """SELECT d.game_date,d.club_id,c.name club,p.name player
                    FROM daily_game d JOIN clubs c ON c.id=d.club_id JOIN players p ON p.id=d.player_id""",
    }
    old_c = keyed(rows(before, queries["candidates"]), ("club_id", "name"))
    new_c = keyed(rows(after, queries["candidates"]), ("club_id", "name"))
    added_c = [new_c[k] for k in new_c.keys() - old_c.keys()]
    changed_c = [new_c[k] for k in new_c.keys() & old_c.keys() if new_c[k] != old_c[k]]
    sections += format_items("Player candidates added", sorted(added_c, key=lambda x:(x['club'],x['name'])), lambda x:f"{x['club']}: {x['name']} ({x['status']})")
    sections += format_items("Player candidates updated", sorted(changed_c, key=lambda x:(x['club'],x['name'])), lambda x:f"{x['club']}: {x['name']} → {x['status']}")

    old_p = keyed(rows(before, queries["players"]), ("club_id", "name"))
    new_p = keyed(rows(after, queries["players"]), ("club_id", "name"))
    added_p = [new_p[k] for k in new_p.keys() - old_p.keys()]
    changed_p = [new_p[k] for k in new_p.keys() & old_p.keys() if new_p[k] != old_p[k]]
    removed_p = [old_p[k] for k in old_p.keys() - new_p.keys()]
    sections += format_items("Validated players added", sorted(added_p, key=lambda x:(x['club'],x['name'])), lambda x:f"{x['club']}: {x['name']}")
    sections += format_items("Validated players updated", sorted(changed_p, key=lambda x:(x['club'],x['name'])), lambda x:f"{x['club']}: {x['name']}")
    sections += format_items("Validated players removed", sorted(removed_p, key=lambda x:(x['club'],x['name'])), lambda x:f"{x['club']}: {x['name']}")

    old_g = keyed(rows(before, queries["games"]), ("game_date", "club_id"))
    new_g = keyed(rows(after, queries["games"]), ("game_date", "club_id"))
    added_g = [new_g[k] for k in new_g.keys() - old_g.keys()]
    changed_g = [new_g[k] for k in new_g.keys() & old_g.keys() if new_g[k] != old_g[k]]
    sections += format_items("Daily mystery players added", sorted(added_g, key=lambda x:(x['game_date'],x['club'])), lambda x:f"{x['game_date']} — {x['club']}: {x['player']}")
    sections += format_items("Daily mystery players changed", sorted(changed_g, key=lambda x:(x['game_date'],x['club'])), lambda x:f"{x['game_date']} — {x['club']}: {x['player']}")
    return sections


def question_changes(before: str, after: str):
    sections = []
    qsql = """SELECT q.id,c.name club,q.question_text,q.status,q.options_json,q.correct_index,
              q.explanation,q.fact_date,q.use_count,q.last_used_date
              FROM questions q JOIN clubs c ON c.id=q.club_id"""
    old_q = keyed(rows(before, qsql), ("id",))
    new_q = keyed(rows(after, qsql), ("id",))
    added_q = [new_q[k] for k in new_q.keys() - old_q.keys()]
    changed_q = [new_q[k] for k in new_q.keys() & old_q.keys() if new_q[k] != old_q[k]]
    removed_q = [old_q[k] for k in old_q.keys() - new_q.keys()]
    retired = [x for x in changed_q if old_q[(x['id'],)]['status'] != x['status'] and x['status'] == 'retired']
    content_changed = [x for x in changed_q if any(old_q[(x['id'],)][k] != x[k] for k in ('question_text','options_json','correct_index','explanation'))]
    usage_changed = [x for x in changed_q if any(old_q[(x['id'],)][k] != x[k] for k in ('use_count','last_used_date'))]
    sections += format_items("Question records added", sorted(added_q,key=lambda x:(x['club'],x['id'])), lambda x:f"#{x['id']} {x['club']}: {x['question_text']}")
    sections += format_items("Question records retired", sorted(retired,key=lambda x:(x['club'],x['id'])), lambda x:f"#{x['id']} {x['club']}: {x['question_text']}")
    sections += format_items("Question content/options updated", sorted(content_changed,key=lambda x:(x['club'],x['id'])), lambda x:f"#{x['id']} {x['club']}: {x['question_text']}")
    sections += format_items("Question usage records updated", sorted(usage_changed,key=lambda x:(x['club'],x['id'])), lambda x:f"#{x['id']} {x['club']}: use count {x['use_count']}, last used {x['last_used_date']}")
    sections += format_items("Question records removed", sorted(removed_q,key=lambda x:(x['club'],x['id'])), lambda x:f"#{x['id']} {x['club']}: {x['question_text']}")

    dsql = """SELECT d.quiz_date,d.club_id,c.name club,d.position,d.question_id,q.question_text
              FROM daily_questions d JOIN clubs c ON c.id=d.club_id JOIN questions q ON q.id=d.question_id"""
    old_d = keyed(rows(before, dsql), ("quiz_date","club_id","position"))
    new_d = keyed(rows(after, dsql), ("quiz_date","club_id","position"))
    added_d = [new_d[k] for k in new_d.keys() - old_d.keys()]
    changed_d = [new_d[k] for k in new_d.keys() & old_d.keys() if new_d[k] != old_d[k]]
    sections += format_items("Daily quiz slots added", sorted(added_d,key=lambda x:(x['quiz_date'],x['club'],x['position'])), lambda x:f"{x['quiz_date']} — {x['club']} Q{x['position']}: #{x['question_id']} {x['question_text']}", 120)
    sections += format_items("Daily quiz slots changed", sorted(changed_d,key=lambda x:(x['quiz_date'],x['club'],x['position'])), lambda x:f"{x['quiz_date']} — {x['club']} Q{x['position']}: #{x['question_id']} {x['question_text']}", 120)
    return sections


def send_report(subject: str, body: str) -> None:
    message = EmailMessage()
    message["From"] = FROM
    message["To"] = TO
    message["Subject"] = subject
    message.set_content(body)
    subprocess.run([SENDMAIL, "-t", "-oi"], input=message.as_bytes(), check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("job", choices=JOBS)
    parser.add_argument("--test-email", action="store_true")
    args = parser.parse_args()
    job = JOBS[args.job]
    now = dt.datetime.now(TZ)
    if args.test_email:
        send_report(f"TEST: {job['label']} reporting enabled", f"Reporting is configured for {job['label']}.\n\nNo agent was run and no database was changed.")
        return

    output = []
    status = "SUCCESS"
    error = None
    with tempfile.TemporaryDirectory(prefix=f"{args.job}-report-") as temp:
        before = os.path.join(temp, "before.sqlite")
        try:
            backup_database(job["db"], before)
            for command in job["commands"]:
                result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                output.append(f"$ {' '.join(command)}\n{result.stdout.strip()}")
                if result.returncode:
                    raise subprocess.CalledProcessError(result.returncode, command, output=result.stdout)
        except Exception as exc:
            status = "FAILED"
            error = f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}"
        changes = []
        try:
            changes = player_changes(before, job["db"]) if args.job == "playerwordle" else question_changes(before, job["db"])
        except Exception as exc:
            changes = [f"Database comparison failed: {type(exc).__name__}: {exc}"]

    subject = f"{status}: {job['label']} — {now.strftime('%d-%b-%Y %H:%M')}"
    body = [
        job["label"],
        f"Run time: {now.strftime('%d-%b-%Y %H:%M:%S %Z')}",
        f"Result: {status}",
        "",
        "DATABASE UPDATES",
        "----------------",
        *changes,
        "",
        "JOB OUTPUT",
        "----------",
        *(output or ["No command output was captured."]),
    ]
    if error:
        body += ["", "ERROR", "-----", error]
    send_report(subject, "\n".join(body))
    if status != "SUCCESS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
