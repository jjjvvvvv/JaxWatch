#!/usr/bin/env python3
"""
Minimal admin view for collection-first system.
Lists sources, last collection date, and per-source collected files.
"""

from __future__ import annotations

from pathlib import Path
from flask import Flask, render_template_string, Response
import json
from datetime import datetime

RAW_DIR = Path("outputs/raw")

app = Flask(__name__)


INDEX_TMPL = """
<!DOCTYPE html>
<html><head><title>JaxWatch Collector Admin</title></head>
<body>
  <h1>JaxWatch Collector Admin</h1>
  <h2>Sources</h2>
  <ul>
  {% for s in sources %}
    <li>
      <a href="/source/{{ s['id'] }}">{{ s['id'] }}</a>
      — latest: {{ s['latest_year'] or 'N/A' }} ({{ s['latest_count'] }} items)
    </li>
  {% endfor %}
  </ul>
</body></html>
"""

SOURCE_TMPL = """
<!DOCTYPE html>
<html><head><title>{{ sid }}</title></head>
<body>
  <h1>Source: {{ sid }}</h1>
  <h3>Years</h3>
  <ul>
  {% for y in years %}
    <li>
      <a href="/source/{{ sid }}/{{ y['year'] }}">{{ y['year'] }}</a>
      — {{ y['count'] }} items
      [<a href="/raw/{{ sid }}/{{ y['year'] }}">raw</a>]
    </li>
  {% endfor %}
  </ul>
  <p><a href="/">Back</a></p>
  </body></html>
"""

YEAR_TMPL = """
<!DOCTYPE html>
<html><head><title>{{ sid }} {{ year }}</title></head>
<body>
  <h1>{{ sid }} — {{ year }}</h1>
  <p>Total items: {{ items|length }}</p>
  <table border="1" cellspacing="0" cellpadding="4">
    <tr>
      <th>#</th>
      <th>date_collected</th>
      <th>doc_type</th>
      <th>title</th>
      <th>url</th>
    </tr>
    {% for i, it in enumerate(items) %}
      <tr>
        <td>{{ i + 1 }}</td>
        <td>{{ it.get('date_collected', '') }}</td>
        <td>{{ it.get('doc_type', '(missing)') }}</td>
        <td>{{ it.get('title', '') }}</td>
        <td><a href="{{ it.get('url','') }}" target="_blank">{{ it.get('url','') }}</a></td>
      </tr>
    {% endfor %}
  </table>
  <p><a href="/source/{{ sid }}">Back to years</a> — <a href="/">Home</a></p>
</body></html>
"""


def list_sources():
    if not RAW_DIR.exists():
        return []
    out = []
    for src_dir in sorted([p for p in RAW_DIR.iterdir() if p.is_dir()]):
        sid = src_dir.name
        years = [yd.name for yd in src_dir.iterdir() if yd.is_dir() and yd.name.isdigit()]
        latest_year = sorted(years)[-1] if years else None
        latest_count = 0
        if latest_year:
            path = src_dir / latest_year / f"{sid}.json"
            if path.exists():
                try:
                    data = json.load(path.open("r"))
                    latest_count = len(data.get("items", []))
                except Exception:
                    latest_count = 0
        out.append({"id": sid, "latest_year": latest_year, "latest_count": latest_count})
    return out


@app.route("/")
def index():
    return render_template_string(INDEX_TMPL, sources=list_sources())


@app.route("/source/<sid>")
def source_view(sid: str):
    src_dir = RAW_DIR / sid
    year_entries = []
    if src_dir.exists():
        for yd in sorted([p for p in src_dir.iterdir() if p.is_dir() and p.name.isdigit()]):
            path = yd / f"{sid}.json"
            count = 0
            if path.exists():
                try:
                    data = json.load(path.open("r"))
                    count = len(data.get("items", []))
                except Exception:
                    count = 0
            year_entries.append({"year": yd.name, "count": count})
    return render_template_string(SOURCE_TMPL, sid=sid, years=year_entries)


@app.route("/source/<sid>/<year>")
def year_view(sid: str, year: str):
    path = RAW_DIR / sid / year / f"{sid}.json"
    if not path.exists():
        return ("Not found", 404)
    try:
        data = json.load(path.open("r"))
    except Exception:
        data = {"items": []}
    items = data.get("items", [])
    return render_template_string(YEAR_TMPL, sid=sid, year=year, items=items)

@app.route("/raw/<sid>/<year>")
def raw_year(sid: str, year: str):
    path = RAW_DIR / sid / year / f"{sid}.json"
    if not path.exists():
        return ("Not found", 404)
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        text = path.read_bytes().decode("utf-8", errors="replace")
    return Response(text, mimetype="application/json")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=5010)
    args = ap.parse_args()
    app.run(host="0.0.0.0", port=args.port, debug=False)
