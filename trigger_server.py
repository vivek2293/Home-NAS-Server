# Copyright (C) 2026 Vivek
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import subprocess
import threading
import logging
import shutil
import time
import queue
import os

# ---------------------------------------------------------------------------
# Logging setup — structured, timestamped, level-prefixed output to stdout
# so `docker compose logs` shows clean, readable entries.
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)-8s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("trigger")

BASE_DIR   = "/downloads"
STAGING    = os.path.realpath(os.path.join(BASE_DIR, "staging"))
QUARANTINE = os.path.realpath(os.path.join(BASE_DIR, "quarantine"))
MEDIA      = os.path.realpath(os.path.join(BASE_DIR, "media"))

log.info("Paths  — staging:    %s", STAGING)
log.info("Paths  — quarantine: %s", QUARANTINE)
log.info("Paths  — media:      %s", MEDIA)

# --- Security: Shared Secret ---
# Loaded from the environment; set in .env and never committed to git.
TRIGGER_SECRET = os.environ.get("TRIGGER_SECRET", "")
if not TRIGGER_SECRET:
    raise RuntimeError("TRIGGER_SECRET environment variable is not set. Refusing to start.")
log.info("Auth   — TRIGGER_SECRET loaded (%d chars)", len(TRIGGER_SECRET))

# Worker queue — capped to prevent memory exhaustion under sustained load
# Security: returns 429 when full rather than accepting unlimited tasks
task_queue = queue.Queue(maxsize=50)
log.info("Queue  — worker queue initialised (maxsize=50)")

# --- Security: Rate Limiter ---
class RateLimiter:
    """Thread-safe token-bucket rate limiter."""
    def __init__(self, rate: float, capacity: float):
        self.rate = rate          # Tokens added per second
        self.capacity = capacity  # Max bucket burst size
        self.tokens = capacity
        self.last_check = time.monotonic()
        self.lock = threading.Lock()

    def allow(self) -> bool:
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_check
            self.last_check = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True
            return False

# Allows bursts up to 5 requests, refilling 1 token every 2 seconds (0.5/sec)
limiter = RateLimiter(rate=0.5, capacity=5.0)
log.info("Limiter — token bucket: rate=%.1f/s  capacity=%.1f", limiter.rate, limiter.capacity)

# --- Security: Input Sanitization ---
def sanitize_target_name(raw_name: str) -> str:
    """
    Sanitizes untrusted input against path traversal attacks.
    Ensures the target remains strictly within the STAGING folder.
    """
    log.debug("Sanitize — raw input: %r", raw_name)

    if not raw_name or not raw_name.strip():
        log.debug("Sanitize — empty name, will scan full staging dir")
        return ""

    # Strip dangerous null bytes and leading/trailing separators
    cleaned = raw_name.replace("\0", "").strip("/\\ ")
    if cleaned != raw_name:
        log.debug("Sanitize — stripped to: %r", cleaned)

    # Extract only the base name component to block ../ or directory traversal
    base_name = os.path.basename(cleaned)
    if not base_name or base_name in (".", ".."):
        raise ValueError("Invalid filename: Attempted directory traversal.")

    # Security: explicitly reject any remaining path separator characters.
    if "/" in base_name or "\\" in base_name or os.sep in base_name:
        raise ValueError("Invalid filename: Path separators not allowed.")

    # Canonicalize and confirm destination sits strictly within STAGING root
    target_path = os.path.realpath(os.path.join(STAGING, base_name))
    if not target_path.startswith(STAGING + os.sep):
        raise ValueError("Traversal detected: Target escapes staging boundary.")

    log.debug("Sanitize — accepted basename: %r → %s", base_name, target_path)
    return base_name

