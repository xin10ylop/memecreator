#!/usr/bin/env python3
"""Creator-side simulation on the exact Pons V2 curve: what a creator who launches with a given configuration and
sells their launch-block inventory on a pre-committed schedule would have made, launch by launch, on the historical
tapes. No synthetic buyers: every outside trade is a real trade from the census; the creator's own later trades are
removed and replaced by the schedule.

Counterfactual rules (the same conventions the fomo-memebot exact replay used for the sniper, applied to the creator):
  * outside BUYS keep their observed gross quote and fee rate (incl. the time-keyed snipe surcharge) and receive the
    tokens the modified curve gives; a buy whose tokens fall short of what it actually received by more than TOL (10%)
    reverts (a minOut failure) and that wallet holds nothing from it;
  * outside SELLS sell the same fraction of the wallet's position as observed (a wallet cannot sell what it does not
    hold in the counterfactual);
  * the creator's sells land at the scheduled time (time rules) or LAT seconds after the triggering event (state
    rules), after every observed trade stamped before that;
  * the creator receives gross x (1 - 1%) on a sell (the platform fee; the creator tax on their own trades accrues
    back to them), pays gross on the launch buy less the creator tax that returns, and earns the creator tax on all
    outside volume in the window.
Cohorts (different inventory sizes) are launches that actually launched with that inventory: the bots' and traders'
response to the configuration is the real one. What is counterfactual is only the creator's exit.

    python3 src/creator_sim.py sep27 sep28 oct06 -> out/creator_sim_<tag>.json (per launch x schedule), out/creator_sim.txt
"""
import sys, os, json, gzip, math, collections, statistics as st, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pons_census as PC

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
X0, Y0 = PC.X0, PC.Y0
TOL = 0.10           # a later buyer's minOut tolerance
LAT = 0.5            # the creator's reaction latency for state-triggered sells (s)
LAUNCH_FEE = 0.0005  # ETH
GAS_CREATE = 0.001   # ETH (5M gas at 0.2 gwei); stress case 0.01
GAS_SELL = 0.00002   # ETH per sell transaction
WINDOW = 21600.0
PLATFORM = 0.01

# ---- schedules: each returns a list of (trigger, fraction_of_remaining_inventory) rules; the engine evaluates them ----
# trigger kinds: ("time", T) sell at T seconds; ("tp", k) when the inventory's curve exit value >= k x cost;
# ("flow", f) after each outside buy sell tokens worth f x that buy's net ETH; ("trail", k, dd) once value >= k x cost, sell when it falls dd from its peak.
SCHEDULES = collections.OrderedDict()
SCHEDULES["hold_6h"] = [("time", WINDOW, 1.0)]
for T in (5, 15, 30, 60, 120, 300, 900, 1800, 3600):
    SCHEDULES[f"all_at_{T}s"] = [("time", T, 1.0)]
for k in (1.25, 1.5, 2.0, 3.0):
    SCHEDULES[f"tp{k}_else_6h"] = [("tp", k, 1.0), ("time", WINDOW, 1.0)]
    SCHEDULES[f"tp{k}_else_5m"] = [("tp", k, 1.0), ("time", 300, 1.0)]
SCHEDULES["ladder_1.5_2_3_else_1h"] = [("tp", 1.5, 1 / 3), ("tp", 2.0, 0.5), ("tp", 3.0, 1.0), ("time", 3600, 1.0)]
for f in (0.25, 0.5, 1.0):
    SCHEDULES[f"flow{f}_else_6h"] = [("flow", f, None), ("time", WINDOW, 1.0)]
    SCHEDULES[f"flow{f}_else_5m"] = [("flow", f, None), ("time", 300, 1.0)]
SCHEDULES["trail_1.3_dd25_else_1h"] = [("trail", 1.3, 0.25), ("time", 3600, 1.0)]
SCHEDULES["half_30s_rest_tp2_else_1h"] = [("time", 30, 0.5), ("tp", 2.0, 1.0), ("time", 3600, 1.0)]


