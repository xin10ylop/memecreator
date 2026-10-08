#!/usr/bin/env python3
"""The strategy as framed, tested walk-forward: on the DESIGN day choose the launch configuration that maximizes
(a) early bot participation and (b) mean creator P&L, among configurations an ordinary creator controls (creator buy
cohort, creator tax, website link, image, hour of day). Then read both designed configurations, untouched, on every
later day against the plain clean cohort. Also the single-factor view on the design day and on every later day.

    python3 src/design_eval.py sep21 sep27 sep28 oct01 oct03 oct06 -> out/design_eval.txt
"""
import sys, os, json, gzip, random, statistics as st, itertools, collections
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = []
def P(s=""):
    print(s); OUT.append(s)
def mean(v):
    return st.mean(v) if v else float("nan")
def q(v, a):
    v = sorted(v); return v[int(a * (len(v) - 1))] if v else float("nan")
def ci(v, B=300):
    if len(v) < 5:
        return (float("nan"), float("nan"))
    r = random.Random(3); bs = sorted(st.mean(r.choices(v, k=len(v))) for _ in range(B)); return bs[int(.025 * B)], bs[int(.975 * B)]

SCHED = "all_at_30s"
FACTORS = {
    "buy": [("0.025-0.05", lambda r: 0.025 <= r["creator_buy"] < 0.05), ("0.05-0.1", lambda r: 0.05 <= r["creator_buy"] < 0.1), ("0.1-0.25", lambda r: 0.1 <= r["creator_buy"] < 0.25)],
    "tax": [("0", lambda r: r["tax_bps"] == 0), ("100", lambda r: r["tax_bps"] == 100), ("150-250", lambda r: 150 <= r["tax_bps"] <= 250), ("300", lambda r: r["tax_bps"] == 300)],
    "website": [("yes", lambda r: r["meta_website"]), ("no", lambda r: not r["meta_website"])],
    "image": [("yes", lambda r: r["meta_image"]), ("no", lambda r: not r["meta_image"])],
    "hour": [("00-06", lambda r: r["hour"] < 6), ("06-12", lambda r: 6 <= r["hour"] < 12), ("12-18", lambda r: 12 <= r["hour"] < 18), ("18-24", lambda r: r["hour"] >= 18)],
}


def load(tag):
    sim = json.load(open(os.path.join(HERE, "out", f"creator_sim_{tag}.json")))
    feats = {r["curve"]: r for r in json.load(gzip.open(os.path.join(HERE, "data", f"features_{tag}.json.gz"), "rt"))["rows"]}
    rows = []
    for r in sim["rows"]:
        f = feats.get(r["curve"])
        if not f or not r["sched"].get(SCHED):
            continue
        clean = f["prior_today"] == 0 and f["prior_week"] == 0 and f["named_n"] == 0 and not f["helper_created"] and not f.get("template_prior")
        if not clean or not (0.025 <= r["creator_buy"] < 0.25):
            continue
        rows.append({**f, "pnl": r["sched"][SCHED]["pnl_cons"], "pnl_hold": r["sched"]["hold_6h"]["pnl_cons"], "pnl_d05": r["sched"][SCHED + "@d0.5"]["pnl_cons"], "pnl_d025": r["sched"][SCHED + "@d0.25"]["pnl_cons"],
                     "sale": r["sched"][SCHED]["proceeds"] - r["sched"][SCHED]["cost"], "tax": r["sched"][SCHED]["tax_income"], "creator_buy": r["creator_buy"]})
    return rows, sim["eth_usd"]


def bot3(r):
    return r["first_bot_t"] is not None and r["first_bot_t"] <= 3


def desc(v, px):
    if not v:
        return "n=0"
    p = [r["pnl"] for r in v]; lo, hi = ci(p); buy = mean([r["creator_buy"] for r in v])
    return (f"n={len(v):4d} | bot<=3s {100*mean([1.0 if bot3(r) else 0.0 for r in v]):3.0f}% | out ETH 60s {mean([r['out_eth_60s'] for r in v]):.3f} | gen>=20 {100*mean([1.0 if r['gen_n_6h']>=20 else 0.0 for r in v]):4.1f}% | "
            f"P&L mean {mean(p):+.4f} [{lo:+.4f},{hi:+.4f}] (${mean(p)*px:+6.1f}) med {st.median(p):+.4f} >0 {100*sum(1 for x in p if x>0)/len(p):3.0f}% | ROI {100*mean(p)/buy:+5.1f}% | sale {mean([r['sale'] for r in v]):+.4f} ({100*mean([r['sale'] for r in v])/buy:+4.1f}%) tax {mean([r['tax'] for r in v]):.4f} | d0.5 {mean([r['pnl_d05'] for r in v]):+.4f} d0.25 {mean([r['pnl_d025'] for r in v]):+.4f} | hold6h {mean([r['pnl_hold'] for r in v]):+.4f}")


