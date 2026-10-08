#!/usr/bin/env python3
# Vendored unchanged from xin10ylop/fomo-memebot (src/analysis/) to pull a fresh out-of-sample day for this study.
"""Pons V2 creator census: every launch in a window, every curve trade in the following hours, and what the creator side
took out. Creator side = the creator address plus the wallets named in the creation call (exempt from the snipe tax).
Per launch: creator tax earned (the 4th word of every Buy/Sell), the creator side's buys and sells on the curve, their
unsold tokens (valued at zero and at the last curve price), the launch fee, volume, buyers. Quotes: ETH and USDG in USD.

    python3 src/analysis/pons_creator_census.py "2026-09-28 00:00" "2026-09-29 00:00" data/derived/edge_check/P/census_sep28.json [hours_after=6]
"""
import json, sys, time, calendar, urllib.request, urllib.error, collections
RPC = "https://rpc.mainnet.chain.robinhood.com"; H = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 Chrome/128", "Accept": "application/json"}
V2F = "0xe33e9e479df8802cb0866d5d05258bec4cf62948"; T_LAUNCH = "0xdcacba5e347ae7abd91cb519eb877af8fa7774e347b85dd3ddcd24a2ba8cdf37"
BUY = "0xec36bf571f136799e8dc0b0b8bea4b04d8bd3d43de838aab0d5fc21d4cbfc455"; SELL = "0x8113d738abdcb6b38357e9d53a54a7157861a09031b453651f0fe7fe151f59df"
ETH_Q = "0x" + "00" * 20; USDG = "0x5fc5360d"; ETH_USD = float(sys.argv[5]) if len(sys.argv) > 5 else 2650.0
calls = [0]
def post(payload):
    for i in range(12):
        try:
            calls[0] += 1
            return json.load(urllib.request.urlopen(urllib.request.Request(RPC, json.dumps(payload).encode(), H), timeout=120))
        except urllib.error.HTTPError as e: time.sleep(min(60, 4 * (i + 1)))
        except Exception: time.sleep(3 + i)
    raise RuntimeError("rpc gave up")
def call(m, p):
    r = post({"jsonrpc": "2.0", "id": 1, "method": m, "params": p})
    if "error" in r:
        msg = str(r["error"])
        if "exceeds limit" in msg or "timed out" in msg: raise OverflowError(msg)     # too many logs, or too slow: split the range
        raise RuntimeError(msg[:160])
    return r["result"]
def logs(flt, a, b):
    try: return call("eth_getLogs", [dict(flt, fromBlock=hex(a), toBlock=hex(b))])
    except OverflowError:
        if b <= a: time.sleep(5); return call("eth_getLogs", [dict(flt, fromBlock=hex(a), toBlock=hex(b))])
        m = (a + b) // 2; return logs(flt, a, m) + logs(flt, m + 1, b)
def block_at(ts):
    lo, hi = 1, int(call("eth_blockNumber", []), 16)
    while lo < hi:
        mid = (lo + hi) // 2
        if int(call("eth_getBlockByNumber", [hex(mid), False])["timestamp"], 16) < ts: lo = mid + 1
        else: hi = mid
    return lo
def main():
    t_lo = calendar.timegm(time.strptime(sys.argv[1], "%Y-%m-%d %H:%M")); t_hi = calendar.timegm(time.strptime(sys.argv[2], "%Y-%m-%d %H:%M")); out = sys.argv[3]
    after_h = float(sys.argv[4]) if len(sys.argv) > 4 else 6.0; t0 = time.time()
    b_lo, b_hi = block_at(t_lo), block_at(t_hi); b_end = min(int(call("eth_blockNumber", []), 16), b_hi + int(after_h * 36000))
    L = []
    for a in range(b_lo, b_hi, 29999):
        for l in logs({"address": V2F, "topics": [T_LAUNCH]}, a, min(a + 29998, b_hi)):
            L.append({"bn": int(l["blockNumber"], 16), "tx": l["transactionHash"], "token": "0x" + l["topics"][1][-40:], "curve": "0x" + l["topics"][2][-40:], "creator": "0x" + l["topics"][3][-40:]})
    print(f"{len(L)} launches, blocks {b_lo}-{b_hi} ({time.time()-t0:.0f} s)", flush=True)
    for i in range(0, len(L), 40):                                   # creation calls, batched
        batch = L[i:i+40]; r = post([{"jsonrpc": "2.0", "id": j, "method": "eth_getTransactionByHash", "params": [x["tx"]]} for j, x in enumerate(batch)])
        got = {x["id"]: x.get("result") for x in (r if isinstance(r, list) else [])}
        for j, x in enumerate(batch):
            tx = got.get(j) or call("eth_getTransactionByHash", [x["tx"]])
            data = bytes.fromhex(tx["input"][2:]); x["sel"] = data[:4].hex(); x["value"] = int(tx["value"], 16) / 1e18; x["from"] = tx["from"].lower(); x["to"] = (tx.get("to") or "").lower()
            words = [data[4 + 32*k: 4 + 32*(k+1)] for k in range((len(data) - 4) // 32)]
            if x["sel"] == "f85f8e41" and len(words) >= 14:
                x["quote"] = "0x" + words[2][12:].hex(); x["tax_bps"] = int.from_bytes(words[13], "big") if int.from_bytes(words[13], "big") <= 2000 else None
                x["named"] = sorted({"0x" + w[12:].hex() for w in words if w[:12] == b"\0" * 12 and int.from_bytes(w[12:], "big") > 2 ** 100} - {x["creator"], x["token"], x["curve"], x["quote"]})
            else:
                x["quote"] = None; x["tax_bps"] = None; x["named"] = []
    print(f"creation calls decoded ({time.time()-t0:.0f} s, {calls[0]} calls)", flush=True)
    curves = {x["curve"]: x for x in L}; trades = collections.defaultdict(list); n_ev = 0
    for a in range(b_lo, b_end, 29999):
        for e in logs({"topics": [[BUY, SELL]]}, a, min(a + 29998, b_end)):
            cv = e["address"].lower()
            if cv not in curves: continue
            d = e["data"][2:]; w = [int(d[k:k+64], 16) for k in range(0, len(d), 64)]
            who = ("0x" + e["topics"][2][-40:]).lower() if len(e["topics"]) > 2 else None
            trades[cv].append([int(e["blockNumber"], 16), int(e["logIndex"], 16), "B" if e["topics"][0] == BUY else "S", who, w[0], w[1], w[2], w[3] if len(w) > 3 else 0])
            n_ev += 1
        print(f"  trades read to block {min(a + 29998, b_end)}: {n_ev} ({time.time()-t0:.0f} s, {calls[0]} calls)", flush=True)
    json.dump({"window": [sys.argv[1], sys.argv[2]], "blocks": [b_lo, b_hi, b_end], "eth_usd": ETH_USD, "launches": L, "trades": trades,
               "trade_fields": ["bn", "logIndex", "kind", "who", "w0 (buy: quote in / sell: tokens in)", "w1 (buy: tokens out / sell: quote out)", "platform fee incl. snipe tax", "creator tax"]}, open(out, "w"))
    print(f"wrote {out}: {len(L)} launches, {n_ev} trades ({time.time()-t0:.0f} s, {calls[0]} calls)", flush=True)
main()
