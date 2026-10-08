# Adversarial audit: `pons_census.py` / `creator_sim.py` (creator exit simulator)

Audited code: `src/creator_sim.py` (version of 09:04, with `after_sell_scale` and `capacity`) and `src/creator_sim_report.py` (09:15). The files changed while the audit ran. All numbers below come from that code, and they match `out/creator_sim.txt` of 09:17. Unless stated otherwise, the cohort is the report's main one: clean, creator buy 0.025-0.25 ETH. Test scripts are in `/tmp/claude-0/-home-user-memecreator/7ea88a5f-9309-50c8-9b35-af405a46bb28/scratchpad/audit/` (t1 to t25). No file under `src/` or `data/` was modified.

## Findings

1. **BLOCKER: Outside demand is assumed not to react to the creator's exit, and most of the early-exit P&L is creator tax on that later flow.** The base case is `after_sell_scale=1.0`.
   - **Evidence, share of P&L (t6).** On sep28, all_at_30s makes +0.0175 ETH, of which 0.0146 is tax income. With no outside buys after the exit, tax falls to 0.0043. So 0.0103 ETH, or 59% of the P&L, is tax on volume that arrives after the creator has dumped. The figure is 54% on oct06.
   - **Evidence, tail (t16).** The top 5% of launches carry 72% of the positive P&L (sep28), and 77% of their P&L is tax. The single largest launch earns +1.96 ETH. That is all tax on 65 ETH of volume, which traded while the real creator held for 3.9 h. That one launch is about 10% of the cohort's total for the day.
   - **Evidence, event study on the real tapes (t7, t7b).**
     - Treated launches: the creator side sold at least 80% of its tokens within 10 s, with the first sell between 15 and 300 s.
     - Controls: launches in the same buy band and the same log2 bins of outside buy ETH, both since creation and in the last 30 s before the sell time, whose creator had not sold.
     - Result: outside volume in the following hour runs at 0.09 to 0.49 of the matched controls.

     | Day | Sample | Controls | Ratio, uncapped | Ratio, per-launch cap 2 ETH |
     |---|---|---|---|---|
     | sep28 | clean, n=363-431 | held through | 0.12 [0.07, 0.17] | 0.22 |
     | sep28 | clean | not yet sold | 0.21 | 0.29 [0.19, 0.41] |
     | oct06 | clean, n=245-293 | held through | 0.12 | 0.26 |
     | oct06 | clean | not yet sold | 0.49 (CI up to 1.13) | 0.35 [0.22, 0.53] |

     This is not a clean causal estimate: creators may dump when momentum fades. But every specification is far below the simulator's 1.0. The central value is about 0.2-0.35.
   - **Evidence, adjusted P&L (t21).** Outside buys after the first creator sell scaled by 0.25 to 0.5, with volume churners removed (finding 4):

     | Schedule | sep27 | sep28 | oct01 | oct06 |
     |---|---|---|---|---|
     | all_at_30s, reported | +0.0176 | +0.0175 | +0.0121 | +0.0202 |
     | all_at_30s, adjusted | +0.0098 to +0.0122 | +0.0090 to +0.0110 | +0.0070 to +0.0085 | +0.0119 to +0.0144 |
     | tp1.5_else_5m, reported | +0.0176 | +0.0166 | +0.0124 | +0.0201 |
     | tp1.5_else_5m, adjusted | +0.010 to +0.012 | +0.008 to +0.010 | +0.008 to +0.009 | +0.012 to +0.015 |
     | flow0.5_else_6h, reported | +0.0177 | +0.0160 | +0.0120 | +0.0192 |
     | flow0.5_else_6h, adjusted | +0.004 to +0.008 | +0.0035 to +0.0069 | +0.003 to +0.006 | +0.006 to +0.010 |

     hold_6h is unaffected by this assumption: +0.0173, +0.0149, +0.0084, +0.0146 with churn removed. So with a realistic response, hold_6h beats every early-exit and flow schedule, and the schedule ranking in report sections 2-4 and 14 does not hold. Section 10 shows 0.5 and 0.0 as a "crude bound", but every other section reports scale 1.0, and the data put the realistic value near 0.25.
   - **Bias: optimistic.** About 35-55% for all_at_T and tp schedules, 60-80% for flow schedules.

