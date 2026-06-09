# Expected Hosting Cost

> For the single-server architecture (**Hetzner CX32 + Coolify + Cloudflare**).
> Prices as of **June 2026**, in **EUR, excluding VAT** unless noted. Confirm exact figures at signup.

---

## Summary

**≈ €6.80 / month** recurring + **~€12 / year** for the domain ≈ **€7.80 / month all-in**, flat — **no renewal cliff**. Adding more apps costs **€0** until you outgrow the server.

---

## Recurring — monthly

| Item | Spec | Cost / mo |
|---|---|---|
| **Server** — Hetzner CX32 | 4 vCPU · 8 GB RAM · 80 GB NVMe · 20 TB traffic | **€6.80** |
| PaaS — Coolify | Open-source, self-hosted | €0 |
| DNS + CDN + WAF — Cloudflare | Free plan, unlimited bandwidth | €0 |
| TLS certificates — Let's Encrypt | Auto-issued via Coolify | €0 |
| **Monthly total** | | **€6.80** |

*Tier alternatives:* CX22 (2 vCPU / 4 GB) = **€3.79/mo** · CX42 (8 vCPU / 16 GB) = **€16.40/mo**.

---

## Recurring — annual / periodic

| Item | Cost |
|---|---|
| Domain `.com` | ~**€11–14 / year** (Cloudflare Registrar at-cost ≈ $10.44; varies by TLD/registrar) |

---

## Optional add-ons

| Item | Purpose | Cost |
|---|---|---|
| Hetzner Storage Box **BX11** | 1 TB offsite backups, unlimited traffic | **€3.20 / mo** |
| Hetzner Cloud server backups | Automatic whole-server snapshots | ~+20% of server (**≈ €1.36 / mo**) |
| Email — Cloudflare Email Routing | Forwarding only (no mailboxes) | €0 |
| Email — Google Workspace | Real mailboxes | ~€5–6 / user / mo |
| LLM — OpenAI API (MR Guardian, optional) | Only if `MR_GUARDIAN_LLM_PROVIDER` enabled | Pay-as-you-go |

---

## All-in monthly scenarios

| Scenario | Components | Cost / mo (+ domain) |
|---|---|---|
| **Lean start** | CX22, Coolify backups to existing storage | **€3.79** |
| **Recommended (minimal)** | CX32, Coolify backups to existing storage | **€6.80** |
| **Recommended (resilient)** | CX32 + BX11 1 TB offsite backups | **€10.00** |

---

## 3-year total cost of ownership

*Recommended (resilient) build, excl. email & VAT:*

| Item | Calc | 3-yr total |
|---|---|---|
| Server (CX32) | €6.80 × 36 | €244.80 |
| Backups (BX11) | €3.20 × 36 | €115.20 |
| Domain | ~€12 × 3 | €36.00 |
| **Total** | | **≈ €396** (~€11 / mo) |

*Without the dedicated backup box:* **≈ €281** (~€7.80 / mo).

---

## How it compares

*Same scope: site + blog + wiki + 2 apps + WordPress.*

| Option | ~Monthly | Runs MR Guardian? | Notes |
|---|---|---|---|
| **This plan** (Hetzner + Coolify) | **€6.80 flat** | ✅ Yes | Unlimited apps; you manage one server |
| Managed (Cloudflare Pages + Render) | site/wiki €0, **+~$7 per app**, WP needs add-ons → **~$15–25+** | ✅ Yes | No server upkeep; cost scales per app |
| Shared host (HostGator / Bluehost / SiteGround) | **~$10–18** after renewal | ❌ No | Good for WordPress only; can't run Docker apps; intro rate needs multi-year prepay, renews 2–3× |

---

## Notes & assumptions

- Hetzner bills in **EUR + VAT** where applicable; a price adjustment took effect **1 April 2026** — figures above reflect current June 2026 list prices.
- USD-billed customers: CX32 ≈ **$7–8 / mo** equivalent.
- **20 TB/mo** traffic is included on the server — far beyond typical needs for these sites.
- Cloudflare **Free** covers DNS, CDN, basic WAF, and unlimited proxied bandwidth.
- **Marginal cost of new apps = €0** until CPU/RAM saturates; then resize in-place to the next CX tier.

---

### Price references

- Hetzner Cloud pricing — <https://www.hetzner.com/cloud>
- Hetzner Storage Box BX11 — <https://www.hetzner.com/storage/storage-box/bx11/>
- Coolify (free, open-source) — <https://coolify.io/>
- Cloudflare plans — <https://www.cloudflare.com/plans/>
- Render pricing (managed comparison) — <https://render.com/pricing>
