#!/usr/bin/env python3
"""Apply the attendance-option rule to every existing database question."""
import sqlite3

from attendance_options import migrate_attendance_options
from build_v3_bank import DB


def main():
    con = sqlite3.connect(DB, timeout=60)
    con.row_factory = sqlite3.Row
    try:
        con.execute("BEGIN IMMEDIATE")
        changed = migrate_attendance_options(con)
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    print(f"updated {changed} attendance questions")


if __name__ == "__main__":
    main()
