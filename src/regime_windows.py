#!/usr/bin/env python3
"""Regime check across the five earlier windows (Aug 12, Aug 20, Aug 27, Sep 2, Sep 3; 12:00-18:00 UTC) from the
per-launch creator-seat summaries in fomo-memebot (data/derived/creator_seat_<day>.json, produced by creator_seat.py):
for each launch q0 (creator's launch-block buy, quote units), tk0, n trades, fees (0.7% of curve volume, the then
fee split), P&L of the creator's layer at several exits (LIFO curve exits, 1% fee), whether/when the creator sold,
and the creator's launch count that day. Quote asset from launch_quotes_<day>.json. Only ETH-quoted launches are
priced here (ETH/USD per window as the original scripts used).

The question for this study: across the fee cycle, how does the size of the creator's own buy relate to (a) whether
anybody else buys, (b) the fee earned, (c) the sale proceeds at fixed exits. Output: out/regime_windows.txt
"""
import json, os, sys, statistics as st, collections

DATA = os.environ.get("FOMO_DATA", "/home/user/xin10ylop/fomo-memebot/data/derived")
DAYS = ["2026-08-12", "2026-08-20", "2026-08-27", "2026-09-02", "2026-09-03"]
ETH_USD = {"2026-08-12": 4600.0, "2026-08-20": 4300.0, "2026-08-27": 4500.0, "2026-09-02": 4400.0, "2026-09-03": 2445.0}
# note: the original scripts priced ETH at 2445 for Sep 3; the earlier windows' ETH price is not recorded in the repo's
# derived files, so the dollar columns below use ETH units and only Sep 3 is given in USD.
BUCKETS = [(0, 0.002, "<0.002"), (0.002, 0.01, "0.002-0.01"), (0.01, 0.03, "0.01-0.03"), (0.03, 0.1, "0.03-0.1"), (0.1, 0.3, "0.1-0.3"), (0.3, 1.0, "0.3-1"), (1.0, 1e9, ">=1")]


def q(v, a):
    v = sorted(v); return v[int(a * (len(v) - 1))] if v else float("nan")


def main():
    out = []
    P = lambda s="": (print(s), out.append(s))
    P("Creator's launch-block buy (ETH) vs outcomes, five windows, ETH-quoted launches, one-off creators (1 launch that day) and serial separately.")
    P("Columns: n | share with any other trade | share creator sold in window | fees/stake (0.7% of volume) | sale P&L/stake as actually timed | at 10 min | at best | TP1.5x hit | median (fees+actual)/stake | mean ETH net per launch (fees+actual)")
    for day in DAYS:
        p = os.path.join(DATA, f"creator_seat_{day}.json")
        if not os.path.exists(p):
            continue
        rows = json.load(open(p)); quotes = json.load(open(os.path.join(DATA, f"launch_quotes_{day}.json")))
        rows = [r for r in rows if quotes.get(r["curve"], "native") == "native" and r["q0"] > 0]
        P(f"\n== {day} 12:00-18:00 UTC: {len(rows)} ETH-quoted launches with a launch-block buy ==")
        for label, sel in (("one-off", lambda r: r["serial"] == 1), ("2-9/day", lambda r: 2 <= r["serial"] <= 9), ("serial 10+", lambda r: r["serial"] >= 10)):
            g = [r for r in rows if sel(r)]
            P(f"  {label} (n={len(g)})")
            for lo, hi, name in BUCKETS:
                v = [r for r in g if lo <= r["q0"] < hi]
                if len(v) < 10:
                    continue
                stake = sum(r["q0"] for r in v)
                any_other = sum(1 for r in v if r["n"] > 1) / len(v)
                sold = sum(1 for r in v if r["sold"]) / len(v)
                fees = sum(r["fees"] for r in v) / stake
                act = sum(r["pnl_realized"] for r in v) / stake
                p10 = sum(r["pnl_10m"] for r in v) / stake
                best = sum(r["pnl_best"] for r in v) / stake
                tp = sum(1 for r in v if r["hit_tp15"]) / len(v)
                med = st.median((r["fees"] + r["pnl_realized"]) / r["q0"] for r in v)
                net = st.mean(r["fees"] + r["pnl_realized"] for r in v)
                P(f"    buy {name:>10s}: n={len(v):5d} | other trade {100*any_other:4.0f}% | sold {100*sold:4.0f}% | fees {100*fees:+6.1f}% | actual {100*act:+6.1f}% | 10m {100*p10:+6.1f}% | best {100*best:+6.1f}% | TP1.5 {100*tp:3.0f}% | median {100*med:+5.0f}% | net {net:+.4f} ETH")
    # the nobody-bought share by bucket, all creators pooled, per window (the simplest 'did bots come' measure available here)
    P("\nShare of launches where nobody else traded, by creator buy bucket (all creators, ETH-quoted):")
    hdr = f"{'window':>12s}" + "".join(f"{b[2]:>12s}" for b in BUCKETS); P(hdr)
    for day in DAYS:
        p = os.path.join(DATA, f"creator_seat_{day}.json")
        if not os.path.exists(p):
            continue
        rows = json.load(open(p)); quotes = json.load(open(os.path.join(DATA, f"launch_quotes_{day}.json")))
        rows = [r for r in rows if quotes.get(r["curve"], "native") == "native" and r["q0"] > 0]
        line = f"{day:>12s}"
        for lo, hi, name in BUCKETS:
            v = [r for r in rows if lo <= r["q0"] < hi]
            line += f"{(100*sum(1 for r in v if r['n'] <= 1)/len(v)):10.0f}%" + f"({len(v):4d})" if v else f"{'-':>12s}"
        P(line)
    os.makedirs("out", exist_ok=True)
    open(os.path.join("out", "regime_windows.txt"), "w").write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
