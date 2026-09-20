# Copyright (C) 2026 Vivek
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Pre-flight system and environment checks.

from __future__ import annotations

import shutil
import subprocess
import sys

from .ui import State, log_ok, log_fail, log_info, YELLOW, RESET


def run_preflight_checks(state: State) -> None:
    """Verify that Docker and Docker Compose are available."""

    # 1. Docker CLI installed?
    if not shutil.which("docker"):
        log_fail("Docker is not installed.")
        print(f"\n{YELLOW}Please install Docker Desktop or Docker Engine first:{RESET}")
        print("👉 https://docs.docker.com/get-docker/\n")
        sys.exit(1)
    log_ok("Docker CLI is installed")

    # 2. Docker daemon running?
    result = subprocess.run(
        ["docker", "info"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        log_fail("Docker daemon is not running.")
        print(
            f"\n{YELLOW}Please start Docker Desktop and ensure it is running, "
            f"then re-run this script.{RESET}\n"
        )
        sys.exit(1)
    log_ok("Docker daemon is active and running")

    # 3. Docker Compose available?
    compose_cmd: list[str] = []
    # Prefer the modern plugin form ("docker compose")
    result_plugin = subprocess.run(
        ["docker", "compose", "version"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if result_plugin.returncode == 0:
        compose_cmd = ["docker", "compose"]
    elif shutil.which("docker-compose"):
        result_standalone = subprocess.run(
            ["docker-compose", "version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result_standalone.returncode == 0:
            compose_cmd = ["docker-compose"]

    if not compose_cmd:
        log_fail("Docker Compose is not available.")
        print(f"\n{YELLOW}Please install Docker Compose (bundled with Docker Desktop):{RESET}")
        print("👉 https://docs.docker.com/compose/install/\n")
        sys.exit(1)

    state.compose_cmd = compose_cmd
    log_ok(f"Docker Compose is available ({' '.join(compose_cmd)})")
