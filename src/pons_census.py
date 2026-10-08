#!/usr/bin/env python3
"""Loader for the Pons V2 (Robinhood Chain) launch censuses collected in the fomo-memebot repository.

A census file (fomo-memebot: src/analysis/pons_creator_census.py) holds every factory launch of one UTC day and every
bonding-curve Buy/Sell event on those curves for the following six hours. This module turns it into per-launch records
with (a) the launch configuration as it was visible in the creation transaction, (b) the on-chain metadata (name,
socials), (c) the full trade tape in seconds since creation with exact curve state, and (d) outcome measures.

Curve (verified on the census to 1e-12): constant product with virtual reserves X0 = 1.68 ETH, Y0 = 1e9 tokens.
  buy : net = quoteIn - platformFee - creatorTax ; tokensOut = Y * net / (X + net) ; X += net ; Y -= tokensOut
  sell: gross = X - X*Y/(Y + tokensIn) ; quoteOut = gross - platformFee - creatorTax ; X -= gross ; Y += tokensIn
Platform fee = 1% of the gross (+ snipe surcharge: 93-98% in the creation second, +6.18% in the next, +0.19% in the one
after; wallets named in the creation call are exempt). Creator tax = tax_bps/1e4 of the gross, paid to the creator.
Blocks are ~100 ms; the census carries block numbers only, converted to seconds with the day's block rate.
"""
import json, os, gzip, collections, time, calendar

DATA = os.environ.get("FOMO_DATA", "/home/user/xin10ylop/fomo-memebot/data/derived")
ETH_Q = "0x" + "00" * 20
USDG_PREFIX = "0x5fc5360d"
X0, Y0 = 1.68, 1e9
GRADUATION_ETH = 4.2
DAYS = {"sep27": "edge_check/P/census_sep27.json", "sep28": "edge_check/P/census_sep28.json"}
# routers / relays seen as the `who` of curve events (the event's sender is the calling contract when a trade is routed)
KNOWN_ROUTERS = {
    "0x65050a9b7e5075a2ba5ced7b1b64ee66262c40dc": "pons_router",
    "0xb92fe925dc43a0ecde6c8b1a2709c170ec4fff4f": "fomo_relay",
}


def _load_json(path):
    op = gzip.open if path.endswith(".gz") else open
    with op(path, "rt") as f:
        return json.load(f)


def load_creation_history():
    """creator -> sorted list of creation timestamps (Sep 21 00:00 -> Sep 28 10:01 UTC), from live_vs_table/creations_week"""
    p = os.path.join(DATA, "live_vs_table", "creations_week.json.gz")
    if not os.path.exists(p):
        return {}
    hist = collections.defaultdict(list)
    for x in _load_json(p):
        hist[x["creator"].lower()].append(x["ts"])
    for k in hist:
        hist[k].sort()
    return hist


class Launch:
    __slots__ = ("day", "bn", "tx", "token", "curve", "creator", "sender", "quote", "tax_bps", "named", "value", "sel",
                 "t0", "hour", "feat", "rows", "side", "q_is_eth", "dec", "px_usd", "tier", "creator_buy", "creator_tokens",
                 "prior_today", "prior_week", "helper_created", "outcome", "proxy_sells", "template_prior")

    def __init__(self):
        self.outcome = {}


