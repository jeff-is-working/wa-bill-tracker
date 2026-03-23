# Session Summary -- 2026-03-22

## What Was Done

### Post-Session Governor Fix (main)
- Fixed cutoff logic hiding passed_legislature and governor bills after Sine Die
- Added post-session stats: Awaiting Governor, Signed Into Law
- Updated header stat cards for post-session state
- Reduced fetch schedule to weekdays only (governor actions are business-day only)

### C6S Application Modernization (2027-session branch, merged to main)

**Sprint 1: Assessment & TDD Scaffolding**
- Technical debt inventory (7 items), 4 ADRs
- 4 Python TDD test files (29 tests), Playwright E2E infrastructure (3 spec files)

**Sprint 2: CSS Extraction & C6S Branding**
- Extracted ~1000 lines inline CSS to styles.css (index.html: 2215 -> 324 lines)
- C6S design tokens: sage green palette, warm earth tones
- Removed Google Fonts dependency (system font stack)

**Sprint 3: JS Modularization & Session Config**
- Split app.js (2310 lines) into 6 ES modules in js/
- Created data/session.json as single config source of truth
- Cookie keys namespaced by session year
- Python pipeline reads from session.json instead of hardcoded constants
- Removed dead TestMeetingsJSONStructure tests

### Dev Server Setup
- VM 205 (wa-tracker-dev) on proxmox04: Ubuntu 24.04, 1 vCPU, 1GB RAM
- Caddy with Cloudflare DNS-challenge TLS cert (custom build, patched token regex)
- Pi-hole local DNS: dev.wa-bill-tracker.org -> 192.168.0.205
- Fixed Pi-hole dnsmasq failure caused by corrupted TOML entry in upstreams array
- Auto-deploy from 2027-session branch via cron (5 min)

### Infrastructure Updates
- Fixed Ansible inventory: Pi-hole and Omada are on proxmox04 (CT 111, CT 110), not proxmox02
- Added all LXC containers to inventory with IPs and purposes
- Cloudflare DNS token stored in ansible-vault (homelab-infra-kv was unavailable due to Azure AD JWT issue)
- Azure Key Vault RBAC: added Secrets Officer role on wa-bill-tracker-kv

## Decisions Made
- Merged 2027-session architectural improvements to main (prod was broken with monolithic code)
- Tagged v2026-pre-modularize as rollback point
- Sprint 4 (2027 session switchover) remains blocked until cutoff calendar published (~Dec 2026)
- Dev server uses Pi-hole local DNS + Caddy DNS-challenge certs (no cloudflared, no port forwarding)

## What's Left
- Sprint 4: Update session.json to 2027 values, archive 2026 data, simplify biennium logic
- Blocked on: official 2027 cutoff calendar (~Dec 2026), session start (~Jan 2027)
- Rotate exposed Cloudflare API tokens (two were exposed in conversation)
- Migrate secrets from ansible-vault to Azure Key Vault once JWT issue resolves
- Debug Azure AD AKV10046 JWT validation error affecting wa-bill-tracker-kv

## Lessons Learned
- Pi-hole v6 regenerates dnsmasq.conf from pihole.toml on every restart -- never edit dnsmasq.conf directly
- Caddy cloudflare DNS module (libdns v0.2.2) has a token regex limited to 50 chars; newer Cloudflare tokens exceed this
- Azure Key Vault RBAC propagation can take minutes; JWT signing key issues (AKV10046) are service-side and unrecoverable without waiting
- Never put secrets in bash tool calls -- always have user run via ! prefix
