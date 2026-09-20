# Copyright (C) 2026 Vivek
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Terminal UI styling, color palette, logging, and helper utilities.
# Also holds the shared State dataclass passed through the pipeline.

from __future__ import annotations

import os
import sys
import platform
import shutil
import subprocess
import urllib.request
import urllib.error
import webbrowser
from dataclasses import dataclass, field

# Reconfigure stdout/stderr on Windows to handle Unicode symbols (✔, ℹ, ⚠, ✖) safely
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Shared pipeline state (replaces Bash globals)
# ---------------------------------------------------------------------------

@dataclass
class State:
    """Mutable bag of values shared across setup modules."""
    # Set by preflight
    compose_cmd: list[str] = field(default_factory=list)   # e.g. ["docker", "compose"]
    # Set by env
    trigger_secret: str = ""
    # Set by credentials
    qbit_user: str = "admin"
    qbit_pass: str = "adminadmin"
    jelly_server_name: str = "Home-NAS"
    jelly_user: str = "admin"
    jelly_pass: str = ""
    # Set by tailscale
    tailscale_running: bool = False
    tailscale_hostname: str = ""
    tailscale_ip: str = ""


# ---------------------------------------------------------------------------
# ANSI colour support
# ---------------------------------------------------------------------------

def _supports_color() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR", "") == ""


if _supports_color():
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    GREEN   = "\033[0;32m"
    CYAN    = "\033[0;36m"
    YELLOW  = "\033[1;33m"
    RED     = "\033[0;31m"
    BLUE    = "\033[0;34m"
    MAGENTA = "\033[0;35m"
    RESET   = "\033[0m"
else:
    BOLD = DIM = GREEN = CYAN = YELLOW = RED = BLUE = MAGENTA = RESET = ""


# ---------------------------------------------------------------------------
# Print helpers
# ---------------------------------------------------------------------------

def print_banner() -> None:
    print(f"{CYAN}{BOLD}")
    print("=================================================================")
    print("             🏠 Home NAS Server - Easy Setup Wizard              ")
    print("=================================================================")
    print(f"{RESET}")
    print(" This wizard will configure and launch your self-hosted media NAS:")
    print(f"   • {BOLD}qBittorrent{RESET}  (Port 8043) - Secure Torrent Downloader")
    print(f"   • {BOLD}Jellyfin{RESET}     (Port 8096) - Media Streaming Server")
    print(f"   • {BOLD}ClamAV{RESET}       (Sandbox)   - Automatic Antivirus Scanner")
    print(f"   • {BOLD}Trigger{RESET}      (Port 9999) - Automated Scan & Move Webhook")
    print()


def step_header(step_num: int, total_steps: int, title: str) -> None:
    print(f"\n{BOLD}{MAGENTA}▶ [Step {step_num}/{total_steps}] {title}{RESET}")
    print(f"{DIM}-----------------------------------------------------------------{RESET}")


def log_ok(msg: str) -> None:
    print(f"  {GREEN}✔{RESET} {msg}")


def log_info(msg: str) -> None:
    print(f"  {BLUE}ℹ{RESET} {msg}")


def log_warn(msg: str) -> None:
    print(f"  {YELLOW}⚠{RESET} {msg}")


def log_fail(msg: str) -> None:
    print(f"  {RED}✖{RESET} {msg}")


# ---------------------------------------------------------------------------
# Cross-platform browser opener
# ---------------------------------------------------------------------------

def open_browser(url: str) -> None:
    """Open *url* in the user's default browser, silently."""
    system = platform.system()
    wsl_distro = os.environ.get("WSL_DISTRO_NAME", "")
    try:
        if system == "Darwin":
            subprocess.run(["open", url], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif wsl_distro and shutil.which("wslview"):
            subprocess.run(["wslview", url], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif system == "Windows" or shutil.which("cmd.exe"):
            # Works on native Windows and Git-Bash
            subprocess.run(["cmd.exe", "/c", "start", "", url], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            webbrowser.open(url)
    except Exception:
        log_warn(f"Could not automatically open browser. Please visit manually: {url}")


# ---------------------------------------------------------------------------
# OSC 8 clickable terminal hyperlink with plain fallback
# ---------------------------------------------------------------------------

def hyperlink(url: str, text: str | None = None) -> str:
    text = text or url
    if sys.stdout.isatty():
        return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"
    return f"{text} ({url})"


# ---------------------------------------------------------------------------
# Robust HTTP health check (IPv4 safe)
# ---------------------------------------------------------------------------

_HEALTHY_CODES = {200, 302, 401, 403}


def check_http_service(port: int) -> bool:
    """Return True if the service on *port* responds with a healthy HTTP status."""
    for host in ("127.0.0.1", "localhost"):
        try:
            req = urllib.request.Request(f"http://{host}:{port}/", method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status in _HEALTHY_CODES:
                    return True
        except urllib.error.HTTPError as exc:
            if exc.code in _HEALTHY_CODES:
                return True
        except Exception:
            pass
    return False
