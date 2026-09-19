# Copyright (C) 2026 Vivek
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

FROM docker:27-cli

# Pre-install Python at build time so startup is fast and the dependency is
# pinned and auditable — not pulled from Alpine CDN at container boot.
RUN apk add --no-cache python3

ENTRYPOINT ["python3", "-u", "/app/trigger_server.py"]
