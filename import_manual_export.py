#!/usr/bin/env python3
"""
Manual data import — morning briefing.

Alternative to fetch_bloomberg.py for machines without a local Bloomberg Terminal
(blpapi requires the desktop Terminal running on the same machine; this doesn't).

Workflow:
    1. On Bloomberg web (or Excel with BDP/BDH), build a table with one row per
       security and one column per field. First column is the ticker, using the
       SAME ticker strings as SECURITIES in fetch_bloomberg.py (e.g. "GT10:GOV").
       Remaining column headers are Bloomberg field mnemonics (e.g. PX_LAST).
    2. Download/save that table as a CSV.
    3. Run: python import_manual_export.py path\\to\\export.csv

Expected CSV shape (header row + one row per security):

    Ticker,PX_LAST,CHG_NET_1D,YLD_YTM_BID,OAS_SPREAD_ASK,DUR_ADJ_MID,RETURN_YTD,RETURN_QTD
    GT2:GOV,4.05,-0.01,4.05,,,,
    GT10:GOV,4.58,0.03,4.58,,,,
    LBUSTRUU:IND,2145.3,,4.41,95,6.2,3.1,0.8
    ...

Not every column is required for every row — leave cells blank if a field doesn't
apply (e.g. Treasuries don't have OAS_SPREAD_ASK). Blank/missing = None, same as
a field Bloomberg didn't return.

This is intentionally simple (values only, minimal validation) as a bridge until
a more robust import path gets signed off. Ticker and field names must match
fetch_bloomberg.py's SECURITIES / FIELDS exactly (case-sensitive) or that row/
column contributes nothing.

The CSV itself is never committed — see .gitignore. Raw Bloomberg field values
must stay local per DATA_POLICY.md, same rule as data.json.
"""

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

from fetch_bloomberg import FIELDS, OUTPUT_FILE, build_payload, load_watchlist

VALID_FIELDS = set(FIELDS)


def parse_csv(path: Path) -> dict:
    raw = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or reader.fieldnames[0] not in ("Ticker", "ticker"):
            raise ValueError('First column header must be "Ticker".')

        unknown_fields = [h for h in reader.fieldnames[1:] if h not in VALID_FIELDS]
        if unknown_fields:
            print(f"  ! Ignoring unrecognized column(s): {', '.join(unknown_fields)}")

        for row in reader:
            ticker = row[reader.fieldnames[0]].strip()
            if not ticker:
                continue
            vals = {}
            for field in FIELDS:
                cell = row.get(field, "")
                cell = cell.strip() if cell else ""
                vals[field] = float(cell) if cell else None
            raw[ticker] = vals
    return raw


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python import_manual_export.py path\\to\\export.csv")
        sys.exit(1)

    csv_path = Path(sys.argv[1])
    if not csv_path.exists():
        print(f"  ERROR: File not found: {csv_path}")
        sys.exit(1)

    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] Importing {csv_path.name}...")

    raw = parse_csv(csv_path)
    print(f"  OK: Parsed {len(raw)} securities")

    watchlist_cfg = load_watchlist()
    payload = build_payload(raw, watchlist_cfg)
    payload["source"] = "Bloomberg (manual export)"

    OUTPUT_FILE.write_text(json.dumps(payload, indent=2))
    print(f"  OK: Wrote {OUTPUT_FILE}")
    print(f"  OK: Timestamp: {payload['fetched_at']}")
    print(f"[{datetime.now():%H:%M:%S}] Done.")
