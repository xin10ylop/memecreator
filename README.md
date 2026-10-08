# memecreator: creator-side launch research on Pons V2 (Robinhood Chain)

Research question: what makes automated buyers buy a freshly launched Pons V2 token, which of those
characteristics go with real follow-through, and how much could a creator who launches a legitimate token and
sells their own launch-block inventory into that demand realistically make.

**Read `docs/REPORT.md`.** Short version: the bots can be attracted (a bigger creator buy, a website link, an
image and a low creator tax move early-bot participation from about 20% to 60-80% of launches), but the
configurations that attract the most bots do not earn more out of sample. The automated buyers of late September
and early October 2026 are small (0.01-0.04 ETH a buy), exit within a minute, and lose money as a class; selling
the creator's inventory into them is worth a few percent of the stake on average with a negative median. Most of
the mean creator income is the creator tax on outside volume, which exists only on the minority of launches that
draw real buyers, and which the launch configuration predicts weakly (AUC 0.60-0.72 out of sample). The
exit-schedule choice does not matter at the precision the data allows, and the day-to-day regime matters more
than any lever the creator holds.

All data comes from the public chain (every Pons V2 factory launch of seven full UTC days and every bonding-curve
trade in the six hours after each) and from the `xin10ylop/fomo-memebot` repository, which documents the launchpad
mechanics (curve, fees, snipe tax, bundles) from an earlier study of the buyers' side. Nothing here simulates or
recommends fake buyers, wash trading, bundle wallets or promotion; the creator cohort studied is first launches
from a wallet, with no named exempt wallets, sent by the creator, and not part of a scripted launch template.

## Layout

| Path | What |
|---|---|
| `docs/REPORT.md` | findings, method, falsification tests, the designed launch and its out-of-sample numbers |
| `src/pons_census.py` | loader for a census day: launch configuration from the creation calldata, metadata, exact curve replay, actor classes, outcome measures |
| `src/build_features.py` | per-launch feature/outcome table (`data/features_<day>.json.gz`) and actor table (`data/actors_<day>.json`), with the scripted-template flag |
| `src/analyze_signals.py` | what predicts bot participation and follow-through: one-way tables, logistic models fit on one day and scored on the others, rush vs follow-through, fleets (`out/signals.txt`) |
| `src/fleet_profiles.py` | what the busiest automated buyers select, their speed, size, hold, realized P&L and follow-through lift (`out/fleet_profiles.txt`) |
| `src/creator_sim.py` | the creator-side counterfactual on the exact curve: 27 pre-committed exit schedules, demand-response bounds, sell capacity (`out/creator_sim_<day>.json`) |
| `src/creator_sim_report.py` | the simulation tables: actual creators, schedule grid on the design day, walk-forward, decomposition, batch risk (`out/creator_sim.txt`) |
| `src/design_eval.py` | the strategy as framed, walk-forward: configure for bots on the design day, read on later days (`out/design_eval.txt`) |
| `src/regime_windows.py` | the five earlier windows (Aug 12 - Sep 3) from the fomo-memebot per-launch summaries (`out/regime_windows.txt`) |
| `src/collect/` | the census collectors, vendored unchanged from fomo-memebot, used to pull the fresh days |
| `data/` | the fresh censuses (`census_<day>.json`, pulled from the public RPC during this study) and the derived tables |
| `out/` | every table the report cites, plus `audit_simulator.md`, an independent review of the simulator |

## Reproducing

```
export FOMO_DATA=/path/to/fomo-memebot/data/derived      # for the Sep 27/28 censuses and the creation history
python3 src/collect/pons_creator_census.py "2026-10-06 00:00" "2026-10-07 00:00" data/census_oct06.json 6 2650
python3 src/collect/pons_launch_features.py data/census_oct06.json
python3 src/build_features.py data/census_oct06.json oct06
python3 src/creator_sim.py oct06
python3 src/creator_sim_report.py sep14 sep21 sep27 sep28 oct01 oct03 oct06   # first tag = design day
python3 src/analyze_signals.py sep14 sep21 sep27 sep28 oct01 oct03 oct06
python3 src/design_eval.py sep14 sep21 sep27 sep28 oct01 oct03 oct06
```

Python 3 with numpy; no other dependencies. The public RPC (`rpc.mainnet.chain.robinhood.com`) needs a browser-like
User-Agent and batches of at most 100.
