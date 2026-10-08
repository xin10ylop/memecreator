# Creator-side launch research on Pons V2 (Robinhood Chain)

What makes automated buyers buy a freshly launched token, which of those characteristics go with real
follow-through, and what a creator who launches a legitimate token and sells their own launch-block inventory into
that demand could realistically make. Seven full UTC days of every Pons V2 launch and every bonding-curve trade in the
six hours after each (Sep 14, Sep 21, Sep 27, Sep 28, Oct 1, Oct 3, Oct 6 2026), 42,484 launches, 2.57 million
trades, pulled from the public chain; the launchpad mechanics from the `xin10ylop/fomo-memebot` study of the buyers'
side; an independent adversarial audit of the simulator (`out/audit_simulator.md`), whose corrections are applied.

Every table cited is in `out/`. Nothing here simulates fake buyers, wash trades, bundle wallets or promotion. The
creator studied is a wallet's first launch, with no named exempt wallets, sent by the creator, and not a
configuration already launched ten or more times earlier that day by three or more addresses (the "clean" cohort).

## 0. The answers

**What type of launch is most likely to attract real automated buyers?** A creator buy of 0.05-0.25 ETH in the
launch block, quoted in ETH, with a website link and an image, a low creator tax, from a wallet with no earlier
launch. On the seven days this moves the share of launches that an automated buyer hits within 3 seconds from about
20% (dust buys) to 55-80%, and the share with any outside buy within 10 seconds to 65-90%. The strongest single
lever is the creator's own buy; the second is a website link; a creator tax of 4% or more and a repeat launch from the
same wallet each cut participation by half or more. Named exempt wallets (a team bundle) draw the most flow of all and
are excluded here by design.

**How much follow-through can we expect?** Little, and it is the same on every day. For that configuration the median
launch draws 0.03-0.12 ETH of outside buying in the first minute and the mean 0.15-0.4 ETH; 5-14% of launches reach
twenty genuine buyers in six hours (30% once, on Sep 14, for 0.1-0.25 ETH buys); under 1% graduate. The price is at
the creator's entry one minute in (median multiple 1.00), 3-11% below it at five minutes, 6-13% below at one hour; it
is above entry at one hour on 4-14% of launches. The automated buyers that arrive first are small (median 0.01-0.04
ETH a buy), gone within a minute, and lose money as a class on every one of the seven days. The follow-through that
exists comes from human app flow and slower scanner bots, and it is predicted by the presence of human buyers in the
first ten seconds (43-51% chance of 0.1 ETH more within five minutes) far better than by bots (14-29%) or by anything
in the launch configuration (out-of-sample AUC 0.56-0.73).

**How profitable could creator inventory distribution realistically be?** Modest in the mean, negative in the median,
and not where the money is. Selling the whole launch-block inventory 30 seconds in, into the real tapes, returns
+3% to +10% of the stake on average for 0.025-0.1 ETH buys and +5% to +19% for 0.1-0.25 ETH buys, with the sale
positive on only 21-55% of launches. The creator's total mean income on such a launch is +0.013 to +0.026 ETH
($33-68) before any behavioural response, of which 75-85% is the creator tax on outside volume, and 77-87% of that tax
is earned after the creator has already sold. When outside buying after the creator's exit is scaled to what real
dumps are followed by (the audit measured 0.2-0.35 of matched controls), the mean falls to +0.007 to +0.012 ETH
($20-33) and holding the inventory for six hours earns more than any early exit. The median launch loses the launch fee
and gas ($2-5). The top 5% of launches carry 62-73% of all positive P&L. A creator running 20 such launches has a 0-4%
chance of a negative total, a 10th-percentile total of +0.03 to +0.09 ETH and a median of +0.19 to +0.35 ETH on about
1.2 ETH of working capital, before the behavioural adjustment; a hundred launches a median of +1.2 to +2.4 ETH on
6 ETH, about 20-40%. It does not scale: a second launch from the same wallet earns a quarter of the first.

**The falsification verdict.** The strategy as framed ("configure the launch to attract bots, sell into them") does
not survive its own test. Configurations chosen on the first day to maximize bot participation earned less than the
plain cohort on every one of the six later days; across 104 configuration cells on seven days the correlation between
a cell's bot share and its return is -0.17. Launches that an early bot does hit earn three to six times more than
launches it does not, but that is the bot selecting launches that would get flow, not the creator buying flow: the
configuration predicts the bot's choice with an AUC of 0.6-0.7 and the follow-through worse than that. The exit
schedule does not matter at the precision the data allows (the best schedule of one day beats the median schedule of
the next day in three of six transitions), and the one schedule that is robust to the behavioural response is the one
that does not sell early. What a legitimate creator earns on Pons is the launchpad's fee on volume, on the minority of
launches that happen to draw a crowd, plus a small and tail-driven sale; the sale into the bots is close to zero-sum
and the bots know it.