2. **MATERIAL (for the benchmark): creator sells routed through relay or router contracts are not attributed to the creator, so `actual_outcome` understates real creators.** Curve events record the calling contract as `who`, and `KNOWN_ROUTERS` lists only 2 addresses.
   - **Evidence (t11, t12, t13).** A single caller that never bought on the curve sells 98-102% of the creator's inventory in one sell in 421 sep28 launches and 268 oct06 launches.
     - These come from 24 and 15 distinct contracts respectively, for example 0x07da9da1 (127 launches) and 0xb3ea566c. The latter is a sell-only contract with 1283 sells and 0 buys.
     - In the clean cohort, 136 of the 377 sep28 "creator never traded" launches are actually full exits of this kind.
   - **Evidence, effect of reattribution.** Reattributing these sells to the creator moves actual pnl_cons from +0.0046 to +0.0133 on sep28 and from +0.0005 to +0.0110 on oct06. The share of real creators who sold within 6 h goes from 0.66 to 0.81 and from 0.65 to 0.80.
   - **Knock-on effects.** `side_first_sell_t` is wrong in the feature table, which feeds the template flag. Report section 1 is wrong ("sold in 6 h", first-sell times, pnl).
   - **Effect on the simulation itself: negligible and slightly pessimistic.** The relay sale is replayed as an outside sell of transferred tokens, so the inventory is sold twice. Fixing this changes the simulated P&L by +0.0002 to +0.0005.
   - **Bias: actual P&L biased low,** so the "simulation beats real creators" gap is overstated. After the fix, real creators' marked P&L (+0.0274 on sep28, +0.0214 on oct06) is at or above simulated all_at_30s.

3. **MATERIAL for the 0.25 ETH-and-up cohorts, minor for 0.025-0.25: the template flag uses hindsight.** It looks at same-day launches after this one and at outcomes: the real creator's median first sell, the bot share (from full-day actor classes), and outside ETH in the first 60 s.
   - **Evidence, 0.025-0.25 (t8).** It removes 33/947, 47/1166, 69/1247 and 0/610 launches (sep27, sep28, oct01, oct06). On sep28, all_at_30s gives +0.0175 with the filter and +0.0176 without it. An ex-ante flag based only on recurrence (no outcomes) gives +0.0184. So it is immaterial here.
   - **Evidence, 0.25 ETH and up on oct06 (t8b).** It removes 115 of 173 launches. These are one script: an identical 0.35 ETH configuration, real median first sell at 7 s, and 1.7% of launches bought by a bot within 3 s.
     - Their simulated P&L is negative: tp2.0_else_6h −0.0108, all_at_30s −0.0076.
     - The walk-forward cell oct06 0.25-0.5 tp2.0_else_6h is +0.0550 [+0.0019, +0.1240] with n=35. Putting the group back gives +0.0046 [−0.0091, +0.0214] with n=150.
   - **Why the exclusion is questionable.** Criterion (a), the real creator's exit time, is irrelevant to a counterfactual that replaces that exit anyway. It is, however, correlated with the demand those configurations receive (bots avoid them).
   - **Bias: optimistic** for large-buy cohorts.

4. **MINOR (material on sep28): volume-bot churn is counted as genuine taxable demand.**
   - **Evidence (t19, t20).** Churners here are single-launch wallets with at least 10 trades and a flat net position.
     - On sep28 they produce 12% of cohort outside volume and 17% of simulated tax.
     - In the largest launch they produce 75% of its 65 ETH volume: many wallets with exactly 34 trades each.
     - Removing them changes all_at_30s from +0.0175 to +0.0150 on sep28 (−14%). The change is −3% on sep27, −5% on oct01 and −3% on oct06.
     - The largest sep28 launch drops from +1.96 to +0.735 ETH.
   - **Why it matters.** If the creator ran or hired these wallets, the tax is self-paid and the 1% platform fee on that volume (about 0.49 ETH on that launch) is a cost the simulator never books.
   - **Bias: optimistic.**

