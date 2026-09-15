"""Explicit match dates for high-scoring opponent questions."""
import datetime as dt
import re


def dated_opponent_question(text, fact_date):
    if not re.search(r'\bhigh[- ]scoring\b', text, re.I) or not re.search(r'\b(?:who did|which (?:team|club|opponent))\b', text, re.I):
        return text
    date = dt.date.fromisoformat(str(fact_date))
    label = f'{date.day} {date.strftime("%B")} {date.year}'
    if label in text or date.isoformat() in text:
        return text
    if 'league match' in text:
        return text.replace('league match', 'league match on ' + label, 1)
    return text.rstrip('?') + ' on ' + label + '?'
