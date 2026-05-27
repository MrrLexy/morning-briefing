#!/usr/bin/env python3
"""
Bloomberg data bridge — morning briefing.

Fetches key fixed income market data from a locally running Bloomberg Terminal,
writes data.json to the briefing repo, and pushes to GitHub so the briefing
generator on any machine can read live values.

Requirements:
    pip install blpapi
    Bloomberg Terminal must be running when this script executes.

Windows Task Scheduler setup (run once on work machine):
    schtasks /create /tn "Bloomberg Briefing Feed" /tr "python C:\\Users\\...\\briefing\\fetch_bloomberg.py" /sc daily /st 06:30 /d MON,TUE,WED,THU,FRI

Repo path below — adjust if the morning-briefing repo is cloned elsewhere on
this machine.
"""

import blpapi
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ── CONFIG ────────────────────────────────────────────────────────────────────
REPO_PATH      = Path(r"C:\Users\a96ve\briefing")   # ← adjust to repo path on work machine
OUTPUT_FILE    = REPO_PATH / "data.json"
WATCHLIST_FILE = REPO_PATH / "watchlist.json"
BBG_HOST       = "localhost"
BBG_PORT       = 8194
# ─────────────────────────────────────────────────────────────────────────────

SECURITIES = [
    # Benchmark indices
    "LBUSTRUU:IND",      # Bloomberg US Agg (LEH_AGG)
    "LUACTRUU:IND",      # Bloomberg US Corp (LEH_CORP)
    "JBCDCOMP:IND",      # JPMorgan CEMBI Broad Div. (JPM_CEMBI)
    "BAMLH0A1HYBB:IND",  # ICE BofA BB US HY (MLGHYBBH)
    # Credit spread series
    "BAMLC0A0CM:IND",    # IG OAS
    "BAMLH0A0HYM2:IND",  # HY OAS (broad)
    "BAMLH0A3HYC:IND",   # CCC OAS
    # Volatility
    "MOVE:IND",          # MOVE index (rate vol)
    # Treasuries
    "GT2:GOV",           # 2Y
    "GT5:GOV",           # 5Y
    "GT10:GOV",          # 10Y
    "GT30:GOV",          # 30Y
    "USGGT10Y:GOV",      # 10Y TIPS real yield
    "USGGBE10:IND",      # 10Y breakeven inflation
    # Cross-asset
    "SPX:IND",           # S&P 500
    "DXY:CUR",           # US Dollar Index
    "CL1:COM",           # WTI crude front-month
    "USOSFR:IND",        # SOFR
]

FIELDS = [
    "PX_LAST",
    "CHG_NET_1D",
    "CHG_PCT_1D",
    "YLD_YTM_BID",
    "OAS_SPREAD_ASK",
    "DUR_ADJ_MID",
    "RETURN_YTD",
    "RETURN_QTD",
]


def load_watchlist() -> list:
    """Return watchlist ticker dicts from watchlist.json, or [] if missing."""
    if not WATCHLIST_FILE.exists():
        return []
    with open(WATCHLIST_FILE) as f:
        cfg = json.load(f)
    return [t for t in cfg.get("tickers", []) if t.get("ticker")]


def bbg_fetch(securities: list, fields: list) -> dict:
    opts = blpapi.SessionOptions()
    opts.setServerHost(BBG_HOST)
    opts.setServerPort(BBG_PORT)

    session = blpapi.Session(opts)
    if not session.start():
        raise RuntimeError(
            "Cannot connect to Bloomberg Terminal — is Terminal running?"
        )
    if not session.openService("//blp/refdata"):
        raise RuntimeError("Failed to open Bloomberg refdata service.")

    svc = session.getService("//blp/refdata")
    req = svc.createRequest("ReferenceDataRequest")
    for s in securities:
        req.append("securities", s)
    for f in fields:
        req.append("fields", f)
    session.sendRequest(req)

    raw = {}
    while True:
        event = session.nextEvent(500)
        for msg in event:
            if msg.hasElement("securityData"):
                arr = msg.getElement("securityData")
                for i in range(arr.numValues()):
                    sec = arr.getValue(i)
                    ticker = sec.getElementAsString("security")
                    fd = sec.getElement("fieldData")
                    vals = {}
                    for field in fields:
                        try:
                            vals[field] = (
                                fd.getElementAsFloat(field)
                                if fd.hasElement(field)
                                else None
                            )
                        except Exception:
                            vals[field] = None
                    raw[ticker] = vals
        if event.eventType() == blpapi.Event.RESPONSE:
            break

    session.stop()
    return raw


def g(raw: dict, ticker: str, field: str, scale: float = 1.0, digits: int = 2):
    """Safe getter — returns rounded float or None."""
    val = raw.get(ticker, {}).get(field)
    return round(val * scale, digits) if val is not None else None


