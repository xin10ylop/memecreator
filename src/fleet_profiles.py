#!/usr/bin/env python3
"""What the automated buyers select: for the busiest bot-class actors (by ETH spent within 10 s of launches), the
configuration of the launches they buy early against the population, their speed, size, hold and realized P&L.
    python3 src/fleet_profiles.py sep27 sep28 oct01 oct06 -> out/fleet_profiles.txt
"""
import sys, os, json, gzip, collections, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pons_census as PC
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = []
def P(s=""):
    print(s); OUT.append(s)
def q(v, a):
    v = sorted(v); return v[int(a * (len(v) - 1))] if v else float("nan")
def mean(v):
    return st.mean(v) if v else float("nan")

for tag in (sys.argv[1:] or ["sep27", "sep28"]):
    src = tag if tag in PC.DAYS else os.path.join(HERE, "data", f"census_{tag}.json")
    Ls, info = PC.load_day(src)
    F = {r["curve"]: r for r in json.load(gzip.open(os.path.join(HERE, "data", f"features_{tag}.json.gz"), "rt"))["rows"]}
    acts = json.load(open(os.path.join(HERE, "data", f"actors_{tag}.json")))
    pop = [L for L in Ls if L.q_is_eth and L.creator_buy > 0]
    early = collections.defaultdict(list)       # actor -> list of (L, t, q)
    pnl = collections.defaultdict(lambda: [0.0, 0.0])
    for L in pop:
        for r in L.rows[1:]:
            w = r["who"]
            if w in L.side:
                continue
            if r["k"] == "B":
                pnl[w][0] += r["q"]
                if r["t"] <= 10:
                    early[w].append((L, r["t"], r["q"]))
            else:
                pnl[w][1] += r["q"]
    def profile(Ls_):
        n = len(Ls_)
        return {"n": n, "buy_med": q([L.creator_buy for L in Ls_], .5), "buy>=0.05": sum(1 for L in Ls_ if L.creator_buy >= 0.05) / n, "tax0": sum(1 for L in Ls_ if L.tax_bps == 0) / n,
                "tax>=300": sum(1 for L in Ls_ if L.tax_bps >= 300) / n, "named>=3": sum(1 for L in Ls_ if len(L.named) >= 3) / n, "web": sum(1 for L in Ls_ if L.feat.get("website")) / n,
                "img": sum(1 for L in Ls_ if L.feat.get("image")) / n, "first_timer": sum(1 for L in Ls_ if L.prior_today == 0 and L.prior_week == 0) / n,
                "template": sum(1 for L in Ls_ if F.get(L.curve, {}).get("template")) / n, "share_med": q([L.creator_tokens / PC.Y0 for L in Ls_], .5)}
    base = profile(pop)
    P(f"\n== {tag}: population of {len(pop)} ETH launches: creator buy median {base['buy_med']:.3f} ETH, >=0.05 {100*base['buy>=0.05']:.0f}%, tax0 {100*base['tax0']:.0f}%, tax>=3% {100*base['tax>=300']:.0f}%, named>=3 {100*base['named>=3']:.0f}%, website {100*base['web']:.0f}%, image {100*base['img']:.0f}%, first-timer {100*base['first_timer']:.0f}%, template {100*base['template']:.0f}% ==")
    ranked = sorted([(w, sum(x[2] for x in early[w])) for w in early if acts.get(w, {}).get("class", "").startswith("bot") or acts.get(w, {}).get("class") == "multi"], key=lambda kv: -kv[1])[:25]
    P(f"  {'actor':14s} {'class':16s} {'early n':>7s} {'ETH<=10s':>8s} {'t med':>6s} {'size med':>8s} {'hold':>6s} | buy med | >=0.05 | tax0 | tax>=3% | named>=3 | web | img | 1st-timer | template | realized P&L (ETH, unsold=0) | lift of follow (others' ETH 10s-5m) vs same-buy-bucket launches without it")
    for w, e in ranked:
        Ls_ = [x[0] for x in early[w]]; pr = profile(Ls_); a = acts[w]
        # follow-through lift
        def bucket(L):
            cb = L.creator_buy
            return 0 if cb < 0.01 else 1 if cb < 0.025 else 2 if cb < 0.05 else 3 if cb < 0.1 else 4 if cb < 0.25 else 5
        withs = {L.curve for L in Ls_}
        fw = [F[L.curve]["out_eth_5m"] - F[L.curve]["out_eth_10s"] for L in Ls_ if L.curve in F]
        byb = collections.defaultdict(list)
        for L in pop:
            if L.curve in F and L.curve not in withs:
                byb[bucket(L)].append(F[L.curve]["out_eth_5m"] - F[L.curve]["out_eth_10s"])
        ctrl = []
        for L in Ls_:
            ctrl.extend(byb[bucket(L)])
        lift = mean(fw) / mean(ctrl) if ctrl and mean(ctrl) > 0 else float("nan")
        P(f"  {w[:14]} {a['class']:16s} {pr['n']:7d} {e:8.2f} {q([x[1] for x in early[w]], .5):6.1f} {q([x[2] for x in early[w]], .5):8.4f} {a['med_hold'] if a['med_hold'] is not None else float('nan'):6.0f} | {pr['buy_med']:7.3f} | {100*pr['buy>=0.05']:5.0f}% | {100*pr['tax0']:3.0f}% | {100*pr['tax>=300']:6.0f}% | {100*pr['named>=3']:7.0f}% | {100*pr['web']:3.0f}% | {100*pr['img']:3.0f}% | {100*pr['first_timer']:8.0f}% | {100*pr['template']:7.0f}% | {pnl[w][1]-pnl[w][0]:+8.3f} ({100*(pnl[w][1]-pnl[w][0])/pnl[w][0] if pnl[w][0] else 0:+5.0f}%) | {lift:4.2f} ({mean(fw):.3f} vs {mean(ctrl):.3f})")
os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
open(os.path.join(HERE, "out", "fleet_profiles.txt"), "w").write("\n".join(OUT) + "\n")