## 1. Scope, data, definitions

**Mechanics (from fomo-memebot sections 20, 24.46-24.47, verified here).** Every Pons V2 token trades on a constant
product curve with virtual reserves X0 = 1.68 ETH and Y0 = 1e9 tokens until 4.2 ETH of net inflow graduates it to a
Uniswap v4 pool. Every trade pays a 1% platform fee and a creator tax of 0-20% (0, 1, 2, 3% typical) set at creation;
buys in the creation second pay a 93-98% snipe surcharge, in the next second +6.18%, in the one after +0.19%; wallets
named in the creation calldata are exempt. The creator's launch-block buy is part of the creation transaction and is
the only trade at the virgin price. Replaying every trade of the censuses with these rules reproduces the observed
token and quote amounts to 1e-12 (`src/pons_census.py`; the audit confirmed 1e-9 on 114,902 buys and 95,092 sells
of Sep 28 with four exceptions). The creator tax is accounted per trade in the curve's events; the prior study decoded
its claim path (a locker contract, claimed by the creator address, gas only). Whether it is paid at trade time or
claimable later was not verified on-chain here; the P&L below counts it as income and says what changes if it is not.

**Data.** Two censuses from fomo-memebot (Sep 27, Sep 28) and five pulled during this study with the same collector
(`src/collect/`): every factory launch of the UTC day, the creation calldata (quote asset, creator tax, named wallets,
name, symbol, image, socials), and every curve Buy/Sell for six hours after each launch, with block numbers converted
to seconds at the day's block rate (about 2 s accuracy). The creation history of Sep 21-28 gives a one-week lookback
for "first launch from the wallet" on the September days; the October days have only the same-day lookback (0.4-0.9%
of their clean cohort launched on an earlier censused day).

| day | launches | curve trades | standard ETH launches with a launch buy | clean cohort, 0.025-0.25 ETH | ETH/USD |
|---|---|---|---|---|---|
| Sep 14 | 16,162 | 1,059,750 | 10,553 | 2,204 | 2,477 |
| Sep 21 | 8,565 | 521,345 | 6,182 | 1,320 | 2,645 |
| Sep 27 | 3,604 | 218,656 | 3,056 | 846 | 2,696 |
| Sep 28 | 4,166 | 287,075 | 3,273 | 1,043 | 2,688 |
| Oct 1 | 4,604 | 244,421 | 3,630 | 1,146 | 2,685 |
| Oct 3 | 2,898 | 169,800 | 2,524 | 740 | 2,668 |
| Oct 6 | 2,485 | 114,721 | 2,132 | 594 | 2,710 |

ETH/USD is the CoinGecko daily close; the simulation tables convert at a flat 2,650 $/ETH, so their dollar figures are
within 7% of the daily rate. ETH is the unit that matters.

**Actors.** The curve event names its caller, which is a wallet or a router contract that aggregates many users. Per
day, callers with 20 or more launches are classed by behaviour: `router` (4+ buys a launch, dispersed sizes: the Pons
app router and a few others, i.e. human flow), `bot_sniper` (median first buy within 3 s, median hold under 30 s),
`bot_early_holder` (within 3 s, holds longer), `bot_late` (20+ launches, arrives later: scanners and followers);
`multi` is 5-19 launches; `other` is a wallet seen on fewer than five. "Genuine" buyers are everything outside the
creator side that is not a bot class. Creator exits sent through a relay contract (a caller that never bought and sells
half to all of the creator's remaining inventory in one trade) are attributed to the creator (audit finding 2; 9-57%
of clean launches, by cohort).

**Clean cohort.** First launch from the wallet (same day and, where the history exists, prior week), no named exempt
wallets, creation sent by the creator address, standard launch path, ETH quote, and not a configuration (exact buy
amount, tax, named count, sender type, social slots, image) already launched ten or more times earlier that day by
three or more addresses. The last rule uses only information available at the launch's own time; the earlier
outcome-based template flag is reported as a sensitivity (section 7.9) and changes the 0.025-0.25 ETH results by
under 5%.

**Walk-forward.** Every choice (configuration, schedule) is made on the earliest day and read untouched on the six
later days. Where a day-by-day choice is tested, the choice on day d is read on day d+1 only.

## 2. Who buys a fresh launch

