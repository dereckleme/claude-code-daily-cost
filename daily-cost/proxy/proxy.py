#!/usr/bin/env python3
"""Reverse proxy to api.anthropic.com that captures rate-limit headers.

Every response from upstream has `anthropic-ratelimit-*` headers. We snapshot
the ones in CAPTURED_PREFIXES/CAPTURED_EXACT into `usage-state-<label>.json`
next to this file, where `<label>` identifies the calling Claude Code config
dir (`.claude` → `default`, `.claude-pessoal` → `pessoal`, …). The client
tags each request by prefixing the URL with `/_env_<label>` — we strip that
segment before forwarding upstream. Body is never read nor stored.

Env:
    CLAUDE_USAGE_PROXY_PORT (default 8765)
    CLAUDE_USAGE_PROXY_BIND (default 127.0.0.1)
    CLAUDE_USAGE_UPSTREAM   (default api.anthropic.com)
"""
import glob
import http.client
import http.server
import json
import os
import re
import socketserver
import ssl
import sys
import threading
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))

UPSTREAM_HOST = os.environ.get("CLAUDE_USAGE_UPSTREAM", "api.anthropic.com")
PORT = int(os.environ.get("CLAUDE_USAGE_PROXY_PORT", "8765"))
BIND = os.environ.get("CLAUDE_USAGE_PROXY_BIND", "127.0.0.1")
HEALTH_PATH = "/_usage_proxy_health"

ENV_PREFIX_RE = re.compile(r"^/_env_([a-z0-9_-]+)(?=/|$)")
DEFAULT_LABEL = "default"


def state_file_for(label):
    safe = re.sub(r"[^a-z0-9_-]+", "-", (label or DEFAULT_LABEL).lower()).strip("-") or DEFAULT_LABEL
    return os.path.join(HERE, f"usage-state-{safe}.json")

HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host",
}

CAPTURED_PREFIXES = ("anthropic-ratelimit-", "anthropic-organization-")
CAPTURED_EXACT = {"retry-after", "anthropic-request-id"}

_state_lock = threading.Lock()


def update_state(label, headers_list):
    captured = {}
    for k, v in headers_list:
        lk = k.lower()
        if lk in CAPTURED_EXACT or any(lk.startswith(p) for p in CAPTURED_PREFIXES):
            captured[lk] = v
    if not captured:
        return
    captured["updated_at"] = datetime.now(timezone.utc).isoformat()
    captured["env_label"] = label
    path = state_file_for(label)
    tmp = path + ".tmp"
    with _state_lock:
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(captured, f)
            os.replace(tmp, path)
        except OSError:
            pass


def read_all_states():
    out = {}
    for path in glob.glob(os.path.join(HERE, "usage-state-*.json")):
        label = os.path.basename(path)[len("usage-state-"):-len(".json")]
        try:
            with open(path, "r", encoding="utf-8") as f:
                out[label] = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
    return out


class ProxyHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    timeout = 600

    def _send_health(self):
        body = json.dumps({"ok": True, "envs": read_all_states()}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass
        self.close_connection = True

    def _split_env_label(self, path):
        m = ENV_PREFIX_RE.match(path)
        if not m:
            return DEFAULT_LABEL, path
        label = m.group(1)
        rest = path[m.end():] or "/"
        return label, rest

    def _read_body(self):
        te = (self.headers.get("transfer-encoding") or "").lower()
        cl = self.headers.get("content-length")
        if cl and cl.isdigit():
            n = int(cl)
            return self.rfile.read(n) if n > 0 else b""
        if "chunked" in te:
            chunks = []
            while True:
                size_line = self.rfile.readline().strip()
                if not size_line:
                    break
                try:
                    size = int(size_line.split(b";")[0], 16)
                except ValueError:
                    break
                if size == 0:
                    self.rfile.readline()
                    break
                chunks.append(self.rfile.read(size))
                self.rfile.readline()
            return b"".join(chunks)
        return b""

    def _forward(self, method):
        if self.path == HEALTH_PATH:
            return self._send_health()

        label, upstream_path = self._split_env_label(self.path)

        body = self._read_body() if method in ("POST", "PUT", "PATCH", "DELETE") else b""
        headers = {}
        for k, v in self.headers.items():
            if k.lower() in HOP_HEADERS or k.lower() == "content-length":
                continue
            headers[k] = v
        headers["Host"] = UPSTREAM_HOST
        if body:
            headers["Content-Length"] = str(len(body))

        ctx = ssl.create_default_context()
        conn = http.client.HTTPSConnection(UPSTREAM_HOST, timeout=self.timeout, context=ctx)
        try:
            conn.request(method, upstream_path, body=body if body else None, headers=headers)
            resp = conn.getresponse()
        except Exception as e:
            try:
                self.send_error(502, f"Upstream error: {e}")
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass
            return

        try:
            update_state(label, resp.getheaders())
            self.send_response(resp.status, resp.reason)
            for k, v in resp.getheaders():
                lk = k.lower()
                if lk in HOP_HEADERS or lk == "content-length":
                    continue
                self.send_header(k, v)
            self.send_header("Transfer-Encoding", "chunked")
            self.send_header("Connection", "close")
            self.end_headers()
            while True:
                chunk = resp.read(4096)
                if not chunk:
                    break
                try:
                    self.wfile.write(f"{len(chunk):X}\r\n".encode())
                    self.wfile.write(chunk)
                    self.wfile.write(b"\r\n")
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    break
            try:
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
        finally:
            try:
                conn.close()
            except Exception:
                pass
        self.close_connection = True

    def do_GET(self): self._forward("GET")
    def do_POST(self): self._forward("POST")
    def do_PUT(self): self._forward("PUT")
    def do_DELETE(self): self._forward("DELETE")
    def do_PATCH(self): self._forward("PATCH")
    def do_OPTIONS(self): self._forward("OPTIONS")
    def do_HEAD(self): self._forward("HEAD")

    def log_message(self, fmt, *args):
        return


class ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    server = ThreadingServer((BIND, PORT), ProxyHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    sys.exit(main())
