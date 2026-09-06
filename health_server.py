#!/usr/bin/env python3
"""
Local server that receives step data from the iPhone Shortcut
and caches it to a local JSON file, keyed by day.

Run:      python3 health_server.py
Shortcut's "Get Contents of URL" should point at:
          http://<your-mac-hostname>.local:8080/steps
"""

import json
import http.server
import socketserver
from datetime import datetime
from pathlib import Path

PORT = 8080
CACHE_FILE = Path.home() / "health_dashboard" / "cache.json"
CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_cache():
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text())
    return {"steps_by_day": {}}


def save_cache(cache):
    CACHE_FILE.write_text(json.dumps(cache, indent=2))


def parse_date(raw_date):
    """Handles Shortcuts' human-readable date format, e.g.
    'Aug 16, 2026 at 12:25 AM' (with a narrow no-break space
    before AM/PM). Falls back to a raw slice if parsing fails."""
    cleaned = str(raw_date).replace("\u202f", " ").strip()
    try:
        dt = datetime.strptime(cleaned, "%b %d, %Y at %I:%M %p")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return cleaned[:10]


def parse_days_field(raw):
    """Shortcuts sent this as newline-separated individual JSON
    objects (not a real nested array) - parse each line on its own."""
    entries = []
    for line in str(raw).strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            print(f"Skipping unparseable line: {line!r}")
    return entries


class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/steps":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        cache = load_cache()
        entries = parse_days_field(payload.get("days", ""))

        for entry in entries:
            date_str = parse_date(entry.get("date", ""))
            steps = entry.get("steps", 0)
            if date_str:
                cache["steps_by_day"][date_str] = steps

        save_cache(cache)
        print(f"Updated {len(entries)} day(s): {cache['steps_by_day']}")

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    with socketserver.TCPServer(("0.0.0.0", PORT), Handler) as httpd:
        print(f"Listening on port {PORT}, writing to {CACHE_FILE}")
        httpd.serve_forever()
