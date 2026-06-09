# Hosting Architecture & Specifications

> Single-server, **subdomain-per-service** hosting for `www.myname.com` and related apps.
> Prepared June 2026. Replace `myname.com` with your registered domain.

---

## 1. Overview

One **Hetzner Cloud VPS** runs **Coolify** (open-source, self-hosted PaaS). Every site and app is a separate Coolify *resource* on its own subdomain, each with its own Git-push deploy pipeline and automatic SSL. **Cloudflare** sits in front for DNS, CDN, and DDoS protection.

**Design goals:** stability, low + predictable cost, and the ability to add new apps at €0 marginal infrastructure cost.

```
                       Internet
                          │
                 ┌────────▼────────┐
                 │   Cloudflare    │  DNS · CDN · WAF · SSL (Full strict)
                 └────────┬────────┘
                          │  *.myname.com  → server IPv4
                 ┌────────▼────────────────────────────┐
                 │   Hetzner VPS (CX32) · Ubuntu 24.04  │
                 │   ┌──────────────────────────────┐   │
                 │   │  Coolify (Traefik proxy+SSL)  │   │
                 │   ├──────────────────────────────┤   │
                 │   │ www        → site            │   │
                 │   │ blog       → WordPress/static│   │
                 │   │ docs       → MkDocs Material │   │
                 │   │ mrguardian → MR Guardian     │   │
                 │   │ wp         → WordPress+MariaDB│   │
                 │   │ *          → future apps     │   │
                 │   └──────────────────────────────┘   │
                 └──────────────────────────────────────┘
```

---

## 2. Domain & DNS map

| Subdomain | Service | Runtime | Persistent data |
|---|---|---|---|
| `myname.com` / `www` | Main site | Static **or** WordPress *(TBD)* | depends on choice |
| `blog.myname.com` | Blog | WordPress or static | DB + uploads (if WP) |
| `docs.myname.com` | Wiki / docs | MkDocs + Material (static HTML) | none (rebuilt from Git) |
| `mrguardian.myname.com` | MR Guardian | Docker (FastAPI + Streamlit + Caddy) | SQLite on volume |
| `wp.myname.com` | Migrated WordPress | WordPress + MariaDB | DB + uploads |
| `*.myname.com` | Future apps | Any Docker / Git app | per app |

**DNS setup:** wildcard `*` A-record plus `@` and `www` → server IPv4, managed in **Cloudflare (Free plan)**, SSL mode **Full (strict)**.

---

## 3. Server (compute)

**Recommended — Hetzner Cloud CX32**

| Attribute | Value |
|---|---|
| vCPU | 4 (shared Intel) |
| RAM | 8 GB |
| Disk | 80 GB NVMe SSD |
| Traffic | 20 TB / month included |
| IP | 1× IPv4 (+ IPv6) |
| OS | Ubuntu 24.04 LTS |
| Region | Nearest to your audience (EU: Falkenstein/Nuremberg/Helsinki · US: Ashburn/Hillsboro) |

**Why 8 GB:** headroom to run WordPress + MariaDB, MR Guardian (Streamlit is the RAM-hungry component), the wiki, and the blog concurrently with room for one or two more apps.

**Start-lean alternative:** CX22 (2 vCPU / 4 GB) if you begin with only the docs + one light app — Hetzner allows in-place upgrade to CX32/CX42 later with a reboot.

---

## 4. Platform layer — Coolify

- Open-source, self-hostable PaaS; installs in one command (Docker + Traefik + dashboard).
- **Built-in reverse proxy (Traefik)** handles per-subdomain routing and **automatic Let's Encrypt SSL** (issue + renew).
- **Git integration:** connect a GitHub/GitLab repo per service; deploy on push.
- **One-click catalog** (280+ services) incl. WordPress, MariaDB/MySQL, PostgreSQL, Redis, Ghost, etc.
- Manages Docker builds, environment variables/secrets, persistent volumes, health checks, and scheduled backups.

---

## 5. Per-service specifications

