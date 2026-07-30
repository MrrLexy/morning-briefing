#!/usr/bin/env python3
"""
Bloomberg copy-paste import — morning briefing.

Takes a raw grid copy-paste straight out of a Bloomberg monitor (BBG Anywhere /
web terminal) and produces data.json. Unlike import_manual_export.py, this does
the ticker translation for you: you paste real Bloomberg syntax ("GT10 Govt")
and it maps to the internal shorthand the briefing uses ("GT10:GOV").

Workflow:
    1. In a Bloomberg monitor, put your securities in rows and these fields
       in columns:
           PX_LAST, CHG_NET_1D, YLD_YTM_BID, OAS_SPREAD_ASK,
           DUR_ADJ_MID, RETURN_YTD, RETURN_QTD
       (Only include the ones available; missing columns are fine.)
    2. Select the grid including the header row, Ctrl+C.
    3. Paste into Notepad, save as e.g. paste.txt (tab-separated).
    4. Run: python import_bbg_paste.py paste.txt

Accepts tab- or comma-separated. First column must be the security; its header
can be anything ("Ticker", "Security", "Name", blank...). Unrecognized tickers
are reported and skipped rather than silently dropped.

The paste file is never committed — see .gitignore. Raw Bloomberg field values
must stay local per DATA_POLICY.md, same rule as data.json.
"""

import csv
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from fetch_bloomberg import FIELDS, OUTPUT_FILE, build_payload, load_watchlist

# Bloomberg yellow-key suffix -> internal shorthand suffix used by the briefing.
YELLOW_KEY_MAP = {
    "govt": "GOV",
    "index": "IND",
    "curncy": "CUR",
    "comdty": "COM",
    "equity": "US",     # briefing only tracks US-listed equities/ETFs
    "us equity": "US",
}

# Securities whose internal shorthand doesn't follow the yellow-key rule.
TICKER_OVERRIDES = {
    "USGGT10Y INDEX": "USGGT10Y:GOV",   # real-yield series, filed under :GOV internally
}

VALID_FIELDS = set(FIELDS)


def normalize_ticker(raw: str) -> str | None:
    """
    'GT10 Govt' -> 'GT10:GOV'      'SPX Index'  -> 'SPX:IND'
    'DXY Curncy' -> 'DXY:CUR'      'AGG US Equity' -> 'AGG:US'
    Already-shorthand input ('GT10:GOV') passes through untouched.
    Returns None if the format isn't recognized.
    """
    s = " ".join(raw.strip().split())
    if not s:
        return None

    # Already internal shorthand?
    if ":" in s and " " not in s:
        return s.upper()

    if s.upper() in TICKER_OVERRIDES:
        return TICKER_OVERRIDES[s.upper()]

    parts = s.split()
    if len(parts) < 2:
        return None

    # Try two-word yellow key first ("US Equity"), then one-word ("Govt").
    for n in (2, 1):
        if len(parts) > n:
            key = " ".join(parts[-n:]).lower()
            if key in YELLOW_KEY_MAP:
                base = " ".join(parts[:-n]).upper().replace(" ", "")
                return f"{base}:{YELLOW_KEY_MAP[key]}"
    return None


def parse_number(cell: str):
    """Bloomberg grids emit '1,234.56', '(12.3)', '--', 'N.A.', '4.58%'."""
    if cell is None:
        return None
    s = cell.strip()
    if not s or s in {"--", "-", "#N/A", "N.A.", "N/A", "NA", "#N/A N/A"}:
        return None
    neg = s.startswith("(") and s.endswith(")")
    if neg:
        s = s[1:-1]
    s = s.replace(",", "").replace("%", "").replace("$", "").strip()
    try:
        val = float(s)
    except ValueError:
        return None
    return -val if neg else val


def sniff_delimiter(text: str) -> str:
    first = text.splitlines()[0] if text.splitlines() else ""
    return "\t" if first.count("\t") >= first.count(",") else ","


def parse_paste(path: Path) -> tuple[dict, list, list]:
    text = path.read_text(encoding="utf-8-sig")
    delim = sniff_delimiter(text)
    reader = csv.reader(io.StringIO(text), delimiter=delim)
    rows = [r for r in reader if any(c.strip() for c in r)]
    if not rows:
        raise ValueError("File appears to be empty.")

    header = [h.strip() for h in rows[0]]
    # Map each column index -> field name, for columns we recognize.
    col_fields = {}
    unknown_cols = []
    for i, h in enumerate(header[1:], start=1):
        canon = re.sub(r"\s+", "_", h.strip()).upper()
        if canon in VALID_FIELDS:
            col_fields[i] = canon
        elif h.strip():
            unknown_cols.append(h)

    if not col_fields:
        raise ValueError(
            "No recognized field columns found. Expected one or more of: "
            + ", ".join(FIELDS)
        )

    raw = {}
    unmapped = []
    for row in rows[1:]:
        ticker = normalize_ticker(row[0]) if row else None
        if not ticker:
            if row and row[0].strip():
                unmapped.append(row[0].strip())
            continue
        vals = {f: None for f in FIELDS}
        for i, field in col_fields.items():
            if i < len(row):
                vals[field] = parse_number(row[i])
        raw[ticker] = vals

    return raw, unknown_cols, unmapped


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python import_bbg_paste.py path\\to\\paste.txt")
        sys.exit(1)

    src = Path(sys.argv[1])
    if not src.exists():
        print(f"  ERROR: File not found: {src}")
        sys.exit(1)

    print(f"[{datetime.now():%H:%M:%S}] Importing {src.name}...")

    raw, unknown_cols, unmapped = parse_paste(src)

    if unknown_cols:
        print(f"  ! Ignored unrecognized column(s): {', '.join(unknown_cols)}")
    if unmapped:
        print(f"  ! Could not map ticker(s): {', '.join(unmapped)}")
        print("    Use Bloomberg syntax ('GT10 Govt') or shorthand ('GT10:GOV').")
    if not raw:
        print("  ERROR: No securities parsed — data.json not written.")
        sys.exit(1)

    print(f"  OK: Parsed {len(raw)} securities")

    payload = build_payload(raw, load_watchlist())
    payload["source"] = "Bloomberg (manual paste)"

    OUTPUT_FILE.write_text(json.dumps(payload, indent=2))
    print(f"  OK: Wrote {OUTPUT_FILE}")
    print(f"  OK: Timestamp: {payload['fetched_at']}")
    print(f"[{datetime.now():%H:%M:%S}] Done.")
