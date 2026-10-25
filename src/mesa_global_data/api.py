from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List
from urllib.parse import parse_qs, urlparse

from .storage import Storage
from .validation import validate_storage


SITE_ORIGIN = "https://mesa-global.santiago-soules.chatgpt.site"


def _payload(storage: Storage, path: str, query: Dict[str, List[str]]) -> Any:
    if path == "/health":
        return {"status": "ok", "service": "mesa-global-data", "read_only": True}
    if path == "/api/market/coverage":
        return {
            "schema_version": "1.0.0",
            "sensors": storage.coverage(),
            "sources": storage.source_health(),
            "validation": validate_storage(storage),
        }
    if path == "/api/market/observations":
        ids = [item for value in query.get("ids", []) for item in value.split(",") if item]
        limit = min(max(int(query.get("limit", ["100"])[0]), 1), 2000)
        return {
            "schema_version": "1.0.0",
            "observations": storage.observations(ids or None, limit_per_sensor=limit),
        }
    if path.startswith("/api/market/series/"):
        sensor_id = path.rsplit("/", 1)[-1]
        limit = min(max(int(query.get("limit", ["500"])[0]), 1), 5000)
        return {
            "schema_version": "1.0.0",
            "sensor_id": sensor_id,
            "observations": storage.observations([sensor_id], limit_per_sensor=limit),
        }
    if path == "/api/market/analyses":
        return {"schema_version": "1.0.0", "analyses": storage.analyses()}
    raise KeyError(path)


def handler_factory(db_path: str):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            storage = Storage(db_path)
            try:
                try:
                    payload = _payload(storage, parsed.path, parse_qs(parsed.query))
                    body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
                    self.send_response(200)
                except (KeyError, ValueError) as exc:
                    body = json.dumps({"status": "error", "detail": str(exc)}).encode("utf-8")
                    self.send_response(404 if isinstance(exc, KeyError) else 400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", SITE_ORIGIN)
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
            finally:
                storage.close()

        def log_message(self, format: str, *args: Any) -> None:
            return

    return Handler


def serve(db_path: str, host: str = "127.0.0.1", port: int = 8787) -> None:
    server = HTTPServer((host, port), handler_factory(db_path))
    print("Mesa Global read-only API listening on http://{}:{}".format(host, port))
    print("Allowed browser origin: {}".format(SITE_ORIGIN))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

