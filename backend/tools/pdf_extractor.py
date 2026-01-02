#!/usr/bin/env python3
"""
Download PDFs referenced in outputs/raw and extract their text.

Inputs:
- Scans outputs/raw/<source>/<YYYY>/*.json (and legacy outputs/raw/<source>/*.json)
- Filters items with URLs ending in .pdf or Legistar View.ashx with M in {A, M, E2, E3}

Outputs per item kept depend on the artifact policy:
- reference_only: only metadata saved under outputs/files/<source>/<YYYY>/meta/*.json
- download: PDF saved to outputs/files/<source>/<YYYY>/<filename>.pdf, text saved alongside
- parse_then_discard: text saved to outputs/files/<source>/<YYYY>/<filename>.pdf.txt and metadata saved under outputs/files/<source>/<YYYY>/meta/*.json without retaining the PDF

CLI:
  python3 -m backend.tools.pdf_extractor [--source ID] [--year YYYY] [--force]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional
from urllib.parse import urlparse, parse_qs

import requests
import pdfplumber
import yaml


RAW_DIR = Path("outputs/raw")
FILES_DIR = Path("outputs/files")
DEBUG_DIR = Path("outputs/debug")
PDF_DEBUG_LOG = DEBUG_DIR / "pdf_extractor.log"


@dataclass
class RawFile:
    source: str
    year: str
    path: Path


def iter_raw_files(source: Optional[str] = None, year: Optional[str] = None) -> Iterable[RawFile]:
    if not RAW_DIR.exists():
        return []
    if source:
        src_dir = RAW_DIR / source
        if not src_dir.exists():
            return []
        if year:
            # Year-based preferred; legacy fallback
            ydir = src_dir / year
            legacy = src_dir / f"{year}.json"
            if ydir.exists():
                for fp in sorted(ydir.glob("*.json")):
                    yield RawFile(source=source, year=year, path=fp)
            elif legacy.exists():
                yield RawFile(source=source, year=year, path=legacy)
        else:
            year_files = list(src_dir.glob("[0-9][0-9][0-9][0-9]/*.json"))
            if year_files:
                for fp in sorted(year_files):
                    yield RawFile(source=source, year=fp.parent.name, path=fp)
            else:
                for fp in sorted(src_dir.glob("*.json")):
                    # Legacy: infer year from filename prefix or current year
                    y = fp.stem[:4] if fp.stem[:4].isdigit() else datetime.now().strftime("%Y")
                    yield RawFile(source=source, year=y, path=fp)
        return

    # All sources
    for src_dir in sorted([p for p in RAW_DIR.iterdir() if p.is_dir()]):
        sid = src_dir.name
        if year:
            ydir = src_dir / year
            legacy = src_dir / f"{year}.json"
            if ydir.exists():
                for fp in sorted(ydir.glob("*.json")):
                    yield RawFile(source=sid, year=year, path=fp)
            elif legacy.exists():
                yield RawFile(source=sid, year=year, path=legacy)
        else:
            yfiles = list(src_dir.glob("[0-9][0-9][0-9][0-9]/*.json"))
            if yfiles:
                for fp in sorted(yfiles):
                    yield RawFile(source=sid, year=fp.parent.name, path=fp)
            else:
                for fp in sorted(src_dir.glob("*.json")):
                    y = fp.stem[:4] if fp.stem[:4].isdigit() else datetime.now().strftime("%Y")
                    yield RawFile(source=sid, year=y, path=fp)


LEGISTAR_VIEW_RE = re.compile(r"view\.ashx", re.I)


def is_cms_getattachment(url: str) -> bool:
    return bool(url and "cms/getattachment" in url.lower())


def is_pdf_like(url: str) -> bool:
    if not url:
        return False
    u = url.lower()
    if "sharepoint.com" in u and "guestaccess.aspx" in u:
        # DIA hosts PDFs behind SharePoint guestaccess links without .pdf extensions
        if "share=" in u:
            return True
    if u.endswith(".pdf"):
        return True
    if is_cms_getattachment(u):
        return True
    if LEGISTAR_VIEW_RE.search(u):
        q = parse_qs(urlparse(url).query)
        m = (q.get("M") or q.get("m") or [""])[0].upper()
        return m in {"A", "M", "E2", "E3"}
    return False


def make_filename(item: dict) -> str:
    # Prefer explicit filename if it ends with .pdf
    fn = (item.get("filename") or "").strip()
    if fn.lower().endswith(".pdf") and re.search(r"[a-z0-9]", fn, re.I):
        return fn
    # Derive from URL
    url = item.get("url") or ""
    # Special handling for DIA CMS getattachment links
    if is_cms_getattachment(url):
        p = urlparse(url).path.strip("/").split("/")
        # Expect [..., 'cms', 'getattachment', GUID, name]
        try:
            gi = p.index("getattachment")
        except ValueError:
            gi = -1
        guid = ""
        name = ""
        if gi >= 0:
            if gi + 1 < len(p):
                guid = p[gi + 1]
            if gi + 2 < len(p):
                name = p[gi + 2]
        if not name:
            # Fallback slug from URL hash
            name = hashlib.md5(url.encode("utf-8")).hexdigest()[:10]
        base = re.sub(r"[^a-zA-Z0-9._-]", "_", name)
        gid = re.sub(r"[^a-zA-Z0-9]", "", guid)[:36]
        stem = f"getattachment_{gid}_{base}" if gid else f"getattachment_{base}"
        if not stem.lower().endswith(".pdf"):
            stem += ".pdf"
        return stem

    path_name = Path(urlparse(url).path).name or "document.pdf"
    if path_name.lower().endswith(".pdf"):
        return path_name
    # Legistar or unknown extension: synthesize a stable name
    q = parse_qs(urlparse(url).query)
    m = (q.get("M") or q.get("m") or [""])[0].upper()
    doc_id = (q.get("ID") or q.get("Id") or q.get("id") or [""])[0]
    h = hashlib.md5(url.encode("utf-8")).hexdigest()[:10]
    mid = f"_{m}" if m else ""
    did = f"_{doc_id}" if doc_id else ""
    return f"view{mid}{did}_{h}.pdf"


def record_debug_event(payload: dict) -> None:
    try:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        event = dict(payload)
        event.setdefault("timestamp", datetime.now().isoformat())
        with PDF_DEBUG_LOG.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(event, sort_keys=True) + "\n")
    except Exception:
        pass


def save_binary(url: str, dest: Path, timeout: float = 45.0) -> tuple[bool, int, str, dict, str]:
    """Download binary with streaming and simple content-type validation.

    Returns (ok, status_code, content_type). When ok is False, file is not saved.
    For cms/getattachment and .pdf URLs, we expect application/pdf content-type.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with requests.get(url, stream=True, timeout=timeout, headers={"User-Agent": "JaxWatchPDF/1.0"}) as r:
            status = r.status_code
            ctype = r.headers.get("Content-Type", "") or ""
            final_url = str(r.url)
            if status != 200:
                return False, status, ctype, dict(r.headers), final_url
            # If explicitly a PDF URL or CMS getattachment, ensure content-type is PDF when provided
            if (url.lower().endswith(".pdf") or is_cms_getattachment(url)) and ("pdf" not in ctype.lower() and ctype != ""):
                # Not a PDF
                return False, status, ctype, dict(r.headers), final_url
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return True, status, ctype, dict(r.headers), final_url
    except Exception:
        return False, -1, "", {}, url