def load_day(tag, hours=6.0):
    """Returns (launches, info). Only factory creations through the standard call (selector f85f8e41) quoted in ETH or
    USDG are kept, since only those have a decodable configuration and a USD price; the rest are counted in info."""
    path = os.path.join(DATA, DAYS[tag]) if tag in DAYS else tag
    if not os.path.exists(path) and os.path.exists(path + ".gz"):
        path = path + ".gz"                                   # the repository ships the fresh censuses gzipped
    C = _load_json(path)
    eth_usd = C["eth_usd"]
    b_lo, b_hi = C["blocks"][0], C["blocks"][1]
    t_lo = calendar.timegm(time.strptime(C["window"][0], "%Y-%m-%d %H:%M"))
    t_hi = calendar.timegm(time.strptime(C["window"][1], "%Y-%m-%d %H:%M"))
    bps = (b_hi - b_lo) / (t_hi - t_lo)                      # blocks per second over the day
    feats_path = (path[:-3] if path.endswith(".gz") else path).replace(".json", "_features.json")
    F = _load_json(feats_path) if os.path.exists(feats_path) else {}
    T = C["trades"]
    hist = load_creation_history()
    info = collections.Counter()
    launches = []
    seen_today = collections.Counter()
    seen_names = {}
    for x in sorted(C["launches"], key=lambda x: x["bn"]):
        info["all"] += 1
        creator = x["creator"].lower()
        seen_today[creator] += 1
        if x.get("sel") != "f85f8e41":
            info["other_path"] += 1; continue
        q = (x.get("quote") or "").lower()
        if q == ETH_Q:
            dec, px = 1e18, eth_usd
        elif q.startswith(USDG_PREFIX):
            dec, px = 1e6, 1.0
        else:
            info["other_quote"] += 1; continue
        L = Launch()
        L.day, L.bn, L.tx, L.token, L.curve = tag, x["bn"], x["tx"], x["token"].lower(), x["curve"].lower()
        L.creator, L.sender, L.quote, L.tax_bps = creator, x["from"].lower(), q, (x.get("tax_bps") if x.get("tax_bps") is not None else 0)
        L.named = sorted(w.lower() for w in x.get("named", []))
        L.value, L.sel = x["value"], x["sel"]
        L.q_is_eth, L.dec, L.px_usd = (q == ETH_Q), dec, px
        L.t0 = t_lo + (x["bn"] - b_lo) / bps
        L.hour = int(((L.t0 - t_lo) % 86400) // 3600)
        L.side = {L.creator, L.sender} | set(L.named)
        L.helper_created = L.sender != L.creator
        L.prior_today = seen_today[creator] - 1
        h = hist.get(creator, [])
        L.prior_week = sum(1 for ts in h if ts < L.t0 - 1)
        f = F.get(L.curve) or {}
        key_n, key_s = (f.get("name") or "").strip().lower(), (f.get("symbol") or "").strip().lower()
        copy = bool(key_n) and ((("n", key_n) in seen_names and seen_names[("n", key_n)] != creator) or (("s", key_s) in seen_names and seen_names[("s", key_s)] != creator))
        for k in (("n", key_n), ("s", key_s)):
            if k[1]:
                seen_names.setdefault(k, creator)
        L.feat = {"name": f.get("name", ""), "symbol": f.get("symbol", ""), "image": bool(f.get("image")), "x": bool(f.get("x")),
                  "x_post": bool(f.get("x_post")), "telegram": bool(f.get("telegram")), "website": bool(f.get("website")),
                  "discord": bool(f.get("discord")), "desc_len": int(f.get("description_len", 0) or 0), "has_meta": bool(f),
                  "copycat": copy, "n_socials": sum(1 for k in ("x", "telegram", "website", "discord") if f.get(k))}
        # the tape
        rows = []
        for t in sorted(T.get(x["curve"], []), key=lambda t: (t[0], t[1])):
            bn, li, kind, who, w0, w1, w2, w3 = t
            who = (who or "").lower()
            tsec = (bn - x["bn"]) / bps
            if kind == "B":
                rows.append({"t": tsec, "bn": bn, "k": "B", "who": who, "q": w0 / dec, "tk": w1 / 1e18, "pf": w2 / dec, "ct": w3 / dec})
            else:
                rows.append({"t": tsec, "bn": bn, "k": "S", "who": who, "q": w1 / dec, "tk": w0 / 1e18, "pf": w2 / dec, "ct": w3 / dec})
        rows = [r for r in rows if r["t"] <= hours * 3600 + 1]
        L.rows = rows
        # the creator's launch-block buy
        if rows and rows[0]["k"] == "B" and rows[0]["bn"] == x["bn"] and rows[0]["who"] in L.side:
            L.creator_buy, L.creator_tokens = rows[0]["q"], rows[0]["tk"]
            L.tier = (rows[0]["pf"] + rows[0]["ct"]) / rows[0]["q"] if rows[0]["q"] > 1e-9 else 0.01 + L.tax_bps / 1e4   # dust buys round the fees to zero
            L.proxy_sells = relabel_proxy_sells(L)
        else:
            L.creator_buy, L.creator_tokens = 0.0, 0.0
            L.tier = 0.01 + L.tax_bps / 1e4
            L.proxy_sells = 0
            info["no_launch_block_buy"] += 1
        info["kept"] += 1
        launches.append(L)
    info["eth_usd"] = eth_usd; info["bps"] = bps; info["t_lo"] = t_lo
    return launches, info


def relabel_proxy_sells(L):
    """Creators often exit through a router or relay contract: the Sell event's caller is then the contract, which
    never bought on the curve. A sell by a caller with no curve-bought holding, of at least half and at most 102% of
    the creator side's remaining launch inventory, is relabelled as the creator's own sell (who = creator,
    proxy = True) so that outcomes, the actual P&L and the counterfactual all treat it as the creator's exit.
    (Independent audit finding 2: without this, 24+ exit contracts hid 15-20% of creator exits.)"""
    held = collections.defaultdict(float); bought_ever = set(); n = 0
    side_unsold = L.creator_tokens
    for r in L.rows[1:]:
        w = r["who"]
        if w in L.side:
            if r["k"] == "B":
                side_unsold += r["tk"]
            else:
                side_unsold = max(0.0, side_unsold - r["tk"])
            continue
        if r["k"] == "B":
            held[w] += r["tk"]; bought_ever.add(w)
        else:
            if w not in bought_ever and held[w] <= 1e-9 and side_unsold > 0 and 0.5 * side_unsold <= r["tk"] <= 1.02 * side_unsold:
                r["who"] = L.creator; r["proxy"] = True; n += 1
                side_unsold = max(0.0, side_unsold - r["tk"])
            else:
                held[w] = max(0.0, held[w] - r["tk"])
    return n


def replay(rows, side=None):
    """Fold a tape on the exact curve. Yields per row: (row, X_after, Y_after, net_or_gross, price_after).
    price = X/Y (quote per token, marginal)."""
    X, Y = X0, Y0
    for r in rows:
        if r["k"] == "B":
            net = r["q"] - r["pf"] - r["ct"]
            if net <= 0 or r["tk"] <= 0 or r["tk"] >= Y:
                yield r, X, Y, 0.0, X / Y; continue
            X += net; Y -= r["tk"]
            yield r, X, Y, net, X / Y
        else:
            if r["tk"] <= 0:
                yield r, X, Y, 0.0, X / Y; continue
            gross = X - X * Y / (Y + r["tk"])
            X -= gross; Y += r["tk"]
            yield r, X, Y, gross, X / Y


def surcharge_second(r, tier):
    """0 = creation second (93-98%), 1 = next second (+6.18%), 2 = the one after (+0.19%), 3 = none; None for a sell"""
    if r["k"] != "B" or r["q"] <= 0:
        return None
    s = r["pf"] / r["q"] - 0.01
    if s > 0.5:
        return 0
    if abs(s - 0.0618) < 0.004:
        return 1
    if abs(s - 0.0019) < 0.0008:
        return 2
    return 3


HORIZONS = [("3s", 3), ("10s", 10), ("30s", 30), ("60s", 60), ("5m", 300), ("15m", 900), ("1h", 3600), ("6h", 21600)]


def classify_actors(launches, bot_min_launches=20):
    """Per outside actor over a day: launches bought, median first-buy delay, median hold, median size; a bot label.
    'who' is the curve caller: a wallet, or a router/relay contract aggregating many users (flagged)."""
    acts = collections.defaultdict(lambda: {"launches": set(), "first_t": [], "holds": [], "sizes": [], "buys": 0, "sells": 0, "eth_in": 0.0, "eth_out": 0.0, "buys_on": collections.Counter()})
    for L in launches:
        if not L.q_is_eth:
            continue
        first = {}
        held = collections.defaultdict(float)
        for r in L.rows:
            w = r["who"]
            if w in L.side:
                continue
            a = acts[w]
            if r["k"] == "B":
                a["launches"].add(L.curve); a["buys"] += 1; a["eth_in"] += r["q"]; a["sizes"].append(r["q"]); a["buys_on"][L.curve] += 1
                if w not in first:
                    first[w] = r["t"]; a["first_t"].append(r["t"])
                held[w] += r["tk"]
            else:
                a["sells"] += 1; a["eth_out"] += r["q"]
                if w in first and held[w] > 0:
                    a["holds"].append(r["t"] - first[w]); held[w] -= r["tk"]
    out = {}
    import statistics as st
    for w, a in acts.items():
        n = len(a["launches"])
        med_first = st.median(a["first_t"]) if a["first_t"] else None
        med_hold = st.median(a["holds"]) if a["holds"] else None
        med_size = st.median(a["sizes"]) if a["sizes"] else 0.0
        sizes = a["sizes"]
        cv = (st.pstdev(sizes) / st.mean(sizes)) if len(sizes) > 1 and st.mean(sizes) > 0 else 0.0
        bpl = (a["buys"] / n) if n else 0.0
        single = (sum(1 for c in a["buys_on"].values() if c == 1) / n) if n else 0.0
        if w in KNOWN_ROUTERS or (n >= bot_min_launches and bpl >= 4.0 and cv >= 1.0):
            cls = "router"
        elif n >= bot_min_launches:
            if med_first is not None and med_first <= 3.0 and med_hold is not None and med_hold <= 30:
                cls = "bot_sniper"            # buys in the first seconds, out within half a minute
            elif med_first is not None and med_first <= 3.0:
                cls = "bot_early_holder"      # buys in the first seconds, holds longer
            else:
                cls = "bot_late"              # many launches, arrives later (scanner / follower bots)
        elif n >= 5:
            cls = "multi"                     # 5-19 launches: semi-automated or active trader
        else:
            cls = "other"
        out[w] = {"class": cls, "launches": n, "buys": a["buys"], "sells": a["sells"], "eth_in": a["eth_in"], "eth_out": a["eth_out"],
                  "med_first_t": med_first, "med_hold": med_hold, "med_size": med_size, "sell_ratio": (a["sells"] / a["buys"]) if a["buys"] else 0.0,
                  "size_cv": cv, "buys_per_launch": bpl, "single_buy_share": single}
    return out


def outcomes(L, actors):
    """Outcome measures for one launch from its tape. Everything is in the launch's quote unit (ETH for ETH launches)."""
    o = {}
    side = L.side
    bot_classes = {"bot_sniper", "bot_early_holder", "bot_late"}
    hz = {k: {"out_eth": 0.0, "out_n": set(), "bot_eth": 0.0, "bot_n": set(), "gen_eth": 0.0, "gen_n": set(), "sell_eth": 0.0} for k, _ in HORIZONS}
    rush = {"n0": set(), "eth0": 0.0, "n1": set(), "eth1": 0.0, "n2": set(), "eth2": 0.0}
    first_outside_t = None; first_bot_t = None
    peak = 0.0; p_after_creator = None; last_price = None
    price_at = {}
    side_sold_eth = 0.0; side_sold_tk = 0.0; side_first_sell_t = None; side_bought_tk = 0.0; side_bought_eth = 0.0
    out_bought_tk = collections.defaultdict(float)
    creator_tax = 0.0; creator_tax_1h = 0.0; platform_fee = 0.0
    graduated = False; grad_t = None
    volume = 0.0
    n_buys = 0; n_sells = 0
    prev_price = X0 / Y0
    for r, X, Y, amt, price in replay(L.rows):
        for k, h in HORIZONS:
            if k not in price_at and r["t"] > h:
                price_at[k] = prev_price
        w = r["who"]; t = r["t"]
        volume += r["q"]; creator_tax += r["ct"]; platform_fee += r["pf"]
        if t <= 3600:
            creator_tax_1h += r["ct"]
        if r["k"] == "B":
            n_buys += 1
            if w in side:
                side_bought_tk += r["tk"]; side_bought_eth += r["q"]
                if p_after_creator is None:
                    p_after_creator = price
            else:
                if first_outside_t is None:
                    first_outside_t = t
                cls = actors.get(w, {}).get("class", "other")
                is_bot = cls in bot_classes
                if is_bot and first_bot_t is None:
                    first_bot_t = t
                out_bought_tk[w] += r["tk"]
                sec = surcharge_second(r, L.tier)
                if sec == 0:
                    rush["n0"].add(w); rush["eth0"] += r["q"]
                elif sec == 1:
                    rush["n1"].add(w); rush["eth1"] += r["q"]
                elif sec == 2:
                    rush["n2"].add(w); rush["eth2"] += r["q"]
                for k, h in HORIZONS:
                    if t <= h:
                        d = hz[k]; d["out_eth"] += r["q"]; d["out_n"].add(w)
                        if is_bot:
                            d["bot_eth"] += r["q"]; d["bot_n"].add(w)
                        else:
                            d["gen_eth"] += r["q"]; d["gen_n"].add(w)
        else:
            n_sells += 1
            if w in side:
                side_sold_eth += r["q"]; side_sold_tk += r["tk"]
                if side_first_sell_t is None:
                    side_first_sell_t = t
            else:
                for k, h in HORIZONS:
                    if t <= h:
                        hz[k]["sell_eth"] += r["q"]
        if p_after_creator is not None and price / p_after_creator > peak:
            peak = price / p_after_creator
        last_price = price
        if not graduated and X - X0 >= GRADUATION_ETH and L.q_is_eth:
            graduated = True; grad_t = t
        prev_price = price
    ref = p_after_creator if p_after_creator else X0 / Y0
    o["n_trades"] = len(L.rows); o["n_buys"] = n_buys; o["n_sells"] = n_sells
    o["volume"] = volume; o["creator_tax"] = creator_tax; o["creator_tax_1h"] = creator_tax_1h; o["platform_fee"] = platform_fee
    o["first_outside_t"] = first_outside_t; o["first_bot_t"] = first_bot_t
    o["peak_mult"] = peak; o["last_mult"] = (last_price / ref) if last_price else 1.0
    for k, _ in HORIZONS:
        o[f"out_eth_{k}"] = hz[k]["out_eth"]; o[f"out_n_{k}"] = len(hz[k]["out_n"])
        o[f"bot_eth_{k}"] = hz[k]["bot_eth"]; o[f"bot_n_{k}"] = len(hz[k]["bot_n"])
        o[f"gen_eth_{k}"] = hz[k]["gen_eth"]; o[f"gen_n_{k}"] = len(hz[k]["gen_n"])
        o[f"sell_eth_{k}"] = hz[k]["sell_eth"]
        o[f"mult_{k}"] = (price_at.get(k, last_price) / ref) if last_price else 1.0
    o["rush_n0"], o["rush_eth0"] = len(rush["n0"]), rush["eth0"]
    o["rush_n1"], o["rush_eth1"] = len(rush["n1"]), rush["eth1"]
    o["rush_n2"], o["rush_eth2"] = len(rush["n2"]), rush["eth2"]
    o["side_bought_eth"] = side_bought_eth; o["side_sold_eth"] = side_sold_eth
    o["side_first_sell_t"] = side_first_sell_t
    o["side_unsold_share"] = (max(0.0, side_bought_tk - side_sold_tk) / side_bought_tk) if side_bought_tk > 0 else None
    o["graduated"] = graduated; o["grad_t"] = grad_t
    o["out_holders_end"] = sum(1 for w, tk in out_bought_tk.items() if tk > 0)
    return o


def feature_row(L, actors=None):
    """Flat dict: configuration (known at creation) + metadata + outcomes."""
    o = L.outcome or outcomes(L, actors or {})
    px = L.px_usd
    d = {"day": L.day, "curve": L.curve, "creator": L.creator, "t0": L.t0, "hour": L.hour, "quote": "ETH" if L.q_is_eth else "USDG",
         "tax_bps": L.tax_bps, "named_n": len(L.named), "helper_created": L.helper_created, "prior_today": L.prior_today, "prior_week": L.prior_week,
         "creator_buy": L.creator_buy, "creator_buy_usd": L.creator_buy * px, "creator_share": L.creator_tokens / Y0, "tier": L.tier,
         "px_usd": px}
    d["proxy_sells"] = getattr(L, "proxy_sells", 0)
    d.update({f"meta_{k}": v for k, v in L.feat.items() if k not in ("name", "symbol")})
    d["name"] = L.feat.get("name", ""); d["symbol"] = L.feat.get("symbol", "")
    d.update(o)
    return d


if __name__ == "__main__":
    import sys
    tag = sys.argv[1] if len(sys.argv) > 1 else "sep28"
    t = time.time()
    Ls, info = load_day(tag)
    print(tag, dict(info), f"{time.time()-t:.1f}s")
    acts = classify_actors(Ls)
    cls = collections.Counter(a["class"] for a in acts.values())
    print("actors", len(acts), dict(cls))
    n = 0
    for L in Ls:
        L.outcome = outcomes(L, acts); n += 1
    print("outcomes", n, f"{time.time()-t:.1f}s")
    rows = [feature_row(L) for L in Ls]
    print(json.dumps(rows[0], indent=0)[:1500])