def main():
    tags = sys.argv[1:] or ["sep21", "sep27", "sep28", "oct01", "oct03", "oct06"]
    days = [(t,) + load(t) for t in tags]
    design, drows, dpx = days[0]
    P(f"Design day {design}: clean cohort, creator buy 0.025-0.25 ETH, schedule {SCHED}. Single-factor cells (n >= 40):")
    best_pnl, best_bot = {}, {}
    for fac, levels in FACTORS.items():
        for lab, f in levels:
            v = [r for r in drows if f(r)]
            if len(v) < 40:
                continue
            P(f"  {fac:8s} {lab:>10s}: " + desc(v, dpx))
            m = mean([r["pnl"] for r in v]); b = mean([1.0 if bot3(r) else 0.0 for r in v])
            if fac not in best_pnl or m > best_pnl[fac][1]:
                best_pnl[fac] = (lab, m)
            if fac not in best_bot or b > best_bot[fac][1]:
                best_bot[fac] = (lab, b)
    lv = {fac: dict(levels) for fac, levels in FACTORS.items()}
    def cfg_filter(choice, facs):
        return lambda r: all(lv[fac][choice[fac][0]](r) for fac in facs)
    designs = {
        "A: max bot participation (buy, tax, website, image)": cfg_filter(best_bot, ["buy", "tax", "website", "image"]),
        "B: max mean P&L (buy, tax, website, image)": cfg_filter(best_pnl, ["buy", "tax", "website", "image"]),
        "C: max bot participation, buy + tax only": cfg_filter(best_bot, ["buy", "tax"]),
        "D: max mean P&L, buy + tax only": cfg_filter(best_pnl, ["buy", "tax"]),
        "base: whole clean cohort 0.025-0.25": lambda r: True,
    }
    P(f"\nChosen on {design}: max-bot levels {{{', '.join(f'{k}: {v[0]} ({100*v[1]:.0f}%)' for k, v in best_bot.items())}}}; max-P&L levels {{{', '.join(f'{k}: {v[0]} ({v[1]:+.4f})' for k, v in best_pnl.items())}}}")
    P("\nWalk-forward: each designed configuration read on every day (the design day first, in-sample):")
    for name, f in designs.items():
        P(f"\n  {name}")
        for t, rows, px in days:
            v = [r for r in rows if f(r)]
            P(f"    {t}: " + desc(v, px))
    # does more bot participation at the configuration level translate into more P&L? cells across all days
    P("\nAcross all days and all single-factor cells (n >= 40): correlation between a cell's bot<=3s share and its mean P&L, and its sale component")
    xs, ys, zs = [], [], []
    for t, rows, px in days:
        for fac, levels in FACTORS.items():
            for lab, f in levels:
                v = [r for r in rows if f(r)]
                if len(v) >= 40:
                    xs.append(mean([1.0 if bot3(r) else 0.0 for r in v])); ys.append(mean([r["pnl"] for r in v]) / mean([r["creator_buy"] for r in v])); zs.append(mean([r["sale"] for r in v]) / mean([r["creator_buy"] for r in v]))
    import numpy as np
    P(f"  cells {len(xs)}: corr(bot share, ROI) = {np.corrcoef(xs, ys)[0,1]:+.2f}; corr(bot share, sale ROI) = {np.corrcoef(xs, zs)[0,1]:+.2f}")
    # launch-level: within the clean cohort, launches that did get a bot within 3 s vs not
    P("\nLaunch level, per day: launches a bot bought within 3 s vs launches no bot bought within 3 s (clean 0.025-0.25):")
    for t, rows, px in days:
        a = [r for r in rows if bot3(r)]; b = [r for r in rows if not bot3(r)]
        P(f"  {t}: bot within 3 s   " + desc(a, px))
        P(f"  {t}: no bot in 3 s    " + desc(b, px))
    open(os.path.join(HERE, "out", "design_eval.txt"), "w").write("\n".join(OUT) + "\n")


if __name__ == "__main__":
    main()