def extract_text(pdf_path: Path) -> str:
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            texts: List[str] = []
            for i, page in enumerate(pdf.pages):
                t = page.extract_text() or ""
                texts.append(f"[[PAGE {i+1}]]\n{t}")
            return "\n\n".join(texts)
    except Exception:
        # Fallback: minimal bytes decode (will be messy)
        try:
            data = pdf_path.read_bytes()
            return data.decode("latin-1", errors="ignore")
        except Exception:
            return ""


def load_artifact_policy() -> dict:
    cfg_path = Path("backend/collector/sources.yaml")
    try:
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out = {}
    for s in (cfg.get("sources") or []):
        sid = s.get("id")
        pol = (s.get("artifact_policy") or "reference_only").strip()
        if sid:
            out[sid] = pol
    return out


def head_metadata(url: str, timeout: float = 30.0) -> tuple[int, dict, str]:
    try:
        resp = requests.head(url, allow_redirects=True, timeout=timeout, headers={"User-Agent": "JaxWatchPDF/1.0"})
        return resp.status_code, dict(resp.headers), str(resp.url)
    except Exception:
        return -1, {}, url


def meta_filename(item: dict) -> str:
    # Base on the PDF filename stem even in reference-only mode
    stem = make_filename(item)
    if stem.lower().endswith('.pdf'):
        stem = stem[:-4]
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", stem)
    return f"{safe}.json"


