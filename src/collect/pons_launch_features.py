#!/usr/bin/env python3
# Vendored unchanged from xin10ylop/fomo-memebot (src/analysis/) to pull a fresh out-of-sample day for this study.
"""What a Pons V2 launch says about itself, read from its creation call: name, symbol, image, description and the five
social slots (X, Telegram, website and two more), plus the launch settings (quote, creator tax, dev buy, exempt wallets).
Strings are recovered by walking the call's words for length-prefixed printable text, which is exact for this ABI.

    python3 src/analysis/pons_launch_features.py data/derived/edge_check/P/census_sep28.json
"""
import json, sys, time, urllib.request, urllib.error
RPC = "https://rpc.mainnet.chain.robinhood.com"; H = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 Chrome/128", "Accept": "application/json"}
def post(payload):
    for i in range(12):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(RPC, json.dumps(payload).encode(), H), timeout=120))
        except urllib.error.HTTPError: time.sleep(min(60, 4 * (i + 1)))
        except Exception: time.sleep(3 + i)
def strings(data):
    """every length-prefixed printable string in the call, in order"""
    words = [data[4 + 32*k: 4 + 32*(k+1)] for k in range((len(data) - 4) // 32)]; out = []; k = 0
    while k < len(words):
        n = int.from_bytes(words[k], "big")
        if 1 <= n <= 4000:
            m = (n + 31) // 32; blob = b"".join(words[k+1: k+1+m])[:n]
            if len(blob) == n and all(32 <= c < 127 or c in (9, 10, 13) or c >= 128 for c in blob) and any(32 <= c < 127 for c in blob):
                try:
                    s = blob.decode("utf-8"); out.append(s); k += 1 + m; continue
                except UnicodeDecodeError: pass
        k += 1
    return out
C = json.load(open(sys.argv[1])); L = C["launches"]; feats = {}
for i in range(0, len(L), 40):
    batch = L[i:i+40]; r = post([{"jsonrpc": "2.0", "id": j, "method": "eth_getTransactionByHash", "params": [x["tx"]]} for j, x in enumerate(batch)])
    got = {y["id"]: y.get("result") for y in (r if isinstance(r, list) else [])}
    for j, x in enumerate(batch):
        tx = got.get(j)
        if not tx: continue
        data = bytes.fromhex(tx["input"][2:])
        if data[:4].hex() != "f85f8e41": continue
        s = strings(data); urls = [u for u in s if u.startswith("http") or "." in u and " " not in u and len(u) < 200 and not u.startswith("ipfs")]
        low = [u.lower() for u in urls]
        f = {"name": s[0] if s else "", "symbol": s[1] if len(s) > 1 else "", "image": next((u for u in s if u.startswith("ipfs://") or u.startswith("https://ipfs")), ""),
             "x": any(("x.com/" in u or "twitter.com/" in u) and "/status/" not in u for u in low), "x_post": any("/status/" in u for u in low), "telegram": any("t.me/" in u for u in low),
             "website": any(u.startswith("http") and not any(d in u for d in ("x.com", "twitter.com", "t.me", "discord", "ipfs")) for u in low), "discord": any("discord" in u for u in low)}
        texts = [t for t in s[2:] if not (t.startswith("http") or t.startswith("ipfs")) and t not in (f["name"], f["symbol"])]
        f["description_len"] = max((len(t) for t in texts), default=0); f["n_strings"] = len(s)
        feats[x["curve"]] = f
    if (i // 40) % 20 == 0: print(f"  {i + len(batch)} of {len(L)}", flush=True)
json.dump(feats, open(sys.argv[1].replace(".json", "_features.json"), "w"))
n = len(feats); print(f"{n} launches with features: X link {sum(f['x'] for f in feats.values())/n:.0%}, X post {sum(f['x_post'] for f in feats.values())/n:.0%}, Telegram {sum(f['telegram'] for f in feats.values())/n:.0%}, website {sum(f['website'] for f in feats.values())/n:.0%}, description {sum(1 for f in feats.values() if f['description_len'] > 0)/n:.0%}")