def inventory_value(X, Y, inv):
    """net ETH the creator gets for selling inv tokens now (platform fee only; creator tax returns)"""
    if inv <= 0:
        return 0.0
    gross = X - X * Y / (Y + inv)
    return gross * (1 - PLATFORM)


def observed_fractions(L):
    """for each outside sell: (fraction of the wallet's curve-bought holding it sold, tokens sold beyond that holding).
    Tokens a wallet sells without having bought them on the curve came by transfer (bundle exits, routers); those
    exist regardless of the curve's state, so they are sold in absolute amount in the counterfactual."""
    held = collections.defaultdict(float); fr = []
    for r in L.rows[1:]:
        w = r["who"]
        if w in L.side:
            fr.append(None); continue
        if r["k"] == "B":
            held[w] += r["tk"]; fr.append(None)
        else:
            h = held[w]
            if h > 1e-9:
                f = min(1.0, r["tk"] / h); excess = max(0.0, r["tk"] - h)
            else:
                f = 0.0; excess = r["tk"]
            held[w] = max(0.0, h - r["tk"]); fr.append((f, excess))
    return fr


def simulate(L, rules, tol=TOL, lat=LAT, keep_side=False, classes=None, after_sell_scale=1.0):
    """after_sell_scale: multiplier on the gross ETH of every outside buy that arrives after the creator's first sell
    (1.0 = the flow is unchanged by the creator's selling; 0.5 = half of it stays away; 0.0 = nobody buys after the
    creator starts selling). A crude bound on the behavioural response the tape cannot show."""
    """Replay one launch with the creator's exit replaced by `rules`. Returns a dict of results in ETH."""
    rows = L.rows
    if not rows or L.creator_buy <= 0:
        return None
    tax = L.tier - PLATFORM
    r0 = rows[0]
    X, Y = X0 + (r0["q"] - r0["pf"] - r0["ct"]), Y0 - r0["tk"]
    inv = r0["tk"]; cost = r0["q"] - r0["ct"]           # the creator tax on their own buy accrues back
    cost_gross = r0["q"]
    fr = observed_fractions(L)
    held = collections.defaultdict(float)
    proceeds = 0.0; n_sells = 0; sold_tk = 0.0; tax_income = 0.0; out_gross = 0.0
    eth_before_first_sell = collections.Counter(); eth_total = collections.Counter(); sold_any = [False]
    churn = churn_actors(L); tax_ex_churn = 0.0; tax_after_exit = 0.0
    first_sell_t = None; peak_val = 0.0; armed = False
    pending = []                                        # (t_land, fraction or ('tokens', tk))
    rules = [list(r) for r in rules]
    done = [False] * len(rules)
    log_val = []
    def do_sell(tk, t):
        nonlocal X, Y, inv, proceeds, n_sells, sold_tk, first_sell_t
        tk = min(tk, inv)
        if tk <= 0:
            return 0.0
        sold_any[0] = True
        gross = X - X * Y / (Y + tk)
        X -= gross; Y += tk; inv -= tk; sold_tk += tk
        got = gross * (1 - PLATFORM) - GAS_SELL
        proceeds += got; n_sells += 1
        if first_sell_t is None:
            first_sell_t = t
        return got
    def check_state_rules(t_now, last_buy_net=None):
        """state-triggered rules evaluated after an event; the sell is queued LAT later"""
        val = inventory_value(X, Y, inv)
        nonlocal peak_val, armed
        peak_val = max(peak_val, val)
        for i, rl in enumerate(rules):
            if done[i] or inv <= 0:
                continue
            kind = rl[0]
            if kind == "tp" and cost > 0 and val >= rl[1] * cost:
                pending.append((t_now + lat, rl[2])); done[i] = True
            elif kind == "trail":
                if cost > 0 and val >= rl[1] * cost:
                    armed = True
                if armed and val <= peak_val * (1 - rl[2]):
                    pending.append((t_now + lat, 1.0)); done[i] = True
            elif kind == "flow" and last_buy_net is not None and last_buy_net > 0:
                # tokens worth f x the buy's net ETH at the current marginal price
                want_eth = rl[1] * last_buy_net
                tk = Y * want_eth / (X - want_eth) if want_eth < X else inv   # tokens whose sale returns want_eth gross
                pending.append((t_now + lat, ("tokens", min(tk, inv))))
    def flush(t_upto):
        """land pending sells and time rules due before t_upto"""
        nonlocal inv
        while True:
            due = []
            for i, rl in enumerate(rules):
                if not done[i] and rl[0] == "time" and rl[1] <= t_upto:
                    due.append((rl[1], i))
            pend = [(t, j) for j, (t, _) in enumerate(pending) if t <= t_upto]
            if not due and not pend:
                return
            items = [(t, "rule", i) for t, i in due] + [(t, "pend", j) for t, j in pend]
            items.sort(key=lambda z: z[0])
            t, kind, idx = items[0]
            if kind == "rule":
                done[idx] = True
                frac = rules[idx][2]
                do_sell(inv * frac, t)
                check_state_rules(t)
            else:
                t_l, what = pending.pop(idx)
                if isinstance(what, tuple):
                    do_sell(what[1], t_l)
                else:
                    do_sell(inv * what, t_l)
                check_state_rules(t_l)
    check_state_rules(0.0)
    for r, f in zip(rows[1:], fr):
        t = r["t"]
        if t > WINDOW:
            break
        flush(t)
        w = r["who"]
        if w in L.side and not keep_side:
            continue                                   # the creator side's own later trades are replaced by the schedule
        if r["k"] == "B":
            rate = (r["pf"] + r["ct"]) / r["q"] if r["q"] > 0 else L.tier
            scale = after_sell_scale if sold_any[0] else 1.0
            if scale <= 0:
                continue
            net = r["q"] * scale * (1 - rate)
            if net <= 0 or net >= X * 1e6:
                continue
            tk = Y * net / (X + net)
            if tk < r["tk"] * scale * (1 - tol):
                continue                               # reverted on minOut
            X += net; Y -= tk; held[w] += tk
            out_gross += r["q"] * scale; tax_income += tax * r["q"] * scale
            if w not in churn:
                tax_ex_churn += tax * r["q"] * scale
            if sold_any[0]:
                tax_after_exit += tax * r["q"] * scale
            if classes is not None:
                c = classes.get(w, "other"); eth_total[c] += net
                if not sold_any[0]:
                    eth_before_first_sell[c] += net
            check_state_rules(t, last_buy_net=net)
        else:
            if f is None:
                s = r["tk"]                            # (creator side with keep_side)
            else:
                s = f[0] * held[w] + f[1]
                if not keep_side:
                    s = min(s, max(0.0, Y0 - Y - inv))  # cannot sell more than outsiders hold in the counterfactual (audit finding 5)
            if s <= 0:
                continue
            gross = X - X * Y / (Y + s)
            X -= gross; Y += s; held[w] = max(0.0, held[w] - s)
            out_gross += gross; tax_income += tax * gross
            if w not in churn:
                tax_ex_churn += tax * gross
            if sold_any[0]:
                tax_after_exit += tax * gross
            check_state_rules(t)
    flush(WINDOW + lat + 1)
    residual_val = inventory_value(X, Y, inv) * 0.97
    pnl_cons = proceeds + tax_income - cost - LAUNCH_FEE - GAS_CREATE
    return {"cost": cost, "cost_gross": cost_gross, "proceeds": proceeds, "tax_income": tax_income, "residual_marked": residual_val,
            "pnl_cons": pnl_cons, "pnl_marked": pnl_cons + residual_val, "sold_share": (sold_tk / r0["tk"]) if r0["tk"] else 0.0,
            "n_sells": n_sells, "first_sell_t": first_sell_t, "out_gross": out_gross, "end_X": X,
            "eth_before_sell": dict(eth_before_first_sell) if classes is not None else None, "eth_total": dict(eth_total) if classes is not None else None,
            "tax_ex_churn": tax_ex_churn, "tax_after_exit": tax_after_exit}