`out/signals.txt` section (D2), `out/fleet_profiles.txt`. Per day, the early automated classes are a few dozen
callers: 17-40 snipers, 30-69 early holders, 96-760 late bots. Their buys are small, median 0.01-0.04 ETH for snipers,
0.006-0.011 ETH for early holders, 0.008-0.02 ETH for late bots. As classes they lose money on every day (unsold at
zero): snipers -1 to -6 ETH a day, early holders -5 to -27, late bots -23 to -98, the 5-19-launch wallets -82 to
-210. The human flow through the app routers and the one-launch wallets together put 1.4-1.8 thousand ETH a day into
fresh curves on the September days and 0.7-1.2 thousand in October; they are the money.

Of the outside ETH that sits on a clean 0.025-0.25 ETH launch 30 seconds in (what a creator selling then would be
selling into): routers 12-39%, late bots 10-36%, early-holder bots 10-17%, snipers 5-17%, 5-19-launch wallets 12-20%,
one-launch wallets 6-17% (`out/creator_sim.txt` section 7).

## 3. What makes the bots buy

`out/signals.txt` sections (A), (B0), (B), (C). All figures are for the clean cohort unless stated; a pattern is
reported only if it holds on every day.

**The creator's own buy is the lever.** Share of launches with a bot buy within 3 s, outside ETH in the first minute
(mean / median), and share reaching twenty genuine buyers in six hours, by launch-block buy, ranges over the seven days:

| creator buy (ETH) | bot within 3 s | any outside buy within 10 s | outside ETH, first 60 s | twenty genuine buyers in 6 h |
|---|---|---|---|---|
| under 0.003 | 11-24% | 18-35% | 0.05-0.10 / 0.000 | 0-4% |
| 0.003-0.01 | 18-39% | 27-47% | 0.05-0.12 / 0.000-0.006 | 1-6% |
| 0.01-0.025 | 26-45% | 33-55% | 0.07-0.12 / 0.000-0.010 | 1-9% |
| 0.025-0.05 | 38-57% | 48-67% | 0.09-0.16 / 0.001-0.02 | 2-6% |
| 0.05-0.1 | 49-64% | 62-69% | 0.14-0.21 / 0.03-0.09 | 4-7% |
| 0.1-0.25 | 54-80% | 70-83% | 0.16-0.39 / 0.03-0.12 | 8-30% |
| 0.25-0.5 | 57-88% | 71-94% | 0.21-0.79 / 0.03-0.31 | 2-37% |

The dose-response is monotone on every day up to 0.5 ETH. Above about 1 ETH (40% of supply and more) the pattern
breaks: those launches are mostly operators, the bots that do buy them are few, and the price falls to 0.4-0.6x by the
hour. The creator's share of supply says the same thing as the buy (a 2-5% share is bought within 3 s on 51-61% of
launches, 10-20% on 22-88%, the spread being Oct 6's one scripted operator).

**Creator tax.** Zero tax draws the most bots (51-82% within 3 s) and the most early money (0.09-0.23 ETH in a
minute) but earns nothing; 1% draws 58-65% and earns 0.006-0.013 ETH a launch; 1.5-2.5% draws 42-55% and earns
0.015-0.025; 3% draws 34-71% and earns the most, 0.026-0.046; 4% and above draws 14-47% and almost no money. The
bots discount the tax rate they will pay on the way out; the creator's income from the tax rises with the rate up to 3%
because the volume falls more slowly than the rate rises.

**Presentation.** A website link raises bot participation by 8-22 points, first-minute outside ETH by 30-80% and the
odds of twenty genuine buyers from 3-7% to 9-14%, on every day. An image matters on the days with many image-less
launches (Sep 14: 25% of launches positive with no image against 39% with one). A Telegram link adds a little to
follow-through (7-12% against 5-7%), an X profile link nothing (three quarters of launches have one), a linked X post
nothing consistent. A copied name or symbol is not penalised. The hour of the day shows no pattern that holds across
days.

**Named exempt wallets.** Three to nine named wallets raise first-minute outside ETH to 0.53-0.73 ETH and the share
with twenty genuine buyers to 24-28%; ten or more to 0.39-0.50 ETH and 15-19%; none, 0.12-0.15 ETH and 4-6%. The
named wallets are the team's own bundle, exempt from the snipe tax; the flow that follows them is the bots chasing a
pump (fomo-memebot section 20.5) and, often, the team's own unnamed wallets. It is the most effective lever in the data
and it is manufactured demand; it is not part of the design here.

**Quote asset.** USDG-quoted launches are 3-4% of the population; their bot share is lower on three of six days and
higher on three, their genuine-buyer share higher but on 22-129 launches a day. Inconclusive; the ETH quote is the
population the bots work.

