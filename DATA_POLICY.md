# Data Handling Policy — Morning Briefing System

**Last updated:** 2026-05-27

---

## What this system does

This repository contains an automated fixed income morning briefing:
- `index.html` — rendered HTML briefing, published to GitHub Pages
- `fetch_bloomberg.py` — script that reads live data from a local Bloomberg Terminal
- `watchlist.json` — user-editable ticker configuration

---

## Bloomberg data — local only

**Bloomberg Terminal market data is never committed to this repository.**

`data.json` is listed in `.gitignore` and is excluded from all git operations.

The fetch script (`fetch_bloomberg.py`) writes `data.json` to the local machine only.
No Bloomberg data values leave the licensed workstation. The published `index.html`
contains rendered text (a finished document) — not a raw data export.

### Why this matters

Bloomberg's Terms of Service prohibit redistribution of Terminal data. Pushing raw
Bloomberg field values (prices, yields, OAS spreads, etc.) to any external system —
including a personal GitHub repository — would likely violate the data license. This
policy keeps all raw Bloomberg values on the licensed workstation at all times.

---

## What IS in this repository

| File | Contains | Pushed to GitHub |
|------|----------|-----------------|
| `index.html` | Rendered briefing HTML | Yes — published to GitHub Pages |
| `fetch_bloomberg.py` | Fetch logic (no data) | Yes |
| `watchlist.json` | Ticker labels only (no data values) | Yes |
| `run_feed.bat` | Local runner script | Yes |
| `DATA_POLICY.md` | This document | Yes |
| `data.json` | Bloomberg data values | **No — gitignored** |

---

## Compliance checklist

- [ ] Confirm with your firm's compliance team that running automated Terminal fetches
      on a work machine is permitted under your Bloomberg license and IT policy
- [ ] Confirm that generating a briefing document from Terminal data for internal
      team distribution is within your licensed use
- [ ] Confirm with IT that `pip install blpapi` and portable Git are permitted on
      the workstation

---

## Intellectual property

The code, HTML/CSS template, email delivery system, and overall briefing structure
in this repository were developed independently on personal equipment and personal
time. Bloomberg owns all rights to the underlying market data values accessed via
the Terminal. This repository does not reproduce, redistribute, or store any
Bloomberg data.

Review your employment agreement's IP assignment clause to confirm whether any
portion of this system constitutes a "work made for hire" under your contract.
If built entirely outside of work hours on personal equipment, the creative work
(template, scripts, design) is generally retained by the individual under US law.
This is general information — not legal advice. Consult your employment attorney
or firm's legal team if there is any ambiguity.
