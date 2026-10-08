#!/usr/bin/env python3
"""Build the per-launch feature/outcome table for a census day and save it with the actor table.

    python3 src/build_features.py sep27            -> data/features_sep27.json.gz, data/actors_sep27.json
    python3 src/build_features.py data/census_oct06.json oct06
"""
import sys, os, json, gzip, time, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pons_census as P

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def template_key(r):
    return (round(r["creator_buy"], 4), r["tax_bps"], r["named_n"], r["helper_created"], r["meta_website"], r["meta_telegram"], r["meta_x"], r["meta_x_post"], r["meta_image"])


def flag_templates(rows):
    """Operators launching from a fresh wallet each time look like first-time creators. A launch is flagged
    `template` when its exact configuration (buy amount, tax, named count, sender type, social slots, image) recurs
    on >= 10 launches from >= 3 creator addresses that day AND the group behaves like a script: the creator side's
    median first sell comes within 60 s, or it names exempt wallets, or almost no bot buys it while outside money
    still arrives within the minute (a wallet set that buys its own launch). `template_n` is the group's size."""
    import statistics as st
    groups = collections.defaultdict(list)
    for r in rows:
        groups[template_key(r)].append(r)
    for k, g in groups.items():
        creators = {r["creator"] for r in g}
        n = len(g)
        scripted = False
        if n >= 10 and len(creators) >= 3:
            sells = [r["side_first_sell_t"] for r in g if r["side_first_sell_t"] is not None]
            med_sell = st.median(sells) if len(sells) >= n / 2 else None
            bot_share = sum(1 for r in g if r["first_bot_t"] is not None and r["first_bot_t"] <= 3) / n
            out60 = st.median(r["out_eth_60s"] for r in g)
            scripted = (med_sell is not None and med_sell <= 60) or k[2] >= 1 or (bot_share <= 0.10 and out60 >= 0.05)
        for r in g:
            r["template_n"] = n if len(creators) >= 3 else 1
            r["template"] = scripted
    # hindsight-free variant: the same exact configuration already launched >= 10 times EARLIER that day from >= 3
    # creator addresses (a fact available at the launch's own time); no outcome enters
    rows_sorted = sorted(rows, key=lambda r: r["t0"])
    seen = collections.defaultdict(lambda: [0, set()])
    for r in rows_sorted:
        k = template_key(r); c = seen[k]
        r["template_prior"] = c[0] >= 10 and len(c[1]) >= 3
        c[0] += 1; c[1].add(r["creator"])


def build(src, tag, eth_usd=None):
    t = time.time()
    Ls, info = P.load_day(src)
    if eth_usd:                                   # override the price the census was pulled with (CoinGecko daily close)
        for L in Ls:
            if L.q_is_eth:
                L.px_usd = eth_usd
        info["eth_usd"] = eth_usd
    for L in Ls:
        L.day = tag
    acts = P.classify_actors(Ls)
    for L in Ls:
        L.outcome = P.outcomes(L, acts)
    rows = [P.feature_row(L) for L in Ls]
    flag_templates(rows)
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    with gzip.open(os.path.join(HERE, "data", f"features_{tag}.json.gz"), "wt") as f:
        json.dump({"info": {k: v for k, v in info.items()}, "rows": rows}, f)
    json.dump(acts, open(os.path.join(HERE, "data", f"actors_{tag}.json"), "w"))
    cls = collections.Counter(a["class"] for a in acts.values())
    print(f"{tag}: {len(rows)} launches ({info['kept']} kept of {info['all']}; other path {info.get('other_path',0)}, other quote {info.get('other_quote',0)}), "
          f"{len(acts)} outside actors {dict(cls)}, {time.time()-t:.0f}s")
    return rows


if __name__ == "__main__":
    a = sys.argv[1:]
    ETH = {"sep27": 2687.0, "sep28": 2688.0, "oct01": 2700.0, "oct03": 2700.0, "oct06": 2710.0, "sep21": 2500.0, "sep14": 2500.0}
    if len(a) == 1:
        build(a[0], a[0], ETH.get(a[0]))
    else:
        build(a[0], a[1], float(a[2]) if len(a) > 2 else ETH.get(a[1]))
