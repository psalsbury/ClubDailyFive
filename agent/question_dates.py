"""Explicit match dates for high-scoring opponent questions."""
import datetime as dt
import re
from display_dates import display_date, format_dates


def dated_opponent_question(text, fact_date):
    if not re.search(r'\bhigh[- ]scoring\b', text, re.I) or not re.search(r'\b(?:who did|which (?:team|club|opponent))\b', text, re.I):
        return text
    text = format_dates(text)
    date = dt.date.fromisoformat(str(fact_date))
    label = display_date(date)
    if label in text or date.isoformat() in text:
        return text
    if 'league match' in text:
        return text.replace('league match', 'league match on ' + label, 1)
    return text.rstrip('?') + ' on ' + label + '?'
