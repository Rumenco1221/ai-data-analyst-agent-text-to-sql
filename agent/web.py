"""Interfaz web sin dependencias externas.

Uso:  python -m agent.web --db data/sales.db --port 8000   →   http://localhost:8000
"""
from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .core import DataAnalystAgent
from .llm import get_provider

STATIC = Path(__file__).parent / "static" / "index.html"
MAX_QUESTION = 300


def make_handler(agent: DataAnalystAgent):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, body: bytes, ctype: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; "
                                                        "script-src 'self' 'unsafe-inline'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._send(200, STATIC.read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/api/health":
                self._send(200, json.dumps({"provider": agent.provider.name,
                                            "tables": sorted(agent.tables)}).encode(), "application/json")
            else:
                self._send(404, b"Not found", "text/plain")

        def do_POST(self):
            if self.path != "/api/ask":
                return self._send(404, b"Not found", "text/plain")
            try:
                length = min(int(self.headers.get("Content-Length", 0)), 10_000)
                question = str(json.loads(self.rfile.read(length) or b"{}").get("question", "")).strip()
            except (ValueError, json.JSONDecodeError):
                return self._send(HTTPStatus.BAD_REQUEST, b'{"error":"JSON invalido"}', "application/json")
            if not question or len(question) > MAX_QUESTION:
                return self._send(HTTPStatus.BAD_REQUEST,
                                  json.dumps({"error": f"Escribí una pregunta de hasta {MAX_QUESTION} caracteres."}).encode(),
                                  "application/json")
            r = agent.ask(question)
            payload = {"ok": r.ok, "sql": r.sql, "rows": r.rows[:200], "answer": r.answer, "error": r.error,
                       "chart": r.chart, "insights": r.insights, "attempts": r.attempts,
                       "latency_ms": r.latency_ms, "provider": r.provider}
            self._send(200, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def log_message(self, fmt, *args):  # logs breves
            print(f"[web] {self.address_string()} {fmt % args}")

    return Handler


def main() -> None:
    ap = argparse.ArgumentParser(description="Interfaz web del AI Data Analyst Agent")
    ap.add_argument("--db", default="data/sales.db")
    ap.add_argument("--provider", default=None)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    agent = DataAnalystAgent(args.db, provider=get_provider(args.provider))
    server = ThreadingHTTPServer((args.host, args.port), make_handler(agent))
    print(f"🤖 Abrí http://{args.host}:{args.port}  · proveedor: {agent.provider.name}")
    server.serve_forever()


if __name__ == "__main__":
    main()