# --- Background Worker ---
def worker():
    log.info("Worker — background thread started (tid=%d)", threading.get_ident())
    while True:
        target_name = task_queue.get()
        q_size = task_queue.qsize()
        log.info("Worker — dequeued %r  (queue depth now: %d)", target_name or "<full staging>", q_size)
        try:
            process_download(target_name)
        except Exception as e:
            log.error("Worker — unhandled exception processing %r: %s", target_name, e, exc_info=True)
        finally:
            task_queue.task_done()

def process_download(target_name: str):
    os.makedirs(QUARANTINE, exist_ok=True)
    os.makedirs(MEDIA, exist_ok=True)

    if target_name:
        target_path = os.path.join(STAGING, target_name)
        # Security: target_name is already validated as a plain basename with no
        # separators, so this join cannot escape /scandir/staging/.
        container_target = f"/scandir/staging/{target_name}"
    else:
        target_path = STAGING
        container_target = "/scandir/staging"

    log.info("Scan   — target (host):      %s", target_path)
    log.info("Scan   — target (container): %s", container_target)

    if not os.path.exists(target_path):
        log.warning("Scan   — target does not exist, skipping: %s", target_path)
        return

    # Log size of item being scanned
    try:
        if os.path.isdir(target_path):
            items = os.listdir(target_path)
            log.info("Scan   — directory with %d item(s): %s", len(items), items)
        else:
            size_mb = os.path.getsize(target_path) / (1024 * 1024)
            log.info("Scan   — file size: %.2f MB", size_mb)
    except OSError as e:
        log.warning("Scan   — could not stat target: %s", e)

    scan_cmd = [
        "docker", "exec", "clamav",
        "clamdscan", "--fdpass",
        "--move=/scandir/quarantine",
        container_target
    ]
    log.debug("Scan   — command: %s", " ".join(scan_cmd))

    t_start = time.monotonic()
    scan_res = subprocess.run(scan_cmd, capture_output=True, text=True)
    elapsed = time.monotonic() - t_start

    log.info("Scan   — finished in %.2fs  exit_code=%d", elapsed, scan_res.returncode)

    if scan_res.stdout:
        for line in scan_res.stdout.strip().splitlines():
            log.info("ClamAV — %s", line)
    if scan_res.stderr:
        for line in scan_res.stderr.strip().splitlines():
            log.warning("ClamAV — stderr: %s", line)

    # Exit code: 0 = Clean, 1 = Infected / Quarantined, 2 = ClamAV Error
    if scan_res.returncode == 0:
        log.info("Result — CLEAN ✓")
        try:
            if target_name:
                dest = os.path.join(MEDIA, target_name)
                log.info("Move   — %s → %s", target_path, dest)
                shutil.move(target_path, dest)
                log.info("Move   — done")
            else:
                items = os.listdir(STAGING)
                log.info("Move   — moving %d item(s) from staging → media", len(items))
                for item in items:
                    src = os.path.join(STAGING, item)
                    dst = os.path.join(MEDIA, item)
                    log.debug("Move   — %s → %s", src, dst)
                    shutil.move(src, dst)
                log.info("Move   — all items moved successfully")
        except Exception as e:
            log.error("Move   — failed to move clean files: %s", e, exc_info=True)
    elif scan_res.returncode == 1:
        log.warning("Result — INFECTED ✗  (moved to quarantine: %s)", QUARANTINE)
    else:
        log.error("Result — CLAMAV ERROR  exit_code=%d", scan_res.returncode)

