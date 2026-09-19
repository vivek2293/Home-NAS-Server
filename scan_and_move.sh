#!/usr/bin/env bash
# Copyright (C) 2026 Vivek
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
set -euo pipefail

# Disable path conversion for Docker flags in Git Bash
export MSYS_NO_PATHCONV=1

# Use absolute paths to eliminate environment ambiguity
# FIX: anchor to the script's own directory, not $(pwd), so it works correctly
# regardless of where the script is invoked from.
SCRIPT_DIR="$( cd "$(dirname "$0")" && pwd )"
BASE_DIR="$SCRIPT_DIR/qbittorrent/downloads"
STAGING="$BASE_DIR/staging"
QUARANTINE="$BASE_DIR/quarantine"
MEDIA="$BASE_DIR/media"

# Target specific item passed as argument, or default to checking staging
TARGET_NAME="${1:-}"

mkdir -p "$QUARANTINE" "$MEDIA" "$STAGING"

if [ -n "$TARGET_NAME" ]; then
    TARGET_PATH="$STAGING/$TARGET_NAME"
    CONTAINER_TARGET="/scandir/staging/$TARGET_NAME"
else
    TARGET_PATH="$STAGING"
    CONTAINER_TARGET="/scandir/staging"
fi

if [ ! -e "$TARGET_PATH" ]; then
    # FIX: warn on stderr instead of silently succeeding, to surface misconfiguration
    echo "[scan_and_move] Warning: target path does not exist: $TARGET_PATH" >&2
    exit 0
fi

# Run ClamAV scan via container
# Exit codes: 0 = clean, 1 = infected, 2 = error
SCAN_EXIT=0
docker exec clamav clamdscan --fdpass --move=/scandir/quarantine "$CONTAINER_TARGET" || SCAN_EXIT=$?

if [ "$SCAN_EXIT" -eq 0 ]; then
    # Move target cleanly to media
    if [ -n "$TARGET_NAME" ]; then
        mv "$TARGET_PATH" "$MEDIA/"
    else
        find "$STAGING" -mindepth 1 -maxdepth 1 -exec mv -t "$MEDIA" {} +
    fi
elif [ "$SCAN_EXIT" -eq 1 ]; then
    echo "Threat detected and isolated in $QUARANTINE" >&2
else
    echo "ClamAV scanning encountered an execution error." >&2
    exit "$SCAN_EXIT"
fi