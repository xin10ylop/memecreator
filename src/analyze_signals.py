#!/usr/bin/env python3
"""What makes automated buyers buy a fresh Pons V2 launch, and what follows. Reads data/features_<day>.json.gz.

Sections: (A) base rates; (B) one-way tables of every launch parameter known at creation against bot participation,
early outside money, genuine demand, follow-through and price path, day by day (a pattern has to hold on every day);
(C) multivariate logistic models fit on one day and scored on the others (AUC, lift); (D) the initial rush against
the follow-through: how much early buying, from how many wallets, precedes continued buying; (E) fleets: which
automated buyers' early presence is followed by more outside money, measured on one day and checked on the next.

    python3 src/analyze_signals.py sep27 sep28 [oct06 ...]      -> out/signals.txt
"""
import sys, os, json, gzip, math, collections, statistics as st
import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = []


def P(s=""):
    print(s); OUT.append(s)


def load(tag):
    d = json.load(gzip.open(os.path.join(HERE, "data", f"features_{tag}.json.gz"), "rt"))
    rows = d["rows"]
    for r in rows:
        r["day"] = tag
    acts = json.load(open(os.path.join(HERE, "data", f"actors_{tag}.json")))
    return rows, acts, d["info"]


def q(v, a):
    v = sorted(v); return v[int(a * (len(v) - 1))] if v else float("nan")


def mean(v):
    return st.mean(v) if v else float("nan")


def share(rows, f):
    return (sum(1 for r in rows if f(r)) / len(rows)) if rows else float("nan")


BUY_B = [(0, 0.003, "<0.003"), (0.003, 0.01, "0.003-0.01"), (0.01, 0.025, "0.01-0.025"), (0.025, 0.05, "0.025-0.05"), (0.05, 0.1, "0.05-0.1"),
         (0.1, 0.25, "0.1-0.25"), (0.25, 0.5, "0.25-0.5"), (0.5, 1.0, "0.5-1"), (1.0, 1e9, ">=1")]


def base(rows):
    """the main population: standard path, ETH-quoted"""
    return [r for r in rows if r["quote"] == "ETH"]


def first_timer(r):
    return r["prior_today"] == 0 and r["prior_week"] == 0


def clean(r):
    """an ordinary creator as far as the chain shows: first launch from the wallet, no named exempt wallets, the
    creation sent by the creator itself, and not part of a scripted template (see build_features.flag_templates)"""
    return first_timer(r) and r["named_n"] == 0 and not r["helper_created"] and not r.get("template_prior", False)


def early_bot(r):
    return r["first_bot_t"] is not None and r["first_bot_t"] <= 3.0


def metrics(v):
    """one line of outcome metrics for a group"""
    if not v:
        return "n=0"
    return (f"n={len(v):5d} | bot<=3s {100*share(v, early_bot):4.0f}% | any out<=10s {100*share(v, lambda r: r['out_n_10s']>0):4.0f}% | "
            f">=3 buyers<=60s {100*share(v, lambda r: r['out_n_60s']>=3):4.0f}% | ETH in 60s mean {mean([r['out_eth_60s'] for r in v]):6.3f} med {q([r['out_eth_60s'] for r in v], .5):6.3f} | "
            f"ETH in 5m mean {mean([r['out_eth_5m'] for r in v]):6.3f} | gen ETH 6h mean {mean([r['gen_eth_6h'] for r in v]):6.3f} med {q([r['gen_eth_6h'] for r in v], .5):6.4f} | "
            f"gen>=20 {100*share(v, lambda r: r['gen_n_6h']>=20):4.1f}% | grad {100*share(v, lambda r: r['graduated']):4.1f}% | "
            f"peak med {q([r['peak_mult'] for r in v], .5):5.2f} | >entry@60s {100*share(v, lambda r: r['mult_60s']>1.0):3.0f}% @5m {100*share(v, lambda r: r['mult_5m']>1.0):3.0f}% @1h {100*share(v, lambda r: r['mult_1h']>1.0):3.0f}% | "
            f"tax ETH mean {mean([r['creator_tax'] for r in v]):7.4f}")


