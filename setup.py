#!/usr/bin/env python3
# Copyright (C) 2026 Vivek
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Interactive One-Time Setup Script for Home NAS Server Stack
# Python port of setup.sh — runs cross-platform anywhere Python 3.8+ is available.
#
# Usage:
#   python setup.py
#   python3 setup.py

from __future__ import annotations

import os
import sys
from pathlib import Path

# Disable MSYS/Git-Bash path conversion for Docker flags on Windows
os.environ.setdefault("MSYS_NO_PATHCONV", "1")

# Anchor to the directory containing this script so relative paths (like
# docker-compose.yml, .env, etc.) resolve correctly regardless of the
# working directory from which the script is invoked.
SCRIPT_DIR = Path(__file__).resolve().parent
os.chdir(SCRIPT_DIR)

TOTAL_STEPS = 6

# ---------------------------------------------------------------------------
# Import modules (after anchoring so relative imports resolve)
# ---------------------------------------------------------------------------
from setup.ui import State, print_banner, step_header
from setup.preflight import run_preflight_checks
from setup.storage import init_storage_dirs
from setup.env import setup_env_secrets
from setup.credentials import prompt_user_credentials
from setup.docker import teardown_existing_stack, start_docker_stack, wait_for_services
from setup.qbittorrent import configure_qbittorrent_api
from setup.jellyfin import configure_jellyfin_api
from setup.tailscale import check_and_setup_tailscale
from setup.summary import display_summary_and_launch


def main() -> None:
    state = State()

    print_banner()

    # Step 1: Pre-flight checks (also sets state.compose_cmd)
    step_header(1, TOTAL_STEPS, "Checking System Prerequisites")
    run_preflight_checks(state)

    # Detect and tear down any pre-existing stack NOW — before any user input —
    # so the user knows upfront that the stack will be reset.
    teardown_existing_stack(state, SCRIPT_DIR)

    # Step 2: Storage directories
    step_header(2, TOTAL_STEPS, "Preparing Storage Directories")
    init_storage_dirs(state, SCRIPT_DIR)

    # Step 3: Security secret configuration
    step_header(3, TOTAL_STEPS, "Configuring Security Secret (.env)")
    setup_env_secrets(state, SCRIPT_DIR)

    # Step 4: User account credentials setup
    step_header(4, TOTAL_STEPS, "Setting Up Your Login Credentials")
    prompt_user_credentials(state)

    # Step 5: Docker stack orchestration & service configuration
    step_header(5, TOTAL_STEPS, "Starting Stack & Configuring Services")
    start_docker_stack(state, SCRIPT_DIR)
    wait_for_services(state)
    configure_qbittorrent_api(state, SCRIPT_DIR)
    configure_jellyfin_api(state)

    # Step 6: Tailscale remote access check & setup
    step_header(6, TOTAL_STEPS, "Remote Access (Tailscale)")
    check_and_setup_tailscale(state)

    # Display final dashboard and prompt browser launch
    display_summary_and_launch(state)


if __name__ == "__main__":
    main()