### 5.1 Main site — `www` *(decision pending)*
- **Static** (Astro / Hugo / plain HTML): built from Git, served as static files — lowest resource use; **or**
- **WordPress**: use the stack in §5.5.

### 5.2 Blog — `blog`
- WordPress (can share the WP stack) or a static generator. Independent subdomain either way.

### 5.3 Wiki / docs — `docs` (MkDocs + Material)
- **Build:** `mkdocs build` → static `site/` directory (Coolify runs the build from your docs repo on each push).
- **Runtime:** static file serving (Coolify static buildpack).
- **Storage:** none persistent — fully regenerated from Git.
- **Theme:** Material for MkDocs.

### 5.4 MR Guardian — `mrguardian`
- **Runtime:** Docker, using the existing `Dockerfile`. Caddy reverse-proxy on `$PORT` → FastAPI/uvicorn (`127.0.0.1:8800`) for `/api/*` and Streamlit (`127.0.0.1:8810`) for `/`.
- **Persistent volume:** mount a Coolify volume at `/data`; SQLite DB lives at `/data/history.sqlite`.
- **Environment (from `render.yaml`):** `MR_GUARDIAN_HISTORY_DB_PATH`, `MR_GUARDIAN_POLICY_DIR`, `MR_GUARDIAN_ADMIN_TOKEN` *(secret)*, `MR_GUARDIAN_LLM_PROVIDER` *(default `disabled`)*, `MR_GUARDIAN_OPENAI_API_KEY` *(optional secret)*, `GITLAB_*` *(optional — live MR reviews)*.
- **Health check:** `GET /api/healthz`.
- **Footprint:** ~0.5–1 vCPU, ~512 MB–1 GB RAM (Streamlit dominant).

### 5.5 WordPress — `wp` (migrated)
- **Stack:** WordPress (PHP-FPM) + MariaDB via Coolify one-click.
- **Persistent volumes:** `wp-content/uploads` and the MariaDB data directory.
- **Migration:** All-in-One WP Migration / Duplicator / Migrate Guru — moves files, DB, themes, plugins, and rewrites URLs to the new subdomain.
- **Footprint:** ~0.5 vCPU, ~512 MB–1 GB RAM (app) + ~256–512 MB (DB).

### 5.6 Future apps — `*`
- **Pattern:** new Coolify resource → connect Git repo or Docker image → assign subdomain → deploy. €0 marginal infra cost until CPU/RAM saturates, then step up the server tier.

---

## 6. Cross-cutting concerns

**SSL / TLS** — Let's Encrypt, auto-issued and auto-renewed per subdomain by Coolify; Cloudflare set to **Full (strict)** so edge↔origin stays encrypted.

**Backups** — Coolify scheduled backups for app volumes + databases; offsite target = **Hetzner Storage Box BX11 (1 TB)** or any S3-compatible bucket. Suggested: daily DB dump + daily/weekly volume snapshot, retain 7–30 days. Optionally enable **Hetzner Cloud server backups** (~+20% of server price) for whole-box restore.

**Email** — *not* provided by the server. Use **Cloudflare Email Routing** (free forwarding) or **Google Workspace / Microsoft 365** for real mailboxes; configure MX/SPF/DKIM in Cloudflare DNS.

**Monitoring & security** — Coolify health checks + notifications (email/Slack/Discord/Telegram); Cloudflare WAF/DDoS (free baseline); server hardening (SSH keys only, UFW firewall, unattended security upgrades, fail2ban); external uptime monitor (e.g., UptimeRobot free) per subdomain.

---

## 7. Prerequisites / accounts

- Registered domain (`myname.com`).
- Hetzner Cloud account.
- Cloudflare account (Free plan).
- GitHub or GitLab repositories for the site, docs, and app(s).
- Existing WordPress export (for the migration).

---

## 8. Open decisions

1. **`www` technology** — static (Astro/Hugo/HTML) vs WordPress.
2. **Region** — latency vs data-residency preference.
3. **Starting tier** — CX32 (recommended) vs CX22 (lean start, upgrade later).
