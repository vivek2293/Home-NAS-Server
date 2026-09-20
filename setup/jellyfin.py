# Copyright (C) 2026 Vivek
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Jellyfin initial setup wizard and media library automation via REST API.

from __future__ import annotations

import getpass
import http.client
import json
import time

from .ui import State, log_ok, log_warn, log_info, BOLD, RESET

_AUTH_HEADER = (
    'MediaBrowser Client="Jellyfin Web", Device="Host", '
    'DeviceId="setup-init-01", Version="10.11.7"'
)


def _send_request(
    method: str,
    path: str,
    body: dict | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, str]:
    """Execute an HTTP request against localhost:8096 and return (status, body)."""
    conn = http.client.HTTPConnection("localhost", 8096, timeout=10)
    try:
        req_headers = {
            "Authorization": _AUTH_HEADER,
            "X-Emby-Authorization": _AUTH_HEADER,
            "Accept": "application/json",
        }
        if headers:
            req_headers.update(headers)

        data = None
        if body is not None:
            data = json.dumps(body)
            req_headers["Content-Type"] = "application/json"

        conn.request(method, path, data, req_headers)
        response = conn.getresponse()
        resp_data = response.read().decode("utf-8", errors="replace")
        return response.status, resp_data
    finally:
        conn.close()


def configure_jellyfin_api(state: State) -> None:
    """Run the Jellyfin startup wizard via REST API to create admin user and /media library."""
    log_info("Configuring Jellyfin via startup wizard API (admin account & /media library)...")

    # Ensure server name is present (prompt user if running standalone)
    if not getattr(state, "jelly_server_name", None):
        server_name = input("  Enter desired Jellyfin server name [default: Home-NAS]: ").strip()
        state.jelly_server_name = server_name or "Home-NAS"

    if not getattr(state, "jelly_pass", None):
        user = input(f"  Enter Jellyfin admin username [default: {state.jelly_user}]: ").strip()
        if user:
            state.jelly_user = user
        state.jelly_pass = getpass.getpass("  Enter Jellyfin admin password: ").strip() or "admin"

    try:
        # ------------------------------------------------------------------
        # 1. Wizard Configuration: GET configuration, then POST configuration
        # ------------------------------------------------------------------
        wizard_ready = False
        for attempt in range(5):
            try:
                # GET configuration first (just like browser step 1)
                _send_request("GET", "/Startup/Configuration")
                status, _ = _send_request(
                    "POST",
                    "/Startup/Configuration",
                    body={
                        "ServerName": state.jelly_server_name,
                        "UICulture": "en-US",
                        "MetadataCountryCode": "US",
                        "PreferredMetadataLanguage": "en",
                    },
                    headers={"Origin": "http://localhost:8096"},
                )
                if status in (200, 204):
                    wizard_ready = True
                    break
            except Exception:
                pass
            time.sleep(3)

        if not wizard_ready:
            raise RuntimeError("Startup configuration endpoint did not become ready in time")

        # ------------------------------------------------------------------
        # 2. Transition to User step (mirrors browser navigating to step 2):
        #    GET /System/Info/Public and GET /Startup/User
        #    In Jellyfin, GET /Startup/User triggers UserManager to instantiate the
        #    initial user object in DB. Without this, POST /Startup/User throws
        #    System.InvalidOperationException: Sequence contains no elements (HTTP 500).
        # ------------------------------------------------------------------
        _send_request("GET", "/System/Info/Public")

        for _ in range(5):
            status, _ = _send_request("GET", "/Startup/User")
            if status in (200, 204):
                break
            time.sleep(3)

        # POST /Startup/User to set chosen username & password
        status, user_resp = _send_request(
            "POST",
            "/Startup/User",
            body={"Name": state.jelly_user, "Password": state.jelly_pass},
            headers={"Origin": "http://localhost:8096"},
        )
        if status not in (200, 204):
            # Retry once in case DB commit was pending
            time.sleep(3)
            _send_request("GET", "/Startup/User")
            status, user_resp = _send_request(
                "POST",
                "/Startup/User",
                body={"Name": state.jelly_user, "Password": state.jelly_pass},
                headers={"Origin": "http://localhost:8096"},
            )
            if status not in (200, 204):
                raise RuntimeError(f"/Startup/User failed: HTTP {status}, {user_resp!r}")

        log_ok(f"Jellyfin admin user '{state.jelly_user}' created")

        # ------------------------------------------------------------------
        # 3. Mark wizard complete
        # ------------------------------------------------------------------
        try:
            _send_request("POST", "/Startup/Complete")
        except Exception:
            pass

        # ------------------------------------------------------------------
        # 4. Authenticate to get Access Token for library setup
        # ------------------------------------------------------------------
        status, auth_resp = _send_request(
            "POST",
            "/Users/AuthenticateByName",
            body={"Username": state.jelly_user, "Pw": state.jelly_pass},
        )
        if status not in (200, 204):
            raise RuntimeError(f"Authentication failed: HTTP {status}, {auth_resp!r}")

        auth_data = json.loads(auth_resp)
        token = auth_data.get("AccessToken")
        if not token:
            raise RuntimeError("Jellyfin did not return an AccessToken")

        log_ok(f"Jellyfin admin login verified (user: {BOLD}{state.jelly_user}{RESET})")

        # ------------------------------------------------------------------
        # 5. Add /media library if not already present
        # ------------------------------------------------------------------
        status, folders_resp = _send_request(
            "GET",
            "/Library/VirtualFolders",
            headers={
                "X-Emby-Token": token,
                "Authorization": f'{_AUTH_HEADER}, Token="{token}"',
            },
        )

        has_media = False
        if status in (200, 204):
            try:
                folders = json.loads(folders_resp)
                has_media = any(
                    f.get("Name") == "Media" or "/media" in f.get("Locations", [])
                    for f in folders
                )
            except Exception:
                pass

        if not has_media:
            status, _ = _send_request(
                "POST",
                "/Library/VirtualFolders?name=Media&collectionType=mixed&refreshLibrary=true",
                body={
                    "Paths": ["/media"],
                    "LibraryOptions": {
                        "Enabled": True,
                        "PathInfos": [{"Path": "/media"}],
                    },
                },
                headers={
                    "X-Emby-Token": token,
                    "Authorization": f'{_AUTH_HEADER}, Token="{token}"',
                    "Origin": "http://localhost:8096",
                },
            )
            if status in (200, 204):
                log_ok("Jellyfin '/media' library initialized automatically")
            else:
                log_warn(f"Could not initialize '/media' library: HTTP {status}")
        else:
            log_ok("Jellyfin '/media' library already present")

    except Exception as e:
        log_warn(
            f"Could not configure Jellyfin automatically: {e}. "
            "Configure manually at http://localhost:8096"
        )