**Supply, curve, liquidity.** Every Pons V2 curve has the same supply and the same virtual reserves, so there is no
lever there; the creator's buy sets the only visible difference in curve state at creation, and it is covered above.

**Repeat launches.** A wallet's second launch of the day with an otherwise identical configuration is bought by a bot
within 3 s on 17-42% of launches against 45-61% for first launches, draws a third to half the outside ETH, and
returns +4% to +20% on the buy against +22% to +44% (`out/creator_sim.txt` section 16); from the tenth launch of the day
it returns about zero. The bots filter repeat launchers, as the prior study found on Sep 3. Rotating fresh wallets to
defeat that filter is the serial-launcher pattern this study excludes.

**Multivariate.** Logistic models on the configuration (log buy, buy thresholds, tax, named, socials, image,
description, copycat, prior launches, helper-sent, hour), fit on one day and scored on the others, clean cohort: a bot
within 3 s AUC 0.59-0.71, three or more buyers within a minute 0.62-0.71, 0.1 ETH in the first minute 0.59-0.67,
0.2 ETH of follow-through between 10 s and 5 min 0.56-0.68, twenty genuine buyers 0.61-0.73. The top decile of the
score hits a bot 57-83% of the time (base 40-50%) and twenty genuine buyers 11-23% (base 4-6%). The coefficients that
hold their sign on every fit: the creator buy, the image, the website, zero tax (positive); a tax of 3% and above
(negative). The configuration tells you a bot is somewhat more likely; it does not tell you money is coming.

## 4. The initial rush against the follow-through

`out/signals.txt` section (D), first-time creators. The rush is outside buying in the creation second and the two
after it; follow-through is outside buying from 3 s to 5 min; late is 5 min to 6 h. Means per launch: rush 0.04-0.06
ETH, follow 0.29-0.41, late 0.19-0.32. The rank correlation between rush and follow is +0.20 to +0.39.

What is in the first ten seconds predicts the next five minutes mostly through who is there:

| first 10 s | share with 0.1 ETH more in the next 5 min | mean follow ETH | twenty genuine buyers in 6 h | median peak |
|---|---|---|---|---|
| no outside buy | 7-18% | 0.04-0.10 | 1-3% | 1.00 |
| bots only | 14-29% | 0.14-0.33 | 2.5-8.5% | 1.03-1.10 |
| at least one human or router buyer | 43-51% | 0.51-1.00 | 19-29% | 1.35-1.61 |

By count and size: one or two outside buyers with under 0.05 ETH give 8-30% odds of 0.1 ETH more; five to nine buyers
with 0.2-1 ETH give 52-62% odds, a 13-20% chance of twenty genuine buyers and a median peak of 1.6x; ten or more
buyers with at least 1 ETH (44-71 launches a day) give 89-97% odds, 82-96% twenty-genuine-buyer odds and a median
peak of 3.9-5.0x. The threshold at which buying continues is therefore about five distinct buyers and 0.2 ETH inside
ten seconds, and it is the number of buyers, especially non-bot buyers, that matters, not the ETH.

## 5. Which fleets go with the strongest subsequent buying

`out/signals.txt` section (E), `out/fleet_profiles.txt`. For each automated caller on 20 or more launches, the ETH
other wallets put in from 10 s to 5 min on the launches it bought within 10 s, against launches in the same creator-buy
bucket it did not buy (lift = ratio of means). Lifts of 4-18x exist: a scanner bot that buys 0.02-0.05 ETH about five
seconds in (`0xb1000000…`) is followed by 4-8x the outside money on every September day and on Oct 6, and itself
loses 54-63% of what it spends; a 0.15-0.18 ETH buyer at two seconds that sells one second later (`0x5b7e7cdf…`) carries
a 5-6x lift; the fastest sniper (`0xe268a3a4…`, 0.7 s, 0.005 ETH, 2 s hold) carries 4-8x in September and 0.26x on
Oct 6. The ranking does not persist: of the fleets active on Sep 14, only seven are still active on any later day, and
the rank correlation of their lifts from Sep 14 is -0.18 to +0.64, mostly about zero (`out/signals.txt` section E).
A six-day run with Sep 21 as the fit day (re-run `src/analyze_signals.py sep21 sep27 sep28 oct01 oct03 oct06`) found
+0.48 and +0.78 to Sep 27/28 and +0.22 to +0.44 to the October days for the ten fleets common to those days: within a
week the smart fleets stay smart, across three weeks the roster turns over. The fleets rotate (the Oct 2+ "sprayer"
contracts the prior study found are not in the September tapes), their stakes are tiny, and the lift is selection: the
smart fleets buy the launches that already show the signs of section 4. A creator cannot invite a particular fleet; the
fleets pick.