def churn_actors(L):
    """outside callers that trade in and out of this launch repeatedly with a flat position (>= 10 trades, net tokens
    under 5% of tokens bought): volume bots whose tax is not evidence of demand (audit finding 4)"""
    n = collections.Counter(); b = collections.defaultdict(float); s_ = collections.defaultdict(float)
    for r in L.rows[1:]:
        w = r["who"]
        if w in L.side:
            continue
        n[w] += 1
        if r["k"] == "B":
            b[w] += r["tk"]
        else:
            s_[w] += r["tk"]
    return {w for w in n if n[w] >= 10 and b[w] > 0 and abs(b[w] - s_[w]) < 0.05 * b[w]}


def capacity(L, T, tol=TOL):
    """Curve state at T with the creator side's later trades removed (outside flow as observed up to T): returns
    (value of the whole inventory / cost, share of inventory sellable with an average net price >= the entry price)."""
    rows = L.rows
    if not rows or L.creator_buy <= 0:
        return None
    r0 = rows[0]; X, Y = X0 + (r0["q"] - r0["pf"] - r0["ct"]), Y0 - r0["tk"]
    inv = r0["tk"]; cost = r0["q"] - r0["ct"]
    fr = observed_fractions(L); held = collections.defaultdict(float)
    for r, f in zip(rows[1:], fr):
        if r["t"] > T:
            break
        w = r["who"]
        if w in L.side:
            continue
        if r["k"] == "B":
            rate = (r["pf"] + r["ct"]) / r["q"] if r["q"] > 0 else L.tier; net = r["q"] * (1 - rate)
            if net <= 0:
                continue
            tk = Y * net / (X + net)
            if tk < r["tk"] * (1 - tol):
                continue
            X += net; Y -= tk; held[w] += tk
        else:
            s_ = f[0] * held[w] + f[1]
            if s_ <= 0:
                continue
            g = X - X * Y / (Y + s_); X -= g; Y += s_; held[w] = max(0.0, held[w] - s_)
    full = inventory_value(X, Y, inv) / cost if cost > 0 else float("nan")
    # largest share s of inventory with average net price >= cost/inv: net(s*inv) >= s*cost ; net is concave so bisect
    lo, hi = 0.0, 1.0
    if inventory_value(X, Y, inv) >= cost:
        share = 1.0
    elif inventory_value(X, Y, inv * 1e-4) < 1e-4 * cost:
        share = 0.0
    else:
        for _ in range(40):
            m = (lo + hi) / 2
            if inventory_value(X, Y, m * inv) >= m * cost:
                lo = m
            else:
                hi = m
        share = lo
    return full, share