# --- HTTP Request Handler ---
class TriggerHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        client = self.address_string()

        # --- Full request dump (DEBUG) ---
        log.debug("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        log.debug("Request — %s %s %s  from %s",
                  self.command, self.path, self.request_version, client)
        for name, value in self.headers.items():
            # Redact the secret so it never appears in log files in plain text
            if name.lower() == "x-trigger-secret":
                display = f"<{len(value)}-char secret>"
            else:
                display = value
            log.debug("Header  — %s: %s", name, display)

        # Peek at the body without consuming it from the socket — read up to
        # Content-Length bytes but only if small enough to log safely.
        # Handle Expect: 100-continue first so the client actually sends the body.
        try:
            if self.headers.get("Expect", "").lower() == "100-continue":
                self.send_response(100)
                self.end_headers()
            peek_len = min(int(self.headers.get("Content-Length", 0)), 512)
            if peek_len > 0:
                body_preview = self.rfile.read(peek_len)
                # Reconstruct rfile so downstream code still reads the full body
                import io
                remaining = int(self.headers.get("Content-Length", 0)) - len(body_preview)
                rest = self.rfile.read(remaining) if remaining > 0 else b""
                self.rfile = io.BufferedReader(
                    io.BytesIO(body_preview + rest),
                    buffer_size=8192,
                )
                log.debug("Body    — %s", body_preview.decode("utf-8", errors="replace"))
            else:
                log.debug("Body    — (empty)")
        except Exception as e:
            log.debug("Body    — (could not preview: %s)", e)
        log.debug("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        # 1. Enforce Rate Limiting
        if not limiter.allow():
            log.warning("HTTP   — 429 rate limited  client=%s", client)
            self.send_response(429)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"429 Too Many Requests\n")
            return

        # 2. Restrict Payload Size (Max 8 KB)
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            log.debug("HTTP   — POST from %s  Content-Length=%d", client, content_length)

            if content_length > 8192:
                log.warning("HTTP   — 413 payload too large  client=%s  size=%d", client, content_length)
                self.send_response(413)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"413 Payload Too Large\n")
                return

            # 3. Validate Shared Secret from X-Trigger-Secret header
            provided_secret = self.headers.get('X-Trigger-Secret', '')
            if not _constant_time_eq(provided_secret, TRIGGER_SECRET):
                log.warning("HTTP   — 403 bad secret  client=%s  header_present=%s",
                            client, bool(provided_secret))
                self.send_response(403)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"403 Forbidden\n")
                return

            post_data = self.rfile.read(content_length).decode('utf-8', errors='ignore')
            params = urllib.parse.parse_qs(post_data)
            raw_target = params.get('name', [''])[0]
            log.debug("HTTP   — raw 'name' param: %r", raw_target)

            # 4. Enforce Path Traversal Sanitization
            sanitized_name = sanitize_target_name(raw_target)
            log.info("HTTP   — accepted request  client=%s  target=%r",
                     client, sanitized_name or "<full staging>")

        except ValueError as e:
            log.warning("HTTP   — 400 bad request  client=%s  reason=%s", client, e)
            self.send_response(400)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(f"400 Bad Request: {str(e)}\n".encode())
            return
        except Exception:
            log.error("HTTP   — 500 internal error  client=%s", client, exc_info=True)
            self.send_response(500)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"500 Internal Server Error\n")
            return

        # 5. Offload to Queue & Acknowledge Immediately
        try:
            task_queue.put_nowait(sanitized_name)
            q_size = task_queue.qsize()
            log.info("Queue  — enqueued %r  (depth: %d/50)", sanitized_name or "<full staging>", q_size)
        except queue.Full:
            log.error("Queue  — 429 queue full (%d/50)  client=%s", task_queue.qsize(), client)
            self.send_response(429)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"429 Queue Full: Try again later\n")
            return

        self.send_response(202)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"202 Accepted: Queued for scanning\n")

    def log_message(self, format, *args):
        # Suppress BaseHTTPServer's default per-request line (we log ourselves above)
        pass


def _constant_time_eq(a: str, b: str) -> bool:
    """
    Constant-time string comparison to prevent timing side-channel attacks
    when validating the shared secret.
    """
    import hmac
    return hmac.compare_digest(a.encode(), b.encode())


if __name__ == '__main__':
    # Start dedicated background processing thread
    t = threading.Thread(target=worker, daemon=True)
    t.start()

    server = HTTPServer(('0.0.0.0', 9999), TriggerHandler)
    log.info("Server — listening on port 9999 (host-localhost only)")
    server.serve_forever()