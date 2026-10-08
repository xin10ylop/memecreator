#!/usr/bin/env python3
"""Tables from the creator simulation (out/creator_sim_<tag>.json) joined to the feature table (template flag, actor
classes). Walk-forward: the configuration and the schedule are chosen on the DESIGN day and then read, untouched, on
every later day.

    python3 src/creator_sim_report.py sep27 sep28 oct01 oct06   (first tag = design day) -> out/creator_sim.txt
"""
import sys, os, json, gzip, math, random, collections, statistics as st
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = []
def P(s=""):
    print(s); OUT.append(s)
def q(v, a):
    v = sorted(v); return v[int(a * (len(v) - 1))] if v else float("nan")
def mean(v):
    return st.mean(v) if v else float("nan")
def ci_mean(v, B=300):
    if len(v) < 5:
        return (float("nan"), float("nan"))
    rnd = random.Random(7); bs = sorted(st.mean(rnd.choices(v, k=len(v))) for _ in range(B))
    return bs[int(0.025 * B)], bs[int(0.975 * B)]

COHORTS = ["<0.003", "0.003-0.01", "0.01-0.025", "0.025-0.05", "0.05-0.1", "0.1-0.25", "0.25-0.5", "0.5-1", ">=1"]
CREATE_STRESS = 0.01   # ETH of creation gas in the stress case (Sep 1-2 congestion level) instead of 0.001


def load(tag):
    d = json.load(open(os.path.join(HERE, "out", f"creator_sim_{tag}.json")))
    f = json.load(gzip.open(os.path.join(HERE, "data", f"features_{tag}.json.gz"), "rt"))["rows"]
    F = {r["curve"]: r for r in f}
    rows = []
    for r in d["rows"]:
        fr = F.get(r["curve"])
        if not fr:
            continue
        r["template"] = fr.get("template", False); r["template_prior"] = fr.get("template_prior", False); r["first_timer"] = fr["prior_today"] == 0 and fr["prior_week"] == 0
        # clean = first launch from the wallet, no named exempt wallets, sent by the creator, and not a configuration
        # already launched >= 10 times earlier that day by >= 3 addresses (hindsight-free); the outcome-based template
        # flag is reported as a sensitivity only
        r["clean"] = r["first_timer"] and r["named_n"] == 0 and not r["helper"] and not r["template_prior"]
        r["clean_outcome_flag"] = r["first_timer"] and r["named_n"] == 0 and not r["helper"] and not r["template"]
        r["gen_n_6h"] = fr["gen_n_6h"]; r["out_eth_5m"] = fr["out_eth_5m"]; r["peak_mult"] = fr["peak_mult"]
        rows.append(r)
    return rows, d["eth_usd"]


def summarize(rows, sched, px, key="pnl_cons", stress=False):
    v = []
    for r in rows:
        s = r["sched"][sched]
        if s is None:
            continue
        x = s[key] - (CREATE_STRESS - 0.001 if stress else 0.0)
        v.append(x)
    if not v:
        return None
    lo, hi = ci_mean(v)
    stake = mean([r["creator_buy"] for r in rows])
    return {"n": len(v), "mean": mean(v), "lo": lo, "hi": hi, "median": st.median(v), "p10": q(v, .1), "p90": q(v, .9), "pos": sum(1 for x in v if x > 0) / len(v),
            "stake": stake, "roi": mean(v) / stake if stake else float("nan"), "sum": sum(v), "usd_mean": mean(v) * px, "usd_median": st.median(v) * px,
            "sold": mean([r["sched"][sched]["sold_share"] for r in rows if r["sched"][sched]]),
            "tax": mean([r["sched"][sched]["tax_income"] for r in rows if r["sched"][sched]])}


def fmt(s, px):
    if not s:
        return "n=0"
    return (f"n={s['n']:4d} | mean {s['mean']:+.4f} ETH [{s['lo']:+.4f},{s['hi']:+.4f}] (${s['usd_mean']:+7.2f}) | median {s['median']:+.4f} (${s['usd_median']:+6.2f}) | p10 {s['p10']:+.4f} p90 {s['p90']:+.4f} | "
            f">0 {100*s['pos']:3.0f}% | ROI on buy {100*s['roi']:+6.1f}% | sold {100*s['sold']:3.0f}% | tax {s['tax']:.4f}")


