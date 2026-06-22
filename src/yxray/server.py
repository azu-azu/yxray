"""Lightweight local HTTP server for yxray inspect with SQL export."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from yxray.models.types import ToolID
from yxray.models.workflow import WorkflowDoc
from yxray.sql import convert_cluster_to_sql


def _make_handler(doc: WorkflowDoc, html: str) -> type[BaseHTTPRequestHandler]:
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path not in ("/", "/index.html"):
                self.send_error(404)
                return
            body = html.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            if self.path != "/api/cluster-to-sql":
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length))
            tool_ids = [ToolID(int(t)) for t in payload.get("tool_ids", [])]
            result = convert_cluster_to_sql(doc, tool_ids)
            response = json.dumps(
                {
                    "sql": result.sql,
                    "is_partial": result.report.is_partial,
                    "warnings": list(result.report.warnings),
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            pass  # suppress per-request logging

    return _Handler


def make_server(doc: WorkflowDoc, html: str, port: int = 7890) -> HTTPServer:
    return HTTPServer(("localhost", port), _make_handler(doc, html))
