#!/usr/bin/env python3
"""
Replit run-target for the Intrustum brand kit.

Verifies every mark against Production Handoff v1.0, then serves the reference
page so the marks are visible in the Replit webview. If any mark is
non-conformant the server refuses to start — you cannot ship drifted marks.

    python3 brand/serve.py            # gate + preview on 0.0.0.0:$PORT (default 8080)
"""
import http.server
import os
import socketserver
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import verify_marks  # noqa: E402

print("Verifying Intrustum marks …\n")
if verify_marks.main() != 0:
    print("\nRefusing to serve non-conformant marks. Fix the assets and re-run.")
    sys.exit(1)

port = int(os.environ.get("PORT", "8080"))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(HERE), **k)

    def log_message(self, *a):  # keep the console focused on the gate result
        pass


with socketserver.TCPServer(("0.0.0.0", port), Handler) as httpd:
    print(f"\nMark reference live → http://0.0.0.0:{port}/index.html")
    httpd.serve_forever()
