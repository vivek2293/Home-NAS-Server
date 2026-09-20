# Copyright (C) 2026 Vivek
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Environment file and security secret generation.

from __future__ import annotations

import re
import secrets
from pathlib import Path

from .ui import State, log_ok, log_info

_KEY = "TRIGGER_SECRET"


def setup_env_secrets(state: State, base_dir: Path) -> None:
    """Read or generate TRIGGER_SECRET and persist it in .env."""
    env_file = base_dir / ".env"

    if env_file.exists():
        content = env_file.read_text(encoding="utf-8")
        m = re.search(rf"^{_KEY}=(.+)$", content, re.MULTILINE)
        if m and m.group(1).strip():
            state.trigger_secret = m.group(1).strip()
            log_ok("Existing security secret loaded from .env")
            return
    else:
        content = ""

    # Generate a fresh 32-byte hex secret
    log_info("Generating a strong 32-byte secret for download webhook verification...")
    new_secret = secrets.token_hex(32)
    state.trigger_secret = new_secret

    if re.search(rf"^{_KEY}=", content, re.MULTILINE):
        content = re.sub(rf"^{_KEY}=.*$", f"{_KEY}={new_secret}", content, flags=re.MULTILINE)
        log_ok("Updated TRIGGER_SECRET in existing .env")
    else:
        if content and not content.endswith("\n"):
            content += "\n"
        content += f"{_KEY}={new_secret}\n"
        log_ok("Saved TRIGGER_SECRET to .env")

    env_file.write_text(content, encoding="utf-8")
