# Session Summary -- 2026-03-23

## What Was Done

### C6S Application Modernization (Sprints 1-3, merged to main)
- Extracted 1,000 lines of inline CSS to styles.css with C6S design tokens (sage green palette)
- Split monolithic app.js (2,310 lines) into 6 ES modules (js/config, state, data, render, notes, app)
- Created data/session.json as single source of truth for session config
- Cookie keys namespaced by session year (wa_tracker_2026_tracked)
- Python pipeline reads BIENNIUM/YEAR from session.json instead of hardcoded constants
- Removed dead TestMeetingsJSONStructure tests (meetings.json never existed)

### Vote Results Tracker (Issue #75)
- Added get_roll_calls() to fetch vote data from WA SOAP API GetRollCalls
- Added parse_governor_action() to extract governor status from history lines
- 541 bills updated with vote data (house/senate yea-nay-absent-excused counts)
- New buildVoteTracker() component replaces pizza tracker on passed/governor/enacted bills
- Governor status row: awaiting signature, signed, or vetoed
- Bills still in legislature keep existing progress tracker

### Post-Session UX
- Red rubber stamp overlays: PASSED on governor/passed_legislature, SIGNED on enacted (Issues #71, #74)
- Banner: "2026 Session Has Ended -- Showing Bills Awaiting Governor Action" (Issue #72)
- Info flyout explains governor action process, shows live bill counts
- Switched data loading from GitHub raw URL to local data/bills.json (Issue #73)

### Bug Fixes
- Fixed "undefined 2026" title -- config.js read wrong field from session.json (Issue #73)
- Fixed "2026 2026" doubled year in title
- Fixed PASSED stamp only on 1 bill -- governor bills also passed legislature (Issue #74)
- Fixed CSP: restored style-src unsafe-inline for JS inline style assignments

### Dev Server (Issue #70)
- VM 205 (wa-tracker-dev) on proxmox04: Ubuntu 24.04, hardened
- Caddy with custom-built Cloudflare DNS module (patched token regex for new CF token format)
- Let's Encrypt TLS cert via Cloudflare DNS-01 challenge
- Pi-hole local DNS: dev.wa-bill-tracker.org -> 192.168.0.205
- Cron auto-deploy from 2027-session branch every 5 minutes

### Infrastructure
- Fixed Pi-hole dnsmasq failure (bad entry in pihole.toml upstreams array)
- Fixed Ansible inventory: Pi-hole (CT 111) and Omada (CT 110) are on proxmox04, not proxmox02
- Added all LXC containers to inventory with IPs and purposes
- Azure Key Vault RBAC: added Secrets Officer on wa-bill-tracker-kv
- Cloudflare token stored in ansible-vault (Azure KV had JWT validation issue)

### Testing Infrastructure
- Playwright E2E: 8 spec files, 35 tests (34 passing, 1 properly failing)
- Python pytest: 174 passing, 1 skipped
- Fixed Playwright port from 3000 (OpenWebUI conflict) to 4200

### Process Improvements
- Added rule to workspace CLAUDE.md and project template: never suppress failing tests
- Added rule to memory: always offer C6S firm teams before starting work
- Added rule to memory: never put secrets in bash commands or conversation
- Added rule to memory: always check ports before configuring servers

## Open Issues
- #76: Remove X-Frame-Options from meta tag (only works as HTTP header)
- #77: Eliminate inline style assignments in JS to remove unsafe-inline from CSP
- #68: Sprint 4 -- 2027 session switchover (blocked on cutoff calendar ~Dec 2026)
- Azure Key Vault wa-bill-tracker-kv JWT validation error (AKV10046) -- service-side, waiting to resolve
- Rotate Cloudflare API tokens exposed in conversation

## Decisions Made
- Merged 2027-session architecture to main (prod was broken with old monolithic code)
- Dev server uses Pi-hole local DNS + Caddy DNS-challenge (no cloudflared, no port forwarding)
- Data served locally from data/bills.json on both prod and dev (no GitHub raw URL)
- Tests that catch real problems must fail -- never suppress to pass

## Lessons Learned
- Pi-hole v6 regenerates dnsmasq.conf from pihole.toml on restart -- never edit dnsmasq.conf directly
- Caddy cloudflare DNS module (libdns v0.2.2) has token regex limited to 50 chars; newer CF tokens exceed this
- session.json field names must match exactly between config.js reader and the JSON file
- GitHub raw CDN caches aggressively -- serving data locally is more reliable
- Port conflicts are silent failures -- always verify ports before configuring services
