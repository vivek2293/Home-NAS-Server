# Copyright (C) 2026 Vivek
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Docker Compose stack lifecycle orchestration and service health polling.

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

from .ui import (
    State, log_ok, log_warn, log_info,
    check_http_service,
    YELLOW, RESET, DIM,
)


def teardown_existing_stack(state: State, base_dir: Path) -> None:
    """If containers already exist, prompt the user and tear them down."""
    result = subprocess.run(
        state.compose_cmd + ["ps", "-q"],
        cwd=str(base_dir),
        capture_output=True,
        text=True,
    )
    existing = result.stdout.strip()

    if not existing:
        return

    print()
    log_warn("Existing stack containers detected.")
    print(f"  {YELLOW}Re-running setup will remove all containers and reset service")
    print(f"  configurations for a clean install.{RESET}")
    print(f"  {DIM}(Downloaded files in qbittorrent/downloads/ are preserved.){RESET}")
    print()

    confirm = input("  Proceed and reset the stack? [Y/n]: ").strip() or "Y"
    if confirm.lower() != "y":
        print()
        log_info("Setup cancelled. Your existing stack is unchanged.")
        sys.exit(0)

    print()
    log_info("Removing existing containers...")
    subprocess.run(
        state.compose_cmd + ["down", "--remove-orphans"],
        cwd=str(base_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    log_info("Wiping service config and cache directories for a clean slate...")
    for rel in ("jellyfin/config", "jellyfin/cache", "qbittorrent/config"):
        target = base_dir / rel
        if target.exists():
            shutil.rmtree(target)

    log_ok("Stack torn down — ready for fresh configuration")
    print()


def start_docker_stack(state: State, base_dir: Path) -> None:
    """Build and start all stack containers in detached mode."""
    log_info("Building and starting all stack containers in background...")
    subprocess.run(
        state.compose_cmd + ["up", "-d", "--build"],
        cwd=str(base_dir),
        check=True,
    )

    log_info("Waiting for container services to initialize (10 seconds)...")
    time.sleep(10)


def _poll_port(port: int) -> bool:
    """Poll a single port every 3 s for up to 5 attempts (15 s). Returns True if healthy."""
    for _ in range(5):
        if check_http_service(port):
            return True
        time.sleep(3)
    return False


def wait_for_services(state: State) -> None:
    """Poll qBittorrent (8043) then Jellyfin (8096) sequentially (max 5 retries, 3s interval)."""
    log_info("Polling service health on localhost...")

    if _poll_port(8043):
        log_ok("qBittorrent is online (http://localhost:8043)")
    else:
        log_warn("qBittorrent is taking longer to respond. It may still be initializing.")

    if _poll_port(8096):
        log_ok("Jellyfin is online (http://localhost:8096)")
    else:
        log_warn("Jellyfin is taking longer to respond. It may still be initializing.")
