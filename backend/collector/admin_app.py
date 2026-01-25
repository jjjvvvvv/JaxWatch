#!/usr/bin/env python3
"""
Minimal admin view for collection-first system.
Lists sources, last collection date, and per-source collected files.
"""

from __future__ import annotations

from pathlib import Path
from flask import Flask, render_template_string, Response, request, redirect, url_for, jsonify
import json
RAW_DIR = Path("outputs/raw")
PROJECTS_INDEX = Path("outputs/projects/projects_index.json")
SOURCES_YAML = Path("backend/collector/sources.yaml")

app = Flask(__name__)

# Import and register enhanced admin API endpoints
try:
    from .admin_api_ext import register_admin_api_extensions
    register_admin_api_extensions(app)
    print("✅ Enhanced admin API endpoints registered")
except ImportError:
    print("⚠️ Enhanced admin API extensions not available")


def _is_remote_url(url: str | None) -> bool:
    return isinstance(url, str) and url.startswith(("http://", "https://"))


def _sanitize_mentions(mentions: list[dict] | None) -> list[dict]:
    sanitized: list[dict] = []
    for m in mentions or []:
        entry = dict(m)
        # Drop any local filesystem references that might sneak in
        for key in ["saved_path", "text_path", "local_text_path", "local_pdf_path"]:
            entry.pop(key, None)
        if not _is_remote_url(entry.get("url")):
            entry["url"] = ""
        sanitized.append(entry)
    return sanitized


def _sanitize_project(proj: dict) -> dict:
    copy = dict(proj)
    copy["mentions"] = _sanitize_mentions(proj.get("mentions") or [])
    return copy


def _sanitize_items(items: list[dict] | None) -> list[dict]:
    sanitized: list[dict] = []
    for it in items or []:
        entry = dict(it)
        for key in ["saved_path", "text_path", "local_text_path", "local_pdf_path"]:
            entry.pop(key, None)
        if not _is_remote_url(entry.get("url")):
            entry["url"] = ""
        sanitized.append(entry)
    return sanitized


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
      — root: {% if s['root_url'] %}<a href="{{ s['root_url'] }}" target="_blank">{{ s['root_url'] }}</a>{% else %}N/A{% endif %}
      — years: {{ s['years_summary'] or 'N/A' }}
      — last_collected_at: {{ s['last_collected_at'] or 'N/A' }}
    </li>
  {% endfor %}
  </ul>
  <h2>Projects</h2>
  <ul>
    <li><a href="/projects">Browse indexed projects</a></li>
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
  <form method="get">
    <label>Filter doc_type:
      <select name="doc_type" onchange="this.form.submit()">
        <option value="">(all)</option>
        {% for opt in ['agenda','minutes','packet','resolution','transcript','addendum','amendments','staff_report','presentation','exhibit'] %}
          <option value="{{ opt }}" {% if current_filter==opt %}selected{% endif %}>{{ opt }}</option>
        {% endfor %}
      </select>
    </label>
  </form>
  <p>Total items: {{ items|length }}</p>
  <table border="1" cellspacing="0" cellpadding="4">
    <tr>
      <th>#</th>
      <th>date_collected</th>
      <th>doc_type</th>
      <th>title</th>
      <th>summary</th>
      <th>url</th>
    </tr>
    {% for it in items %}
      <tr>
        <td>{{ loop.index }}</td>
        <td>{{ it.get('date_collected', '') }}</td>
        <td>{{ it.get('doc_type', '(missing)') }}</td>
        <td>{{ it.get('title', '') }}</td>
        <td style="max-width: 400px; font-size: 0.9em;">
          {% if it.get('summary') %}
            <details>
              <summary>View Summary</summary>
              <p style="white-space: pre-wrap;">{{ it.get('summary') }}</p>
            </details>
          {% else %}
            <span style="color: #ccc;">(none)</span>
          {% endif %}
        </td>
        <td>{% if it.get('url') %}<a href="{{ it.get('url') }}" target="_blank">Link</a>{% else %}—{% endif %}</td>
      </tr>
    {% endfor %}
  </table>
  <p><a href="/source/{{ sid }}">Back to years</a> — <a href="/">Home</a></p>