5. **MINOR: the replay does not conserve tokens.** Sells by wallets of tokens they did not buy on the curve (`excess`) are replayed in absolute amounts. That covers router attribution, relay exits and transfers.
   - **Evidence, scale (t10, t14).** Excess tokens average 0.97x the creator's inventory per launch on sep28 and 1.87x on oct06.
     - Under all_at_30s on sep28, the curve's X falls below X0 in 305 of 1119 launches.
     - The creator is paid more ETH than the curve really holds in 78 launches (all_at_30s) and in 362 launches (hold_6h).
   - **Evidence, effect (t15).** Capping each outside sell at the tokens actually outstanding raises P&L by +0.0001 (all_at_30s) to +0.0010 (hold_6h). The phantom sells mainly add sell pressure.
   - **Bias: slightly pessimistic,** but the replay is internally inconsistent.

6. **MINOR (bug): the creator tax rate is wrong when the launch buy is dust.**
   - **Cause.** `tax = L.tier − 0.01` with `tier = (pf+ct)/q`. For launch buys of 1e-18 to 2e-18 ETH, the fees round to zero, so tier = 0 and tax = −1% instead of `tax_bps` (10%).
   - **Evidence (t2, t17).** This affects 66, 35 and 10 launches (sep27, sep28, oct06). Simulated tax is −0.004, −0.001 and −0.011 ETH against actual +0.036, +0.012 and +0.111 ETH. None of these launches are in the clean cohort.
   - **Bias: pessimistic** (for tax-only creators). Fix: use `L.tax_bps/1e4`.

7. **VERIFIED OK: curve math, fees and the creator-tax round trip.**
   - **Replay (t1).** Observed tokensOut and gross (q+pf+ct) are reproduced to under 1e-9 relative error for 114,902 buys and 95,092 sells (sep28) and for 49,612 buys and 42,475 sells (oct06).
     - The exceptions are 4 launches per day, which drift 0.07-1.3% after one point (probably a state change that is not logged), plus wei-dust sells.
     - The sell platform fee is exactly 1% of gross on every non-dust sell, with no snipe surcharge on sells.
     - The creator tax (`ct`) equals `tax_bps` × q on buys and × gross on sells, on every non-dust trade.
     - value − q0 = 0.0005 on all 3,273 sep28 and 2,132 oct06 launches, confirming the launch fee.
   - **No-op test (t3).** `simulate(keep_side=True)` with no creator sell reproduces the observed final X to under 1e-9, except in 4 and 3 launches.
   - **Tax round trip.** The launch buy costs q−ct, a sell pays gross×0.99, and tax income comes only from rows outside the creator side. There is no double counting.
   - **Flow formula (t17).** `tk = Y·W/(X−W)` returns gross = W exactly (maximum relative error 7e-11 over 100k random states), and f=1 restores the pre-buy state exactly. The code comment "at the current marginal price" is wrong: this is the exact sale value including slippage. The sale also lands 0.5 s later, so the realized gross ≠ W. Neither is a bias.

8. **VERIFIED OK (minor issues): `actual_outcome` arithmetic** (sells q+ct, buys q−ct, plus outside `ct`) is correct for the side as defined. Its problem is the side definition (finding 2).
   - Actual sells carry no `GAS_SELL`, while the simulation charges 0.00002 ETH per sell. This is negligible.
   - `GAS_CREATE` = 0.001 ETH is about 13x too high: one sampled creation cost 3.82M gas × 0.020 gwei = 7.7e-5 ETH (t-RPC). This is conservative.