def process_file(raw: RawFile, policy_map: dict[str, str], force: bool = False) -> tuple[int, int]:
    created_downloads = 0
    created_meta_only = 0
    try:
        data = json.load(raw.path.open("r"))
    except Exception as e:
        print(f"⚠️  Failed to read {raw.path}: {e}")
        return 0, 0
    items = data.get("items", [])
    year = data.get("year") or raw.year
    source_id = data.get("source") or raw.source
    policy = policy_map.get(source_id, "reference_only")

    meta_dir = FILES_DIR / source_id / str(year) / "meta"
    if policy in {"reference_only", "parse_then_discard"}:
        meta_dir.mkdir(parents=True, exist_ok=True)
    for it in items:
        url = it.get("url") or ""
        if not is_pdf_like(url):
            continue
        source = source_id

        if policy == "reference_only":
            # HEAD only and save meta
            mfn = meta_filename(it)
            mpath = meta_dir / mfn
            if mpath.exists() and not force:
                continue
            status_code, headers, final_url = head_metadata(url)
            meta = dict(it)
            meta.update({
                "saved_at": datetime.now().isoformat(),
                "status_code": status_code,
                "content_type": headers.get("Content-Type", ""),
                "content_length": headers.get("Content-Length", ""),
                "last_modified": headers.get("Last-Modified", ""),
                "etag": headers.get("ETag", ""),
                "final_url": final_url,
            })
            try:
                mpath.write_text(json.dumps(meta, indent=2), encoding="utf-8")
                created_meta_only += 1
                print(f"🛈 Saved meta for {source}/{year}: {mfn} (status={status_code})")
            except Exception as e:
                print(f"⚠️  Failed writing meta for {url}: {e}")
            continue

        if policy == "parse_then_discard":
            fn = make_filename(it)
            out_dir = FILES_DIR / source / str(year)
            out_dir.mkdir(parents=True, exist_ok=True)
            meta_dir.mkdir(parents=True, exist_ok=True)
            txt_path = out_dir / (fn + ".txt")
            mfn = meta_filename(it)
            meta_path = meta_dir / mfn
            if txt_path.exists() and meta_path.exists() and not force:
                continue
            with tempfile.TemporaryDirectory() as tmpdir:
                temp_pdf = Path(tmpdir) / fn
                ok, status_code, content_type, headers, final_url = save_binary(url, temp_pdf)
                if not ok:
                    print(f"⚠️  Skipping parse-only artifact (status={status_code} ctype='{content_type}') for {url}")
                    failure_meta = dict(it)
                    failure_meta.update({
                        "saved_at": datetime.now().isoformat(),
                        "status_code": status_code,
                        "content_type": content_type,
                        "headers": headers,
                        "final_url": final_url,
                        "failure_stage": "download",
                        "failure_reason": "non_pdf_response" if "pdf" not in (content_type or "").lower() else "http_error",
                    })
                    try:
                        meta_path.write_text(json.dumps(failure_meta, indent=2), encoding="utf-8")
                    except Exception as e:
                        print(f"⚠️  Failed writing failure meta for {url}: {e}")
                    record_debug_event({
                        "event": "download_failed",
                        "source": source,
                        "year": year,
                        "url": url,
                        "status_code": status_code,
                        "content_type": content_type,
                        "final_url": final_url,
                        "policy": policy,
                    })
                    continue
                try:
                    text = extract_text(temp_pdf)
                except Exception as e:
                    print(f"⚠️  Text extraction failed for temp PDF {temp_pdf}: {e}")
                    text = ""
            try:
                txt_path.write_text(text, encoding="utf-8")
            except Exception as e:
                print(f"⚠️  Failed writing text for {url}: {e}")
                continue

            meta = dict(it)
            meta.update({
                "saved_at": datetime.now().isoformat(),
                "status_code": status_code,
                "content_type": content_type,
                "content_length": (headers or {}).get("Content-Length", ""),
                "last_modified": (headers or {}).get("Last-Modified", ""),
                "etag": (headers or {}).get("ETag", ""),
                "final_url": final_url,
                "local_text_path": str(txt_path),
            })
            try:
                meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            except Exception as e:
                print(f"⚠️  Failed writing meta for {url}: {e}")
                continue
            created_downloads += 1
            print(f"✅ Parsed + discarded PDF for {source}/{year}: {fn}")
            continue

        # Download policy
        fn = make_filename(it)
        out_dir = FILES_DIR / source / str(year)
        pdf_path = out_dir / fn
        txt_path = pdf_path.with_name(pdf_path.name + ".txt")
        meta_path = pdf_path.with_name(pdf_path.name + ".meta.json")
        if pdf_path.exists() and txt_path.exists() and meta_path.exists() and not force:
            continue
        print(f"⬇️  Downloading {url} -> {pdf_path}")
        ok, status_code, content_type, headers, final_url = save_binary(url, pdf_path)
        if not ok:
            print(f"⚠️  Skipping (status={status_code} ctype='{content_type}') for {url}")
            try:
                if pdf_path.exists():
                    pdf_path.unlink()
            except Exception:
                pass
            failure_meta = dict(it)
            failure_meta.update({
                "saved_at": datetime.now().isoformat(),
                "status_code": status_code,
                "content_type": content_type,
                "headers": headers,
                "final_url": final_url,
                "failure_stage": "download",
                "failure_reason": "non_pdf_response" if "pdf" not in (content_type or "").lower() else "http_error",
            })
            try:
                meta_path.write_text(json.dumps(failure_meta, indent=2), encoding="utf-8")
            except Exception as e:
                print(f"⚠️  Failed writing failure meta for {pdf_path}: {e}")
            record_debug_event({
                "event": "download_failed",
                "source": source,
                "year": year,
                "url": url,
                "status_code": status_code,
                "content_type": content_type,
                "final_url": final_url,
                "policy": policy,
            })
            continue
        try:
            text = extract_text(pdf_path)
            txt_path.write_text(text, encoding="utf-8")
        except Exception as e:
            print(f"⚠️  Text extraction failed for {pdf_path}: {e}")
        meta = dict(it)
        meta.update({
            "saved_path": str(pdf_path),
            "text_path": str(txt_path),
            "saved_at": datetime.now().isoformat(),
            "content_type": content_type,
            "status_code": status_code,
            "content_length": headers.get("Content-Length", ""),
            "last_modified": headers.get("Last-Modified", ""),
            "etag": headers.get("ETag", ""),
            "final_url": final_url,
        })
        try:
            meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"⚠️  Failed writing meta for {pdf_path}: {e}")
        created_downloads += 1
        print(f"✅ Saved PDF + text for {source}/{year}: {pdf_path.name}")
    return created_downloads, created_meta_only