def build_watchlist_data(raw: dict, watchlist_cfg: list) -> list:
    """Build watchlist entries with live Bloomberg data."""
    out = []
    for item in watchlist_cfg:
        ticker = item["ticker"]
        out.append({
            "ticker":   ticker,
            "label":    item.get("label", ticker),
            "px_last":  g(raw, ticker, "PX_LAST",    digits=2),
            "chg_pct":  g(raw, ticker, "CHG_PCT_1D", digits=2),
            "yield":    g(raw, ticker, "YLD_YTM_BID", digits=3),
            "oas":      g(raw, ticker, "OAS_SPREAD_ASK", digits=1),
            "ytd_ret":  g(raw, ticker, "RETURN_YTD",  digits=2),
        })
    return out


def build_payload(raw: dict, watchlist_cfg: list = None) -> dict:
    watchlist = build_watchlist_data(raw, watchlist_cfg or [])
    now = datetime.now()
    return {
        "fetched_at": now.isoformat(timespec="seconds"),
        "data_date":  now.strftime("%Y-%m-%d"),
        "source":     "Bloomberg Terminal",

        "benchmarks": {
            "leh_agg": {
                "label":      "Bloomberg US Aggregate",
                "ticker":     "LBUSTRUU",
                "level":      g(raw, "LBUSTRUU:IND", "PX_LAST"),
                "yield_pct":  g(raw, "LBUSTRUU:IND", "YLD_YTM_BID",  digits=3),
                "oas_bps":    g(raw, "LBUSTRUU:IND", "OAS_SPREAD_ASK", digits=1),
                "duration":   g(raw, "LBUSTRUU:IND", "DUR_ADJ_MID",  digits=2),
                "return_qtd": g(raw, "LBUSTRUU:IND", "RETURN_QTD",   digits=2),
                "return_ytd": g(raw, "LBUSTRUU:IND", "RETURN_YTD",   digits=2),
            },
            "leh_corp": {
                "label":      "Bloomberg US Corporate",
                "ticker":     "LUACTRUU",
                "level":      g(raw, "LUACTRUU:IND", "PX_LAST"),
                "yield_pct":  g(raw, "LUACTRUU:IND", "YLD_YTM_BID",  digits=3),
                "oas_bps":    g(raw, "LUACTRUU:IND", "OAS_SPREAD_ASK", digits=1),
                "duration":   g(raw, "LUACTRUU:IND", "DUR_ADJ_MID",  digits=2),
                "return_qtd": g(raw, "LUACTRUU:IND", "RETURN_QTD",   digits=2),
                "return_ytd": g(raw, "LUACTRUU:IND", "RETURN_YTD",   digits=2),
            },
            "jpm_cembi": {
                "label":      "JPMorgan CEMBI Broad Div.",
                "ticker":     "JBCDCOMP",
                "level":      g(raw, "JBCDCOMP:IND", "PX_LAST"),
                "yield_pct":  g(raw, "JBCDCOMP:IND", "YLD_YTM_BID",  digits=3),
                "spread_bps": g(raw, "JBCDCOMP:IND", "OAS_SPREAD_ASK", digits=1),
                "duration":   g(raw, "JBCDCOMP:IND", "DUR_ADJ_MID",  digits=2),
                "return_qtd": g(raw, "JBCDCOMP:IND", "RETURN_QTD",   digits=2),
                "return_ytd": g(raw, "JBCDCOMP:IND", "RETURN_YTD",   digits=2),
            },
            "mlghybbh": {
                "label":      "ICE BofA BB US High Yield",
                "ticker":     "BAMLH0A1HYBB",
                "level":      g(raw, "BAMLH0A1HYBB:IND", "PX_LAST"),
                "yield_pct":  g(raw, "BAMLH0A1HYBB:IND", "YLD_YTM_BID",   digits=3),
                "oas_bps":    g(raw, "BAMLH0A1HYBB:IND", "OAS_SPREAD_ASK", digits=1),
                "duration":   g(raw, "BAMLH0A1HYBB:IND", "DUR_ADJ_MID",   digits=2),
                "return_qtd": g(raw, "BAMLH0A1HYBB:IND", "RETURN_QTD",    digits=2),
                "return_ytd": g(raw, "BAMLH0A1HYBB:IND", "RETURN_YTD",    digits=2),
            },
        },

        "credit": {
            "ig_oas":  {
                "spread_bps": g(raw, "BAMLC0A0CM:IND",   "PX_LAST",    digits=1),
                "chg_1d_bps": g(raw, "BAMLC0A0CM:IND",   "CHG_NET_1D", scale=100, digits=1),
            },
            "hy_oas":  {
                "spread_bps": g(raw, "BAMLH0A0HYM2:IND", "PX_LAST",    digits=1),
                "chg_1d_bps": g(raw, "BAMLH0A0HYM2:IND", "CHG_NET_1D", scale=100, digits=1),
            },
            "hy_bb":   {
                "spread_bps": g(raw, "BAMLH0A1HYBB:IND", "PX_LAST",    digits=1),
                "chg_1d_bps": g(raw, "BAMLH0A1HYBB:IND", "CHG_NET_1D", scale=100, digits=1),
            },
            "ccc_oas": {
                "spread_bps": g(raw, "BAMLH0A3HYC:IND",  "PX_LAST",    digits=1),
                "chg_1d_bps": g(raw, "BAMLH0A3HYC:IND",  "CHG_NET_1D", scale=100, digits=1),
            },
        },

        "rates": {
            "us2y":         {"yield_pct": g(raw, "GT2:GOV",       "PX_LAST", digits=3), "chg_1d_bps": g(raw, "GT2:GOV",       "CHG_NET_1D", scale=100, digits=1)},
            "us5y":         {"yield_pct": g(raw, "GT5:GOV",       "PX_LAST", digits=3), "chg_1d_bps": g(raw, "GT5:GOV",       "CHG_NET_1D", scale=100, digits=1)},
            "us10y":        {"yield_pct": g(raw, "GT10:GOV",      "PX_LAST", digits=3), "chg_1d_bps": g(raw, "GT10:GOV",      "CHG_NET_1D", scale=100, digits=1)},
            "us30y":        {"yield_pct": g(raw, "GT30:GOV",      "PX_LAST", digits=3), "chg_1d_bps": g(raw, "GT30:GOV",      "CHG_NET_1D", scale=100, digits=1)},
            "tips10y":      {"yield_pct": g(raw, "USGGT10Y:GOV",  "PX_LAST", digits=3)},
            "breakeven10y": {"rate_pct":  g(raw, "USGGBE10:IND",  "PX_LAST", digits=3)},
            "sofr":         {"rate_pct":  g(raw, "USOSFR:IND",    "PX_LAST", digits=3)},
        },

        "volatility": {
            "move": {
                "level":  g(raw, "MOVE:IND", "PX_LAST",    digits=1),
                "chg_1d": g(raw, "MOVE:IND", "CHG_NET_1D", digits=2),
            },
        },

        "market": {
            "spx": {"level": g(raw, "SPX:IND", "PX_LAST", digits=0), "chg_pct": g(raw, "SPX:IND", "CHG_PCT_1D", digits=2)},
            "dxy": {"level": g(raw, "DXY:CUR", "PX_LAST", digits=2), "chg_pct": g(raw, "DXY:CUR", "CHG_PCT_1D", digits=2)},
            "wti": {"level": g(raw, "CL1:COM", "PX_LAST", digits=2), "chg_pct": g(raw, "CL1:COM", "CHG_PCT_1D", digits=2)},
        },

        "watchlist": watchlist,
    }


