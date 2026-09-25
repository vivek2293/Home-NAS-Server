# Home NAS Stack

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

A self-hosted, Docker-based home media server stack — download, scan, and stream your media from your own hardware. Use [Tailscale](https://tailscale.com) to stream to any of your devices, no matter where you are.

Get started with the [Quick Start](#option-a-quick-start-for-lazy-people) or read the full [Setup Guide](#setup).

> **Note on responsible use**
> BitTorrent is a legitimate file-transfer protocol used to distribute Linux ISOs, open-source software, Creative Commons content, and more. This stack is built around that use case. Downloading copyrighted material without permission is illegal — that's on you, not the tool.

---

## What's Inside

| Service | Purpose | Port |
|---|---|---|
| **[qBittorrent](https://www.qbittorrent.org/)** | Torrent client with web UI | `8043` (localhost only) |
| **[Jellyfin](https://jellyfin.org/)** | Media server for streaming | `8096` (localhost only) |
| **[ClamAV](https://www.clamav.net/)** | Antivirus scan on every download | — |
| **trigger-service** | Webhook that auto-scans & moves completed downloads | `9999` (localhost only) |
| **docker-socket-proxy** | Restricts raw Docker socket access for security | — |
| **dashboard** | Static landing page — links to all services | `8080` (localhost only) |

**[qBittorrent](https://www.qbittorrent.org/)** handles all downloading — it's a lightweight, open-source torrent client with a clean web interface, so you can manage downloads from any browser without installing anything extra.

**[Jellyfin](https://jellyfin.org/)** is a free, open-source media server that organises your files into a Netflix-style library and streams them to any device.

**[ClamAV](https://www.clamav.net/)** is an open-source antivirus engine that scans every downloaded file before it reaches your library, keeping your system clean without any manual intervention.

The **trigger-service** is a small custom webhook server that acts as the glue — qBittorrent calls it when a download finishes, and it kicks off the ClamAV scan automatically.

The **docker-socket-proxy** sits between the trigger-service and Docker to ensure that the webhook can only run the scanner, and nothing else — a deliberate security boundary.


### How it works

1. qBittorrent downloads a file to a **staging** directory.
2. On completion, it calls the **trigger-service** (via `host.docker.internal:9999`).
3. The trigger-service invokes `scan_and_move.sh`, which runs a **[ClamAV](https://www.clamav.net/)** scan.
4. Clean files are moved to `media/` (served by Jellyfin). Infected files are moved to `quarantine/`.

---

## Setup

### Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| [Docker Engine](https://docs.docker.com/get-docker/) | 24.0+ | Linux or Docker Desktop (Windows/macOS) |
| [Docker Compose](https://docs.docker.com/compose/) | v2.0+ | Comes bundled with Docker Desktop |
| [Python](https://www.python.org/) | 3.8+ | Required for the automated setup wizard |
| Bash | Any | Linux native; use WSL2 or Git Bash on Windows |
| curl | Any | Required for the download trigger command |
| openssl | Any | Optional — used to manually generate `TRIGGER_SECRET` |

---

### Option A: Quick Start (For Lazy People)

If you just want everything up and running without touching config files or manual steps, open your terminal and run:

```bash
# 1. Clone the repository
git clone https://github.com/vivek2293/Home-NAS-Server.git

# 2. Enter the directory
cd Home-NAS-Server

# 3. Run the setup wizard
python setup.py      # or: python3 setup.py
```

The wizard takes care of the heavy lifting: verifying prerequisites, creating storage directories, generating security secrets, booting the Docker stack, and configuring service credentials and webhook triggers automatically.

> **Note:** If the automated setup encounters any issues or fails in your environment, please [open an issue](https://github.com/vivek2293/Home-NAS-Server/issues/new) and follow **Option B** below to complete the setup manually.

---

### Option B: Manual Setup & Customization (For Control Freaks)

If you prefer configuring each component yourself, want to see how the stack works under the hood, or need to set things up manually, follow the step-by-step instructions below.

#### 1. Clone the repo

```bash
git clone https://github.com/vivek2293/Home-NAS-Server.git
cd Home-NAS-Server
```

#### 2. Configure environment variables

Edit the `.env` file and set your secret:

```env
TRIGGER_SECRET=your_random_secret_here
```

> Generate a strong secret with: `openssl rand -hex 32`

#### 3. Start the stack

```bash
docker compose up -d
```

#### 4. First-time qBittorrent setup

Get the auto-generated password from the logs:

```bash
# Bash
docker logs qbittorrent 2>&1 | grep -i "password"

# PowerShell
docker logs qbittorrent | findstr /i "password"
```

Open **http://localhost:8043**, log in with `admin` / `<password from logs>`, and **change your password** immediately via *Settings → Web UI*.

#### 5. Configure the download trigger

In qBittorrent Settings → **Downloads**:

- Tick **"Run on torrent finished"**
- Set the command to call the trigger-service webhook:

```
curl -s -X POST http://host.docker.internal:9999/trigger -H "X-Trigger-Secret: <TRIGGER_SECRET>" -d '{"name": "%N"}'
```

> Replace `<TRIGGER_SECRET>` with the exact same value you set in your `.env` file.

#### 6. First-time Jellyfin setup

Open **http://localhost:8096** and follow the setup wizard.

- Add a media library pointing to `/media` (already mounted in the container).


---

## Remote Access via Tailscale

[Tailscale](https://tailscale.com) is a zero-config VPN built on WireGuard. Once set up, all your devices — phone, laptop, TV — join a private network and can reach your NAS as if they were on the same WiFi. Refer to the [Tailscale documentation](https://tailscale.com/docs) for platform-specific installation instructions and advanced configuration.

> **How Tailscale routes traffic**
> When your device and the NAS are on the same local network, Tailscale automatically uses a **direct peer-to-peer connection** (fast, zero latency overhead). When you're away from home, it routes securely through Tailscale's relay network (DERP) — so streaming always works, wherever you are.

### Install & authenticate

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

### Expose services over HTTPS

```bash
tailscale serve --bg --https=443 http://localhost:8080   # Dashboard  (your default landing page)
tailscale serve --bg --https=8043 http://localhost:8043  # qBittorrent
tailscale serve --bg --https=8096 http://localhost:8096  # Jellyfin
```

Once configured, open `https://<tailscale-hostname>` in any browser on your tailnet to reach the **dashboard** — it links to all services so you never need to remember a port number.

> **Why all ports are localhost-only:** Every service in this stack binds only to `127.0.0.1`, so they are invisible to devices on the same WiFi or LAN. All remote access goes exclusively through Tailscale's encrypted WireGuard tunnel.

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

### Managing downloads from your phone

qBittorrent's web UI works in any mobile browser — no app needed. Once Tailscale is running, open your browser and navigate to:

```
https://<tailscale-hostname>:8043
```

Log in and you can add torrents, monitor progress, and manage your queue from anywhere. The full pipeline then runs automatically:

1. qBittorrent downloads the file to the **staging** directory.
2. On completion it calls the **trigger-service**, which runs a **ClamAV** scan.
3. If the scan passes, the file is moved to `media/` — picked up by Jellyfin in **~60 seconds**.
4. If the scan fails, the file is moved to `quarantine/` and is **never served**.

> You can also trigger an immediate Jellyfin library refresh manually — see the section below.

---

### Streaming on your phone

Jellyfin has an official Android app — [download it from the Play Store](https://play.google.com/store/apps/details?id=org.jellyfin.mobile). Once Tailscale is set up, open the app and enter your Tailscale address as the server URL:

```
https://<tailscale-hostname>:8096
```

You'll be able to browse and stream your entire library from any device, whether you're home or away.

> **New files not showing up?** Jellyfin scans for new content automatically, but it can take 30–60 seconds. To trigger an immediate refresh, open the sidebar (tap the three-line menu), go to **Dashboard**, then tap **Scan all libraries**.

---

## Directory Structure

```
.
├── docker-compose.yml
├── trigger.Dockerfile
├── trigger_server.py       # Webhook server (trigger-service)
├── scan_and_move.sh        # ClamAV scan + file routing script
├── .env                    # Secrets (not committed)
├── dashboard/
│   ├── index.html          # Landing page served at https://<tailscale-hostname>
│   ├── style.css           # All styles
│   └── app.js              # Service definitions & DOM renderer
├── clamav/config/          # ClamAV virus definitions (auto-updated)
├── jellyfin/config/        # Jellyfin config & metadata
└── qbittorrent/
    ├── config/             # qBittorrent config
    └── downloads/
        ├── staging/        # Downloads land here first
        ├── media/          # Clean files served by Jellyfin
        └── quarantine/     # Infected files isolated here
```

**Tip — adding files manually:**

- **Skip the scan:** If you already trust a file (e.g. a personal video or a purchased download), you can drop it directly into `qbittorrent/downloads/media/`. Jellyfin will pick it up automatically — no scan required.
- **Scan before serving:** If you'd prefer to run it through [ClamAV](https://www.clamav.net/) first, place the file in `qbittorrent/downloads/staging/` and then run the scan script manually:

  ```bash
  ./scan_and_move.sh
  ```

  Clean files will be moved to `media/` automatically. Anything suspicious goes to `quarantine/`.

---

## Security & System Isolation

This stack is designed around defense-in-depth, strict isolation, and the principle of least privilege. No service has unrestricted access to the host system or to directories outside its explicit scope.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                               Host Machine                                  │
│                                                                             │
│  ┌─────────────────────────┐            ┌────────────────────────────────┐  │
│  │       qBittorrent       │            │            Jellyfin            │  │
│  │  • Isolated container   │            │  • Isolated container          │  │
│  │  • Writes ONLY staging/ │            │  • READ-ONLY access to media/  │  │
│  │  • No access to host/OS │            │  • Zero write permissions      │  │
│  └────────────┬────────────┘            └────────────────▲───────────────┘  │
│               │ (download complete)                      │                  │
│               ▼                                          │ (scanned clean)  │
│  ┌─────────────────────────┐            ┌────────────────┴───────────────┐  │
│  │     trigger-service     │  executes  │             ClamAV             │  │
│  │  • Localhost (127.0.0.1)│ ─────────► │  • Scans downloads before move │  │
│  │  • Secret auth required │  via proxy │  • Isolated sandbox engine     │  │
│  │  • Non-root UID 1000    │            │  • Threats go to quarantine/   │  │
│  └────────────┬────────────┘            └────────────────────────────────┘  │
│               │                                                             │
│               ▼ (restricted API)                                            │
│  ┌─────────────────────────┐                                                │
│  │   docker-socket-proxy   │ ──► /var/run/docker.sock (Read-Only)           │
│  │  • Blocks dangerous ops │                                                │
│  └─────────────────────────┘                                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1. Filesystem & Storage Isolation
- **qBittorrent is sandboxed to `staging/`**: qBittorrent only mounts `./qbittorrent/downloads/staging` as `/downloads`. It cannot write to `media/`, cannot access `quarantine/`, and has zero access to the host filesystem. Even if a downloaded archive contains malicious scripts, it remains contained in `staging/`.
- **Jellyfin has Read-Only access**: The media folder is mounted into Jellyfin as `:ro` (`./qbittorrent/downloads/media:/media:ro`). Even if Jellyfin or its web client were compromised, it cannot tamper with, overwrite, or delete media files or host data.
- **ClamAV quarantine gate**: Downloaded files are never moved to `media/` until ClamAV verifies they are clean. Any infected payload is immediately routed into `quarantine/`, isolated from both Jellyfin and the host.

### 2. Docker Socket Protection (docker-socket-proxy)
- Granting raw Docker socket (`/var/run/docker.sock`) access to a container is equivalent to root on the host. To prevent this, the raw socket is mounted **read-only (`:ro`)** solely to **`docker-socket-proxy`**.
- The `trigger-service` communicates with Docker only through this proxy over a private bridge network (`trigger-proxy-net`).
- The proxy strictly limits API endpoints (`EXEC=1`, `POST=1`, `CONTAINERS=1`): it only permits executing commands inside the `clamav` container. It explicitly **blocks** container creation, deletion, volume mounting, privilege escalation, or image modification.

### 3. Process & User Isolation
- **Non-root container execution**: Services run with explicit non-root user mappings (`PUID=1000`, `PGID=1000`, `user: "1000:1000"`), matching standard unprivileged user permissions.
- **Read-only code mounts**: The webhook server script (`trigger_server.py`) is mounted read-only (`:ro`), preventing runtime modification.

### 4. Network & Ingress Security
- **Localhost-only ports**: Every service WebUI is bound strictly to `127.0.0.1` — qBittorrent (`:8043`), Jellyfin (`:8096`), dashboard (`:8080`), and the trigger webhook (`:9999`) are all invisible to devices on the same WiFi or LAN. Only torrent peer traffic (`:6881`) is left open on all interfaces, as it must be reachable from the internet.
- **Tailscale as the sole ingress**: All remote access is routed through Tailscale's encrypted WireGuard tunnel. The dashboard at `https://<tailscale-hostname>` acts as a single, memorable entry point.
- **Shared secret authentication**: All calls to the trigger endpoint require a valid `X-Trigger-Secret` header matching `TRIGGER_SECRET`.
- **Private overlay network**: Tailscale encrypts and authenticates all remote traffic point-to-point via WireGuard, avoiding open public router ports.

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

Building and maintaining this took a fair amount of time and iteration. If it helped you get your home NAS up and running — or even just saved you an afternoon of research — consider leaving a star. It costs nothing, but it genuinely helps the project reach others who might benefit from it.

[⭐ Star this repo on GitHub](https://github.com/vivek2293/Home-NAS-Server) — it means a lot, thank you!

---

## License

This project is licensed under the **GNU General Public License v3.0**.

You are free to use, modify, and distribute this project, but any derivative work must also be released under GPL v3. No organisation may incorporate this code into proprietary software or sell it as a closed-source product.

See the [LICENSE](./LICENSE) file for the full license text.
