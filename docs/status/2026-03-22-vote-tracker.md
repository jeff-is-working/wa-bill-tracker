# Session Summary -- 2026-03-22 (Vote Tracker Feature)

## What Was Done

### Vote Results Tracker (Issue #75)
- Added get_roll_calls() to fetch vote data from WA SOAP API GetRollCalls method
- Added parse_governor_action() to extract governor status from bill history lines
- 541 bills updated with vote data (house/senate yea-nay-absent-excused counts)
- New buildVoteTracker() component replaces pizza tracker on passed/governor/enacted bills
- Governor status row shows: awaiting signature, signed, or vetoed
- Bills still in legislature keep the existing progress tracker
- Mobile responsive (stacks chambers vertically on small screens)

### Bug Fixes
- Fixed "undefined 2026" title (config.js read wrong field from session.json) -- Issue #73
- Fixed "WA Legislative Tracker 2026 2026" doubled year (siteTitle already includes year)
- Fixed PASSED stamp only on 1 bill (governor bills also passed legislature) -- Issue #74
- Fixed dev server data URL (dev serves local bills.json with vote data, prod uses GitHub raw)

### Post-Session UX (Issues #71, #72)
- Red rubber stamp overlays: PASSED on governor/passed_legislature bills, SIGNED on enacted
- Banner updated: "2026 Session Has Ended -- Showing Bills Awaiting Governor Action"
- Info flyout replaced with post-session content explaining governor action process

## Decisions Made
- Dev server fetches data locally (has vote data), prod fetches from GitHub raw URL
- Vote data fetched only for bills past passed_origin status (~541 bills)
- Enacted bills from 2025 session excluded from vote data fetch (prior session)

## What's Left
- Merge vote tracker from 2027-session to main when ready for prod
- Sprint 4: 2027 session switchover (blocked on cutoff calendar ~Dec 2026)
- Rotate exposed Cloudflare API tokens
