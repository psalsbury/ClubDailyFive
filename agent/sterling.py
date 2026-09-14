"""Sterling-only question presentation. Historical ECB rates via Frankfurter.
Source: https://api.frankfurter.dev/v1/2021-01-01..2026-02-02?base=EUR&symbols=GBP
Amounts are approximate conversions of the dataset's rounded euro figures,
not a claim about the exact sterling contract fee. Never relabel currencies.
"""
import bisect
import datetime as dt
from decimal import Decimal
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import urllib.request

EURO = re.compile(r"€\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(million|billion|thousand|[mkb])?(?!\w)", re.I)
FOREIGN = re.compile(r"[€$¥₹₽]|\b(?:EUR|USD|AUD|CAD|JPY|euros?|dollars?|yen)\b", re.I)
SCALE = {"m": 1000000, "million": 1000000, "k": 1000, "thousand": 1000, "b": 1000000000, "billion": 1000000000}
@lru_cache(maxsize=1)
def rate_data():
    return json.loads(Path(__file__).with_name("eur_gbp_rates.json").read_text())["rates"]

@lru_cache(maxsize=512)
def rate_for(date):
    target = dt.date.fromisoformat(date)
    rates = rate_data()
    days = sorted(rates)
    i = bisect.bisect_right(days, date) - 1
    day = days[i] if i >= 0 else None
    if day and 0 <= (target - dt.date.fromisoformat(day)).days <= 7:
        return day, Decimal(str(rates[day]["GBP"]))
    url = f"https://api.frankfurter.dev/v1/{date}?base=EUR&symbols=GBP"
    with urllib.request.urlopen(url, timeout=30) as response:
        data = json.load(response)
    day = data["date"]
    if not 0 <= (target - dt.date.fromisoformat(day)).days <= 7:
        raise ValueError(f"No suitable historic GBP rate for {date}")
    rate = Decimal(str(data["rates"]["GBP"]))
    if not Decimal("0") < rate < Decimal("2"):
        raise ValueError("Invalid GBP rate")
    return day, rate

def format_gbp(value, places=1):
    if value >= 1000000:
        return f"£{value / 1000000:.{places}f}m"
    if value >= 1000:
        return f"£{value / 1000:.{places}f}k"
    return f"£{value:.2f}"

def assert_sterling(q):
    content = "\n".join([q["question_text"], *json.loads(q["options_json"]), q["explanation"]])
    if FOREIGN.search(content):
        raise ValueError("Non-sterling currency in question; source conversion required")

def sterling_question(q):
    out = dict(q)
    fields = [out["question_text"], *json.loads(out["options_json"]), out["explanation"]]
    if not any("€" in text for text in fields):
        assert_sterling(out)
        return out
    day, rate = rate_for(out["fact_date"])
    def convert(text, places):
        return EURO.sub(lambda m: format_gbp(Decimal(m[1].replace(",", "")) * SCALE.get((m[2] or "").lower(), 1) * rate, places), text)
    original_options = json.loads(out["options_json"])
    for places in (1, 2, 3, 4, 6):
        options = [convert(s, places) for s in original_options]
        if len(set(options)) == len(options):
            break
    else:
        raise ValueError("Sterling conversion produced duplicate answer options")
    text = convert(out["question_text"], places)
    text = text.replace("What was the transfer fee for", "Approximately what was the transfer fee in pounds sterling for")
    explanation = convert(out["explanation"], places)
    explanation = explanation.replace("The recorded fee was", "The approximate sterling equivalent was")
    explanation += f" Approximate sterling conversion using the historical exchange rate on {day}."
    out.update(question_text=text, options_json=json.dumps(options, ensure_ascii=False), explanation=explanation)
    assert_sterling(out)
    if out.get("semantic_key"):
        out["content_hash"] = hashlib.sha256((out["semantic_key"] + "|" + text).encode()).hexdigest()
    return out
