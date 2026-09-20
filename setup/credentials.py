# Copyright (C) 2026 Vivek
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Interactive user credentials setup.
# Credentials are applied via each service's REST API after the stack starts;
# no client-side hashing is required.

from __future__ import annotations

import getpass

from .ui import (
    State, log_ok, log_warn,
    BOLD, CYAN, DIM, RESET,
)


def _prompt_password(service_label: str, default: str = "", allow_default_without_confirm: bool = False) -> str:
    """Prompt for a password with confirmation and optional default bypass."""
    prompt_suffix = f" [default: {default}]" if default else ""
    while True:
        pwd = getpass.getpass(f"  Enter {service_label} password{prompt_suffix}: ")
        if not pwd and default:
            if allow_default_without_confirm:
                log_warn(f"Using default password '{default}' — consider changing it after setup for security.")
                return default
            pwd = default
        if not pwd:
            log_warn(f"Password cannot be blank for {service_label}. Please enter a password.")
            continue
        confirm = getpass.getpass(f"  Confirm {service_label} password: ")
        if pwd == confirm:
            return pwd
        log_warn("Passwords do not match. Please try again.")


def prompt_user_credentials(state: State) -> None:
    """Interactively prompt for qBittorrent and Jellyfin credentials."""
    print(" Configure the credentials for qBittorrent and Jellyfin.")
    print(f" {DIM}(Your passwords will remain private and never be displayed in logs){RESET}\n")

    # ------------------------------------------------------------------
    # qBittorrent
    # ------------------------------------------------------------------
    print(f"{CYAN}{BOLD}[qBittorrent Downloader]{RESET}")
    qbit_user = input("  Enter qBittorrent username [default: admin]: ").strip()
    state.qbit_user = qbit_user or "admin"
    state.qbit_pass = _prompt_password(
        "qBittorrent",
        default="adminadmin",
        allow_default_without_confirm=True,
    )
    log_ok(f"qBittorrent username set to: {BOLD}{state.qbit_user}{RESET}")

    # ------------------------------------------------------------------
    # Jellyfin
    # ------------------------------------------------------------------
    print(f"\n{CYAN}{BOLD}[Jellyfin Media Server]{RESET}")
    jelly_server_name = input("  Enter desired Jellyfin server name [default: Home-NAS]: ").strip()
    state.jelly_server_name = jelly_server_name or "Home-NAS"

    jelly_user = input("  Enter desired Jellyfin admin username [default: admin]: ").strip()
    state.jelly_user = jelly_user or "admin"
    state.jelly_pass = _prompt_password("Jellyfin admin")
    log_ok(f"Jellyfin username set to: {BOLD}{state.jelly_user}{RESET}")
