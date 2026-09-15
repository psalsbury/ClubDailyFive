#!/usr/bin/env python3
"""API-Football client with a hard process-safe quota of 95 calls per UTC day."""
from __future__ import annotations

import datetime as dt
import json
import os
import sqlite3
import urllib.error
import urllib.parse
import urllib.request

API_BASE = "https://v3.football.api-sports.io"
QUOTA_DB = os.getenv("API_FOOTBALL_QUOTA_DB", "/var/lib/clubdailyfive/api_football_quota.sqlite")
DAILY_LIMIT = 95


class DailyQuotaExceeded(RuntimeError):
    pass


def _utc_day() -> str:
    return dt.datetime.now(dt.timezone.utc).date().isoformat()


def reserve_call() -> tuple[int, int]:
    """Atomically reserve one call before network access.

    Failed HTTP/network attempts remain counted, which makes the ceiling
    conservative and guarantees the application never initiates call 96.
    """
    con = sqlite3.connect(QUOTA_DB, timeout=30, isolation_level=None)
    try:
        con.execute("PRAGMA busy_timeout=30000")
        con.execute(
            """CREATE TABLE IF NOT EXISTS api_football_daily_usage (
                   utc_day TEXT PRIMARY KEY,
                   calls INTEGER NOT NULL CHECK(calls >= 0 AND calls <= 95)
               )"""
        )
        con.execute("BEGIN IMMEDIATE")
        day = _utc_day()
        row = con.execute(
            "SELECT calls FROM api_football_daily_usage WHERE utc_day=?", (day,)
        ).fetchone()
        used = int(row[0]) if row else 0
        if used >= DAILY_LIMIT:
            con.rollback()
            raise DailyQuotaExceeded(
                f"API-Football daily limit reached ({used}/{DAILY_LIMIT} for {day} UTC)"
            )
        new_used = used + 1
        con.execute(
            """INSERT INTO api_football_daily_usage(utc_day,calls) VALUES(?,?)
               ON CONFLICT(utc_day) DO UPDATE SET calls=excluded.calls""",
            (day, new_used),
        )
        con.commit()
        return new_used, DAILY_LIMIT
    except Exception:
        if con.in_transaction:
            con.rollback()
        raise
    finally:
        con.close()


def usage() -> tuple[str, int, int]:
    day = _utc_day()
    con = sqlite3.connect(QUOTA_DB, timeout=30)
    try:
        con.execute(
            """CREATE TABLE IF NOT EXISTS api_football_daily_usage (
                   utc_day TEXT PRIMARY KEY,
                   calls INTEGER NOT NULL CHECK(calls >= 0 AND calls <= 95)
               )"""
        )
        row = con.execute(
            "SELECT calls FROM api_football_daily_usage WHERE utc_day=?", (day,)
        ).fetchone()
        return day, int(row[0]) if row else 0, DAILY_LIMIT
    finally:
        con.close()


def get(endpoint: str, params: dict[str, object] | None = None) -> dict:
    api_key = os.getenv("API_FOOTBALL_KEY", "").strip()
    if not api_key:
        raise RuntimeError("API_FOOTBALL_KEY is not configured")
    reserve_call()
    path = endpoint if endpoint.startswith("/") else "/" + endpoint
    url = API_BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"x-apisports-key": api_key})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read(2048).decode("utf-8", "replace")
        raise RuntimeError(f"API-Football HTTP {exc.code}: {body}") from exc


if __name__ == "__main__":
    day, used, limit = usage()
    print(json.dumps({"utc_day": day, "calls_reserved": used, "daily_limit": limit}))