The bigger picture from the prior study still holds: the fleet that mattered on Sep 3 (one wallet spending $107k in six
hours at $614 a launch, +29% a trade) is gone; the automated classes of mid-September to October are small, fast and
net losers, and the first legal outside seat was measured at about zero on the exact curve from Sep 7 onward.

## 6. The creator simulation

`src/creator_sim.py`, `out/creator_sim.txt`. For every clean launch, the creator's own later trades (including relay
exits) are removed from the tape and replaced by a pre-committed schedule; every outside trade is a real one. Outside
buys keep their gross ETH and fee rate (including the time-keyed snipe surcharge) and receive what the modified curve
gives, reverting if that is more than 10% short of what they really received; outside sells sell the same fraction of
the wallet's position as observed, plus tokens it received by transfer, capped at what outsiders hold; state-triggered
sells land 0.5 s after their trigger. The creator pays the launch buy less the returned tax, 0.0005 ETH launch fee,
0.001 ETH creation gas (about 13x a sampled real creation, so conservative) and 0.00002 ETH a sell, receives
gross x 0.99 on a sell, earns the creator tax on outside volume in the window, and values unsold inventory at zero
(section 7.6 marks it instead). With the creator's trades kept and no schedule, the replay reproduces the observed
curve state on 500 of 500 launches; with a single sell placed at the real creator's time it is within 2% of the real
proceeds on 1,683 of 1,774 single-exit launches. 27 schedules: sell all at T seconds (5 s to 1 h), take-profit
multiples with a time fallback, a ladder, "sell tokens worth half of each outside buy", a trailing stop, half at 30 s and
the rest on a double, and hold six hours.

### 6.1 What the actual creators made (exact, no counterfactual)

Section 1 of `out/creator_sim.txt`. With unsold inventory marked at the last curve price less 3%, the clean cohort's
real exits returned, per launch, mean / share positive:

| creator buy | Sep 14 | Sep 21 | Sep 27 | Sep 28 | Oct 1 | Oct 3 | Oct 6 |
|---|---|---|---|---|---|---|---|
| 0.025-0.05 | +0.012 / 28% | +0.017 / 28% | +0.014 / 35% | +0.014 / 37% | +0.014 / 40% | +0.012 / 35% | +0.019 / 43% |
| 0.05-0.1 | +0.031 / 42% | +0.036 / 46% | +0.035 / 47% | +0.026 / 47% | +0.015 / 47% | +0.025 / 45% | +0.029 / 53% |
| 0.1-0.25 | +0.083 / 57% | +0.124 / 60% | +0.120 / 60% | +0.091 / 42% | +0.036 / 58% | +0.052 / 52% | +0.038 / 48% |

Medians are -0.001 to -0.002 ETH in the two smaller cohorts and about zero in 0.1-0.25. Real creators sold within six
hours on 82-95% of launches, median first sell 40-170 s; a quarter to a third of those exits went through relay
contracts. These are the people the bots have already filtered, on the days' flow; they are the reference the
schedules have to beat and they do not beat them by much.

### 6.2 The schedules, and why they all look the same

Clean cohort, 0.025-0.25 ETH, mean P&L per launch (ETH), unsold at zero, base case (section 4 of the file):

| schedule | Sep 14 | Sep 21 | Sep 27 | Sep 28 | Oct 1 | Oct 3 | Oct 6 |
|---|---|---|---|---|---|---|---|
| all at 30 s | +0.0235 | +0.0256 | +0.0197 | +0.0186 | +0.0126 | +0.0151 | +0.0207 |
| all at 5 min | +0.0297 | +0.0302 | +0.0214 | +0.0199 | +0.0131 | +0.0181 | +0.0201 |
| take 1.5x else 5 min | +0.0272 | +0.0278 | +0.0200 | +0.0186 | +0.0136 | +0.0165 | +0.0210 |
| half of each buy | +0.0271 | +0.0252 | +0.0197 | +0.0183 | +0.0127 | +0.0169 | +0.0197 |
| hold 6 h | +0.0216 | +0.0259 | +0.0207 | +0.0196 | +0.0106 | +0.0154 | +0.0167 |
| median | -0.0013 to -0.0020 on every schedule and day | | | | | | |
| share positive, all at 30 s | 37% | 40% | 43% | 41% | 46% | 39% | 48% |

The schedules agree because the mean is not the sale. Decomposition (section 13), all at 30 s:

