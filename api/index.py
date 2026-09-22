"""Vercel serverless entry for BREWMETRIC POS.

Wraps brewmetric.py Store/rendering logic as a WSGI app.
Local dev still uses `python brewmetric.py` (ThreadingHTTPServer).
On Vercel (`VERCEL=1`), DATA is redirected to /tmp (writable).
"""
import os
import sys

# make project root importable (brewmetric.py is one level up)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import brewmetric as bm
from urllib.parse import parse_qs

# Vercel filesystem is read-only except /tmp
if os.environ.get("VERCEL"):
    bm.DATA = "/tmp/brewmetric_data.json"
    # CSS_FILE stays at project root (read-only is fine)
    bm.CSS_FILE = os.path.join(ROOT, "brewmetric.css")
    # re-init store to load from /tmp if exists (ignore errors)
    try:
        bm.store = bm.Store()
    except Exception:
        pass


def _read_body(environ):
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except (ValueError, TypeError):
        length = 0
    if length:
        return environ["wsgi.input"].read(length).decode()
    return ""


def app(environ, start_response):
    path = (environ.get("PATH_INFO") or "/").split("?")[0]
    method = (environ.get("REQUEST_METHOD") or "GET").upper()

    # Serve CSS via WSGI as fallback (Vercel also serves it statically)
    if path == "/brewmetric.css":
        try:
            with open(bm.CSS_FILE, "rb") as f:
                data = f.read()
            start_response("200 OK", [("Content-Type", "text/css; charset=utf-8"), ("Content-Length", str(len(data)))])
            return [data]
        except OSError:
            body = b"Not found"
            start_response("404 Not Found", [("Content-Type", "text/plain"), ("Content-Length", str(len(body)))])
            return [body]

    if path not in ("/", "/prep"):
        body = b"Not found"
        start_response("404 Not Found", [("Content-Type", "text/plain"), ("Content-Length", str(len(body)))])
        return [body]

    if method == "POST":
        raw = _read_body(environ)
        cmd = parse_qs(raw).get("do", [""])[0]
        try:
            bm.store.act(cmd)
        except (ValueError, IndexError, KeyError):
            pass
        part = cmd.split(":")
        if path == "/prep":
            anchor = ""
        else:
            if part[0] in ("inc", "dec", "page"):
                anchor = "#" + part[1] if len(part) > 1 else "#tp"
            elif part[0] in ("send", "reset"):
                anchor = "#sum"
            else:
                anchor = "#tp"
        location = path + anchor
        start_response("303 See Other", [("Location", location), ("Content-Length", "0")])
        return [b""]

    # GET
    html = (bm.prep() if path == "/prep" else bm.home()).encode()
    start_response("200 OK", [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(html)))])
    return [html]


# Vercel Python runtime looks for `app` or `handler`
handler = app
