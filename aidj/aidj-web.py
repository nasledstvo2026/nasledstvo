#!/usr/bin/env python3
"""
AI DJ — Web Server (serves player page + audio files)
Port 8765
"""

import http.server
import os
import socketserver

PORT = 8765
AIDJ_DIR = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=AIDJ_DIR, **kwargs)

    def log_message(self, format, *args):
        # Quiet mode — only log errors
        if args[0].startswith("4") or args[0].startswith("5"):
            super().log_message(format, *args)


if __name__ == "__main__":
    os.chdir(AIDJ_DIR)
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"[AI DJ Web] Serving {AIDJ_DIR} on port {PORT}")
        httpd.serve_forever()