def table(name, days, buckets, key, pop=None):
    P(f"\n-- {name} --")
    for lo, hi, lab in buckets if isinstance(buckets[0], tuple) else buckets:
        for tag, rows in days:
            v = [r for r in rows if (pop is None or pop(r)) and lo <= key(r) < hi]
            if len(v) >= 8:
                P(f"  {lab:>14s} {tag}: " + metrics(v))


def flag_table(name, days, key, pop=None):
    P(f"\n-- {name} --")
    for val, lab in ((True, "yes"), (False, "no")):
        for tag, rows in days:
            v = [r for r in rows if (pop is None or pop(r)) and bool(key(r)) == val]
            if len(v) >= 8:
                P(f"  {lab:>14s} {tag}: " + metrics(v))


# ----- logistic regression (IRLS, ridge) -----
def design(rows):
    X = []; names = None
    for r in rows:
        cb = max(r["creator_buy"], 1e-5)
        f = collections.OrderedDict()
        f["log_buy"] = math.log10(cb)
        f["buy>=0.05"] = 1.0 if cb >= 0.05 else 0.0
        f["buy>=0.25"] = 1.0 if cb >= 0.25 else 0.0
        f["buy>=1"] = 1.0 if cb >= 1.0 else 0.0
        f["tax0"] = 1.0 if r["tax_bps"] == 0 else 0.0
        f["tax>=300"] = 1.0 if r["tax_bps"] >= 300 else 0.0
        f["named1-2"] = 1.0 if 1 <= r["named_n"] <= 2 else 0.0
        f["named3-9"] = 1.0 if 3 <= r["named_n"] <= 9 else 0.0
        f["named10+"] = 1.0 if r["named_n"] >= 10 else 0.0
        f["website"] = 1.0 if r["meta_website"] else 0.0
        f["telegram"] = 1.0 if r["meta_telegram"] else 0.0
        f["x"] = 1.0 if r["meta_x"] else 0.0
        f["x_post"] = 1.0 if r["meta_x_post"] else 0.0
        f["desc"] = 1.0 if r["meta_desc_len"] > 0 else 0.0
        f["image"] = 1.0 if r["meta_image"] else 0.0
        f["copycat"] = 1.0 if r["meta_copycat"] else 0.0
        f["prior_today>0"] = 1.0 if r["prior_today"] > 0 else 0.0
        f["prior_week>0"] = 1.0 if r["prior_week"] > 0 else 0.0
        f["helper"] = 1.0 if r["helper_created"] else 0.0
        f["h00-06"] = 1.0 if r["hour"] < 6 else 0.0
        f["h06-12"] = 1.0 if 6 <= r["hour"] < 12 else 0.0
        f["h18-24"] = 1.0 if r["hour"] >= 18 else 0.0
        if names is None:
            names = list(f.keys())
        X.append([1.0] + list(f.values()))
    return np.array(X), ["const"] + names


def logit_fit(X, y, l2=1.0, iters=60):
    w = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-X @ w)); W = p * (1 - p) + 1e-9
        g = X.T @ (y - p) - l2 * np.r_[0, w[1:]]
        H = (X * W[:, None]).T @ X + l2 * np.diag(np.r_[0, np.ones(X.shape[1] - 1)])
        step = np.linalg.solve(H, g); w += step
        if np.max(np.abs(step)) < 1e-7:
            break
    return w


def auc(y, s):
    order = np.argsort(s); r = np.empty(len(s)); r[order] = np.arange(1, len(s) + 1)
    # average ranks for ties
    s_sorted = s[order]; i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and s_sorted[j + 1] == s_sorted[i]:
            j += 1
        if j > i:
            r[order[i:j + 1]] = (i + 1 + j + 1) / 2
        i = j + 1
    n1 = y.sum(); n0 = len(y) - n1
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0) if n1 and n0 else float("nan")


