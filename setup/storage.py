# Copyright (C) 2026 Vivek
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Storage directory structure initialization.

from __future__ import annotations

from pathlib import Path

from .ui import State, log_ok

_DIRS = [
    "clamav/config",
    "jellyfin/config",
    "jellyfin/cache",
    "qbittorrent/config/qBittorrent",
    "qbittorrent/downloads/staging",
    "qbittorrent/downloads/media",
    "qbittorrent/downloads/quarantine",
]


def init_storage_dirs(state: State, base_dir: Path) -> None:
    """Create required storage directories relative to *base_dir*."""
    for rel in _DIRS:
        path = base_dir / rel
        if path.exists():
            log_ok(f"Exists:  {rel}/")
        else:
            path.mkdir(parents=True, exist_ok=True)
            log_ok(f"Created: {rel}/")