def main():
    tags = sys.argv[1:] or ["sep27", "sep28", "oct06"]
    days = [(t,) + load(t) for t in tags]
    design = tags[0]
    scheds = list(days[0][1][0]["sched"].keys())
    P(f"Creator inventory simulation on the exact curve. Design day {design}; later days are read untouched. Costs: launch fee 0.0005 ETH, creation gas 0.001 ETH, 0.00002 ETH per sell; the creator tax on outside volume (6 h) is income; unsold inventory at zero (pnl_cons).")
    for t, rows, px in days:
        P(f"  {t}: {len(rows)} ETH launches with a launch-block buy; first-timers {sum(1 for r in rows if r['first_timer'])}; clean {sum(1 for r in rows if r['clean'])}; ETH/USD {px}")
    # 1. the actual creators, by cohort (exact, no counterfactual)
    P("\n== 1. What the actual creators made (their real exits, exact): clean cohort by launch-block buy ==")
    for t, rows, px in days:
        P(f"  {t}")
        for c in COHORTS:
            v = [r for r in rows if r["clean"] and r["cohort"] == c]
            if len(v) < 8:
                continue
            a = [r["actual"]["pnl_cons"] for r in v]; lo, hi = ci_mean(a)
            sold = [r for r in v if r["actual"]["first_sell_t"] is not None]
            am = [r["actual"]["pnl_marked"] for r in v]; xb = mean([r["actual"]["extra_buys"] for r in v])
            P(f"    buy {c:>10s}: n={len(v):4d} | proxy exits {100*sum(1 for r in v if r.get('proxy_sells'))/len(v):3.0f}% | pnl (unsold=0) mean {mean(a):+.4f} ETH (${mean(a)*px:+7.2f}) median {st.median(a):+.4f} | pnl (unsold marked) mean {mean(am):+.4f} [{ci_mean(am)[0]:+.4f},{ci_mean(am)[1]:+.4f}] (${mean(am)*px:+7.2f}) median {st.median(am):+.4f} >0 {100*sum(1 for x in am if x>0)/len(am):3.0f}% | ROI(marked) {100*mean(am)/mean([r['creator_buy'] for r in v]):+6.1f}% | sold in 6 h {100*len(sold)/len(v):3.0f}%, median first sell {q([r['actual']['first_sell_t'] for r in sold], .5) if sold else float('nan'):5.0f} s | extra buys by the creator side mean {xb:.4f} | tax mean {mean([r['actual']['tax_income'] for r in v]):.4f}")
    # 2. schedule grid on the design day, clean cohort, per cohort
    P(f"\n== 2. Schedule grid on the design day ({design}), clean cohort: mean P&L per launch (ETH) with unsold at zero; rows = schedule, columns = creator buy cohort ==")
    rows0 = days[0][1]; px0 = days[0][2]
    hdr = f"  {'schedule':28s}" + "".join(f"{c:>12s}" for c in COHORTS); P(hdr)
    P("  " + "n:".ljust(28) + "".join(f"{sum(1 for r in rows0 if r['clean'] and r['cohort']==c):12d}" for c in COHORTS))
    best = {}
    for s in scheds:
        line = f"  {s:28s}"
        for c in COHORTS:
            v = [r for r in rows0 if r["clean"] and r["cohort"] == c]
            S = summarize(v, s, px0) if len(v) >= 8 else None
            line += f"{S['mean']:+12.4f}" if S else f"{'-':>12s}"
            if S and (c not in best or S["mean"] > best[c][1]):
                best[c] = (s, S["mean"])
        P(line)
    P("\n  ROI on the launch buy (mean P&L / mean buy), same grid:")
    for s in scheds:
        line = f"  {s:28s}"
        for c in COHORTS:
            v = [r for r in rows0 if r["clean"] and r["cohort"] == c]
            S = summarize(v, s, px0) if len(v) >= 8 else None
            line += f"{100*S['roi']:+11.1f}%" if S else f"{'-':>12s}"
        P(line)
    P("\n  best schedule per cohort on the design day: " + ", ".join(f"{c}: {best[c][0]} ({best[c][1]:+.4f})" for c in COHORTS if c in best))
    # 3. walk-forward: design-day choices read on the later days
    P("\n== 3. Walk-forward: the design day's best schedule per cohort, read on every day (clean cohort) ==")
    for c in COHORTS:
        if c not in best:
            continue
        s = best[c][0]
        P(f"  cohort {c}, schedule {s}:")
        for t, rows, px in days:
            v = [r for r in rows if r["clean"] and r["cohort"] == c]
            S = summarize(v, s, px) if len(v) >= 8 else None
            P(f"    {t}: " + fmt(S, px))
    # 4. fixed, simple schedules across days (no selection at all), the whole clean cohort and the 0.025-0.25 band
    P("\n== 4. Fixed schedules with no selection, every day: clean cohort, creator buy 0.025-0.25 ETH ==")
    for s in ("all_at_15s", "all_at_30s", "all_at_60s", "all_at_300s", "tp1.5_else_5m", "tp2.0_else_5m", "tp1.5_else_6h", "flow0.5_else_5m", "flow0.5_else_6h", "ladder_1.5_2_3_else_1h", "hold_6h"):
        P(f"  {s}")
        for t, rows, px in days:
            v = [r for r in rows if r["clean"] and 0.025 <= r["creator_buy"] < 0.25]
            P(f"    {t}: " + fmt(summarize(v, s, px), px))
    # 5. stress: creation gas at the congestion level
    P("\n== 5. Stress: creation gas 0.01 ETH instead of 0.001 (Sep 1-2 congestion level), clean cohort 0.025-0.25 ETH, all_at_30s and tp1.5_else_5m ==")
    for s in ("all_at_30s", "tp1.5_else_5m"):
        for t, rows, px in days:
            v = [r for r in rows if r["clean"] and 0.025 <= r["creator_buy"] < 0.25]
            P(f"    {s} {t}: " + fmt(summarize(v, s, px, stress=True), px))
    # 6. marked value instead of zero for unsold inventory
    P("\n== 6. Unsold inventory marked at the last curve price less 3% instead of zero (pnl_marked), clean 0.025-0.25 ETH ==")
    for s in ("all_at_30s", "tp1.5_else_5m", "flow0.5_else_6h", "hold_6h"):
        for t, rows, px in days:
            v = [r for r in rows if r["clean"] and 0.025 <= r["creator_buy"] < 0.25]
            P(f"    {s} {t}: " + fmt(summarize(v, s, px, key="pnl_marked"), px))
    # 7. who is on the other side: outside ETH by buyer class before the creator's first sell (all_at_30s), clean 0.025-0.25
    P("\n== 7. Who the creator sells to: outside ETH (net into the curve) by buyer class before the creator's first sell, all_at_30s, clean 0.025-0.25 ETH ==")
    for t, rows, px in days:
        tot = collections.Counter(); n = 0
        for r in rows:
            if r["clean"] and 0.025 <= r["creator_buy"] < 0.25 and r["sched"]["all_at_30s"] and r["sched"]["all_at_30s"].get("eth_before_sell"):
                tot.update(r["sched"]["all_at_30s"]["eth_before_sell"]); n += 1
        T = sum(tot.values())
        P(f"  {t}: n={n}, total {T:.2f} ETH: " + ", ".join(f"{k} {100*v/T:.0f}%" for k, v in tot.most_common()))
    # 8. the all-first-timers view (templates included) for comparison, 0.025-0.25, all_at_30s; and the outcome-based template flag
    P("\n== 8. Same schedule on all first-timers (templates and named wallets included), 0.025-0.25 ETH; and the clean cohort under the outcome-based template flag instead of the hindsight-free one ==")
    for t, rows, px in days:
        v = [r for r in rows if r["first_timer"] and 0.025 <= r["creator_buy"] < 0.25]
        P(f"    all first-timers  all_at_30s {t}: " + fmt(summarize(v, "all_at_30s", px), px))
        v = [r for r in rows if r["clean_outcome_flag"] and 0.025 <= r["creator_buy"] < 0.25]
        P(f"    outcome-flag clean all_at_30s {t}: " + fmt(summarize(v, "all_at_30s", px), px))
        for c in ("0.25-0.5", "0.5-1"):
            v1 = [r for r in rows if r["clean"] and r["cohort"] == c]; v2 = [r for r in rows if r["clean_outcome_flag"] and r["cohort"] == c]
            if len(v1) >= 5:
                P(f"    cohort {c} {t}: hindsight-free clean n={len(v1)} mean {summarize(v1, 'all_at_30s', px)['mean']:+.4f} | outcome-flag clean n={len(v2)} mean {summarize(v2, 'all_at_30s', px)['mean'] if len(v2)>=5 else float('nan'):+.4f}")
    # 9. the tail: share of the clean cohort's total P&L from the top 5% of launches
    P("\n== 9. Concentration: share of the schedule's total positive P&L from the top 5% of launches (clean 0.025-0.25, all_at_30s / tp1.5_else_5m) ==")
    for s in ("all_at_30s", "tp1.5_else_5m"):
        for t, rows, px in days:
            v = sorted([r["sched"][s]["pnl_cons"] for r in rows if r["clean"] and 0.025 <= r["creator_buy"] < 0.25 and r["sched"][s]], reverse=True)
            if v:
                top = sum(v[: max(1, len(v) // 20)]); pos = sum(x for x in v if x > 0)
                P(f"    {s} {t}: top 5% of {len(v)} launches = {100*top/pos if pos else float('nan'):.0f}% of positive P&L; sum {sum(v):+.3f} ETH; launches with P&L > +0.05 ETH: {sum(1 for x in v if x > 0.05)}")
    # 10. demand response: later outside buys scaled after the creator's first sell
    P("\n== 10. Demand response bound: outside buys arriving after the creator's first sell scaled by 1.0 (base), 0.5, 0.0; clean 0.025-0.25 ETH; mean P&L ETH (unsold at zero) ==")
    P("  (values: scale 1.0 / 0.5 / 0.25 / 0.0; the independent audit's event study of real creator dumps puts the outside volume in the following hour at 0.09-0.49 of matched controls, central 0.2-0.35, so 0.25-0.5 is the realistic band)")
    for s in ("all_at_5s", "all_at_30s", "all_at_60s", "all_at_300s", "tp1.5_else_5m", "flow0.5_else_6h", "hold_6h"):
        line = f"  {s:18s}"
        for t, rows, px in days:
            v = [r for r in rows if r["clean"] and 0.025 <= r["creator_buy"] < 0.25]
            vals = []
            for suf in ("", "@d0.5", "@d0.25", "@d0.0"):
                S = summarize(v, s + suf, px); vals.append(S["mean"] if S else float("nan"))
            line += f" | {t}: {vals[0]:+.4f} / {vals[1]:+.4f} / {vals[2]:+.4f} / {vals[3]:+.4f}"
        P(line)
    P("  tax earned after the creator's exit as a share of total tax (base case), and tax excluding churn actors (>= 10 trades on the launch, flat position):")
    for s in ("all_at_30s", "tp1.5_else_5m", "hold_6h"):
        line = f"  {s:18s}"
        for t, rows, px in days:
            v = [r["sched"][s] for r in rows if r["clean"] and 0.025 <= r["creator_buy"] < 0.25 and r["sched"].get(s)]
            T = sum(x["tax_income"] for x in v); A = sum(x.get("tax_after_exit", 0.0) for x in v); C = sum(x.get("tax_ex_churn", x["tax_income"]) for x in v)
            line += f" | {t}: after-exit {100*A/T if T else float('nan'):3.0f}%, ex-churn {C/len(v):.4f} vs {T/len(v):.4f}"
        P(line)
    P("  (sale component only = mean P&L minus mean tax income minus 0.0015 ETH of fixed costs; the tax income also shrinks with the scaled flow)")
    for s in ("all_at_30s", "tp1.5_else_5m", "hold_6h"):
        line = f"  {s:18s} tax income"
        for t, rows, px in days:
            v = [r for r in rows if r["clean"] and 0.025 <= r["creator_buy"] < 0.25]
            vals = [mean([r["sched"][s + suf]["tax_income"] for r in v if r["sched"].get(s + suf)]) for suf in ("", "@d0.5", "@d0.0")]
            line += f" | {t}: {vals[0]:.4f} / {vals[1]:.4f} / {vals[2]:.4f}"
        P(line)
    # 11. capacity
    P("\n== 11. Sell capacity on the observed outside flow (creator's own later trades removed): value of the whole inventory / cost, and the share of inventory sellable at an average price >= entry, at T seconds; clean cohort, medians and shares ==")
    for c in ("0.01-0.025", "0.025-0.05", "0.05-0.1", "0.1-0.25", "0.25-0.5"):
        for t, rows, px in days:
            v = [r for r in rows if r["clean"] and r["cohort"] == c and r.get("capacity")]
            if len(v) < 8:
                continue
            line = f"  {c:>10s} {t}: n={len(v):4d}"
            for T in ("10", "30", "60", "300", "3600"):
                full = [r["capacity"][T][0] for r in v if r["capacity"][T]]; sh = [r["capacity"][T][1] for r in v if r["capacity"][T]]
                line += f" | T={T:>4s}s: value/cost med {q(full,.5):.3f} p75 {q(full,.75):.3f}, >=1 {100*sum(1 for x in full if x>=1)/len(full):3.0f}%, break-even share med {q(sh,.5):.2f} mean {mean(sh):.2f}"
            P(line)
    # 12. cohort profile from the feature table: what the bots and the follow-through look like for the clean cohort
    P("\n== 12. Cohort profile (clean cohort): bot within 3 s, any outside buy within 10 s, outside ETH by horizon (mean / median), price multiple vs the creator's entry (median) and share above entry ==")
    for t, rows, px in days:
        f = {r["curve"]: r for r in json.load(gzip.open(os.path.join(HERE, "data", f"features_{t}.json.gz"), "rt"))["rows"]}
        for c in COHORTS:
            v = [f[r["curve"]] for r in rows if r["clean"] and r["cohort"] == c and r["curve"] in f]
            if len(v) < 8:
                continue
            bot = sum(1 for r in v if r["first_bot_t"] is not None and r["first_bot_t"] <= 3) / len(v); any10 = sum(1 for r in v if r["out_n_10s"] > 0) / len(v)
            P(f"  {t} buy {c:>10s}: n={len(v):4d} | bot<=3s {100*bot:3.0f}% any<=10s {100*any10:3.0f}% | out ETH 60s {mean([r['out_eth_60s'] for r in v]):.3f}/{q([r['out_eth_60s'] for r in v],.5):.3f} 5m {mean([r['out_eth_5m'] for r in v]):.3f}/{q([r['out_eth_5m'] for r in v],.5):.3f} 6h {mean([r['out_eth_6h'] for r in v]):.3f}/{q([r['out_eth_6h'] for r in v],.5):.3f} | genuine ETH 6h {mean([r['gen_eth_6h'] for r in v]):.3f} | mult med 10s {q([r['mult_10s'] for r in v],.5):.2f} 60s {q([r['mult_60s'] for r in v],.5):.2f} 5m {q([r['mult_5m'] for r in v],.5):.2f} 1h {q([r['mult_1h'] for r in v],.5):.2f} 6h {q([r['mult_6h'] for r in v],.5):.2f} | >entry 60s {100*sum(1 for r in v if r['mult_60s']>1)/len(v):3.0f}% 5m {100*sum(1 for r in v if r['mult_5m']>1)/len(v):3.0f}% 1h {100*sum(1 for r in v if r['mult_1h']>1)/len(v):3.0f}% | peak med {q([r['peak_mult'] for r in v],.5):.2f} p90 {q([r['peak_mult'] for r in v],.9):.2f} | gen>=20 {100*sum(1 for r in v if r['gen_n_6h']>=20)/len(v):4.1f}%")
    # 13. decomposition: sale P&L (proceeds - cost) vs creator tax vs fixed costs, per cohort and schedule
    P("\n== 13. Decomposition per launch (clean cohort): sale P&L = proceeds - cost of the launch buy; tax = creator tax on outside volume; fixed costs 0.0015 ETH. Mean (median) sale P&L in ETH and as % of the buy, share of launches with a positive sale ==")
    for s in ("all_at_30s", "tp2.0_else_6h", "flow0.5_else_6h", "hold_6h", "all_at_30s@d0.5"):
        P(f"  schedule {s}")
        for c in ("0.01-0.025", "0.025-0.05", "0.05-0.1", "0.1-0.25", "0.25-0.5"):
            line = f"    buy {c:>10s}:"
            for t, rows, px in days:
                v = [r for r in rows if r["clean"] and r["cohort"] == c and r["sched"].get(s)]
                if len(v) < 8:
                    line += f" | {t}: -"; continue
                sale = [r["sched"][s]["proceeds"] - r["sched"][s]["cost"] for r in v]; tax = [r["sched"][s]["tax_income"] for r in v]; stake = mean([r["creator_buy"] for r in v])
                line += f" | {t}: n={len(v):3d} sale {mean(sale):+.4f} ({st.median(sale):+.4f}) = {100*mean(sale)/stake:+5.1f}% of buy, sale>0 {100*sum(1 for x in sale if x>0)/len(v):3.0f}%, tax {mean(tax):.4f} = {100*mean(tax)/stake:4.1f}%"
            P(line)
    # 14. day-to-day walk-forward over schedules: pick the best schedule on day d (clean 0.025-0.25), read on day d+1
    P("\n== 14. Schedule selection walk-forward (clean 0.025-0.25 ETH): the schedule with the highest mean on day d, read on day d+1, against the median schedule and the simplest one (all_at_30s) ==")
    base_scheds = [k for k in scheds if "@" not in k]
    for i in range(len(days) - 1):
        t0, rows0, px0 = days[i]; t1, rows1, px1 = days[i + 1]
        v0 = [r for r in rows0 if r["clean"] and 0.025 <= r["creator_buy"] < 0.25]; v1 = [r for r in rows1 if r["clean"] and 0.025 <= r["creator_buy"] < 0.25]
        m0 = {k: summarize(v0, k, px0)["mean"] for k in base_scheds}; m1 = {k: summarize(v1, k, px1)["mean"] for k in base_scheds}
        bestk = max(m0, key=m0.get); worstk = min(m0, key=m0.get)
        med1 = st.median(m1.values())
        P(f"  {t0} -> {t1}: best on {t0} = {bestk} ({m0[bestk]:+.4f}) reads {m1[bestk]:+.4f} on {t1}; worst on {t0} = {worstk} ({m0[worstk]:+.4f}) reads {m1[worstk]:+.4f}; median schedule on {t1} {med1:+.4f}; all_at_30s {m1['all_at_30s']:+.4f}; best on {t1} itself {max(m1, key=m1.get)} ({max(m1.values()):+.4f}); spread across schedules on {t1} {max(m1.values())-min(m1.values()):.4f}")
    # 15. batch risk: what a creator running N such launches sees (resampled from the day's clean cohort)
    P("\n== 15. Batch risk (clean 0.025-0.25 ETH, all_at_30s and tp1.5_else_5m): the sum over N launches resampled 2,000 times from the day; P(sum < 0), p10 / median / p90 of the sum in ETH; capital = N x mean buy ==")
    rnd = random.Random(11)
    for s in ("all_at_30s", "tp1.5_else_5m", "all_at_30s@d0.5"):
        for t, rows, px in days:
            v = [r["sched"][s]["pnl_cons"] for r in rows if r["clean"] and 0.025 <= r["creator_buy"] < 0.25 and r["sched"].get(s)]
            buy = mean([r["creator_buy"] for r in rows if r["clean"] and 0.025 <= r["creator_buy"] < 0.25])
            line = f"  {s:16s} {t}:"
            for N in (10, 20, 50, 100):
                sums = sorted(sum(rnd.choices(v, k=N)) for _ in range(2000))
                line += f" | N={N:3d}: P(<0) {100*sum(1 for x in sums if x < 0)/len(sums):3.0f}%, p10 {sums[200]:+.3f} med {sums[1000]:+.3f} p90 {sums[1800]:+.3f} (capital {N*buy:.1f} ETH)"
            P(line)
    # 16. the repeat penalty: the same configuration launched by a wallet that already launched that day
    P("\n== 16. Repeat launches (wallet already launched earlier that day; otherwise the same filters: no named wallets, self-sent, not a template), 0.025-0.25 ETH, all_at_30s ==")
    for t, rows, px in days:
        f = {r["curve"]: r for r in json.load(gzip.open(os.path.join(HERE, "data", f"features_{t}.json.gz"), "rt"))["rows"]}
        v = [r for r in rows if r["prior_today"] > 0 and r["named_n"] == 0 and not r["helper"] and not r["template"] and 0.025 <= r["creator_buy"] < 0.25]
        if len(v) < 8:
            continue
        fv = [f[r["curve"]] for r in v if r["curve"] in f]
        bot = sum(1 for r in fv if r["first_bot_t"] is not None and r["first_bot_t"] <= 3) / len(fv)
        P(f"  {t}: " + fmt(summarize(v, "all_at_30s", px), px) + f" | bot<=3s {100*bot:3.0f}% | out ETH 60s mean {mean([r['out_eth_60s'] for r in fv]):.3f} | by launches earlier that day: " + ", ".join(f"{lab}: n={len(g)} mean {mean([r['sched']['all_at_30s']['pnl_cons'] for r in g]):+.4f}" for lab, g in (("1-2", [r for r in v if r['prior_today'] <= 2]), ("3-9", [r for r in v if 3 <= r['prior_today'] <= 9]), ("10+", [r for r in v if r['prior_today'] >= 10])) if g))
    open(os.path.join(HERE, "out", "creator_sim.txt"), "w").write("\n".join(OUT) + "\n")


if __name__ == "__main__":
    main()
