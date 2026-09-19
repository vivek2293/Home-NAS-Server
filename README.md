# Home NAS Stack

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![GitHub Stars](https://img.shields.io/github/stars/vivek2293/Home-NAS-Server?style=social)](https://github.com/vivek2293/Home-NAS-Server/stargazers)

A self-hosted, Docker-based home media server stack — download, scan, and stream your media from your own hardware. Use [Tailscale](https://tailscale.com) to stream to any of your devices, no matter where you are.

> **Note on responsible use**
> BitTorrent is a legitimate file-transfer protocol used to distribute Linux ISOs, open-source software, Creative Commons content, and more. This stack is built around that use case. Downloading copyrighted material without permission is illegal — that's on you, not the tool.

---

## What's Inside

| Service | Purpose | Port |
|---|---|---|
| **qBittorrent** | Torrent client with web UI | `8043` |
| **Jellyfin** | Media server for streaming | `8096` |
| **ClamAV** | Antivirus scan on every download | — |
| **trigger-service** | Webhook that auto-scans & moves completed downloads | `9999` (localhost only) |
| **docker-socket-proxy** | Restricts raw Docker socket access for security | — |

### How it works

1. qBittorrent downloads a file to a **staging** directory.
2. On completion, it calls the **trigger-service** (via `host.docker.internal:9999`).
3. The trigger-service invokes `scan_and_move.sh`, which runs a **ClamAV** scan.
4. Clean files are moved to `media/` (served by Jellyfin). Infected files are moved to `quarantine/`.

---

## Setup

### Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| [Docker Engine](https://docs.docker.com/get-docker/) | 24.0+ | Linux or Docker Desktop (Windows/macOS) |
| [Docker Compose](https://docs.docker.com/compose/) | v2.0+ | Comes bundled with Docker Desktop |
| Bash | Any | Linux native; use WSL2 or Git Bash on Windows |
| curl | Any | Required for the download trigger command |
| openssl | Any | Optional — used to generate `TRIGGER_SECRET` |

### 1. Clone the repo

```bash
git clone https://github.com/vivek2293/Home-NAS-Server.git
cd <repo-name>
```

### 2. Configure environment variables

Edit the `.env` file and set your secret:

```env
TRIGGER_SECRET=your_random_secret_here
```

> Generate a strong secret with: `openssl rand -hex 32`

### 3. Start the stack

```bash
docker compose up -d
```

### 4. First-time qBittorrent setup

Get the auto-generated password from the logs:

```bash
# Bash
docker logs qbittorrent 2>&1 | grep -i "password"

# PowerShell
docker logs qbittorrent | findstr /i "password"
```

Open **http://localhost:8043**, log in with `admin` / `<password from logs>`, and **change your password** immediately via *Settings → Web UI*.

### 5. Configure the download trigger

In qBittorrent Settings → **Downloads**:

- Tick **"Run on torrent finished"**
- Set the command to call the trigger-service webhook (authenticated with `TRIGGER_SECRET`):

```
curl -s -X POST http://host.docker.internal:9999/trigger \
  -H "X-Trigger-Secret: <TRIGGER_SECRET>" \
  -d '{"name": "%N"}'
```

### 6. First-time Jellyfin setup

Open **http://localhost:8096** and follow the setup wizard.

- Add a media library pointing to `/media` (already mounted in the container).
- Enable **"Allow remote connections to this server"** if you plan to access it outside your LAN.

---

## Remote Access via Tailscale

[Tailscale](https://tailscale.com) is a zero-config VPN built on WireGuard. Once set up, all your devices — phone, laptop, TV — join a private network and can reach your NAS as if they were on the same WiFi.

> **How Tailscale routes traffic**
> When your device and the NAS are on the same local network, Tailscale automatically uses a **direct peer-to-peer connection** (fast, zero latency overhead). When you're away from home, it routes securely through Tailscale's relay network (DERP) — so streaming always works, wherever you are.

### Install & authenticate

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

### Expose services over HTTPS

```bash
tailscale serve --bg --https=8043 http://localhost:8043   # qBittorrent
tailscale serve --bg --https=8096 http://localhost:8096   # Jellyfin
```

You can then access your services at `https://<tailscale-hostname>:8043` and `https://<tailscale-hostname>:8096` from any device on your tailnet.

### Useful commands

```bash
# See all devices on your tailnet and their connection status
tailscale status

# Check which ports are being served and their URLs
tailscale serve status

# Confirm whether a connection to your NAS is direct or relayed
tailscale ping <nas-tailscale-hostname>
```

---

## Directory Structure

```
.
├── docker-compose.yml
├── trigger.Dockerfile
├── trigger_server.py       # Webhook server (trigger-service)
├── scan_and_move.sh        # ClamAV scan + file routing script
├── .env                    # Secrets (not committed)
├── clamav/config/          # ClamAV virus definitions (auto-updated)
├── jellyfin/config/        # Jellyfin config & metadata
└── qbittorrent/
    ├── config/             # qBittorrent config
    └── downloads/
        ├── staging/        # Downloads land here first
        ├── media/          # Clean files served by Jellyfin
        └── quarantine/     # Infected files isolated here
```

---

## Security Notes

- The **docker-socket-proxy** ensures `trigger-service` can only exec into the `clamav` container — it cannot start, stop, or inspect other containers.
- The trigger endpoint is bound to `127.0.0.1:9999` only — not exposed to the network.
- Always keep your `TRIGGER_SECRET` private and rotate it if leaked.

---

## Reporting Issues

If you run into a bug or something isn't working as expected, please [open an issue](https://github.com/vivek2293/Home-NAS-Server/issues/new) on GitHub.

To help diagnose the problem quickly, include the following in your report:

```
**Describe the issue**
A clear description of what went wrong.

**Steps to reproduce**
1. ...
2. ...

**Expected behaviour**
What you expected to happen.

**Actual behaviour**
What actually happened.

**Environment**
- OS: (e.g. Ubuntu 22.04, Windows 11 + WSL2)
- Docker version: (docker --version)
- Docker Compose version: (docker compose version)

**Relevant logs**
(paste output from: docker compose logs --tail=500)
```

---

## Acknowledgements

If this project saved you time or helped you get your home NAS running, a GitHub star goes a long way — it helps others find the project and lets me know it's been useful.

[Star this repo on GitHub](https://github.com/vivek2293/Home-NAS-Server) — thank you!

---

## License

This project is licensed under the **GNU General Public License v3.0**.

You are free to use, modify, and distribute this project, but any derivative work must also be released under GPL v3. No organisation may incorporate this code into proprietary software or sell it as a closed-source product.

See the [LICENSE](./LICENSE) file for the full license text.
