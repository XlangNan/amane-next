"""Fake GitHub /releases/latest — 本地演示「有新版本」UI.

AMANE_UPDATE_URL=http://127.0.0.1:18765/releases/latest AMANE_TOKEN=off just dev-api
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "127.0.0.1"
PORT = 18765
BODY = {
    "tag_name": "v1.2.0",
    "html_url": "https://github.com/sqzw-x/amane/releases/tag/v1.2.0",
}


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        payload = json.dumps(BODY).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("ETag", '"demo-v1.2.0"')
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), _Handler)
    print(  # noqa: T201
        f"mock GitHub latest → http://{HOST}:{PORT}/releases/latest  (tag {BODY['tag_name']})", flush=True
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