| creator buy | sale P&L as % of the buy (mean), 7 days | sale positive on | creator tax as % of the buy |
|---|---|---|---|
| 0.025-0.05 | +3% to +9% | 21-38% | 27-45% |
| 0.05-0.1 | +6% to +10% | 31-49% | 13-36% |
| 0.1-0.25 | +5% to +19% | 32-55% | 9-33% |

The sale component is a few percent of the stake and positive on a minority of launches; the tax is two to five times
it. Selling everything on a double (take-profit 2x, else six hours) lifts the 0.1-0.25 ETH cohort's sale to +12% to
+42% of the buy, but it is positive on only 14-34% of launches: a lottery on the 5% of launches that run.

### 6.3 Schedule selection does not survive a day

Section 14. The schedule with the highest mean on day d, read on day d+1, against the median schedule of day d+1:
Sep 14 to 21, the pick (take 3x) reads +0.0293 against a median of +0.0272; Sep 21 to 27, +0.0214 against +0.0206;
Sep 27 to 28, +0.0204 against +0.0190; Sep 28 to Oct 1, +0.0128 against +0.0127; Oct 1 to 3, +0.0199 against +0.0167;
Oct 3 to 6, +0.0198 against +0.0203. The spread across all 27 schedules on a day is 0.003-0.007 ETH; the swing in the
whole cohort from one day to the next is as large. There is no schedule to optimize; the day decides.

### 6.4 The behavioural response, and the ranking that reverses

The base case keeps every outside buy that really happened after the real creator's exit, as if the creator's selling
did not change anyone's mind. The audit's event study on the real tapes (real dumps of at least 80% of the inventory
between 15 and 300 s, against matched launches whose creator had not sold) puts outside volume in the following hour
at 0.09-0.49 of the controls, central 0.2-0.35. Scaling every outside buy that arrives after the creator's first sell
(section 10 of the file; four columns: 1.0 / 0.5 / 0.25 / 0.0):

| schedule | Sep 14 | Sep 21 | Sep 27 | Sep 28 | Oct 1 | Oct 3 | Oct 6 |
|---|---|---|---|---|---|---|---|
| all at 30 s | .0235/.0155/.0115/.0075 | .0256/.0168/.0123/.0079 | .0197/.0140/.0112/.0083 | .0186/.0132/.0106/.0079 | .0126/.0091/.0073/.0056 | .0151/.0101/.0075/.0050 | .0207/.0150/.0121/.0091 |
| all at 5 min | .0297/.0253/.0231/.0209 | .0302/.0240/.0209/.0178 | .0214/.0179/.0162/.0145 | .0199/.0163/.0145/.0127 | .0131/.0111/.0102/.0092 | .0181/.0153/.0139/.0125 | .0201/.0167/.0151/.0134 |
| half of each buy | .0271/.0151/.0092/.0029 | .0252/.0138/.0078/.0016 | .0197/.0098/.0049/-.0001 | .0183/.0096/.0051/.0005 | .0127/.0067/.0036/.0005 | .0169/.0092/.0053/.0013 | .0197/.0110/.0064/.0017 |
| hold 6 h | .0216 | .0259 | .0207 | .0196 | .0106 | .0154 | .0167 |

At the realistic 0.25 the 30-second exit earns +0.007 to +0.012 ETH ($20-33) a launch and holding six hours earns
more on every day; the "sell into each buy" schedules, the ones closest to the brief's idea of distribution into
demand, fall to a third or less of their base and to about zero at the bound. The reason is in the tax: 77-87% of the
tax the 30-second exit books is earned after the exit, on volume the exit itself would discourage. Removing the volume
churners (callers with ten or more trades on a launch and a flat position; 12% of volume and 17% of tax on Sep 28)
takes a further 15-30% off the tax (section 10, "ex-churn").

### 6.5 Capacity: how much inventory can be sold at break-even

Section 11, on the observed flow with the creator's own trades removed. At 30 s the whole inventory is worth at least
its cost on 21-38% of 0.025-0.05 ETH launches, 31-49% of 0.05-0.1 and 32-55% of 0.1-0.25; the median share of inventory
sellable at an average price at or above entry is 0.14-0.26, 0.54-0.97 and 0.77-1.00 respectively (larger buys sit lower
on the curve, so more of the inventory clears at cost). At five minutes the shares fall to 8-27% of launches whole, and
at one hour to 4-15%. The window in which the inventory can be distributed at or above cost, where it exists, is the
first minute.

### 6.6 Risk, concentration, stress

