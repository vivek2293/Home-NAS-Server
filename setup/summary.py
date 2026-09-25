# Copyright (C) 2026 Vivek
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Final summary dashboard and interactive browser launching.

from __future__ import annotations

import sys

from .ui import (
    State, log_info,
    hyperlink, open_browser,
    BOLD, CYAN, GREEN, DIM, RESET,
)


def display_summary_and_launch(state: State) -> None:
    """Print the final service dashboard and optionally open browser tabs."""
    compose_str = " ".join(state.compose_cmd)

    print(f"\n{GREEN}{BOLD}=================================================================")
    print("                  🎉 Stack is Up and Ready!                      ")
    print(f"================================================================={RESET}\n")

    print(f" {BOLD}Service Dashboard & Access Information:{RESET}")
    print(" -----------------------------------------------------------------")

    # Dashboard
    if state.tailscale_running and state.tailscale_hostname:
        print(f" 🏠 {BOLD}Dashboard{RESET} (Landing page):")
        print(f"    • Tailscale URL:   {hyperlink(f'https://{state.tailscale_hostname}')}")
        print(f"    {DIM}Links to all services — start here.{RESET}")
        print()

    # qBittorrent
    print(f" 📥 {BOLD}qBittorrent{RESET} (Downloads):")
    print(f"    • Localhost URL:   {hyperlink('http://localhost:8043')}")
    if state.tailscale_running and state.tailscale_hostname:
        print(f"    • Tailscale URL:   {hyperlink(f'https://{state.tailscale_hostname}:8043')}")
    print(f"    • Username:        {CYAN}{state.qbit_user}{RESET}")
    print(f"    • Password:        {DIM}[Configured as entered]{RESET}")
    print(f"    • Download Trigger: {GREEN}Active & Automated (Auto-scans via ClamAV){RESET}")

    print()

    # Jellyfin
    print(f" 🎬 {BOLD}Jellyfin{RESET} (Media Server):")
    print(f"    • Localhost URL:   {hyperlink('http://localhost:8096')}")
    if state.tailscale_running and state.tailscale_hostname:
        print(f"    • Tailscale URL:   {hyperlink(f'https://{state.tailscale_hostname}:8096')}")
    print(f"    • Username:        {CYAN}{state.jelly_user}{RESET}")
    print(f"    • Password:        {DIM}[Configured as entered]{RESET}")
    print(f"    • Media Library:   {GREEN}Ready (/media configured){RESET}")

    print(" -----------------------------------------------------------------")

    print(f"\n {BOLD}Helpful Management Commands:{RESET}")
    print(f"   • Stop all services:      {CYAN}{compose_str} stop{RESET}")
    print(f"   • Start all services:     {CYAN}{compose_str} up -d{RESET}")
    print(f"   • View stack logs:        {CYAN}{compose_str} logs -f{RESET}")
    print(f"   • Manual scan & move:     {CYAN}bash scan_and_move.sh{RESET}")
    print(" -----------------------------------------------------------------\n")

    # Prompt to open browser (only when running interactively)
    if sys.stdin.isatty():
        if state.tailscale_running and state.tailscale_hostname:
            dashboard_url = f"https://{state.tailscale_hostname}"
            prompt_url = dashboard_url
        else:
            dashboard_url = "http://localhost:8080"
            prompt_url = dashboard_url

        choice = input(
            f"Would you like to open the dashboard ({prompt_url}) in your browser now? [Y/n]: "
        ).strip() or "Y"
        if choice.lower() == "y":
            log_info("Opening dashboard in your default browser...")
            open_browser(dashboard_url)
    else:
        open_browser("http://localhost:8080")

    print(f"\n{GREEN}{BOLD}Enjoy your Home NAS! 🚀{RESET}\n")
