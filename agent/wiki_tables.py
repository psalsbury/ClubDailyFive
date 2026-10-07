"""Parse Wikipedia HTML tables into grids, expanding rowspan/colspan and keeping each cell's links."""
from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from urllib.parse import unquote


class _Tables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.stack = [], []
        self.row = self.cell = None
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'table':
            self.stack.append({'class': a.get('class', ''), 'rows': []})
        elif not self.stack:
            return
        elif tag == 'tr':
            self.row = []
        elif tag in ('td', 'th') and self.row is not None:
            self.cell = {'text': '', 'links': [], 'rowspan': int(re.sub(r'\D', '', a.get('rowspan', '1')) or 1),
                         'colspan': int(re.sub(r'\D', '', a.get('colspan', '1')) or 1), 'th': tag == 'th'}
        elif tag == 'a' and self.cell is not None and a.get('href', '').startswith('/wiki/'):
            self.cell['links'].append(unquote(a['href'][6:].split('#')[0]).replace('_', ' '))
        elif tag in ('sup', 'style') and self.cell is not None:
            self.skip += 1
        elif tag == 'br' and self.cell is not None:
            self.cell['text'] += ' '

    def handle_endtag(self, tag):
        if tag in ('sup', 'style') and self.skip:
            self.skip -= 1
        elif tag in ('td', 'th') and self.cell is not None and self.row is not None:
            self.cell['text'] = re.sub(r'\s+', ' ', self.cell['text']).strip()
            self.row.append(self.cell); self.cell = None
        elif tag == 'tr' and self.row is not None and self.stack:
            self.stack[-1]['rows'].append(self.row); self.row = None
        elif tag == 'table' and self.stack:
            self.tables.append(self.stack.pop())

    def handle_data(self, data):
        if self.cell is not None and not self.skip:
            self.cell['text'] += data


def tables(html_text: str, css: str = 'wikitable'):
    p = _Tables(); p.feed(html_text)
    out = []
    for t in p.tables:
        if css not in t['class']:
            continue
        grid, pending = [], {}
        for row in t['rows']:
            line, col, cells = [], 0, list(row)
            while cells or col in pending:
                if col in pending:
                    cell, left = pending[col]
                    line.append(cell)
                    if left > 1: pending[col] = (cell, left - 1)
                    else: del pending[col]
                    col += 1
                    continue
                cell = cells.pop(0)
                for _ in range(cell['colspan']):
                    line.append(cell)
                    if cell['rowspan'] > 1: pending[col] = (cell, cell['rowspan'] - 1)
                    col += 1
            grid.append(line)
        out.append(grid)
    return out


def header_index(grid, *names):
    """Find the header row and the column index of each wanted header (prefix match, case-insensitive)."""
    for i, row in enumerate(grid[:3]):
        heads = [re.sub(r'\[.*?\]', '', c['text']).strip().lower() for c in row]
        idx = []
        for n in names:
            hit = next((j for j, h in enumerate(heads) if h.startswith(n.lower())), None)
            idx.append(hit)
        if all(x is not None for x in idx):
            return i, idx
    return None, None