def actual_outcome(L):
    """the creator side's real result on the tape (exact): sells - later buys - launch buy + tax, unsold at zero"""
    rows = L.rows
    r0 = rows[0]; tax = L.tier - PLATFORM
    buys = sum(r["q"] - r["ct"] for r in rows if r["k"] == "B" and r["who"] in L.side)
    sells = sum(r["q"] + r["ct"] for r in rows if r["k"] == "S" and r["who"] in L.side)
    tax_in = sum(r["ct"] for r in rows if r["who"] not in L.side)
    tk_b = sum(r["tk"] for r in rows if r["k"] == "B" and r["who"] in L.side); tk_s = sum(r["tk"] for r in rows if r["k"] == "S" and r["who"] in L.side)
    first_sell = next((r["t"] for r in rows if r["k"] == "S" and r["who"] in L.side), None)
    X, Y = X0, Y0
    for _, Xa, Ya, _, _ in PC.replay([x for x in rows if x["t"] <= WINDOW]):
        X, Y = Xa, Ya
    unsold = max(0.0, tk_b - tk_s)
    marked = inventory_value(X, Y, unsold) * 0.97
    extra_buys = sum(r["q"] - r["ct"] for r in rows[1:] if r["k"] == "B" and r["who"] in L.side)
    return {"pnl_cons": sells + tax_in - buys - LAUNCH_FEE - GAS_CREATE, "pnl_marked": sells + tax_in - buys - LAUNCH_FEE - GAS_CREATE + marked,
            "sold_share": (tk_s / tk_b) if tk_b else 0.0, "first_sell_t": first_sell, "proceeds": sells, "tax_income": tax_in, "cost": buys, "extra_buys": extra_buys, "unsold_marked": marked}