Section 15: resampling the day's clean 0.025-0.25 ETH launches, selling at 30 s, base case. Twenty launches (about 1.2
ETH of launch buys): P(total < 0) 0-4%, 10th percentile +0.03 to +0.09 ETH, median +0.19 to +0.35, 90th +0.54 to +1.24.
A hundred launches (5.5-6.9 ETH): median +1.2 to +2.4 ETH, 10th percentile +0.7 to +1.3. With the behavioural scale at
0.5 the hundred-launch median is +0.85 to +1.65 ETH. Section 9: the top 5% of launches carry 62-73% of the positive
P&L on every day; 44-212 launches a day (of 594-2,204) make more than 0.05 ETH. Section 5: at the Sep 1-2 congestion
gas price (creation 0.01 ETH instead of 0.001) the mean falls by 0.009 ETH to +0.003 to +0.016 and the share of positive
launches to 17-31%. Section 6: marking unsold inventory at the last price instead of zero changes nothing for the
schedules that liquidate and little for hold.

### 6.7 The strategy as framed, tested

`src/design_eval.py`, `out/design_eval.txt`. On the design day (Sep 14) the single-factor cells with the most bot
participation are a 0.1-0.25 ETH buy (60%), zero tax (82%), a website (64%) and an image (57%); the cells with the
highest mean P&L are the same buy, a 3% tax, a website and an image. Read on the six later days (all at 30 s, clean,
0.025-0.25 ETH), mean P&L per launch:

| configuration | Sep 21 | Sep 27 | Sep 28 | Oct 1 | Oct 3 | Oct 6 |
|---|---|---|---|---|---|---|
| plain clean cohort (n = 594-1,320) | +0.0256 | +0.0197 | +0.0186 | +0.0126 | +0.0151 | +0.0207 |
| most bots: 0.1-0.25 ETH, zero tax (n = 15-51) | +0.0197 | +0.0060 | +0.0096 | +0.0045 | +0.0082 | +0.0017 |
| highest P&L: 0.1-0.25 ETH, 3% tax (n = 3-21) | +0.0910 | +0.0688 | +0.0193 | +0.0466 | +0.0104 | -0.0017 |

The bot-maximizing configuration draws the bots (65-80% within 3 s) and earns less than the plain cohort on all six
days: with no tax its income is the sale alone, +2% to +14% of the buy. The P&L-maximizing configuration is the tax
one; it beats the cohort on four days with 3-21 launches a day and confidence intervals that include zero on five of
six. Across 104 single-factor cells on the seven days the correlation between a cell's bot share and its return on the
buy is -0.17, and with its sale return +0.18. At the launch level the bots are a strong marker: clean launches a bot
bought within 3 s returned +0.018 to +0.044 ETH (49-61% positive) against +0.005 to +0.011 (17-36%) for the rest. The
creator cannot buy that marker with the configuration; the bots award it to launches that look like they will get flow,
and their guess is right often enough that they are the signal rather than the cause.

## 7. Regime

`out/regime_windows.txt` (the five earlier windows from fomo-memebot's per-launch summaries, 12:00-18:00 UTC, ETH
launches, one-off creators), against the seven full days here.

| window | one-off creators' sale as actually timed, % of stake, 0.01-1 ETH buys | share hitting 1.5x at any point |
|---|---|---|
| Aug 12 (launchpad week two) | +1.5% to +4% | 3-13% |
| Aug 20 (fee trough) | +11% to +25% | 11-23% |
| Aug 27 (ramp) | +6% to +32% | 18-50% |
| Sep 2 (peak week) | +20% to +36% | 18-59% |
| Sep 3 (fee peak) | +27% to +57% | 25-74% |
| Sep 14 to Oct 6 (this study, simulated 30 s exit) | +3% to +19% | peak above 1.5x on 10-25% |

On Sep 3 the prior study counted 185 sniper wallets, the fastest spending $614 a launch; the automated classes of
Sep 14-Oct 6 spend $25-110 a launch. The launchpad's gas subsidy ended at the turn of the month and launches fell
from 16,162 (Sep 14) to 2,485 (Oct 6) a day, but the clean cohort's per-launch numbers did not fall with them: the
seven days read +0.013 to +0.026 ETH mean with no trend, the bots' participation 45-61%, the follow-through the same.
What changed between early and mid September is the size of the money chasing launches; what did not change
afterwards is that it is small.

## 8. Falsification tests and what they left standing

- **Out of sample, walk-forward.** Every configuration and schedule choice is made on Sep 14 and read on six later
  days; day-to-day schedule picks are read on the next day only. The bot-maximizing design loses to the plain cohort on
  six of six days; the schedule pick beats the median schedule on three of six transitions.