def model_section(days, targets, pop):
    P("\n== (C) multivariate logistic models: fit on one day, scored on the others (first-time creators, ETH) ==")
    for tname, tf in targets:
        P(f"\n  target: {tname}")
        for i, (ftag, frows) in enumerate(days):
            fr = [r for r in frows if pop(r)]
            X, names = design(fr); y = np.array([1.0 if tf(r) else 0.0 for r in fr])
            if y.sum() < 10 or y.sum() > len(y) - 10:
                P(f"    fit {ftag}: too few positives ({int(y.sum())})"); continue
            w = logit_fit(X, y)
            line = f"    fit {ftag} (n={len(fr)}, base {100*y.mean():.1f}%, in-sample AUC {auc(y, X @ w):.3f})"
            for ttag, trows in days:
                if ttag == ftag:
                    continue
                tr = [r for r in trows if pop(r)]
                Xt, _ = design(tr); yt = np.array([1.0 if tf(r) else 0.0 for r in tr]); s = Xt @ w
                p = 1 / (1 + np.exp(-s)); top = np.argsort(-p)[: max(1, len(p) // 10)]
                line += f" | test {ttag}: AUC {auc(yt, s):.3f}, base {100*yt.mean():.1f}%, top-decile hit {100*yt[top].mean():.1f}%"
            P(line)
            coef = sorted(zip(names[1:], w[1:]), key=lambda kv: -abs(kv[1]))[:8]
            P("      largest coefficients: " + ", ".join(f"{n} {c:+.2f}" for n, c in coef))


def bot_size_section(days, acts_by_day):
    P("\n== (D2) what the early automated buyers actually spend (ETH launches, buys within 3 s by bot-class actors) ==")
    for tag, rows in days:
        acts = acts_by_day[tag]
        for cls in ("bot_sniper", "bot_early_holder", "bot_late", "multi", "router", "other"):
            v = [a for a in acts.values() if a["class"] == cls]
            if not v:
                continue
            sizes = [a["med_size"] for a in v if a["med_size"] > 0]
            P(f"  {tag} {cls:16s}: actors {len(v):5d} | launches/actor med {q([a['launches'] for a in v], .5):5.0f} | med buy size med {q(sizes, .5):.4f} ETH p90 {q(sizes, .9):.4f} | ETH in total {sum(a['eth_in'] for a in v):8.1f} out {sum(a['eth_out'] for a in v):8.1f} | net {sum(a['eth_out']-a['eth_in'] for a in v):+8.1f} ETH (unsold at zero)")


def rush_section(days):
    P("\n== (D) the initial rush against the follow-through (first-time creators, ETH) ==")
    P("  rush = outside buying in the creation second and the two after it (the snipe-tax seconds); follow = outside buying 3 s-5 min from any wallet; late = 5 min-6 h.")
    for tag, rows in days:
        v = [r for r in rows if first_timer(r)]
        rush = [r["rush_eth0"] + r["rush_eth1"] + r["rush_eth2"] for r in v]; foll = [r["out_eth_5m"] - r["out_eth_3s"] for r in v]
        late = [r["out_eth_6h"] - r["out_eth_5m"] for r in v]
        nz = [(a, b, c) for a, b, c in zip(rush, foll, late)]
        P(f"\n  {tag}: n={len(v)}; mean rush {mean(rush):.4f} ETH, follow {mean(foll):.4f}, late {mean(late):.4f}; launches with any rush {100*share(v, lambda r: r['out_n_3s']>0):.0f}%, any follow {100*sum(1 for b in foll if b>0.001)/len(v):.0f}%, follow >= 0.1 ETH {100*sum(1 for b in foll if b>=0.1)/len(v):.1f}%")
        lr = np.log10(np.array(rush) + 1e-4); lf = np.log10(np.array(foll) + 1e-4)
        P(f"    rank corr(rush, follow) = {np.corrcoef(np.argsort(np.argsort(lr)), np.argsort(np.argsort(lf)))[0,1]:+.3f}; corr(log rush, log follow) = {np.corrcoef(lr, lf)[0,1]:+.3f}")
        P("    by number of distinct outside buyers in the first 10 s and ETH in the first 10 s -> share with >= 0.1 ETH more from 10 s to 5 min, mean follow ETH, share with >= 20 genuine buyers in 6 h, median peak multiple:")
        for nlo, nhi, nlab in ((0, 1, "0"), (1, 2, "1"), (2, 3, "2"), (3, 5, "3-4"), (5, 10, "5-9"), (10, 1000, "10+")):
            for elo, ehi, elab in ((0, 0.01, "<0.01"), (0.01, 0.05, "0.01-0.05"), (0.05, 0.2, "0.05-0.2"), (0.2, 1.0, "0.2-1"), (1.0, 1e9, ">=1")):
                g = [r for r in v if nlo <= r["out_n_10s"] < nhi and elo <= r["out_eth_10s"] < ehi]
                if len(g) >= 10:
                    f2 = [r["out_eth_5m"] - r["out_eth_10s"] for r in g]
                    P(f"      buyers {nlab:>4s}, ETH {elab:>9s}: n={len(g):5d} | follow>=0.1 {100*sum(1 for x in f2 if x>=0.1)/len(g):4.0f}% | follow mean {mean(f2):6.3f} | gen>=20 {100*share(g, lambda r: r['gen_n_6h']>=20):4.1f}% | peak med {q([r['peak_mult'] for r in g], .5):4.2f} | >entry@5m {100*share(g, lambda r: r['mult_5m']>1):3.0f}%")
        P("    who the early buyers are (first 10 s): bots only vs humans/routers present -> follow-through:")
        for lab, f in (("no outside buy", lambda r: r["out_n_10s"] == 0), ("bots only", lambda r: r["out_n_10s"] > 0 and r["gen_n_10s"] == 0), ("non-bots present", lambda r: r["gen_n_10s"] > 0)):
            g = [r for r in v if f(r)]
            if g:
                f2 = [r["out_eth_5m"] - r["out_eth_10s"] for r in g]
                P(f"      {lab:>18s}: n={len(g):5d} | follow>=0.1 {100*sum(1 for x in f2 if x>=0.1)/len(g):4.0f}% | follow mean {mean(f2):6.3f} | gen>=20 {100*share(g, lambda r: r['gen_n_6h']>=20):4.1f}% | peak med {q([r['peak_mult'] for r in g], .5):4.2f}")


def fleet_section(days, acts_by_day):
    P("\n== (E) fleets: which automated buyers' early presence is followed by more outside money ==")
    P("  For each actor with >= 20 launches on the day: launches it bought within 10 s; the ETH other wallets put in during the next 5 min (from 10 s), against launches in the same creator-buy bucket where it did not buy. Lift = ratio of means. Fit day first, then the same actors on the test day.")
    def bucket(r):
        cb = r["creator_buy"]
        for lo, hi, lab in BUY_B:
            if lo <= cb < hi:
                return lab
        return "?"
    # per-launch early buyers need the tape: rebuild from census via pons_census (fast enough)
    sys.path.insert(0, os.path.join(HERE, "src")); import pons_census as PC
    early = {}
    for tag, rows in days:
        src = tag if tag in PC.DAYS else os.path.join(HERE, "data", f"census_{tag}.json")
        Ls, _ = PC.load_day(src)
        e = {}
        for L in Ls:
            if not L.q_is_eth:
                continue
            e[L.curve] = {r["who"] for r in L.rows if r["k"] == "B" and r["who"] not in L.side and r["t"] <= 10.0}
        early[tag] = e
    results = {}
    for tag, rows in days:
        acts = acts_by_day[tag]; v = [r for r in rows if first_timer(r)]
        bybucket = collections.defaultdict(list)
        for r in v:
            bybucket[bucket(r)].append(r)
        res = {}
        for a, info in acts.items():
            if info["launches"] < 20 or info["class"] == "router":
                continue
            withs = [r for r in v if a in early[tag].get(r["curve"], ())]
            if len(withs) < 10:
                continue
            fw = [r["out_eth_5m"] - r["out_eth_10s"] for r in withs]
            # matched: same bucket mix
            ctrl = []
            for r in withs:
                ctrl.extend([x["out_eth_5m"] - x["out_eth_10s"] for x in bybucket[bucket(r)] if a not in early[tag].get(x["curve"], ())])
            lift = (mean(fw) / mean(ctrl)) if ctrl and mean(ctrl) > 0 else float("nan")
            res[a] = {"class": info["class"], "n": len(withs), "follow_mean": mean(fw), "ctrl_mean": mean(ctrl), "lift": lift, "gen20": share(withs, lambda r: r["gen_n_6h"] >= 20),
                      "med_first": info["med_first_t"], "med_size": info["med_size"], "med_hold": info["med_hold"], "buy_med": q([r["creator_buy"] for r in withs], .5), "launches": info["launches"]}
        results[tag] = res
    fit_tag = days[0][0]
    P(f"\n  ranked by lift on {fit_tag} (actors buying >= 10 first-time launches within 10 s):")
    P(f"  {'actor':14s} {'class':16s} {'launches':>8s} {'early n':>7s} {'first_t':>7s} {'size':>7s} {'hold':>6s} {'cr.buy med':>10s} | " + " | ".join(f"{t}: lift (follow with/without) gen20%" for t, _ in days))
    ranked = sorted(results[fit_tag].items(), key=lambda kv: -kv[1]["lift"] if not math.isnan(kv[1]["lift"]) else 0)
    for a, r0 in ranked[:30]:
        line = f"  {a[:14]} {r0['class']:16s} {r0['launches']:8d} {r0['n']:7d} {r0['med_first'] if r0['med_first'] is not None else float('nan'):7.1f} {r0['med_size']:7.4f} {r0['med_hold'] if r0['med_hold'] is not None else float('nan'):6.0f} {r0['buy_med']:10.3f} | "
        for t, _ in days:
            rr = results[t].get(a)
            line += (f"{t}: {rr['lift']:4.2f} ({rr['follow_mean']:.3f}/{rr['ctrl_mean']:.3f}) {100*rr['gen20']:3.0f}%" if rr else f"{t}: -") + " | "
        P(line)
    # stability of the ranking between days
    common = [a for a in results[fit_tag] if all(a in results[t] for t, _ in days[1:])]
    if len(common) >= 5 and len(days) > 1:
        for t, _ in days[1:]:
            x = [results[fit_tag][a]["lift"] for a in common]; y = [results[t][a]["lift"] for a in common]
            rx = np.argsort(np.argsort(x)); ry = np.argsort(np.argsort(y))
            P(f"\n  {len(common)} actors present on both {fit_tag} and {t}: rank correlation of their lifts {np.corrcoef(rx, ry)[0,1]:+.2f}")
    # class-level view
    P("\n  by actor class (early presence within 10 s) on each day: launches, follow mean with vs without, gen20 share:")
    for tag, rows in days:
        acts = acts_by_day[tag]; v = [r for r in rows if first_timer(r)]
        for cls in ("bot_sniper", "bot_early_holder", "bot_late", "multi", "router"):
            members = {a for a, i in acts.items() if i["class"] == cls}
            withs = [r for r in v if early[tag].get(r["curve"], set()) & members]
            without = [r for r in v if not (early[tag].get(r["curve"], set()) & members)]
            if withs:
                P(f"    {tag} {cls:16s}: with n={len(withs):5d} follow {mean([r['out_eth_5m']-r['out_eth_10s'] for r in withs]):.3f} gen20 {100*share(withs, lambda r: r['gen_n_6h']>=20):4.1f}% | without n={len(without):5d} follow {mean([r['out_eth_5m']-r['out_eth_10s'] for r in without]):.3f} gen20 {100*share(without, lambda r: r['gen_n_6h']>=20):4.1f}%")
    return results


def main():
    tags = sys.argv[1:] or ["sep27", "sep28"]
    days = []; acts_by_day = {}
    for t in tags:
        rows, acts, info = load(t); days.append((t, base(rows))); acts_by_day[t] = acts
        P(f"{t}: {len(rows)} standard launches, {len(base(rows))} ETH-quoted; first-time creators (no launch earlier that day or in the prior week on record) {sum(1 for r in base(rows) if first_timer(r))}; ETH/USD {info['eth_usd']}")
    P("\n== (A) base rates, ETH-quoted launches ==")
    for tag, rows in days:
        P(f"  {tag} all          : " + metrics(rows))
        P(f"  {tag} first-timers : " + metrics([r for r in rows if first_timer(r)]))
        P(f"  {tag} serial today : " + metrics([r for r in rows if r['prior_today'] > 0]))
    for tag, rows in days:
        P(f"  {tag} clean cohort : " + metrics([r for r in rows if clean(r)]) + f" | templates excluded {sum(1 for r in rows if first_timer(r) and r.get('template'))}")
    P("\n== (B0) the clean cohort (first launch from the wallet, no named wallets, self-sent, not a scripted template) ==")
    table("creator's launch-block buy (ETH), clean", days, BUY_B, lambda r: r["creator_buy"], clean)
    table("creator tax (bps), clean, buy 0.02-0.5 ETH", days, [(0, 1, "0"), (1, 150, "100"), (150, 300, "150-250"), (300, 400, "300"), (400, 2001, "400+")], lambda r: r["tax_bps"], lambda r: clean(r) and 0.02 <= r["creator_buy"] < 0.5)
    table("socials, clean, buy 0.02-0.5 ETH", days, [(0, 1, "0"), (1, 2, "1"), (2, 10, "2+")], lambda r: r["meta_n_socials"], lambda r: clean(r) and 0.02 <= r["creator_buy"] < 0.5)
    flag_table("website, clean, buy 0.02-0.5 ETH", days, lambda r: r["meta_website"], lambda r: clean(r) and 0.02 <= r["creator_buy"] < 0.5)
    flag_table("telegram, clean, buy 0.02-0.5 ETH", days, lambda r: r["meta_telegram"], lambda r: clean(r) and 0.02 <= r["creator_buy"] < 0.5)
    flag_table("image, clean, buy 0.02-0.5 ETH", days, lambda r: r["meta_image"], lambda r: clean(r) and 0.02 <= r["creator_buy"] < 0.5)
    table("hour (UTC), clean, buy 0.02-0.5 ETH", days, [(0, 6, "00-06"), (6, 12, "06-12"), (12, 18, "12-18"), (18, 24, "18-24")], lambda r: r["hour"], lambda r: clean(r) and 0.02 <= r["creator_buy"] < 0.5)
    P("\n== (B) one-way tables, first-time creators unless stated ==")
    ft = first_timer
    table("creator's launch-block buy (ETH)", days, BUY_B, lambda r: r["creator_buy"], ft)
    table("creator's launch-block buy (ETH), serial creators (prior launch today)", days, BUY_B, lambda r: r["creator_buy"], lambda r: r["prior_today"] > 0)
    table("creator's share of supply", days, [(0, 0.005, "<0.5%"), (0.005, 0.01, "0.5-1%"), (0.01, 0.02, "1-2%"), (0.02, 0.05, "2-5%"), (0.05, 0.1, "5-10%"), (0.1, 0.2, "10-20%"), (0.2, 0.4, "20-40%"), (0.4, 1.0, ">=40%")], lambda r: r["creator_share"], ft)
    table("creator tax (bps)", days, [(0, 1, "0"), (1, 150, "100"), (150, 300, "150-250"), (300, 400, "300"), (400, 2001, "400+")], lambda r: r["tax_bps"], ft)
    table("named exempt wallets", days, [(0, 1, "0"), (1, 3, "1-2"), (3, 10, "3-9"), (10, 1000, "10+")], lambda r: r["named_n"], ft)
    table("named exempt wallets, creator buy 0.05-0.5 ETH only", days, [(0, 1, "0"), (1, 3, "1-2"), (3, 10, "3-9"), (10, 1000, "10+")], lambda r: r["named_n"], lambda r: ft(r) and 0.05 <= r["creator_buy"] < 0.5)
    for k, lab in (("meta_website", "website"), ("meta_telegram", "telegram"), ("meta_x", "X profile"), ("meta_x_post", "links an X post"), ("meta_image", "image"), ("meta_copycat", "copycat name/symbol seen earlier that day")):
        flag_table(lab, days, lambda r, k=k: r[k], ft)
    flag_table("has a description", days, lambda r: r["meta_desc_len"] > 0, ft)
    table("social links count", days, [(0, 1, "0"), (1, 2, "1"), (2, 10, "2+")], lambda r: r["meta_n_socials"], ft)
    flag_table("creation sent by a helper contract (sender != creator)", days, lambda r: r["helper_created"], ft)
    table("hour of day (UTC)", days, [(0, 6, "00-06"), (6, 12, "06-12"), (12, 18, "12-18"), (18, 24, "18-24")], lambda r: r["hour"], ft)
    table("creator's launches earlier that day (all creators)", days, [(0, 1, "0"), (1, 3, "1-2"), (3, 10, "3-9"), (10, 10000, "10+")], lambda r: r["prior_today"])
    table("creator's launches in the prior week (none today)", days, [(0, 1, "0"), (1, 3, "1-2"), (3, 10, "3-9"), (10, 10000, "10+")], lambda r: r["prior_week"], lambda r: r["prior_today"] == 0)
    table("presentation within creator buy 0.1-1 ETH: socials count", days, [(0, 1, "0"), (1, 2, "1"), (2, 10, "2+")], lambda r: r["meta_n_socials"], lambda r: ft(r) and 0.1 <= r["creator_buy"] < 1.0)
    table("tax within creator buy 0.1-1 ETH", days, [(0, 1, "0"), (1, 150, "100"), (150, 300, "150-250"), (300, 2001, "300+")], lambda r: r["tax_bps"], lambda r: ft(r) and 0.1 <= r["creator_buy"] < 1.0)
    # USDG for contrast
    P("\n-- quote asset (all first-timers incl. USDG; USDG amounts in USDG) --")
    for tag in tags:
        rows, _, _ = load(tag)
        for qn in ("ETH", "USDG"):
            v = [r for r in rows if r["quote"] == qn and first_timer(r)]
            if len(v) >= 8:
                P(f"  {qn:>6s} {tag}: n={len(v):5d} | bot<=3s {100*share(v, early_bot):4.0f}% | any out<=10s {100*share(v, lambda r: r['out_n_10s']>0):4.0f}% | >=3 buyers<=60s {100*share(v, lambda r: r['out_n_60s']>=3):4.0f}% | gen>=20 {100*share(v, lambda r: r['gen_n_6h']>=20):4.1f}% | out $ in 60s mean {mean([r['out_eth_60s']*r['px_usd'] for r in v]):7.1f} | out $ 6h mean {mean([r['out_eth_6h']*r['px_usd'] for r in v]):8.1f}")
    targets = [("a bot buys within 3 s", early_bot), (">= 3 outside buyers within 60 s", lambda r: r["out_n_60s"] >= 3), ("outside ETH in first 60 s >= 0.1", lambda r: r["out_eth_60s"] >= 0.1),
               ("outside ETH 10 s-5 min >= 0.2 (follow-through)", lambda r: r["out_eth_5m"] - r["out_eth_10s"] >= 0.2), (">= 20 genuine buyers in 6 h", lambda r: r["gen_n_6h"] >= 20), ("graduates", lambda r: r["graduated"]),
               ("price above creator entry at 5 min", lambda r: r["mult_5m"] > 1.0)]
    model_section(days, targets, first_timer)
    P("\n  (same models on the clean cohort)")
    model_section(days, targets, clean)
    rush_section(days)
    bot_size_section(days, acts_by_day)
    fleet_section(days, acts_by_day)
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    open(os.path.join(HERE, "out", "signals.txt"), "w").write("\n".join(OUT) + "\n")


if __name__ == "__main__":
    main()