def process_single_pdf(pdf_path: Path, force: bool = False) -> int:
    pdf = pdf_path.expanduser()
    if not pdf.exists() or not pdf.is_file():
        print(f"⚠️  Single-file mode: '{pdf}' not found or not a file")
        return 1
    if pdf.suffix.lower() != ".pdf":
        print(f"⚠️  Single-file mode expects a PDF, received '{pdf.name}'")
        return 1

    txt_path = pdf.with_name(pdf.name + ".txt")
    if txt_path.exists() and not force:
        print(f"🛈 Text already exists at {txt_path}, use --force to overwrite")
        return 0

    try:
        text = extract_text(pdf)
    except Exception as exc:
        print(f"⚠️  Failed extracting text from {pdf}: {exc}")
        return 1

    try:
        txt_path.write_text(text, encoding="utf-8")
    except Exception as exc:
        print(f"⚠️  Failed writing text to {txt_path}: {exc}")
        return 1

    print(f"✅ Extracted text for {pdf} -> {txt_path}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Fetch PDFs and extract their text")
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--source", help="Limit to a single source id", default=None)
    group.add_argument("--file", help="Process a single local PDF file", default=None)
    ap.add_argument("--year", help="Limit to a single year (YYYY)", default=None)
    ap.add_argument("--force", action="store_true", help="Re-download and re-extract even if files exist")
    args = ap.parse_args(argv)

    if args.file:
        if args.year:
            ap.error("--year cannot be used with --file")
        return process_single_pdf(Path(args.file), force=args.force)

    total_dl = 0
    total_meta = 0
    found_any = False
    policy_map = load_artifact_policy()
    for rf in iter_raw_files(args.source, args.year):
        found_any = True
        dl, meta_only = process_file(rf, policy_map, force=args.force)
        total_dl += dl
        total_meta += meta_only
    if not found_any:
        print("⚠️  No raw files found under outputs/raw")
        return 1
    print(f"\n🏁 Artifact processing complete. Downloads: {total_dl}  Meta-only: {total_meta}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