- **Survivor and selection bias.** The population is every launch of the day, dead ones included; the median launch
  loses the fee. First-timer, no-named, self-sent and the prior-recurrence rule use only information available at
  creation. The outcome-based template flag is a sensitivity only; it moves the 0.025-0.25 ETH band by under 5% and
  the 0.25-0.5 ETH band by up to 2x on one day (Oct 6), which is why that band is not relied on.
- **Operator contamination.** All first-time wallets with templates and bundles included read +0.018 to +0.031 ETH
  against +0.013 to +0.026 clean: operators inflate the naive number by 30-50%. Fresh-wallet operators who do not
  repeat a configuration ten times a day cannot be separated from ordinary creators; what remains of them biases the
  clean cohort up, not down.
- **The behavioural response.** The fixed-flow assumption was the simulator's largest optimism (audit finding 1); it
  is bounded in section 6.4 with the audit's own measurement and reverses the schedule ranking.
- **Attribution of creator exits.** Relay exits were being counted as outsiders' sells; corrected (audit finding 2),
  which raised the real creators' numbers and left the simulation nearly unchanged.
- **Token conservation, dust-fee tier, churn.** Corrected or measured (audit findings 4-6); each under 0.001 ETH a
  launch except churn, which is 15-30% of the tax.
- **Mechanics.** Curve, fees and the snipe schedule reproduce every trade; schedule placement, latency (0.5-12 s) and
  the revert tolerance move results by under 0.001 ETH.
- **Not tested and material.** Whether the creator tax reaches the creator as income at these rates (it is about 80%
  of the mean); whether a human creator can place the launch buy and the sells at the assumed times from an app or a
  script; what the launchpad does to its fee split or snipe tax next; and whether the October regime, with the gas
  subsidy gone and launches at a sixth of the mid-September count, persists.

## 9. The launch the data supports, and what to expect from it

A legitimate launch that the evidence favours: ETH quote; a launch-block buy of 0.05-0.1 ETH ($135-270; 0.1-0.25
ETH if the capital at risk is acceptable, with the understanding that the tail is where its mean comes from); a creator
tax of 1-2% (3% earns more tax but loses a quarter of the bots; 0% is the bots' preference and the creator's loss); an
image, an original name, a website link; one launch per wallet; no named wallets, no helper contract, no bundle. Hold
the inventory rather than dump it: six hours earns at least as much as any exit once the response of the buyers to the
dump is priced, and the price is at or above entry for 30-50% of launches during the first minute if a partial sale at
cost is wanted. Expected on the seven days' flow, per launch, for the 0.05-0.1 ETH buy: a bot within 3 s on 49-64% of
launches, any buyer within 10 s on 62-69%, 0.14-0.21 ETH of outside buying in the first minute (median 0.03-0.09),
twenty genuine buyers on 4-7%, a median price 6% below entry at one hour; mean income +0.013 to +0.030 ETH ($35-80)
with the tax counted and the flow unresponsive, +0.010 to +0.020 with the response priced, median -$4, positive on
41-56% of launches, the top 5% of launches carrying two thirds of the gain. That is the number before the question of
whether the tax is collectible and before gas moves.

What would change the answer: a return of large, slow automated buyers (the Sep 3 regime, when a one-off creator's
sale alone paid +27% to +57% of the stake); a change in the snipe-tax schedule or the fee split; evidence that the
creator tax does or does not reach the creator; a week of October data showing the launch count stabilizing or
collapsing further. The scripts in `src/` re-run on any new census day in minutes.

## Appendix: files

| file | content |
|---|---|
| `out/signals.txt` | sections (A) base rates, (B0) clean cohort, (B) all first-timers, (C) models, (D) rush vs follow-through, (D2) bot sizes and P&L, (E) fleets |
| `out/fleet_profiles.txt` | the 25 busiest early automated buyers per day: speed, size, hold, what they select, realized P&L, lift |
| `out/creator_sim.txt` | sections 1-16 of the simulation (actual creators, schedule grid, walk-forward, fixed schedules, stress, marking, counterparties, templates, concentration, demand response, capacity, cohort profile, decomposition, schedule walk-forward, batch risk, repeat launches) |
| `out/design_eval.txt` | the configuration walk-forward and the bot-share correlations |
| `out/regime_windows.txt` | the Aug 12 - Sep 3 windows from fomo-memebot's per-launch summaries |
| `out/audit_simulator.md` | the independent audit of the simulator; its findings 1-6 are addressed in the code and the text above |
| `data/features_<day>.json.gz`, `data/actors_<day>.json` | per-launch configuration, metadata and outcomes; per-caller classes |
| `data/census_<day>.json.gz`, `data/census_<day>_features.json` | the fresh censuses and their decoded metadata |
