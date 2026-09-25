# Copyright (C) 2026 Vivek
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Tailscale remote access detection and configuration.

from __future__ import annotations

import json
import shutil
import subprocess

from .ui import State, log_ok, log_warn, log_info, BOLD, CYAN, DIM, RESET


def check_and_setup_tailscale(state: State) -> None:
    """Detect Tailscale, optionally configure Serve for HTTPS on ports 443, 8043 & 8096."""

    if not shutil.which("tailscale"):
        log_info("Tailscale is not installed on this system.")
        print(
            f"  {DIM}Tailscale allows you to securely stream Jellyfin and manage "
            f"downloads from your phone anywhere.{RESET}"
        )
        print(f"  {BOLD}To set up Tailscale later:{RESET}")
        print(f"    • Install:  {CYAN}curl -fsSL https://tailscale.com/install.sh | sh{RESET}"
              "  (or visit https://tailscale.com/download)")
        print(f"    • Connect:  {CYAN}sudo tailscale up{RESET}")
        print(f"    • Expose:   {CYAN}tailscale serve --bg --https=443  http://localhost:8080{RESET}  # Dashboard")
        print(f"                {CYAN}tailscale serve --bg --https=8043 http://localhost:8043{RESET}  # qBittorrent")
        print(f"                {CYAN}tailscale serve --bg --https=8096 http://localhost:8096{RESET}  # Jellyfin\n")
        return

    # Check if connected
    try:
        ip_result = subprocess.run(
            ["tailscale", "ip", "-4"],
            capture_output=True, text=True,
        )
        tailscale_ip = ip_result.stdout.strip()
    except Exception:
        tailscale_ip = ""

    if not tailscale_ip:
        log_warn("Tailscale is installed but not currently connected.")
        print(f"  To connect, run: {CYAN}sudo tailscale up{RESET}\n")
        return

    state.tailscale_running = True
    state.tailscale_ip = tailscale_ip

    # Resolve the Tailscale DNS hostname
    try:
        status_result = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True, text=True,
        )
        status_data = json.loads(status_result.stdout)
        dns_name = (
            status_data.get("Self", {})
            .get("DNSName", "")
            .rstrip(".")
        )
        state.tailscale_hostname = dns_name or tailscale_ip
    except Exception:
        state.tailscale_hostname = tailscale_ip

    log_ok(f"Tailscale detected and active (Device IP: {BOLD}{tailscale_ip}{RESET})")

    print()
    choice = input(
        "Would you like to expose the dashboard, qBittorrent & Jellyfin securely via Tailscale Serve? [Y/n]: "
    ).strip() or "Y"

    if choice.lower() == "y":
        log_info("Configuring Tailscale Serve for dashboard (443), qBittorrent (8043) & Jellyfin (8096)...")

        # Dashboard on port 443 — the default landing page
        result = subprocess.run(
            ["tailscale", "serve", "--bg", "--https=443", "http://localhost:8080"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode != 0:
            log_warn("Could not configure Tailscale serve for dashboard (port 443) "
                     "(may require sudo/admin permissions)")

        # Service WebUIs
        for port in (8043, 8096):
            result = subprocess.run(
                ["tailscale", "serve", "--bg", f"--https={port}", f"http://localhost:{port}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if result.returncode != 0:
                log_warn(
                    f"Could not configure Tailscale serve for port {port} "
                    "(may require sudo/admin permissions)"
                )
        log_ok("Tailscale remote URLs configured!")
