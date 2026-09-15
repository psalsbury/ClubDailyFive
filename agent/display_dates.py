"""Presentation-only date formatting; never change identities, URLs or seasons."""
import datetime as dt
import hashlib
import json
import re
MONTHS = ('Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec')
NAMES = ('January','February','March','April','May','June','July','August','September','October','November','December')
LOOKUP = {name.lower():i+1 for i,name in enumerate(NAMES)}
LOOKUP.update({name.lower():i+1 for i,name in enumerate(MONTHS)})
PATTERN = re.compile(r'https?://\S+|\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}(?:st|nd|rd|th)?[ -](?:'+ '|'.join(NAMES+MONTHS)+r')[ ,\-]+\d{4}\b|\b\d{1,2}/\d{1,2}/\d{4}\b',re.I)


def display_date(value):
    date = dt.date.fromisoformat(value) if isinstance(value,str) else value
    return f'{date.day:02d}-{MONTHS[date.month-1]}-{date.year:04d}'


def format_dates(text):
    def replace(match):
        value=match.group()
        if value.lower().startswith(('http://','https://')): return value
        try:
            if re.fullmatch(r'\d{4}-\d{2}-\d{2}',value): return display_date(value)
            parts=re.split(r'[ /,\-]+',value)
            day=int(re.sub(r'(st|nd|rd|th)$','',parts[0],flags=re.I))
            month=int(parts[1]) if parts[1].isdigit() else LOOKUP[parts[1].lower()]
            return display_date(dt.date(int(parts[2]),month,day))
        except (ValueError,KeyError): return value
    return PATTERN.sub(replace,text)


def format_question(row):
    out=dict(row)
    for field in ('question_text','explanation'): out[field]=format_dates(out[field])
    options=[format_dates(x) for x in json.loads(out['options_json'])]
    if len(set(options))!=len(options): raise ValueError('Date formatting would duplicate answer options')
    out['options_json']=json.dumps(options,ensure_ascii=False)
    out['content_hash']=hashlib.sha256((out['semantic_key']+'|'+out['question_text']).encode()).hexdigest()
    return out