def git_push(timestamp: str):
    label = datetime.fromisoformat(timestamp).strftime("%Y-%m-%d %H:%M")
    cmds = [
        ["git", "-C", str(REPO_PATH), "pull",   "origin", "main", "--rebase"],
        ["git", "-C", str(REPO_PATH), "add",    "data.json"],
        ["git", "-C", str(REPO_PATH), "commit", "-m", f"data: Bloomberg fetch {label}"],
        ["git", "-C", str(REPO_PATH), "push",   "origin", "main"],
    ]
    for cmd in cmds:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            if "nothing to commit" in (r.stdout + r.stderr):
                print("  (no changes to commit)")
                return
            raise RuntimeError(f"Git failed: {' '.join(cmd[2:])}\n{r.stderr.strip()}")
        print(f"  ✓ {' '.join(cmd[2:])}")


if __name__ == "__main__":
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] Starting Bloomberg fetch...")

    try:
        watchlist_cfg = load_watchlist()
        wl_tickers    = [t["ticker"] for t in watchlist_cfg]
        all_securities = SECURITIES + [t for t in wl_tickers if t not in SECURITIES]

        raw = bbg_fetch(all_securities, FIELDS)
        print(f"  ✓ Received data for {len(raw)} securities ({len(wl_tickers)} watchlist)")

        payload = build_payload(raw, watchlist_cfg)
        OUTPUT_FILE.write_text(json.dumps(payload, indent=2))
        print(f"  ✓ Wrote {OUTPUT_FILE}")
        print(f"  ✓ Timestamp: {payload['fetched_at']}")

        git_push(payload["fetched_at"])
        print(f"[{datetime.now():%H:%M:%S}] Done.")

    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