</body></html>
"""

PROJECTS_LIST_TMPL = """
<!DOCTYPE html>
<html><head><title>Projects</title></head>
<body>
  <h1>Projects Index</h1>
  <form method="get">
    <label>Filter doc_type:
      <select name="doc_type" onchange="this.form.submit()">
        <option value="">(all)</option>
        {% for opt in ['resolution','ordinance','project','ddrb','council_file'] %}
          <option value="{{ opt }}" {% if current_filter==opt %}selected{% endif %}>{{ opt }}</option>
        {% endfor %}
      </select>
    </label>
  </form>
  <p>Total: {{ projects|length }}</p>
  {% set has_pending = (projects | selectattr('pending_review') | list | length) > 0 %}
  {% if has_pending %}
    <div style="padding:8px; background:#fff3cd; border:1px solid #ffeeba; margin-bottom:10px;">
      ⚠️ Some projects are pending review. Use the approve button in details.
    </div>
  {% endif %}
  <table border="1" cellspacing="0" cellpadding="4">
    <tr>
      <th>#</th>
      <th>id</th>
      <th>title</th>
      <th>doc_type</th>
      <th>source</th>
      <th>meeting_date</th>
      <th>review</th>
      <th>mentions</th>
    </tr>
    {% for p in projects %}
      <tr>
        <td>{{ loop.index }}</td>
        <td><a href="/projects/{{ p['id'] }}">{{ p['id'] }}</a></td>
        <td>{{ p.get('title','') }}</td>
        <td>{{ p.get('doc_type','') }}</td>
        <td>{{ p.get('source','') }}</td>
        <td>{{ p.get('meeting_date','') }}</td>
        <td>{{ 'pending' if p.get('pending_review') else 'ok' }}</td>
        <td>{{ (p.get('mentions') or []) | length }}</td>
      </tr>
    {% endfor %}
  </table>
  <p><a href="/">Home</a></p>
</body></html>
"""

PROJECT_DETAIL_TMPL = """
<!DOCTYPE html>
<html><head><title>{{ proj.get('id') }}</title></head>
<body>
  <h1>Project: {{ proj.get('id') }}</h1>
  <form method="post" action="/projects/{{ proj['id'] }}/edit">
    <p>Title: <input type="text" name="title" size="80" value="{{ proj.get('title','')|e }}"/></p>
    <p>Doc Type: <input type="text" name="doc_type" value="{{ proj.get('doc_type','')|e }}"/></p>
    <p>Source: <input type="text" name="source" value="{{ proj.get('source','')|e }}"/></p>
    <p>Meeting Date: <input type="text" name="meeting_date" value="{{ proj.get('meeting_date','')|e }}"/></p>
    <p>Meeting Title: <input type="text" name="meeting_title" size="80" value="{{ proj.get('meeting_title','')|e }}"/></p>
    <p>
      <label><input type="checkbox" name="pending_review" value="1" {% if proj.get('pending_review') %}checked{% endif %}> Pending review</label>
    </p>
    <p>
      <button type="submit">Save</button>
      <button type="submit" formaction="/projects/{{ proj['id'] }}/approve">Approve</button>
      <button type="submit" formaction="/projects/{{ proj['id'] }}/delete" onclick="return confirm('Delete this project?');">Delete</button>
    </p>
  </form>
  <h3>Mentions ({{ (proj.get('mentions') or []) | length }})</h3>
  <table border="1" cellspacing="0" cellpadding="4">
    <tr><th>#</th><th>source</th><th>date</th><th>doc_type</th><th>title</th><th>snippet</th><th>url</th></tr>
    {% for m in proj.get('mentions') or [] %}
      <tr>
        <td>{{ loop.index }}</td>
        <td>{{ m.get('source','') }}</td>
        <td>{{ m.get('date','') }}</td>
        <td>{{ m.get('doc_type','') or m.get('doc','') }}</td>
        <td>{{ m.get('title','') }}</td>
        <td>{{ m.get('snippet','') }}</td>
        <td>{% if m.get('url') %}<a href="{{ m.get('url') }}" target="_blank">link</a>{% else %}—{% endif %}</td>
      </tr>
    {% endfor %}
  </table>
  <p><a href="/projects">Back to projects</a> — <a href="/">Home</a></p>
