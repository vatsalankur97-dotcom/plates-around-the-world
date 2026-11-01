#!/usr/bin/env python3
"""Local preview server. Not used by Netlify.

Extensionless paths map to the .html file and return 200.
Unknown paths return 404.html with status 404.
HTTPS is on by default so Lighthouse can pass the HTTPS check.
Certs are written under /tmp and are not part of the site.

    python3 scripts/serve.py
    PORT=8080 HTTPS=0 python3 scripts/serve.py
"""

from __future__ import annotations

import http.server
import os
import ssl
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        split = urlsplit(self.path)
        path = split.path
        if path != "/" and path.endswith("/"):
            path = path[:-1] or "/"
        rel = path.lstrip("/")
        query = ("?" + split.query) if split.query else ""
        if path == "/":
            self.path = "/index.html" + query
            return super().do_GET()
        direct = ROOT / rel
        html_file = ROOT / (rel + ".html")
        if direct.is_file():
            return super().do_GET()
        if html_file.is_file():
            self.path = "/" + rel + ".html" + query
            return super().do_GET()
        body = (ROOT / "404.html").read_bytes()
        self.send_response(404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):
        self.do_GET()


def main() -> None:
    port = int(os.environ.get("PORT", "8443"))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    scheme = "http"
    if os.environ.get("HTTPS", "1") != "0":
        cert = "/tmp/plates-dev.pem"
        key = "/tmp/plates-dev.key"
        if not os.path.exists(cert):
            subprocess.check_call([
                "openssl", "req", "-x509", "-newkey", "rsa:2048",
                "-keyout", key, "-out", cert, "-days", "2", "-nodes",
                "-subj", "/CN=localhost",
            ])
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert, key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        scheme = "https"
    print(f"serving {scheme}://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