9. **VERIFIED, NOT A SOURCE OF OPTIMISM: event ordering, the 0.5 s latency, and the time-rule placement.**
   - **Time-rule placement (t9).** For T = 5, 15, 30 and 60 s, landing the sell exactly at T, 1 ms earlier, or with a random 0-3 s delay changes P&L by at most 0.0003. Only 1% of (launch, T) pairs have an outside trade within 0.05 s of T.
   - **Latency.** Raising latency from 0.5 s to 12 s changes the tp, trail, flow and ladder schedules by at most +0.001. Longer latency is marginally better.
   - **Clock check (t22).** Buys paying the second-1 surcharge have derived t of 0.1-3.2 s, and second-2 buys have 0.5-4.2 s. So the block-to-seconds conversion is good to about 2 s.
   - **Revert tolerance (t18).** Changing TOL from 0.02 to 1.0 moves P&L by at most 0.0003.

10. **MINOR: outside sells modelled as fractions of holdings.** The aggregate sensitivity is small. Both directions exist:
    - **Understated impact.** Holders who would exit on the creator's first tranche keep their observed, later sell times. This helps multi-tranche schedules. A "panic" variant (any holder who sells after the creator's first sell dumps everything) changes half_30s_rest_tp2 and ladder by −0.0004 to −0.0007, and all_at_30s by 0 (t10).
    - **Overstated impact.** Wallets that really sold because the real creator dumped still sell at that time in a counterfactual where the creator holds. This hurts hold and late schedules.
    - **Router aggregation.** Because `who` aggregates many users behind a router, a user's sell of directly bought tokens through the router is replayed in absolute amount, even when that user's counterfactual buy reverted (feeds finding 5).

11. **MINOR: the first-timer definition is inconsistent across days.**
    - `creations_week` covers 2026-09-21 00:00 to 09-28 10:01. So October days have no prior-week lookback, and on sep21 (the report's new design day) the lookback starts the same day.
    - At least 0.4% (oct01) and 0.9% (oct06) of "clean" creators had launched on an earlier censused day. This is a lower bound.
    - It is not hindsight. Direction unclear.

12. **MINOR: graduation is not modelled.** On sep28, 3 clean launches graduated on the real tape and 4 cross 4.2 ETH under hold_6h. In those, the creator keeps selling into the bonding curve after graduation. Negligible count.

13. **UNVERIFIED, HIGH-LEVERAGE ASSUMPTION: creator tax is paid to the creator wallet at trade time.** Tax is about 80% of the reported P&L. I could not confirm this on-chain:
    - the public RPC returns "historical state not available" for balance deltas;
    - `debug_traceTransaction` is not available;
    - the RPC rate-limited me (HTTP 429).

    If the tax accrues to a claimable balance, goes to a configurable recipient, or is forfeited when a curve does not graduate, every number changes. One archive-node balance delta, or a read of the contract, would settle it.

## Verdict

- **Not an upper bound.** The base case (`after_sell_scale=1`) is optimistic for every schedule that exits before 6 h: by roughly 1.5-2x for all_at_T and tp schedules and 3-5x for flow schedules (finding 1). Churn (finding 4) and, for large buys, the hindsight template filter (finding 3) add to that. Some conventions err the other way, so the bias is not uniformly upward: creation gas, the dust tax bug, token conservation and relay double-sells are all pessimistic.
- **Not a central estimate for the early-exit or flow schedules,** and the schedule ranking is an artifact of the no-response assumption.
- **Closest to central: hold_6h** (+0.008 to +0.017 ETH per launch on a stake of about 0.06 ETH, churn removed). It does not depend on post-exit demand.
- **What survives:** a positive mean of roughly +0.007 to +0.015 ETH per launch for simple exits once corrected. But the median is negative in every cell (−0.0008 to −0.0022). Only 28-47% of launches make money, and the mean depends on the 5% tail and on the unverified tax-payment assumption (finding 13).
- **The benchmark is also off.** The "actual creators" figures are biased low (finding 2), so comparisons that show the simulator beating real creators are not reliable.