</body></html>
"""


def list_sources():
    # Build list strictly from sources.yaml, enriching with any raw data we have
    try:
        import yaml
        cfg = yaml.safe_load(SOURCES_YAML.read_text(encoding="utf-8"))
        configured = cfg.get("sources") or []
    except Exception:
        configured = []

    out = []
    for s in configured:
        sid = s.get("id")
        if not sid:
            continue
        root_url = s.get("root_url")
        src_dir = RAW_DIR / sid
        counts = []
        last_collected_at = None
        if src_dir.exists():
            years = [yd.name for yd in src_dir.iterdir() if yd.is_dir() and yd.name.isdigit()]
            for y in sorted(years):
                path = src_dir / y / f"{sid}.json"
                if not path.exists():
                    continue
                try:
                    data = json.load(path.open("r"))
                    c = len(data.get("items", []))
                    counts.append(f"{y}:{c}")
                    last_collected_at = data.get("last_collected_at") or data.get("updated_at") or last_collected_at
                except Exception:
                    continue
        years_summary = ", ".join(counts[-5:]) if counts else None
        out.append({
            "id": sid,
            "years_summary": years_summary,
            "root_url": root_url,
            "last_collected_at": last_collected_at,
        })
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
    doc_filter = (request.args.get("doc_type") or "").strip().lower() or None
    if doc_filter:
        items = [it for it in items if (it.get("doc_type") or "").lower() == doc_filter]
    sanitized_items = _sanitize_items(items)
    return render_template_string(YEAR_TMPL, sid=sid, year=year, items=sanitized_items, current_filter=doc_filter)

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


def load_projects() -> list[dict]:
    if PROJECTS_INDEX.exists():
        try:
            return json.load(PROJECTS_INDEX.open("r"))
        except Exception:
            return []
    return []


def save_projects(items: list[dict]) -> None:
    PROJECTS_INDEX.parent.mkdir(parents=True, exist_ok=True)
    PROJECTS_INDEX.write_text(json.dumps(items, indent=2), encoding="utf-8")


@app.route("/projects")
def projects_index():
    projs = load_projects()
    doc_filter = (request.args.get("doc_type") or "").strip().lower() or None
    if doc_filter:
        projs = [p for p in projs if (p.get("doc_type") or "").lower() == doc_filter]
    # Pending first, then by id/title
    projs = sorted(projs, key=lambda p: (0 if p.get("pending_review") else 1, p.get("id", ""), p.get("title", "")))
    sanitized = [_sanitize_project(p) for p in projs]
    return render_template_string(PROJECTS_LIST_TMPL, projects=sanitized, current_filter=doc_filter)


@app.route("/projects/<pid>")
def project_detail(pid: str):
    projs = load_projects()
    for p in projs:
        if str(p.get("id")) == pid:
            return render_template_string(PROJECT_DETAIL_TMPL, proj=_sanitize_project(p))
    return ("Not found", 404)


@app.route("/projects/<pid>/edit", methods=["POST"])
def project_edit(pid: str):
    projs = load_projects()
    for p in projs:
        if str(p.get("id")) == pid:
            # Editable fields
            for k in ["title", "doc_type", "source", "meeting_date", "meeting_title"]:
                val = request.form.get(k)
                if val is not None:
                    p[k] = val
            # Checkbox: present => True, missing => False
            p["pending_review"] = True if request.form.get("pending_review") else False
            save_projects(projs)
            return redirect(url_for("project_detail", pid=pid))
    return ("Not found", 404)


@app.route("/projects/<pid>/delete", methods=["POST"])
def project_delete(pid: str):
    projs = load_projects()
    new_list = [p for p in projs if str(p.get("id")) != pid]
    if len(new_list) == len(projs):
        return ("Not found", 404)
    save_projects(new_list)
    return redirect(url_for("projects_index"))


@app.route("/projects/<pid>/approve", methods=["POST"])
def project_approve(pid: str):
    projs = load_projects()
    for p in projs:
        if str(p.get("id")) == pid:
            p["pending_review"] = False
            save_projects(projs)
            return redirect(url_for("project_detail", pid=pid))
    return ("Not found", 404)






if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=5010)
    args = ap.parse_args()
    app.run(host="0.0.0.0", port=args.port, debug=False)
