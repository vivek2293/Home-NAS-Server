# Copyright (C) 2026 Vivek
# SPDX-License-Identifier: GPL-3.0-or-later
#
# qBittorrent API credential and webhook trigger setup.
from __future__ import annotations

import http.client
import json
import re
import subprocess
import time
import urllib.parse
from pathlib import Path

from .env import setup_env_secrets
from .ui import State, log_ok, log_warn, log_info

# Regex to extract the temporary password from container logs
_TEMP_PASS_RE = re.compile(
    r"temporary password is provided for this session:\s+(\S+)",
    re.IGNORECASE,
)

def configure_qbittorrent_api(state: State, script_dir: Path) -> None:
    """Login with temp password, set credentials and autorun webhook via API."""

    # ------------------------------------------------------------------
    # 1. Poll docker logs for the one-time temp password
    # ------------------------------------------------------------------
    log_info("Reading qBittorrent temporary password from container logs...")
    temp_pass = ""
    for _ in range(5):
        try:
            logs = subprocess.run(
                ["docker", "logs", "qbittorrent"],
                capture_output=True,   # captures as bytes
            )
            # Decode as UTF-8 with replacement so Windows cp1252 / ANSI escape
            # bytes (e.g. 0x90) never cause a UnicodeDecodeError.
            combined = (logs.stdout + logs.stderr).decode("utf-8", errors="replace")
            m = _TEMP_PASS_RE.search(combined)
            if m:
                temp_pass = m.group(1).strip()
                break
        except Exception:
            pass
        time.sleep(3)

    if not temp_pass:
        log_warn(
            "Could not read qBittorrent temporary password from logs. "
            "Configure manually at http://localhost:8043"
        )
        return
    try:
        conn = http.client.HTTPConnection("localhost", 8043, timeout=5)
        # Login
        payload = urllib.parse.urlencode({
            "username": "admin",
            "password": temp_pass,
        })
        conn.request(
            "POST",
            "/api/v2/auth/login",
            payload,
            {"Content-Type": "application/x-www-form-urlencoded"},
        )
        response = conn.getresponse()
        login_result = response.read().decode("utf-8", errors="replace")

        if not (response.status == 200 or response.status == 204):
            raise RuntimeError(
                f"Login failed: HTTP {response.status}, {login_result!r}"
            )

        # Extract SID cookie
        sid = response.getheader("Set-Cookie")
        if not sid:
            raise RuntimeError("qBittorrent did not return a session cookie")

        # Ensure trigger_secret is available
        if not state.trigger_secret:
            setup_env_secrets(state, script_dir)

        # Build autorun command:
        # qBittorrent on Linux uses Qt's QProcess::startDetached which splits by space
        # and ONLY recognizes double quotes (""), NOT single quotes ('').
        # --data-urlencode "name=%N" correctly encodes names with spaces/special characters
        # for trigger_server.py (urllib.parse.parse_qs).
        autorun_program = (
            f'curl -s -X POST http://host.docker.internal:9999/trigger '
            f'-H "X-Trigger-Secret: {state.trigger_secret}" '
            f'--data-urlencode "name=%N"'
        )

        preferences = {
            "web_ui_username": state.qbit_user,
            "web_ui_password": state.qbit_pass,
            "autorun_enabled": True,
            "autorun_program": autorun_program,
        }

        payload = urllib.parse.urlencode({
            "json": json.dumps(preferences),
        })

        conn.request(
            "POST",
            "/api/v2/app/setPreferences",
            payload,
            {
                "Content-Type": "application/x-www-form-urlencoded",
                "Cookie": sid.split(";", 1)[0],
            },
        )

        response = conn.getresponse()
        response.read()

        if response.status != 200:
            raise RuntimeError(
                f"setPreferences failed: HTTP {response.status}"
            )

        log_ok("qBittorrent credentials and webhook configured via API")

    except Exception as e:
        log_warn(
            f"Could not configure qBittorrent automatically: {e}. "
            "Configure manually at http://localhost:8043"
        )