def cohort_of(L):
    cb = L.creator_buy
    for lo, hi, lab in ((0, 0.003, "<0.003"), (0.003, 0.01, "0.003-0.01"), (0.01, 0.025, "0.01-0.025"), (0.025, 0.05, "0.025-0.05"), (0.05, 0.1, "0.05-0.1"),
                        (0.1, 0.25, "0.1-0.25"), (0.25, 0.5, "0.25-0.5"), (0.5, 1.0, "0.5-1"), (1.0, 1e9, ">=1")):
        if lo <= cb < hi:
            return lab
    return "?"


def run_day(tag, px_usd=None):
    src = tag if tag in PC.DAYS else os.path.join(HERE, "data", f"census_{tag}.json")
    Ls, info = PC.load_day(src)
    px = px_usd or info["eth_usd"]
    ap = os.path.join(HERE, "data", f"actors_{tag}.json")
    classes = {a: v["class"] for a, v in json.load(open(ap)).items()} if os.path.exists(ap) else None
    out = []
    t = time.time()
    for L in Ls:
        if not L.q_is_eth or L.creator_buy <= 0 or L.sel != "f85f8e41":
            continue
        base = {"curve": L.curve, "creator": L.creator, "t0": L.t0, "hour": L.hour, "creator_buy": L.creator_buy, "creator_share": L.creator_tokens / Y0,
                "tax_bps": L.tax_bps, "named_n": len(L.named), "prior_today": L.prior_today, "prior_week": L.prior_week, "helper": L.helper_created,
                "cohort": cohort_of(L), "socials": L.feat.get("n_socials", 0), "website": L.feat.get("website", False), "telegram": L.feat.get("telegram", False),
                "n_out_trades": sum(1 for r in L.rows[1:] if r["who"] not in L.side), "proxy_sells": getattr(L, "proxy_sells", 0)}
        base["actual"] = actual_outcome(L)
        res = {}
        for name, rules in SCHEDULES.items():
            res[name] = simulate(L, rules, classes=classes)
        for name in ("all_at_5s", "all_at_30s", "all_at_60s", "all_at_300s", "tp1.5_else_5m", "flow0.5_else_6h", "hold_6h"):
            for sc in (0.5, 0.25, 0.0):
                res[f"{name}@d{sc}"] = simulate(L, SCHEDULES[name], after_sell_scale=sc)
        base["sched"] = res
        base["capacity"] = {str(T): capacity(L, T) for T in (10, 30, 60, 300, 3600)}
        out.append(base)
    json.dump({"tag": tag, "eth_usd": px, "rows": out}, open(os.path.join(HERE, "out", f"creator_sim_{tag}.json"), "w"))
    print(f"{tag}: simulated {len(out)} launches x {len(SCHEDULES)} schedules in {time.time()-t:.0f}s")
    return out, px


if __name__ == "__main__":
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    for tag in (sys.argv[1:] or ["sep27", "sep28"]):
        run_day(tag)
