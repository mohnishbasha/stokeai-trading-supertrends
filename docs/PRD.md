# Super Trends Market Agent: Product Requirements Document

| Field | Value |
|---|---|
| Document | `docs/PRD.md` |
| Product | Super Trends Market Agent (short form: Super Trends) |
| Version | 1.0.0 |
| Date | 2026-11-14 |
| Status | Approved for build (Step 1 baseline) |
| Owner | Mohinish Shaikh, Serverless Ventures LLC |
| License | Super Trends Community License (PolyForm Noncommercial License 1.0.0, SPDX `PolyForm-Noncommercial-1.0.0`). Source-available, free for noncommercial use. |

> **Source of truth.** This PRD is the source of truth for product behavior. It was seeded from `BUILD_PROMPT.md` and now supersedes it for anything it covers. `docs/ARCHITECTURE.md` is the source of truth for structure and contracts. Any change to the behavior described here follows the Spec Change Protocol (section 16): the PRD is updated in the same pull request as the code, or the PR states "internal only, no spec change", or a spec issue is filed and closed within the same sprint. Any change to a scoring formula, weight, or threshold is always updated in the same PR and also bumps `scoring.version` in `config/scoring.yaml`.

## Table of contents

1. Product summary
2. Users
3. The core feature and the daily loop
4. Honesty requirements
5. Disclaimer
6. User stories
7. Signal Engine Specification (verbatim)
8. Functional requirements
9. Non-functional requirements
10. Default scoring configuration (`config/scoring.yaml`)
11. Watchlist seed
12. Product surfaces reference (API, MCP, CLI, environments)
13. Glossary
14. Out of scope for v1
15. Traceability: user stories to functional requirements
16. Spec Change Protocol
17. Ambiguities and resolutions

---

## 1. Product summary

**Name:** Super Trends Market Agent. "Super Trends" in prose and UI; `supertrends` as the slug for the CLI, Python package, namespaces, and metrics.

**Tagline:** *Know which way the tape is leaning.*

**What it does.** Super Trends watches a list of stocks, applies the TradingView Supertrend algorithm together with eleven supporting technical and fundamental factors, including Ripster EMA Clouds, and turns the result into one composite score per ticker. Every trading day it publishes the three strongest buys and the two strongest sells in a web UI, each with the evidence and a plain-language justification. The same results are available through an HTTP API, a CLI, and an MCP server for AI agents.

**Where it runs.** The reference deployment is self-hosted on StokeAI infrastructure (k3s on NVIDIA DGX Spark, ARM64). Super Trends is a CPU-only workload. It consumes an LLM through the existing Stoke gateway (OpenAI-compatible) and deploys no models, GPUs, or cluster components. Canonical URL: `supertrends.openstoke.com`; staging: `supertrends-stage.openstoke.com`. A public DNS name does not mean public access: the default deployment is private (tailnet only).

**Relationship to other products.**
- **TastyStocks** is the long-form, fundamentals-first research memo with an 8-factor 0 to 100 model. Super Trends is the daily, technicals-first signal engine. Super Trends reuses the TastyStocks score bands (80 to 100, 65 to 79, 50 to 64, below 50) for its display score so the two products read the same way. Super Trends does not generate memos and does not replace TastyStocks.
- **Stoke / StokeAI** is the infrastructure Super Trends deploys on.

**What Super Trends is not.** It is not a broker, it places no orders, it holds no brokerage credentials, and it is not personalized investment advice. It never asks for or stores a user's holdings, account size, risk tolerance, or goals, and never outputs position sizes, options strikes or expiries, leverage, or order instructions. It is software for running your own analysis; it provides no signals service, and each user needs their own market data license.

**Licensing posture.** The repository is public and the project is source-available under the PolyForm Noncommercial License 1.0.0 (unmodified), copyright 2026 Serverless Ventures LLC. Anyone may read, run, modify, and share it for noncommercial purposes. Commercial use requires a separate written license from Serverless Ventures LLC (legal@serverlessvc.com). Every file, UI string, and package description calls it "source-available" and "free for noncommercial use"; no other licensing label is used. A running instance and its picks are private to its owner.

## 2. Users

| User | Description | Primary surfaces |
|---|---|---|
| Trader (primary) | One active equity and options trader who runs his own infrastructure and wants a disciplined, repeatable daily read on a watchlist. | Web UI (Today, Ticker, Watchlist, Track Record, Runs, Settings), CLI |
| AI agents (secondary) | Pi, Goose, OpenCode, and Claude Code, querying Super Trends through MCP. | MCP server (stdio and streamable HTTP), Pi extension |
| Operator | The same person in an operations role: deploys, upgrades, rolls back, and monitors the service on the Stoke cluster. | Helm chart, Flux, Grafana, alerts, CLI |

There are no user accounts in v1. Read endpoints are open inside the private network boundary; write actions require a bearer token.

## 3. The core feature and the daily loop

### 3.1 The core feature

The Today screen: three buy cards and two sell cards for the latest trading day, each with a score, the Supertrend state, a factor contribution breakdown, key price levels, and a written justification. This screen is the product. Everything else supports it.

### 3.2 The daily loop

1. After the US market close, a scheduled run ingests the day's bars for every watchlist ticker and the benchmarks (SPY, QQQ).
2. The indicator engine computes all indicators on daily and weekly bars, and buy/sell volume from intraday bars.
3. Twelve factor scores are computed per ticker. Regime and fundamentals adjust the weights. A composite score is produced.
4. Tickers are ranked. The top 3 qualifying buys and top 2 qualifying sells are selected.
5. A justification is written for each pick from the computed evidence.
6. Results are stored immutably and shown in the UI, the API, the CLI, and MCP.
7. Later runs measure how earlier picks performed and update the track record.

The scheduled run is a Kubernetes CronJob at `30 17 * * 1-5` in time zone `America/New_York`. On non-trading days the run command exits 0 with "market closed" and publishes nothing. The run moves through the states `queued -> ingesting -> computing -> scoring -> selecting -> narrating -> published | failed`, and publication is atomic (see FR-901 to FR-904).

## 4. Honesty requirements

These are functional requirements, not copy. Each is also expressed as one or more FRs (see the traceability notes in brackets).

- The algorithm is not always right, and the product says so. Every pick shows a confidence value and an invalidation level ("this view is wrong if price closes below X"). [FR-327, FR-503, FR-703]
- The Track Record screen shows every past pick and what happened next, including the losers. Picks are never edited or deleted after publication. [FR-607, FR-709]
- If fewer than 3 tickers qualify as buys or fewer than 2 as sells, Super Trends shows fewer. It never pads the list to hit the count. An empty side shows "No qualifying sells today" with the nearest candidate and the reason it missed. [FR-407, FR-408, FR-704]
- Buy/sell volume is an estimate derived from bar data. The UI labels it "estimated order flow" and shows the data quality level. Super Trends never claims to see the real order book. [FR-218, FR-714]
- Every screen that shows a recommendation carries the disclaimer text defined in section 5. [FR-713, FR-803, FR-813, FR-816]

Related rules that follow from honesty:
- Backtest results are labeled as hypothetical everywhere they appear. [FR-612]
- Statistics with fewer than 20 samples are labeled "small sample", and every statistic shows its sample size. [FR-604, FR-605]
- Losing picks are shown with the same prominence as winners. [FR-709]
- Every number shows its as-of date; Super Trends is an end-of-day product and never presents a fake "live" feel. [FR-718]
- No certainty language anywhere: "guaranteed", "sure thing", "can't lose", "will go to" never appear in UI copy or narratives. [FR-506, FR-509, FR-719]

## 5. Disclaimer

The disclaimer appears on every screen, API payload, CLI output, and MCP result that contains a pick. The text is exactly:

> Super Trends output is general market analysis generated by an algorithm from technical and fundamental data. It is not investment advice, not a recommendation tailored to you, and not an offer to buy or sell any security. The algorithm can be and often is wrong. Past and backtested performance does not predict future results. You are responsible for your own decisions.

The API returns it in a top-level `"disclaimer"` field of every payload that contains picks. Every MCP tool description ends with: "Informational market analysis only. Super Trends places no trades and gives no personalized advice." A surface that shows a pick without the disclaimer is a `priority:p0` bug.

Compliance posture that accompanies the disclaimer:
- Super Trends produces general, impersonal market analysis for its owner. It is not a registered investment adviser and does not give personalized advice.
- No brokerage integration and no brokerage credentials. This is a hard boundary for v1.
- The default deployment is private (tailnet only). The product adds no public sharing features. Before giving anyone else access, sharing picks publicly, or charging for them, the owner talks to a securities lawyer (recorded in the owner checklist).
- Market data is shown only to the owner by default; the owner confirms the vendor plan permits the intended use (recorded in the owner checklist).

## 6. User stories

US-001 to US-020 are the seed set and are reproduced verbatim. US-021 onward extend them.

| ID | Story |
|---|---|
| US-001 | As a trader, I open Super Trends in the morning and see yesterday's close-of-day top 3 buys and top 2 sells without clicking anything. |
| US-002 | As a trader, I read why each pick was made in under 30 seconds: a short narrative plus a factor-by-factor breakdown. |
| US-003 | As a trader, I see the Supertrend line, its direction, and how many bars ago it flipped for any ticker. |
| US-004 | As a trader, I manage a watchlist: add, remove, and group tickers, and seed it from a default list. |
| US-005 | As a trader, I open a ticker and see a chart with Supertrend, SMAs, Fibonacci levels, and support and resistance drawn on it. |
| US-006 | As a trader, I see the full ranked watchlist with scores so I can look past the top 5. |
| US-007 | As a trader, I see the invalidation level for every pick so I know when the view is wrong. |
| US-008 | As a trader, I review the track record: hit rate and average forward return for buys and sells at 1, 5, 10, and 20 trading days, against SPY. |
| US-009 | As a trader, I see which regime each ticker is in (trending, ranging, transitional) and how that changed the weights. |
| US-010 | As a trader, I am warned when a pick has earnings within 5 trading days. |
| US-011 | As a trader, I can trigger a run manually and watch its progress. |
| US-012 | As a trader, I can browse any past date and see exactly what was published that day, with the scoring config that produced it. |
| US-013 | As a trader, I can tune weights and thresholds in a config file, and every result records which config version produced it. |
| US-014 | As a trader, I can backtest a config over history before trusting it. |
| US-015 | As an agent, I call `supertrends_recommend` over MCP and receive today's picks with evidence as structured JSON. |
| US-016 | As an agent, I call `supertrends_analyze` with a ticker and receive the full factor breakdown. |
| US-017 | As an operator, I deploy Super Trends to the Stoke k3s cluster with one Flux HelmRelease and roll back with one command. |
| US-018 | As an operator, I see run health, data freshness, and provider errors in Grafana. |
| US-019 | As a trader, if the LLM is down, I still get picks with a template-written justification. |
| US-020 | As a trader, if market data is missing or stale for a ticker, that ticker is excluded and flagged, never scored on bad data. |
| US-021 | As a trader, I see a confidence value for every pick and which conditions lowered it (extreme volatility, degraded data, weekly conflict, event risk). |
| US-022 | As a trader, when fewer tickers qualify than the maximum on a side, I see only the qualifying ones, and an empty side shows "No qualifying buys today" or "No qualifying sells today" with the nearest candidate and the reason it missed. |
| US-023 | As a trader, I see near-duplicate tickers that also qualified but were skipped by the correlation guard, and which selected pick each one duplicates. |
| US-024 | As a trader, I see buy/sell volume labeled "estimated order flow" with its data quality level, so I never mistake it for real order book data. |
| US-025 | As a trader, I see "day N on the list" for a ticker that has been picked on consecutive trading days. |
| US-026 | As a trader, I filter the Today screen and the ranking table by watchlist group (for example semis, fab-7, country-etfs) without changing the published overall picks. |
| US-027 | As a trader, I see which watchlist tickers were excluded or unresolved and why (stale, insufficient history, unresolved symbol, needs review). |
| US-028 | As a trader, I see the expected one-day move (ATR) and the key support, resistance, Fibonacci, and next-target levels on every pick card. |
| US-029 | As a trader, I see a fundamentals summary and the earnings countdown for a ticker, and whether its fundamentals data is current, stale, or missing. |
| US-030 | As a trader, I run `supertrends today`, `supertrends analyze TICKER`, and `supertrends rank` in a terminal and get the same results as the UI, with `--json` for scripting. |
| US-031 | As an agent, I call `supertrends_rank`, `supertrends_status`, `supertrends_track_record`, `supertrends_watchlist`, and `supertrends_run` over MCP, and write actions are refused without the token. |
| US-032 | As a trader using Pi, I use `/supertrends today`, `/supertrends analyze <ticker>`, and `/supertrends rank`, and see streaming progress when I trigger a run. |
| US-033 | As an operator, I am alerted when no run is published for the latest completed session by 19:00 ET, when data is stale, when provider errors exceed 20 percent for 15 minutes, or when narrative fallback exceeds 50 percent of a run. |
| US-034 | As an operator, I back up the database to a file and restore it, and old intraday data is pruned automatically without breaking any pick's evidence. |
| US-035 | As a trader, I start a demo with synthetic data, with no API keys, network, or cluster, and verify that every product function works. |
| US-036 | As a trader, I see the disclaimer on every screen, payload, CLI output, and MCP result that contains a pick. |
| US-037 | As a trader, I see the active scoring config, its version, and its hash in Settings, and the provider and LLM health status. |
| US-038 | As a trader, I see on the Ticker screen the history of this ticker's scores and every day it appeared as a pick. |
| US-039 | As a trader, I read the track record with sample sizes next to every statistic and a "small sample" label below 20 samples, and backtest figures are always labeled hypothetical. |
| US-040 | As an operator, a failed or interrupted run never replaces the last good published result, and two simultaneous triggers start only one run. |

---

## 7. Signal Engine Specification (verbatim)

This section is copied verbatim from the seed specification. Formulas, tables, weights, thresholds, and code blocks are not weakened, summarized, or simplified. Heading levels are adjusted to fit this document; the text is unchanged. References such as "See S2-T02" point to tasks in `docs/SPRINT_PLAN.md`. Section 17 records where the literal reading is ambiguous and how the implementation resolves it.

This is the heart of the product. Implement it exactly. All parameters live in `config/scoring.yaml`; the values below are the defaults.

### 7.1 Conventions

- Bars are OHLCV, split and dividend adjusted, in exchange time (America/New_York). Daily bars are primary. Weekly bars are resampled from daily (week ending Friday). Intraday bars are 5-minute, regular session only.
- Minimum history to score a ticker: 250 daily bars. Below that the ticker is `insufficient_history` and excluded.
- Every factor returns a **factor score** in the closed range -100 (max bearish) to +100 (max bullish), a list of **evidence items** (name, value, unit, human reason), and a **quality** flag (`ok`, `degraded`, `missing`).
- `clip(x, a, b)` bounds x to [a, b]. `RMA` is Wilder's smoothing: seeded with the SMA of the first n values, then `rma[t] = (rma[t-1] * (n-1) + x[t]) / n`. `EMA` uses alpha = 2/(n+1), seeded with the SMA of the first n values.
- Trend direction convention inside Super Trends: `+1` is up (bullish), `-1` is down (bearish). Note that TradingView's `ta.supertrend` returns the opposite sign (negative means up). Super Trends converts at the boundary and documents it; never mix the two conventions.

### 7.2 Factor 1: Supertrend (the lead factor)

Match TradingView's built-in Supertrend with defaults ATR length 10 and factor 3.0.

```
hl2[t]        = (high[t] + low[t]) / 2
tr[t]         = max(high[t]-low[t], |high[t]-close[t-1]|, |low[t]-close[t-1]|)
atr[t]        = RMA(tr, 10)[t]
basic_up[t]   = hl2[t] + 3.0 * atr[t]
basic_lo[t]   = hl2[t] - 3.0 * atr[t]

final_up[t]   = basic_up[t]  if basic_up[t] < final_up[t-1] or close[t-1] > final_up[t-1]
                else final_up[t-1]
final_lo[t]   = basic_lo[t]  if basic_lo[t] > final_lo[t-1] or close[t-1] < final_lo[t-1]
                else final_lo[t-1]

if atr[t-1] is undefined:            dir[t] = -1   (down, matches TradingView warm-up)
elif st[t-1] == final_up[t-1]:       dir[t] = +1 if close[t] > final_up[t] else -1
else:                                dir[t] = -1 if close[t] < final_lo[t] else +1

st[t]         = final_lo[t] if dir[t] == +1 else final_up[t]
```

Derived values: `st_dir_d` (daily direction), `st_dir_w` (weekly direction), `bars_since_flip`, `st_distance_atr = (close - st) / atr` (signed), `st_line` (the invalidation level).

Factor score:

```
base      = +60 if st_dir_d == +1 else -60
weekly    = +25 * st_dir_d if st_dir_w == st_dir_d else -15 * st_dir_d   (weekly agreement strengthens, conflict weakens)
freshness = +15 * st_dir_d if bars_since_flip <= 5 else 0        (a fresh flip is the strongest signal)
stretch   = -10 * st_dir_d if |st_distance_atr| > 4 else 0       (far from the line: late entry)
score     = clip(base + weekly + freshness + stretch, -100, 100)
```

Parity requirement: on the golden fixtures, Super Trends's Supertrend line matches a TradingView export to within 0.01 per bar after warm-up (first 100 bars ignored), and direction matches on every bar. See S2-T02.

### 7.3 Factor 2: SMA analysis

SMA 20, 50, 200 on daily closes.

```
+30 / -30   close above / below SMA200
+25 / -25   SMA50 above / below SMA200
+20 / -20   close above / below SMA50
+15 / -15   SMA20 slope over 5 bars positive / negative
+10 / -10   golden cross / death cross (SMA50 vs SMA200) within the last 10 bars
score = clip(sum, -100, 100)
```

### 7.4 Factor 3: MACD

MACD(12, 26, 9) on daily closes: `line = EMA12 - EMA26`, `signal = EMA9(line)`, `hist = line - signal`.

```
+35 / -35   line above / below signal
+25 / -25   line above / below zero
+25 / -25   hist rising / falling for 3 consecutive bars
+15 / -15   bullish / bearish signal cross within the last 3 bars
score = clip(sum, -100, 100)
```

Weekly MACD is computed and reported as evidence. If weekly `line` vs `signal` disagrees with daily, multiply the factor score by 0.75.

### 7.5 Factor 4: Divergences

Oscillators: RSI(14, Wilder), MACD histogram, OBV. Pivots: a pivot low at bar p is a low lower than the 5 bars on each side; pivot high is the mirror. A pivot is confirmed 5 bars after it forms, so a divergence is only known 5 bars late. Never use an unconfirmed pivot (NFR-007).

Within the last 60 bars, compare the two most recent confirmed pivot lows (and separately the two most recent pivot highs):

```
regular bullish:  price lower low,   oscillator higher low
regular bearish:  price higher high, oscillator lower high
hidden bullish:   price higher low,  oscillator lower low     (trend continuation)
hidden bearish:   price lower high,  oscillator higher high
```

Only divergences whose second pivot is within the last 15 bars count.

```
RSI divergence        +/- 40
MACD hist divergence  +/- 35
OBV divergence        +/- 25
hidden divergences count at half value
if the same divergence type also exists on weekly bars (pivot width 3): multiply the total by 1.25
score = clip(sum, -100, 100)
```

### 7.6 Factor 5: Mean reversion

```
z       = (close - SMA20) / stdev20                      (population stdev of 20 closes)
pct_b   = (close - lowerBB) / (upperBB - lowerBB)         (Bollinger 20, 2.0; evidence only)
rsi     = RSI(14)
z_part  = -60 * clip(z / 2.5, -1, 1)                      (stretched up is bearish, stretched down is bullish)
rsi_part= +40 if rsi <= 30; -40 if rsi >= 70; else linear from +40 at 30 to -40 at 70
score   = clip(z_part + rsi_part, -100, 100)
```

This factor fights the trend factors on purpose. The regime weighting below decides who wins.

### 7.7 Factor 6: Fibonacci retracement

Swing detection: ZigZag on daily closes over the last 120 bars with a reversal threshold of `max(8%, 3 * ATR%)` where `ATR% = atr14 / close`. Take the most recent completed leg A to B (B is the last confirmed swing extreme). Levels are measured from B back toward A: 23.6, 38.2, 50.0, 61.8, 78.6 percent. Extensions 127.2 and 161.8 percent are computed for evidence and for the narrative's "next level" line.

For an up leg (A low, B high) with price pulling back:

```
near(level) = |close - level| <= 0.5 * atr14
holding     = close[t] > close[t-1] and low[t] >= level - 0.5 * atr14
+60  near 38.2 and holding
+70  near 50.0 and holding
+80  near 61.8 and holding
-50  close below the 78.6 level (the swing has failed)
+20  close above B (leg resumed; next target is the 127.2 extension)
 0   otherwise
```

Mirror every rule for a down leg (A high, B low) with the signs flipped. If no leg qualifies, score 0 with quality `degraded`.

### 7.8 Factor 7: Support and resistance

Collect confirmed pivot highs and lows (width 5) over the last 250 bars. Cluster pivots whose prices are within `0.5 * atr14` of each other. A cluster is a level; its strength is `touches * recency_weight` where recency decays linearly from 1.0 (today) to 0.3 (250 bars ago). Keep the 4 strongest levels above price (resistance) and 4 below (support). Add the 52-week high and low as levels.

```
d_s   = (close - nearest_support) / atr14          (>= 0)
d_r   = (nearest_resistance - close) / atr14       (>= 0)
rr    = d_r / max(d_s, 0.25)
base  = clip((rr - 1) * 40, -60, 60)               (room above vs room below)
+40   close above a resistance level that was intact yesterday, with relative volume >= 1.5
-40   close below a support level that was intact yesterday, with relative volume >= 1.5
score = clip(base + breakout, -100, 100)
```

`relative volume = volume / SMA20(volume)`.

### 7.9 Factor 8: Volatility

```
atr_pct        = atr14 / close
atr_pct_rank   = percentile rank of atr_pct over 252 bars
bbw            = (upperBB - lowerBB) / SMA20
bbw_rank       = percentile rank of bbw over 126 bars
hv20           = stdev of 20 daily log returns * sqrt(252)

squeeze        = bbw_rank < 15
expansion      = bbw_rank > 85 and bbw rising 3 bars

+30 * st_dir_d   if squeeze            (compressed volatility tends to resolve with the trend)
+20 * st_dir_d   if expansion and close moved in st_dir_d direction over 3 bars
score = that sum, then multiplied by 0.5 if atr_pct_rank > 90
```

Volatility also feeds confidence (see Confidence) and position-agnostic risk evidence: `expected_1d_move = atr14`, shown on every card.

### 7.10 Factor 9: Volume oscillator

TradingView's Volume Oscillator, short 5, long 10:

```
vo        = 100 * (EMA5(volume) - EMA10(volume)) / EMA10(volume)
ret5      = close[t] / close[t-5] - 1
vo_part   = clip(vo * 2, -60, 60) * sign(ret5)          (rising volume confirms the 5-bar move, falling volume fades it)
obv_slope = sign of the least-squares slope of OBV over 20 bars
obv_part  = 40 * obv_slope
score     = clip(vo_part + obv_part, -100, 100)
```

Note the sign logic: positive `vo` with a falling price is bearish (selling on rising volume). Negative `vo` gives a negative `vo_part` in an up move (a rally on fading volume) and a positive one in a down move (a decline on fading volume).

### 7.11 Factor 10: Buy / sell volume (estimated order flow)

From 5-minute regular-session bars, classify each bar's volume:

```
if high > low:   buy = volume * (close - low) / (high - low);  sell = volume - buy
else:            buy = volume if close >= prev_close else 0;   sell = volume - buy
daily_delta      = sum(buy) - sum(sell)
delta_pct        = daily_delta / sum(volume)
delta_pct_10     = mean of delta_pct over the last 10 sessions
cmf20            = Chaikin Money Flow over 20 daily bars
score            = clip(delta_pct_10 * 300, -50, 50) + clip(cmf20 * 200, -50, 50)
```

Quality levels, stored and shown:
- `intraday`: 5-minute bars available for at least 8 of the last 10 sessions.
- `daily_estimate`: intraday missing; apply the same formula to daily bars. Factor weight is multiplied by 0.6.
- `trades` (optional upgrade, behind a provider capability flag): tick rule classification from trade prints. Not required for v1; the interface must allow it.

Also detect and report as evidence: accumulation days (up close on relative volume >= 1.5) and distribution days (down close on relative volume >= 1.5) in the last 20 sessions.

### 7.12 Factor 11: Fundamentals overlay

Refreshed weekly and on the day after an earnings report. Sub-scores, each clipped to its range:

```
revenue growth YoY (latest quarter)       +/- 20    linear: -10% -> -20, +20% -> +20
EPS growth YoY (latest quarter)           +/- 20    linear: -20% -> -20, +30% -> +20
gross margin change vs 4 quarters ago     +/- 15    linear: -3pt -> -15, +3pt -> +15
free cash flow margin (TTM)               +/- 15    linear: -5% -> -15, +20% -> +15
net debt / EBITDA                         +/- 10    <= 1 -> +10, >= 4 -> -10, linear between
valuation: forward P/E (or EV/Sales when earnings are negative) percentile vs own 3-year history
                                          +/- 20    10th pct -> +20, 90th pct -> -20
score = clip(sum, -100, 100)
```

ETFs and tickers with no fundamentals (QQQ, SPY) get quality `missing`; the factor's weight is redistributed proportionally across the other factors. Fundamentals older than 120 days are `degraded` and the weight is halved.

Earnings proximity: `days_to_earnings` (trading days) is stored per ticker. It is not part of the fundamentals score; it drives the event-risk rules below.

### 7.13 Factor 12: Ripster EMA Clouds

Match Ripster47's "Ripster EMA Clouds" TradingView indicator with its default settings: MA type EMA, source `hl2`, five clouds. A cloud is the band between a short and a long EMA of `hl2`, computed on daily bars.

| Cloud | Short / long EMA | Role in Super Trends |
|---|---|---|
| `c1` | 8 / 9 | pullback zone |
| `c2` | 5 / 12 | short-term trend |
| `c3` | 34 / 50 | trend bias: the line between bullish and bearish |
| `c4` | 72 / 89 | intermediate trend (evidence and levels only, not scored) |
| `c5` | 180 / 200 | long-term trend |

```
src             = hl2
ema_s, ema_l    = EMA(src, short), EMA(src, long)            for each cloud, EMA as defined in Conventions
top[t], bot[t]  = max(ema_s[t], ema_l[t]), min(ema_s[t], ema_l[t])
cloud_dir[t]    = +1 if ema_s[t] > ema_l[t] else -1           (TradingView colors the cloud green / red)
pos(c)[t]       = +1 if close[t] > top(c)[t], -1 if close[t] < bot(c)[t], 0 inside the cloud
stack[t]        = +1 if bot(c2)[t] > top(c3)[t]               (5/12 cloud fully above the 34/50 cloud)
                  -1 if top(c2)[t] < bot(c3)[t]               (5/12 cloud fully below the 34/50 cloud)
                   0 otherwise
```

Derived values: `rc_bias = pos(c3)`, `rc_stack = stack`, `rc_bars_since_stack_flip` (bars since `stack` last changed to its current nonzero value), `rc_c3_top` and `rc_c3_bot` (the 34/50 cloud edges, reported as the trend-bias level), and `rc_dir_w` (direction of the 34/50 cloud on weekly bars, evidence only).

Factor score:

```
bias      = 30 * pos(c3)               (above the 34/50 cloud is bullish, below is bearish, inside is 0)
trend     = 20 * cloud_dir(c2)
stacking  = 20 * stack
mid       = 10 * cloud_dir(c3)
long      = 10 * pos(c5)
pullback  = 10 * stack  if stack != 0 and, within the last 3 bars, price tested the 8/9 cloud from the trend side
                        (bullish: some low <= top(c1); bearish: some high >= bot(c1))
                        and close[t] is still on the trend side of it (bullish: close > bot(c1); bearish: close < top(c1))
            0 otherwise                (a held pullback into the 8/9 cloud is the preferred entry)
score     = clip(bias + trend + stacking + mid + long + pullback, -100, 100)
```

Parity requirement: on a TradingView daily export with the Ripster EMA Clouds indicator at default settings, computed on the exact bars in the export, every one of the ten EMAs matches within 0.01 per bar after a 200-bar warm-up, and every cloud direction matches on every bar after warm-up. See S2-T10.

### 7.14 Regime detection and dynamic weights

Base weights (sum 100):

| # | Factor | Base weight |
|---|---|---|
| 1 | Supertrend | 20 |
| 2 | SMA analysis | 7 |
| 3 | MACD | 8 |
| 4 | Divergences | 9 |
| 5 | Mean reversion | 7 |
| 6 | Fibonacci retracement | 5 |
| 7 | Support and resistance | 7 |
| 8 | Volatility | 4 |
| 9 | Volume oscillator | 6 |
| 10 | Buy / sell volume | 9 |
| 11 | Fundamentals | 8 |
| 12 | Ripster EMA Clouds | 10 |

Ripster EMA Clouds overlaps the moving-average and momentum factors, so its 10 points were taken mostly from SMA analysis (-3) and MACD (-2), and one point each from Divergences, Mean reversion, Fibonacci, Support and resistance, and Volatility.

Per-ticker regime from ADX(14) on daily bars:
- `trending`: ADX >= 25
- `ranging`: ADX < 20
- `transitional`: otherwise

Regime multipliers applied to the base weights, then renormalized to sum 100:

| Factor | trending | ranging | transitional |
|---|---|---|---|
| Supertrend | 1.25 | 0.70 | 1.00 |
| SMA analysis | 1.20 | 0.70 | 1.00 |
| MACD | 1.10 | 0.90 | 1.00 |
| Divergences | 0.90 | 1.20 | 1.00 |
| Mean reversion | 0.50 | 1.60 | 1.00 |
| Fibonacci | 1.00 | 1.10 | 1.00 |
| Support and resistance | 0.90 | 1.40 | 1.00 |
| Volatility | 1.00 | 1.00 | 1.00 |
| Volume oscillator | 1.00 | 1.00 | 1.00 |
| Buy / sell volume | 1.00 | 1.00 | 1.00 |
| Fundamentals | 1.00 | 1.00 | 1.00 |
| Ripster EMA Clouds | 1.20 | 0.70 | 1.00 |

Fundamental and event adjustments (applied after regime multipliers, before renormalizing):
- `days_to_earnings <= 5`: fundamentals weight x 1.5, and the pick carries the `event_risk` flag.
- Fundamentals score <= -40: the buy threshold for that ticker rises by 5 display points.
- Fundamentals score >= +40: the sell threshold for that ticker falls by 5 display points.

Market regime (benchmark filter) from QQQ and SPY daily Supertrend:
- Both down: `risk_off`. Buy threshold +5 for every ticker.
- Both up: `risk_on`. Sell threshold -5 for every ticker.
- Mixed: `neutral`. No change.

Every adjustment that fired is stored with the result and shown in the UI ("Weights adjusted: trending regime, earnings in 3 days").

### 7.15 Composite score, confidence, and bands

```
composite = sum(w_i * s_i) / sum(w_i)            over factors with quality != missing, range -100..100
display   = round((composite + 100) / 2, 1)      range 0..100
```

Bands on the display score (aligned with TastyStocks):

| Display score | Band |
|---|---|
| 80 to 100 | Strong Buy |
| 65 to 79.9 | Buy |
| 50 to 64.9 | Neutral, leaning up |
| 35.1 to 49.9 | Neutral, leaning down |
| 20.1 to 35 | Sell |
| 0 to 20 | Strong Sell |

Confidence (0 to 100):

```
agreement = share of total weight held by factors whose score has the same sign as composite     (0..1)
confidence = 100 * agreement
           - 15 if atr_pct_rank > 90
           - 10 if any factor quality is degraded
           - 10 if st_dir_w != st_dir_d
           - 10 if rc_stack == -st_dir_d          (the Ripster 5/12 vs 34/50 stack opposes the daily Supertrend)
           - 10 if event_risk
confidence = clip(confidence, 0, 100)
```

### 7.16 Selection rules

A ticker is a **buy candidate** when all hold: display >= 65 (plus any threshold adjustments), `st_dir_d == +1`, `rc_bias >= 0` (close not below the 34/50 cloud), confidence >= 50, data quality not `stale`, average 20-day dollar volume >= 20,000,000.

A ticker is a **sell candidate** when all hold: display <= 35 (minus any threshold adjustments), `st_dir_d == -1`, `rc_bias <= 0` (close not above the 34/50 cloud), confidence >= 50, data quality not `stale`, same liquidity floor.

"Sell" means bearish: reduce, exit, or avoid. Super Trends does not recommend short selling or any specific instrument, size, or expiry.

Ranking: buys by display descending; sells by display ascending. Tie-breakers in order: higher confidence, more recent Supertrend flip, higher relative volume, alphabetical ticker. Publish the top 3 buys and top 2 sells. Counts are config (`selection.max_buys`, `selection.max_sells`).

Correlation guard: the watchlist contains many near-duplicates (several S&P 500 ETFs, sector ETFs and their largest holdings). Walk each side's ranked candidates in order and skip any candidate whose 60-day return correlation with an already selected pick on that side is above 0.9, until the side is full or candidates run out. Skipped tickers are shown as "also qualified" with the pick they duplicate.

Stickiness rule: none in v1. Each day stands alone. A ticker may appear on consecutive days; the UI shows "day N on the list".

### 7.17 Justification

For each pick, store a structured evidence document:

```json
{
  "ticker": "ORCL", "date": "2026-11-13", "side": "buy",
  "display_score": 78.4, "confidence": 71, "band": "Buy",
  "regime": "trending", "market_regime": "risk_on",
  "supertrend": {"dir_d": 1, "dir_w": 1, "bars_since_flip": 3, "line": 212.40, "distance_atr": 1.2},
  "invalidation": {"level": 212.40, "rule": "daily close below the Supertrend line"},
  "levels": {"support": [215.1, 208.7], "resistance": [229.5, 236.0], "fib": {"61.8": 214.2}, "next_target": 236.0},
  "factors": [
    {"id": "supertrend", "score": 100, "weight": 23.4, "contribution": 23.4,
     "reasons": ["Daily Supertrend flipped up 3 bars ago", "Weekly Supertrend agrees"]}
  ],
  "adjustments": ["trending regime"],
  "flags": [],
  "config_hash": "sha256:..."
}
```

`contribution = weight * score / 100`, so contributions sum to the composite. Reasons are produced by deterministic templates in code, one per rule that fired.

Narrative: 3 to 5 sentences, written by an LLM from the evidence document only, through an OpenAI-compatible endpoint (on Stoke: the existing gateway in front of vLLM). Rules:
- The system prompt forbids any number, level, or claim not present in the evidence document, forbids price targets beyond `next_target`, forbids the words "guaranteed", "will", "can't lose", and forbids advice on position size, options, or leverage.
- Order: lead with the Supertrend state and the Ripster 34/50 cloud bias, then the two largest positive contributions, then the largest opposing factor ("what argues against it"), then the invalidation level.
- **Numeric guard:** after generation, extract every number from the narrative. Each must match a value in the evidence document within rounding. Any unmatched number rejects the narrative.
- On rejection, timeout (8 seconds), or endpoint error: retry once at temperature 0, then fall back to the deterministic template narrative. The stored narrative records `source: llm | template` and the model name.
- The narrative never changes a score, a rank, or a selection.

### 7.18 Track record

For every published pick store `entry_price = next session's open`. On later runs compute forward returns at 1, 5, 10, and 20 trading days, for the pick and for SPY over the same window. A buy "hit" is a positive excess return versus SPY; a sell "hit" is a negative excess return. Report hit rate, mean and median excess return, and worst pick, per side, per horizon, overall and by band, with the sample size next to every statistic. Statistics with fewer than 20 samples are labeled "small sample".

### 7.19 Backtest

`supertrends backtest --from YYYY-MM-DD --to YYYY-MM-DD --config config/scoring.yaml` replays the daily loop over stored history with no look-ahead (indicators at day t use bars up to t; entries at t+1 open; fundamentals use the value known at t). Output: the same track-record statistics plus an equity curve for "equal weight the daily buys, hold 5 days", against SPY. Backtest results are labeled as hypothetical everywhere they appear.

---

## 8. Functional requirements

Each functional requirement has an ID, a statement, and acceptance criteria in Given / When / Then form. Groups: Watchlist (FR-0xx), Ingestion (FR-1xx), Indicators (FR-2xx), Scoring (FR-3xx), Selection (FR-4xx), Justification (FR-5xx), Track record and backtest (FR-6xx), UI (FR-7xx), API / CLI / MCP (FR-8xx), Operations (FR-9xx). Every rule in the Signal Engine Specification (section 7) maps to at least one FR. Where an FR restates a formula, section 7 is authoritative; parameter names refer to keys in `config/scoring.yaml` (section 10).

### 8.1 Watchlist (FR-0xx)

#### FR-001: One default watchlist with named groups
The system holds exactly one default watchlist. Tickers belong to zero or more named groups; membership is many-to-many and each symbol is stored once and scored once per run.
- **Given** a symbol that is a member of three groups, **When** the watchlist is read, **Then** the symbol appears once with three group memberships, and a run produces exactly one score for it.

#### FR-002: Add a ticker
`POST /api/v1/watchlist/items` adds a symbol, optionally to one or more groups. The symbol must match `^[A-Z][A-Z0-9.\-]{0,9}$` and resolve against the active market data provider's reference data (on the fixture provider, the regex alone is the check).
- **Given** a valid bearer token and a symbol that resolves, **When** the add request is sent, **Then** the response is 201 and the symbol appears in the watchlist and is ingested on the next run.
- **Given** a symbol that fails the regex or does not resolve, **When** the add request is sent, **Then** the response is an RFC 9457 problem (422) whose detail names the reason, and the watchlist is unchanged.
- **Given** no bearer token or a wrong token, **When** the add request is sent, **Then** the response is 401 and nothing changes.

#### FR-003: Remove a ticker
`DELETE /api/v1/watchlist/items/{symbol}` removes a symbol from the watchlist (all group memberships). Historical bars, scores, and published picks for the symbol are kept.
- **Given** a valid token and a symbol on the watchlist, **When** the delete request is sent, **Then** the response is 204, the symbol is no longer scored on later runs, and its past recommendations still appear in the track record.
- **Given** a symbol not on the watchlist, **When** the delete request is sent, **Then** the response is 404 problem JSON.

#### FR-004: Manage groups
The trader can add a ticker to a group, remove it from a group, and list groups, through the API, the Watchlist screen, the CLI (`supertrends watchlist list|add|remove`), and the MCP `supertrends_watchlist` tool.
- **Given** a ticker in group `semis`, **When** the trader adds it to group `fab-7`, **Then** it belongs to both groups and is still stored once.

#### FR-005: Watchlist cap
The watchlist has a hard cap of 300 tickers.
- **Given** a watchlist with 300 tickers, **When** a 301st ticker is added, **Then** the response is 422 with a problem detail stating the cap, and the watchlist is unchanged.

#### FR-006: Seed on first start
On first start (empty watchlist tables), the system loads `config/watchlist.seed.yaml` (section 11): 14 groups, 200 unique equity and ETF symbols, benchmarks `[SPY, QQQ]`. The seed file is written exactly as given in section 11. Later starts do not reseed; the owner's later edits live in the database, not in git.
- **Given** an empty database, **When** the application starts, **Then** all 14 groups exist and every seed symbol is present with its group memberships.
- **Given** a database where the owner removed a seed symbol, **When** the application restarts, **Then** the symbol is not re-added.

#### FR-007: Unresolved seed symbols are never guessed
At first ingest every seed symbol is validated against the provider's reference data. A symbol that does not resolve is recorded with status `unresolved` and a reason, excluded from scoring, shown on the Watchlist screen, and added to `docs/OWNER_CHECKLIST.md`. It is never substituted with a guessed symbol.
- **Given** a seed symbol the provider does not recognize, **When** first ingest runs, **Then** the symbol has status `unresolved` with a reason, it is not scored, and no other symbol is added in its place.

#### FR-008: Needs-review symbols
Symbols listed under `needs_review` in the seed start excluded until the owner confirms them, except those whose note says only "may be missing" or "confirm the current symbol"; those are attempted and fall back to `unresolved` if they do not resolve.
- **Given** `CITI` under `needs_review` with a note that it is not a US-listed ticker, **When** the seed loads, **Then** `CITI` is stored as excluded pending review and is not ingested.
- **Given** `XIACF` with the note "may be missing from the provider", **When** first ingest runs and the provider does not resolve it, **Then** it becomes `unresolved` with the reason.
- **Given** the owner confirms a needs-review symbol, **When** the next run starts, **Then** the symbol is ingested and scored like any other.

#### FR-009: VIX is evidence only
`VIX` is never scored. It is ingested only if the provider offers the index, and it is exposed as evidence for the market regime.
- **Given** the provider offers VIX, **When** a run completes, **Then** VIX has no factor scores, never appears in rankings or picks, and its latest value appears in the market regime evidence.

#### FR-010: Crypto pairs kept but not ingested
Crypto pairs from the owner's lists are stored in `config/watchlist.crypto.yaml` with status `deferred: not ingested or scored in v1`. They are not loaded into the watchlist, ingested, or scored.
- **Given** the crypto file exists, **When** a run executes, **Then** no crypto symbol is fetched or scored.

#### FR-011: Benchmarks always ingested
`SPY` and `QQQ` (config `benchmarks`) are always ingested as benchmarks, even if removed from the watchlist, because the market regime and the track record depend on them.
- **Given** SPY was removed from the watchlist, **When** a run executes, **Then** SPY bars are still ingested, the market regime is computed, and SPY is not ranked unless it is on the watchlist.

#### FR-012: Watchlist reads are open, writes require the token
`GET /api/v1/watchlist` needs no token; all mutating watchlist operations on every surface require the bearer token.
- **Given** no token, **When** `GET /api/v1/watchlist` is called, **Then** it returns 200 with the watchlist and groups, including each symbol's status (`active`, `unresolved`, `needs_review`, `excluded`).

### 8.2 Ingestion (FR-1xx)

#### FR-101: Bar conventions
Bars are OHLCV, split and dividend adjusted, in exchange time (America/New_York). Daily bars are primary.
- **Given** a ticker with a 2:1 split in its history, **When** daily bars are stored, **Then** all prices before the split are adjusted so the series is continuous, and timestamps are exchange dates in America/New_York.

#### FR-102: Weekly resampling
Weekly bars are resampled from daily bars, with the week ending Friday (or the last trading day of that week when Friday is a holiday). Open is the first open, high the max high, low the min low, close the last close, volume the sum.
- **Given** a week with a Friday holiday, **When** weekly bars are resampled, **Then** that week's bar closes on Thursday's close and is labeled with the week ending date.

#### FR-103: Intraday bars
Intraday bars are 5-minute, regular session only (09:30 to 16:00 ET, or to the early close on half days).
- **Given** a provider response that includes pre-market and after-hours 5-minute bars, **When** they are stored, **Then** only regular-session bars are kept.

#### FR-104: Incremental, idempotent ingestion
Ingestion fetches per ticker from the last stored bar forward and upserts. For the daily update on the Massive provider it uses the grouped daily bars endpoint (one call per date for the whole market); per-ticker calls are used only for backfill, corporate actions, and intraday bars. `supertrends ingest` runs ingestion standalone; runs call the same function.
- **Given** a fully ingested database, **When** ingestion runs again for the same date, **Then** no rows change.

#### FR-105: Corporate actions
On detection of a new split for a ticker, the full adjusted history for that ticker is refetched.
- **Given** a split reported for ticker X today, **When** ingestion runs, **Then** X's full daily history is refetched and replaced with the newly adjusted series, and the event is logged.

#### FR-106: Trading calendar
The trading calendar is `exchange_calendars` XNYS, including half days and holidays.
- **Given** the last completed session was before a market holiday, **When** ingestion runs on the holiday, **Then** no ticker is marked stale because of the holiday.

#### FR-107: Data quality pass
After ingestion every ticker receives a data quality status: `ok`, `degraded`, `stale` (latest daily bar older than the last completed session), or `insufficient_history`. A ticker with a gap of more than 3 sessions in the scoring window is `degraded`.
- **Given** a ticker whose latest daily bar is two sessions old, **When** the quality pass runs, **Then** the ticker is `stale`.
- **Given** a ticker with a 4-session gap, **When** the quality pass runs, **Then** it is `degraded`.

#### FR-108: Minimum history
Minimum history to score a ticker is `min_history_bars` (default 250) daily bars. Below that the ticker is `insufficient_history` and excluded.
- **Given** a ticker with 249 daily bars, **When** a run scores, **Then** the ticker is excluded with reason `insufficient_history`. **Given** 250 bars, **Then** it is scored.

#### FR-109: Never score on bad data
Tickers that are `stale`, `insufficient_history`, `unresolved`, or pending review are excluded from scoring and selection, and each is listed in the run summary with its reason.
- **Given** a run where ticker ABC is stale, **When** the run publishes, **Then** ABC has no factor scores for the run, appears in `excluded` with reason `stale` in `GET /api/v1/recommendations/latest`, and is flagged on the Watchlist screen.

#### FR-110: Pluggable providers
`MarketDataProvider` (daily bars, intraday bars, splits and dividends; capability flags `intraday`, `trades`, `adjusted`) and `FundamentalsProvider` (quarterly financials, forward estimates if available, earnings dates) are typed protocols. A registry selects them from `SUPERTRENDS_MARKET_PROVIDER` and `SUPERTRENDS_FUNDAMENTALS_PROVIDER`; the two may be different vendors.
- **Given** `SUPERTRENDS_MARKET_PROVIDER=unknown`, **When** the app starts, **Then** it fails at startup with a message naming the unknown provider and listing valid names.
- **Given** a market provider of one vendor and a fundamentals provider of another, **When** a run executes, **Then** both are used without code changes.

#### FR-111: Fixture provider
A deterministic synthetic provider (seeded geometric Brownian motion with regime switches, gaps, a split, and volume patterns) produces 3 years of daily and 30 days of 5-minute bars for 12 synthetic tickers plus SPY and QQQ stand-ins. It powers dev, CI, kind, demo, and smoke tests. No vendor data is committed.
- **Given** the same seed, **When** the fixture provider generates data twice, **Then** the bars are identical, and the dataset includes at least one trending, one ranging, and one reversing ticker.

#### FR-112: Massive provider with rate limiting
The Massive (formerly Polygon.io) adapter supports daily aggregates, 5-minute aggregates, splits, dividends, and financials. Base URL is configurable (`https://api.massive.com` default; `https://api.polygon.io` legacy). A token bucket enforces `SUPERTRENDS_PROVIDER_RATE_PER_MIN` (default 5). 429 and 5xx responses are retried with exponential backoff and jitter. Responses are cached by (endpoint, params). Every call is recorded in `provider_calls` (provider, endpoint path, status, duration, timestamp) with no secret.
- **Given** a sequence of 429 responses followed by 200, **When** the adapter fetches, **Then** it retries with backoff and succeeds, and `supertrends_provider_rate_limited_total` increments.
- **Given** any call, **When** it is logged or recorded, **Then** the API key appears in no log line, error message, or `provider_calls` row.

#### FR-113: Unconfigured provider does not block startup
- **Given** no Massive API key, **When** the app starts, **Then** the Massive provider reports `unconfigured` in `GET /api/v1/status`, and the app starts on the fixture provider.

#### FR-114: Alternate provider
One alternate market data provider (Alpaca Market Data or Tiingo, chosen by ADR) implements the same interface and passes the same contract test suite.
- **Given** `SUPERTRENDS_MARKET_PROVIDER` set to the alternate, **When** a run executes, **Then** bars come from the alternate with no code change.

#### FR-115: Point-in-time fundamentals
Fundamentals are refreshed weekly and on the day after an earnings report. Every fundamentals row stores `known_at`, the time the value became known, and every consumer (live scoring and backtest) uses only rows with `known_at` at or before the scoring date.
- **Given** a fundamentals row with `known_at` = 2026-08-01, **When** a backtest scores 2026-07-31, **Then** that row is not used.

#### FR-116: Earnings calendar and days to earnings
Earnings dates are stored per ticker with a `confirmed` flag. `days_to_earnings` (in trading days, on the XNYS calendar) is computed and stored per ticker per run.
- **Given** a confirmed earnings date 3 trading days after the run date, **When** the run computes, **Then** `days_to_earnings` = 3 for that ticker.

#### FR-117: Liquidity statistics
Average 20-day dollar volume (mean of close times volume over the last 20 daily bars) is computed per ticker per run and stored on `tickers.avg_dollar_volume_20d`.
- **Given** 20 bars with close 10 and volume 3,000,000, **When** the run computes, **Then** average 20-day dollar volume is 30,000,000.

#### FR-118: Provider failures isolate per ticker
A provider error for one ticker marks that ticker's data per the quality rules and does not stop ingestion for other tickers. A provider outage for all tickers fails the run cleanly (FR-902).
- **Given** a provider timeout on ticker X only, **When** ingestion completes, **Then** X keeps its previous bars and becomes `stale` if its latest bar is older than the last completed session, and all other tickers are ingested.

### 8.3 Indicators (FR-2xx)

All indicator functions are pure (no I/O), take a pandas DataFrame or numpy arrays, and return arrays of the same length with NaN during warm-up.

#### FR-201: Smoothing primitives
`clip(x, a, b)` bounds x to [a, b]. `RMA` is Wilder's smoothing: seeded with the SMA of the first n values, then `rma[t] = (rma[t-1] * (n-1) + x[t]) / n`. `EMA` uses alpha = 2/(n+1), seeded with the SMA of the first n values. `SMA` is the arithmetic mean of the last n values. `stdev` is the population standard deviation unless stated otherwise.
- **Given** a hand-computed fixture for each of `sma`, `ema`, `rma`, `stdev`, `true_range`, `atr`, `rsi`, `obv`, `percentile_rank`, `linreg_slope`, **When** the function runs, **Then** every value matches within 1e-9 and the first n-1 values are NaN where the definition requires warm-up.

#### FR-202: Output shape and warm-up
- **Given** an input of length N, **When** any public indicator runs, **Then** it returns length N with NaN for every bar before the indicator is defined, and never raises on short inputs.

#### FR-203: Direction convention
Inside Super Trends `+1` is up (bullish) and `-1` is down (bearish). TradingView's `ta.supertrend` returns the opposite sign; conversion happens only at the import boundary of the parity test. The two conventions are never mixed.
- **Given** a TradingView export where direction is negative on an up trend, **When** the parity test loads it, **Then** the value is converted to `+1` before comparison, and no production code path contains the TradingView convention.

#### FR-204: Supertrend computation
Supertrend is computed exactly as in section 7.2 with `supertrend.atr_length` (10) and `supertrend.factor` (3.0): `hl2`, true range, `atr = RMA(tr, 10)`, basic bands, ratcheting final bands, direction rules (including `dir[t] = -1` while `atr[t-1]` is undefined), and `st[t] = final_lo[t] if dir[t] == +1 else final_up[t]`.
- **Given** the hand-computed 40-bar golden fixture that covers both flip directions and band ratcheting, **When** Supertrend runs, **Then** line and direction match every bar.
- **Given** any input after warm-up, **When** Supertrend runs, **Then** direction is always +1 or -1, the line is below close when direction is +1, and above close when direction is -1 (property test).

#### FR-205: Supertrend derived values
For each ticker the engine derives `st_dir_d` (daily direction), `st_dir_w` (weekly direction, from Supertrend on weekly bars with the same parameters), `bars_since_flip` (daily bars since the last daily direction change), `st_distance_atr = (close - st) / atr` (signed), and `st_line` (the daily Supertrend value, which is the invalidation level).
- **Given** a daily direction change 3 bars ago, **When** derived values are computed, **Then** `bars_since_flip` = 3, and `st_line` equals the latest daily Supertrend value.

#### FR-206: TradingView parity
On the golden TradingView fixtures (owner-supplied CSV exports for two tickers with the built-in Supertrend (10, 3) columns, placed in `tests/golden/tradingview/`), the Supertrend line matches within 0.01 per bar after a 100-bar warm-up and direction matches on every bar. Until the files exist the parity test is skipped with a visible reason; before the v1.0.0 release it must pass, not skip.
- **Given** the parity files, **When** the parity test runs, **Then** `|line - tv_line| <= 0.01` for every bar after bar 100, and direction (after sign conversion) is equal on every bar.

#### FR-207: SMA indicators
SMA 20, 50, 200 on daily closes; SMA20 slope over `sma.slope_bars` (5) bars; golden and death cross (SMA50 vs SMA200) detection reporting the bar index of the cross, with a lookback of `sma.cross_lookback` (10).
- **Given** a fixture where SMA50 crosses above SMA200 on bar k, **When** cross detection runs, **Then** a golden cross is reported at index k, and it counts as "within the last 10 bars" for bars k through k+9.

#### FR-208: MACD daily and weekly
MACD(12, 26, 9): `line = EMA12 - EMA26`, `signal = EMA9(line)`, `hist = line - signal`, computed on daily closes and on weekly closes.
- **Given** a reference fixture, **When** MACD runs, **Then** line, signal, and hist match within 1e-6, and signal crosses report their bar index.

#### FR-209: RSI and OBV
RSI(14) uses Wilder smoothing (RMA of gains and losses). OBV adds volume on up closes, subtracts it on down closes, and is unchanged on equal closes.
- **Given** a hand-computed fixture, **When** RSI and OBV run, **Then** values match within 1e-9.

#### FR-210: Confirmed pivots
A pivot low at bar p is a low lower than the `width` bars on each side; a pivot high is the mirror. A pivot is confirmed `width` bars after it forms and is never reported earlier. Width is 5 on daily bars and 3 on weekly bars for divergences, and 5 for support and resistance.
- **Given** a series whose lowest low is 3 bars from the end, **When** `pivots(width=5)` runs, **Then** that bar is not marked as a pivot.

#### FR-211: Divergence detection
For RSI(14), MACD histogram, and OBV, on daily (width 5) and weekly (width 3) bars, within the last `divergence.window_bars` (60) bars, the detector compares the two most recent confirmed pivot lows and, separately, the two most recent confirmed pivot highs, and classifies regular bullish (price lower low, oscillator higher low), regular bearish (price higher high, oscillator lower high), hidden bullish (price higher low, oscillator lower low), and hidden bearish (price lower high, oscillator higher high). Only divergences whose second pivot is within the last `divergence.recency_bars` (15) bars count. Each record carries both pivot bars, prices, and oscillator values.
- **Given** constructed fixtures for each of the four types, **When** the detector runs, **Then** each type is detected with correct pivot bars.
- **Given** a divergence whose second pivot is not yet confirmed, **When** the detector runs, **Then** it is not reported.
- **Given** a monotonic series, **When** the detector runs, **Then** nothing is reported.

#### FR-212: Mean reversion and volatility indicators
Bollinger Bands (20, 2.0), %B, z-score `(close - SMA20) / stdev20` with population stdev, bandwidth `bbw = (upperBB - lowerBB) / SMA20` and its percentile rank over 126 bars, `atr14` (RMA of true range, 14), `atr_pct = atr14 / close` and its percentile rank over 252 bars, HV20 (stdev of 20 daily log returns times sqrt(252)), squeeze flag (`bbw_rank < 15`), and expansion flag (`bbw_rank > 85` and bbw rising 3 bars).
- **Given** reference fixtures, **When** these run, **Then** values match, and percentile ranks use only the trailing window ending at bar t.

#### FR-213: Fibonacci levels
ZigZag on daily closes over the last `fibonacci.lookback_bars` (120) bars with reversal threshold `max(8%, 3 * ATR%)` where `ATR% = atr14 / close`. The most recent completed leg A to B is selected (B is the last confirmed swing extreme). Retracements 23.6, 38.2, 50.0, 61.8, 78.6 percent are measured from B back toward A; extensions 127.2 and 161.8 percent are computed for evidence and the "next level" line.
- **Given** a constructed up-leg from 100 to 200 followed by a pullback, **When** levels are computed, **Then** the 61.8 level equals 200 - 0.618 * 100 = 138.2 within 1e-6, and the 127.2 extension equals 227.2.

#### FR-214: Support and resistance levels
Confirmed pivot highs and lows (width 5) over the last 250 bars are clustered when prices are within `0.5 * atr14`. Each cluster is a level with strength `touches * recency_weight`, recency decaying linearly from 1.0 (today) to 0.3 (250 bars ago). The 4 strongest levels above price (resistance) and 4 below (support) are kept, plus the 52-week high and low as levels.
- **Given** pivots at 100.0 and 100.3 with `atr14` = 1.0, **When** clustering runs, **Then** they merge into one level with 2 touches.
- **Given** 10 candidate levels above price, **When** levels are selected, **Then** the 4 with the highest strength are kept as resistance, plus the 52-week high.

#### FR-215: Breakout and breakdown detection
A breakout is a close above a resistance level that was intact yesterday with relative volume (`volume / SMA20(volume)`) >= 1.5; a breakdown is the mirror for support. A breakout is flagged only on the bar it happens.
- **Given** a close above an intact resistance on relative volume 1.6 on bar t, **When** detection runs, **Then** a breakout is flagged on bar t and not on bar t+1.

#### FR-216: Volume indicators
Volume oscillator (short 5, long 10) `vo = 100 * (EMA5(volume) - EMA10(volume)) / EMA10(volume)`, relative volume, OBV least-squares slope over 20 bars, and Chaikin Money Flow over 20 daily bars.
- **Given** reference fixtures, **When** these run, **Then** values match within 1e-6.

#### FR-217: Estimated buy/sell split
For each 5-minute regular-session bar: if high > low, `buy = volume * (close - low) / (high - low)` and `sell = volume - buy`; else `buy = volume if close >= prev_close else 0` and `sell = volume - buy`. `daily_delta = sum(buy) - sum(sell)`, `delta_pct = daily_delta / sum(volume)`, `delta_pct_10` is the mean of `delta_pct` over the last 10 sessions.
- **Given** any bar, **When** the split runs, **Then** buy + sell = volume exactly.
- **Given** a zero-range bar with close >= previous close, **When** the split runs, **Then** all volume is buy.

#### FR-218: Order flow quality levels
Flow quality is stored and shown: `intraday` when 5-minute bars exist for at least 8 of the last 10 sessions; `daily_estimate` when intraday data is missing, in which case the same formula is applied to daily bars; `trades` is an optional upgrade behind the provider `trades` capability flag (tick rule from trade prints), not required in v1, but the interface allows it.
- **Given** intraday bars for only 7 of the last 10 sessions, **When** the flow factor computes, **Then** quality is `daily_estimate`, the daily formula is used, and the flag is visible on the card and Ticker screen.

#### FR-219: Accumulation and distribution days
Accumulation days (up close on relative volume >= 1.5) and distribution days (down close on relative volume >= 1.5) in the last 20 sessions are counted and reported as evidence.
- **Given** 3 qualifying up closes and 1 qualifying down close in the last 20 sessions, **When** evidence is built, **Then** it reports 3 accumulation days and 1 distribution day.

#### FR-220: ADX
ADX(14) with +DI and -DI on daily bars, using Wilder smoothing.
- **Given** a reference fixture, **When** ADX runs, **Then** ADX, +DI, and -DI match within 1e-6.

#### FR-224: Ripster EMA Clouds indicator and TradingView parity
Ten EMAs on `hl2` per section 7.13 (EMA as defined in section 7.1), the cloud top, bottom and direction for each of the five clouds, `pos`, `stack`, and the derived values `rc_bias`, `rc_stack`, `rc_bars_since_stack_flip`, `rc_c3_top`, `rc_c3_bot`, and `rc_dir_w` (34/50 direction on weekly bars, evidence only). On the golden TradingView fixtures (the owner's exports with the Ripster EMA Clouds indicator at default settings, in `tests/golden/tradingview/`), computed on the export's own bars, each of the ten EMAs matches within 0.01 per bar and each cloud direction matches on every bar after a 200-bar warm-up. Until the files exist the parity test is skipped with a visible reason; before the v1.0.0 release it must pass, not skip.
- **Given** the hand-computed fixture covering a stack flip in each direction, a close inside a cloud, and a held and a failed 8/9 pullback, **When** the clouds run, **Then** `top`, `bot`, `cloud_dir`, `pos`, `stack`, and `rc_bars_since_stack_flip` match every bar.
- **Given** any input after warm-up, **When** the clouds run, **Then** `top >= bot` for every cloud, and `stack` is nonzero only when the 5/12 and 34/50 clouds do not overlap (property test).
- **Given** the parity files, **When** the parity test runs, **Then** every EMA is within 0.01 and every cloud direction is equal on every bar after bar 200.

#### FR-221: No look-ahead harness
Every public indicator is registered with a property test: computing on `bars[:t]` yields the same values for indexes below `t - confirm_lag` as computing on the full series. A test fails if any public indicator function is missing from the registry.
- **Given** a deliberately leaky indicator injected in a test, **When** the harness runs, **Then** the harness fails.

#### FR-222: Determinism hash
- **Given** the fixture dataset and the default config, **When** all indicators are computed, **Then** the hash of all outputs equals the committed hash, and CI fails on any change.

#### FR-223: Indicator snapshots
One snapshot per ticker per run (JSON of indicator values and levels) is stored in `indicator_snapshots` with the config hash.
- **Given** the same inputs and config, **When** the snapshot is recomputed, **Then** the JSON document is byte-identical.

### 8.4 Scoring (FR-3xx)

#### FR-301: Factor result contract
Every factor implements `id` and `compute(snapshot, context) -> FactorResult`. A `FactorResult` has a factor score in the closed range -100 (max bearish) to +100 (max bullish), a list of evidence items (name, value, unit, human reason), and a quality flag (`ok`, `degraded`, `missing`).
- **Given** a factor implementation that returns 101, **When** it is validated, **Then** an error is raised and the run fails cleanly before publication.
- **Given** any factor result, **When** it is stored in `factor_scores`, **Then** score, weight, contribution, quality, and evidence are present.

#### FR-302: Factor registry consistency
The twelve factor IDs are `supertrend`, `sma`, `macd`, `divergence`, `mean_reversion`, `fibonacci`, `levels`, `volatility`, `volume_osc`, `flow`, `fundamentals`, `ripster`.
- **Given** the registry and `config/scoring.yaml`, **When** the app starts, **Then** every weight key maps to a registered factor and every registered factor has a weight; otherwise startup fails naming the mismatch.

#### FR-303: Factor 1, Supertrend score
`base = +60 if st_dir_d == +1 else -60`; `weekly = +25 * st_dir_d if st_dir_w == st_dir_d else -15 * st_dir_d`; `freshness = +15 * st_dir_d if bars_since_flip <= 5 else 0`; `stretch = -10 * st_dir_d if |st_distance_atr| > 4 else 0`; `score = clip(base + weekly + freshness + stretch, -100, 100)`.
- **Given** `st_dir_d` +1, `st_dir_w` +1, `bars_since_flip` 3, `st_distance_atr` 1.2, **When** scored, **Then** score = 100.
- **Given** `st_dir_d` -1, `st_dir_w` +1, `bars_since_flip` 10, `st_distance_atr` -5, **When** scored, **Then** score = -60 + 15 + 0 + 10 = -35.
- **Given** `bars_since_flip` 5, **Then** freshness applies; **given** 6, **Then** it does not.
- **Given** `|st_distance_atr|` exactly 4, **Then** stretch does not apply (strictly greater than 4 is required).

#### FR-304: Factor 2, SMA score
Sum of: +30 / -30 close above / below SMA200; +25 / -25 SMA50 above / below SMA200; +20 / -20 close above / below SMA50; +15 / -15 SMA20 slope over 5 bars positive / negative; +10 / -10 golden / death cross within the last 10 bars. `score = clip(sum, -100, 100)`.
- **Given** every bullish condition true, **When** scored, **Then** score = 100. **Given** every bearish condition true, **Then** score = -100.
- **Given** close above SMA200, SMA50 below SMA200, close above SMA50, SMA20 slope negative, and no cross, **Then** score = 30 - 25 + 20 - 15 = 10.

#### FR-305: Factor 3, MACD score
Sum of: +35 / -35 line above / below signal; +25 / -25 line above / below zero; +25 / -25 hist rising / falling for 3 consecutive bars; +15 / -15 bullish / bearish signal cross within the last 3 bars; `score = clip(sum, -100, 100)`. Weekly MACD is computed and reported as evidence; if weekly `line` vs `signal` disagrees with daily, the factor score is multiplied by 0.75 (`macd.weekly_disagree_multiplier`).
- **Given** line above signal, line above zero, hist falling 3 bars, no recent cross, and weekly line below its signal, **When** scored, **Then** score = (35 + 25 - 25) * 0.75 = 26.25.
- **Given** weekly agreement, **Then** no multiplier is applied.

#### FR-306: Factor 4, Divergences score
Points: RSI divergence +/- 40, MACD hist divergence +/- 35, OBV divergence +/- 25 (bullish positive, bearish negative). Hidden divergences count at half value. If the same divergence type also exists on weekly bars (pivot width 3), the total is multiplied by 1.25. `score = clip(sum, -100, 100)`.
- **Given** a regular bullish RSI divergence and a hidden bullish OBV divergence on daily, no weekly confirmation, **When** scored, **Then** score = 40 + 12.5 = 52.5.
- **Given** the same plus the same divergence type on weekly bars, **Then** score = 52.5 * 1.25 = 65.625.
- **Given** a divergence whose second pivot is 16 bars old, **Then** it contributes 0.

#### FR-307: Factor 5, Mean reversion score
`z = (close - SMA20) / stdev20` (population); `pct_b` is evidence only; `z_part = -60 * clip(z / 2.5, -1, 1)`; `rsi_part = +40 if rsi <= 30; -40 if rsi >= 70; else linear from +40 at 30 to -40 at 70`; `score = clip(z_part + rsi_part, -100, 100)`.
- **Given** z = 2.5 and RSI = 70, **When** scored, **Then** score = -100.
- **Given** z = -1.25 and RSI = 50, **Then** z_part = 30, rsi_part = 0, score = 30.
- **Given** RSI = 40, **Then** rsi_part = 20.

#### FR-308: Factor 6, Fibonacci score (up leg)
For an up leg (A low, B high) with price pulling back: `near(level) = |close - level| <= 0.5 * atr14`; `holding = close[t] > close[t-1] and low[t] >= level - 0.5 * atr14`. +60 near 38.2 and holding; +70 near 50.0 and holding; +80 near 61.8 and holding; -50 close below the 78.6 level (the swing has failed); +20 close above B (leg resumed; next target is the 127.2 extension); 0 otherwise.
- **Given** an up leg, close within 0.5 * atr14 of the 61.8 level, close above the prior close, and low not below the level minus 0.5 * atr14, **When** scored, **Then** score = 80.
- **Given** an up leg and close below the 78.6 level, **Then** score = -50.
- **Given** an up leg and close above B, **Then** score = 20 and the next target in evidence is the 127.2 extension.

#### FR-309: Factor 6, mirror rules and missing leg
Every rule is mirrored for a down leg (A high, B low) with signs flipped. If no leg qualifies, score is 0 with quality `degraded`.
- **Given** a down leg with close near the 50.0 level and holding (mirror: close below prior close, high not above level plus 0.5 * atr14), **When** scored, **Then** score = -70.
- **Given** no ZigZag leg meets the reversal threshold in 120 bars, **Then** score = 0 and quality = `degraded`.

#### FR-310: Factor 7, Support and resistance score
`d_s = (close - nearest_support) / atr14` (>= 0); `d_r = (nearest_resistance - close) / atr14` (>= 0); `rr = d_r / max(d_s, 0.25)`; `base = clip((rr - 1) * 40, -60, 60)`; +40 on a close above a resistance level intact yesterday with relative volume >= 1.5; -40 on a close below a support level intact yesterday with relative volume >= 1.5; `score = clip(base + breakout, -100, 100)`.
- **Given** `d_s` = 1 and `d_r` = 3, **When** scored, **Then** rr = 3 and base = 60.
- **Given** `d_s` = 0.1 and `d_r` = 0.5, **Then** rr = 0.5 / 0.25 = 2 and base = 40.
- **Given** base 60 and a breakout on relative volume 1.5, **Then** score = 100.

#### FR-311: Factor 8, Volatility score
+30 * `st_dir_d` if squeeze; +20 * `st_dir_d` if expansion and close moved in the `st_dir_d` direction over 3 bars; the sum is multiplied by 0.5 if `atr_pct_rank > 90`. `expected_1d_move = atr14` is produced as risk evidence for every scored ticker.
- **Given** a squeeze, `st_dir_d` = +1, and `atr_pct_rank` = 50, **When** scored, **Then** score = 30.
- **Given** the same with `atr_pct_rank` = 95, **Then** score = 15.
- **Given** expansion, `st_dir_d` = -1, and close lower than 3 bars ago, **Then** the expansion term is -20.

#### FR-312: Factor 9, Volume oscillator score
`vo = 100 * (EMA5(volume) - EMA10(volume)) / EMA10(volume)`; `ret5 = close[t] / close[t-5] - 1`; `vo_part = clip(vo * 2, -60, 60) * sign(ret5)`; `obv_slope` = sign of the least-squares slope of OBV over 20 bars; `obv_part = 40 * obv_slope`; `score = clip(vo_part + obv_part, -100, 100)`.
- **Given** vo = 20, ret5 < 0, and a falling OBV slope, **When** scored, **Then** vo_part = -40, obv_part = -40, score = -80 (selling on rising volume).
- **Given** vo = -10 and ret5 > 0, **Then** vo_part = -20 (a rally on fading volume).
- **Given** vo = -10 and ret5 < 0, **Then** vo_part = +20 (a decline on fading volume).

#### FR-313: Factor 10, Buy / sell volume score
`score = clip(delta_pct_10 * 300, -50, 50) + clip(cmf20 * 200, -50, 50)`. When quality is `daily_estimate`, the factor weight is multiplied by 0.6 (`flow.daily_estimate_weight_multiplier`).
- **Given** `delta_pct_10` = 0.1 and `cmf20` = 0.3, **When** scored, **Then** score = 30 + 50 = 80.
- **Given** quality `daily_estimate`, **Then** the flow weight is multiplied by 0.6 before renormalization and the adjustment is listed.

#### FR-314: Factor 11, Fundamentals sub-scores
Sub-scores, each clipped to its range: revenue growth YoY (latest quarter) +/- 20, linear -10% -> -20, +20% -> +20; EPS growth YoY (latest quarter) +/- 20, linear -20% -> -20, +30% -> +20; gross margin change vs 4 quarters ago +/- 15, linear -3pt -> -15, +3pt -> +15; free cash flow margin (TTM) +/- 15, linear -5% -> -15, +20% -> +15; net debt / EBITDA +/- 10, <= 1 -> +10, >= 4 -> -10, linear between; valuation (forward P/E, or EV/Sales when earnings are negative) percentile vs own 3-year history +/- 20, 10th pct -> +20, 90th pct -> -20. `score = clip(sum, -100, 100)`.
- **Given** revenue growth +5%, **When** scored, **Then** the revenue sub-score = 0. **Given** +40%, **Then** it is clipped to +20.
- **Given** net debt / EBITDA 2.5, **Then** that sub-score = 0. **Given** 0.5, **Then** +10.
- **Given** valuation at the 50th percentile, **Then** that sub-score = 0; at the 5th percentile, +20.
- **Given** negative earnings, **Then** valuation uses EV/Sales percentile.

#### FR-315: Fundamentals quality and weight handling
ETFs and tickers with no fundamentals (for example QQQ, SPY) get quality `missing`, and the factor's weight is redistributed proportionally across the other factors. Fundamentals older than 120 days (`fundamentals.stale_days`) are `degraded` and the weight is halved (`fundamentals.stale_weight_multiplier` 0.5). `days_to_earnings` is not part of the fundamentals score.
- **Given** QQQ, **When** scored, **Then** fundamentals quality = `missing`, the fundamentals factor has weight 0, and the other eleven weights sum to 100.
- **Given** fundamentals with latest `period_end` data 130 days old, **Then** quality = `degraded` and the fundamentals weight is half its pre-quality value before renormalization.

#### FR-316: Base weights
Base weights (sum 100): Supertrend 20, SMA 7, MACD 8, Divergences 9, Mean reversion 7, Fibonacci 5, Support and resistance 7, Volatility 4, Volume oscillator 6, Buy / sell volume 9, Fundamentals 8, Ripster EMA Clouds 10.
- **Given** a `config/scoring.yaml` whose twelve weights do not sum to 100, **When** the config is loaded, **Then** validation fails with a message naming the weights block.

#### FR-317: Per-ticker regime
From ADX(14) on daily bars: `trending` if ADX >= 25; `ranging` if ADX < 20; `transitional` otherwise.
- **Given** ADX = 25.0, **Then** regime = `trending`. **Given** 19.99, **Then** `ranging`. **Given** 20.0 or 24.99, **Then** `transitional`.

#### FR-318: Regime multipliers and renormalization
The regime multiplier table in section 7.14 is applied to the base weights; the weights are then renormalized to sum 100. `transitional` multipliers are all 1.00; Volatility, Volume oscillator, Buy / sell volume, and Fundamentals are 1.00 in every regime, and Ripster EMA Clouds is 1.20 trending, 0.70 ranging, 1.00 transitional.
- **Given** a trending ticker with no other adjustments and all factors present, **When** weights are computed, **Then** pre-normalization weights are Supertrend 25, SMA 8.4, MACD 8.8, Divergences 8.1, Mean reversion 3.5, Fibonacci 5, Levels 6.3, Volatility 4, Volume oscillator 6, Flow 9, Fundamentals 8, Ripster 12 (sum 104.1), and after renormalization they sum to 100 (Supertrend 24.02 to two decimals, Ripster 11.53).
- **Given** each cell of the multiplier table, **When** tested, **Then** the applied multiplier equals the table value.

#### FR-319: Earnings event adjustment
If `days_to_earnings <= 5` (`events.earnings_window_days`), the fundamentals weight is multiplied by 1.5 (`events.earnings_fundamentals_multiplier`) after regime multipliers and before renormalizing, and the ticker (and any pick for it) carries the `event_risk` flag.
- **Given** `days_to_earnings` = 3, **When** weights are computed, **Then** fundamentals weight is multiplied by 1.5 before renormalization, `event_risk` is set, and "earnings in 3 days" is listed in adjustments.
- **Given** `days_to_earnings` = 6, **Then** no event adjustment applies.

#### FR-320: Fundamentals threshold shifts
Fundamentals score <= -40: the buy threshold for that ticker rises by 5 display points. Fundamentals score >= +40: the sell threshold for that ticker falls by 5 display points.
- **Given** a fundamentals score of -40, **When** selection evaluates the ticker, **Then** its buy threshold is 70.
- **Given** a fundamentals score of +45, **Then** its sell threshold is 30.
- **Given** fundamentals quality `missing`, **Then** no fundamentals threshold shift applies.

#### FR-321: Market regime
From the daily Supertrend direction of QQQ and SPY: both down is `risk_off` (buy threshold +5 for every ticker); both up is `risk_on` (sell threshold -5 for every ticker); mixed is `neutral` (no change). VIX, when available, is evidence only.
- **Given** SPY and QQQ both with daily direction -1, **When** the run selects, **Then** `market_regime` = `risk_off` and every buy threshold is raised by 5.
- **Given** SPY +1 and QQQ -1, **Then** `market_regime` = `neutral`.

#### FR-322: Threshold adjustments stack
Threshold shifts are additive.
- **Given** `risk_off` and a ticker with fundamentals score -50, **When** selection evaluates it, **Then** its buy threshold is 65 + 5 + 5 = 75.
- **Given** `risk_on` and fundamentals score +40, **Then** its sell threshold is 35 - 5 - 5 = 25.

#### FR-323: Adjustments are recorded and shown
Every adjustment that fired (regime, event, quality multipliers, threshold shifts, market regime) is stored with the result, appears in the evidence document's `adjustments`, and is shown in the UI ("Weights adjusted: trending regime, earnings in 3 days").
- **Given** a trending ticker with earnings in 3 days, **When** the result is stored, **Then** adjustments contain "trending regime" and "earnings in 3 days", and the Ticker screen shows before and after weights.

#### FR-324: Composite score
`composite = sum(w_i * s_i) / sum(w_i)` over factors with quality != missing; range -100..100. The final adjusted weights over non-missing factors are renormalized to sum 100.
- **Given** a factor with quality `missing`, **When** the composite is computed, **Then** that factor is excluded from numerator and denominator.

#### FR-325: Display score
`display = round((composite + 100) / 2, 1)`; range 0..100.
- **Given** composite 0, **Then** display = 50.0. **Given** composite 56.8, **Then** display = 78.4. **Given** composite -100, **Then** display = 0.0.

#### FR-326: Bands
Bands on the display score: 80 to 100 Strong Buy; 65 to 79.9 Buy; 50 to 64.9 Neutral, leaning up; 35.1 to 49.9 Neutral, leaning down; 20.1 to 35 Sell; 0 to 20 Strong Sell.
- **Given** display 80.0, **Then** band = Strong Buy; 79.9, Buy; 65.0, Buy; 64.9, Neutral, leaning up; 50.0, Neutral, leaning up; 49.9, Neutral, leaning down; 35.1, Neutral, leaning down; 35.0, Sell; 20.1, Sell; 20.0, Strong Sell.

#### FR-327: Confidence
`agreement` = share of total weight held by factors whose score has the same sign as composite (0..1). `confidence = 100 * agreement`, minus 15 if `atr_pct_rank > 90`, minus 10 if any factor quality is degraded, minus 10 if `st_dir_w != st_dir_d`, minus 10 if `rc_stack == -st_dir_d` (FR-335), minus 10 if `event_risk`; then `clip(confidence, 0, 100)`. The deductions that fired are stored and shown next to the confidence value.
- **Given** agreement 0.80 and no deductions, **Then** confidence = 80.
- **Given** agreement 0.80, `atr_pct_rank` 95, and weekly disagreement, **Then** confidence = 80 - 15 - 10 = 55.
- **Given** agreement 0.30 with all five deductions, **Then** confidence = clip(30 - 55, 0, 100) = 0.

#### FR-328: Contributions
`contribution = weight * score / 100` per factor, so contributions sum to the composite.
- **Given** any scored ticker, **When** contributions are summed, **Then** the sum equals the composite within 1e-9.

#### FR-329: Deterministic scoring
Same bars plus same config hash produce byte-identical factor scores and ranking. The LLM never influences a score, rank, or selection; no LLM output is passed into scoring, ranking, or selection code.
- **Given** two clean runs on the fixture dataset with the same config, **When** results are compared, **Then** factor scores, composites, display scores, confidence, and ranking are byte-identical.

#### FR-330: Scoring configuration file
All scoring parameters live in `config/scoring.yaml` (defaults in section 10), validated by a pydantic model with a JSON schema export. `config_hash` is the sha256 of the canonical JSON of the document, formatted `sha256:<hex>`.
- **Given** an unknown key or an out-of-range value, **When** the config loads, **Then** loading fails with a message naming the key.
- **Given** the same document with keys reordered, **When** hashed, **Then** the hash is identical.

#### FR-331: Config versioning
Every distinct config hash is stored in `config_versions` with the full document, its `scoring.version`, and first-seen time. `scoring.version` must be bumped when weights, thresholds, or formulas change; a CI check fails if the hash of `config/scoring.yaml` changed without a version bump.
- **Given** a PR that changes a weight without bumping `scoring.version`, **When** CI runs, **Then** the check fails.

#### FR-332: Every result records its config
Every run, factor score, indicator snapshot, recommendation, and evidence document records the config hash that produced it.
- **Given** any past recommendation, **When** its date is browsed, **Then** the exact config document that produced it can be displayed via its hash.

#### FR-333: Factor 12, Ripster EMA Clouds score
`bias = 30 * pos(c3)`; `trend = 20 * cloud_dir(c2)`; `stacking = 20 * stack`; `mid = 10 * cloud_dir(c3)`; `long = 10 * pos(c5)`; `pullback = 10 * stack` if `stack != 0` and, within the last 3 bars (`ripster.pullback_lookback_bars`), price tested the 8/9 cloud from the trend side (bullish: some low <= `top(c1)`; bearish: some high >= `bot(c1)`) and `close[t]` is still on the trend side of it (bullish: `close > bot(c1)`; bearish: `close < top(c1)`), otherwise 0; `score = clip(bias + trend + stacking + mid + long + pullback, -100, 100)`. The 72/89 cloud is evidence only and is not scored.
- **Given** close above the 34/50 cloud, **Then** `bias` = +30; **given** below, -30; **given** inside the cloud (`pos(c3)` = 0), **Then** `bias` = 0.
- **Given** a bullish 5/12 cloud (`cloud_dir(c2)` = +1), **Then** `trend` = +20; **given** bearish, -20.
- **Given** the 5/12 cloud fully above the 34/50 cloud (`stack` = +1), **Then** `stacking` = +20; **given** fully below, -20; **given** overlapping clouds, 0.
- **Given** a bullish 34/50 cloud, **Then** `mid` = +10; **given** bearish, -10.
- **Given** close above the 180/200 cloud, **Then** `long` = +10; **given** below, -10; **given** inside, 0.
- **Given** `stack` = +1, a low at or below `top(c1)` 2 bars ago, and a close above `bot(c1)`, **Then** `pullback` = +10 (held). **Given** the same with a close at or below `bot(c1)` (failed), **Then** `pullback` = 0. **Given** the only test of the 8/9 cloud was 4 bars ago (stale), **Then** `pullback` = 0. **Given** `stack` = -1 and a high at or above `bot(c1)` within 3 bars with a close below `top(c1)`, **Then** `pullback` = -10.
- **Given** all six components at their bullish maximum (30 + 20 + 20 + 10 + 10 + 10 = 100), **Then** score = 100; **given** all at their bearish maximum, -100.

#### FR-334: Ripster selection gate
A buy candidate requires `rc_bias >= 0` (close not below the 34/50 cloud) and a sell candidate requires `rc_bias <= 0` (close not above the 34/50 cloud). Close inside the 34/50 cloud (`rc_bias` = 0) passes both gates. A candidate rejected by the gate is recorded with the reason.
- **Given** a buy candidate on every other rule with `rc_bias` = -1, **When** selection runs, **Then** it is not a buy candidate, and the recorded reason is "close below the 34/50 cloud".
- **Given** a sell candidate on every other rule with `rc_bias` = +1, **Then** it is not a sell candidate, and the recorded reason is "close above the 34/50 cloud".
- **Given** `rc_bias` = 0, **Then** the Ripster gate passes for both sides.

#### FR-335: Ripster confidence deduction
Confidence is reduced by 10 (`ripster.confidence_stack_conflict_penalty`) when `rc_stack == -st_dir_d`, that is, when the 5/12 vs 34/50 stack opposes the daily Supertrend. The deduction is stored and shown next to the confidence value like the others in FR-327.
- **Given** `st_dir_d` = +1 and `rc_stack` = -1, **Then** confidence is reduced by 10. **Given** `st_dir_d` = +1 and `rc_stack` = +1 or 0, **Then** no Ripster deduction applies.
- **Given** agreement 0.80 and `st_dir_d` = -1 with `rc_stack` = +1, **Then** confidence = 80 - 10 = 70.

### 8.5 Selection (FR-4xx)

#### FR-401: Buy candidate
A ticker is a buy candidate when all hold: display >= 65 (plus any threshold adjustments), `st_dir_d == +1`, `rc_bias >= 0` (close not below the 34/50 cloud), confidence >= 50, data quality not `stale`, average 20-day dollar volume >= 20,000,000.
- **Given** display 70, `st_dir_d` +1, confidence 60, quality `ok`, dollar volume 25,000,000, and no threshold shifts, **When** selection runs, **Then** the ticker is a buy candidate.
- **Given** the same with `st_dir_d` -1, **Then** it is not a buy candidate.
- **Given** the same with confidence 49, or dollar volume 19,999,999, **Then** it is not a buy candidate.
- **Given** display 69 under `risk_off` (threshold 70), **Then** it is not a buy candidate.
- **Given** the same as the first case with `rc_bias` = -1, **Then** it is not a buy candidate (FR-334). **Given** `rc_bias` = 0, **Then** it is a buy candidate.

#### FR-402: Sell candidate
A ticker is a sell candidate when all hold: display <= 35 (minus any threshold adjustments), `st_dir_d == -1`, `rc_bias <= 0` (close not above the 34/50 cloud), confidence >= 50, data quality not `stale`, average 20-day dollar volume >= 20,000,000.
- **Given** display 33, `st_dir_d` -1, confidence 55, quality `ok`, dollar volume 50,000,000, and `neutral` market regime, **Then** the ticker is a sell candidate.
- **Given** display 33 under `risk_on` (threshold 30), **Then** it is not a sell candidate.
- **Given** the same as the first case with `rc_bias` = +1, **Then** it is not a sell candidate (FR-334). **Given** `rc_bias` = 0, **Then** it is a sell candidate.

#### FR-403: Meaning of "sell"
"Sell" means bearish: reduce, exit, or avoid. Super Trends does not recommend short selling or any specific instrument, size, or expiry. The UI, narratives, CLI help, MCP tool descriptions, and user guide state this meaning.
- **Given** any sell card, **When** it renders, **Then** it shows the word "Sell", a down triangle, and no instrument, size, expiry, or short-selling instruction.

#### FR-404: Ranking
Buys are ranked by display descending; sells by display ascending.
- **Given** buy candidates with display 72, 81, 68, **Then** the buy order is 81, 72, 68.

#### FR-405: Tie-breakers
Ties are broken in this order: higher confidence, more recent Supertrend flip (smaller `bars_since_flip`), higher relative volume, alphabetical ticker.
- **Given** two buys with equal display and confidence, `bars_since_flip` 2 and 7, **Then** the one with 2 ranks first.
- **Given** two candidates equal on display, confidence, flip age, and relative volume, **Then** the alphabetically earlier ticker ranks first.

#### FR-406: Pick counts
Super Trends publishes the top `selection.max_buys` (3) buys and top `selection.max_sells` (2) sells.
- **Given** 8 qualifying buys and 5 qualifying sells with no correlation conflicts, **Then** exactly 3 buys and 2 sells are published.

#### FR-407: Never pad
If fewer tickers qualify than the maximum on a side, Super Trends publishes fewer. Non-qualifying tickers are never added to reach the count.
- **Given** exactly 1 qualifying buy, **When** the run publishes, **Then** the result has 1 buy, not 3.

#### FR-408: Nearest miss
For each side with fewer picks than the maximum, the result records the nearest candidate that missed (the non-qualifying ticker closest to that side's threshold among tickers that were scored) and the reason it missed (for example "score above the sell threshold of 35", "Supertrend direction is up", "close below the 34/50 cloud", "confidence 44 below 50", "liquidity below the floor").
- **Given** no qualifying sells, **When** the run publishes, **Then** `nearest_miss.sell` contains a ticker, its display score, and a reason, and the Today screen shows "No qualifying sells today" with that ticker and reason.

#### FR-409: Correlation guard
Walk each side's ranked candidates in order and skip any candidate whose 60-day return correlation (`selection.correlation_window`) with an already selected pick on that side is above 0.9 (`selection.correlation_max`), until the side is full or candidates run out. Correlation uses daily close-to-close returns over the last 60 sessions.
- **Given** SPY, VOO, and IVV stand-ins all qualifying as buys with pairwise correlation above 0.9, **When** selection runs, **Then** only the highest ranked of the three is picked, and the side fills with the next non-duplicate candidates.
- **Given** correlation exactly 0.9, **Then** the candidate is not skipped.

#### FR-410: Also qualified
Candidates skipped by the correlation guard are recorded as "also qualified" with the pick they duplicate.
- **Given** VOO skipped because of SPY, **Then** `also_qualified` contains VOO with `duplicates: SPY`, and the Today screen shows it under the SPY card.

#### FR-411: No stickiness, day count shown
There is no stickiness rule in v1: each day stands alone. A ticker may appear on consecutive days; the result records `days_on_list` (consecutive published trading days on the same side, counting today) and the UI shows "day N on the list".
- **Given** ORCL picked as a buy on the previous two published trading days and today, **Then** `days_on_list` = 3.

#### FR-412: Excluded tickers are never candidates
- **Given** a ticker excluded for `stale`, `insufficient_history`, `unresolved`, or pending review, **When** selection runs, **Then** it is neither a candidate nor a nearest miss, and it appears only in `excluded`.

### 8.6 Justification (FR-5xx)

#### FR-501: Evidence document
For each pick a structured evidence document is stored with: ticker, date, side, display_score, confidence, band, regime, market_regime, supertrend (`dir_d`, `dir_w`, `bars_since_flip`, `line`, `distance_atr`), ripster (`bias`, `stack`, `bars_since_stack_flip`, `c2_dir`, `c3_dir`, `c3_top`, `c3_bot`, `dir_w`), invalidation (`level`, `rule`), levels (support, resistance, fib, `cloud_34_50`, next_target), factors (id, score, weight, contribution, reasons), adjustments, flags, config_hash, plus `expected_1d_move` and flow quality. The shape follows section 7.17 and validates against a committed JSON schema.
- **Given** any published pick, **When** its evidence document is validated against the schema, **Then** it passes, and every factor in the run appears in `factors`.

#### FR-502: Deterministic reasons
Reasons are produced by deterministic templates in code, one per rule that fired.
- **Given** a Supertrend score with the weekly agreement and freshness rules firing, **Then** reasons include "Daily Supertrend flipped up 3 bars ago" and "Weekly Supertrend agrees" (with the actual values), and no reason exists for a rule that did not fire.

#### FR-503: Invalidation level
Every pick has an invalidation level equal to the daily Supertrend line: for a buy, "daily close below the Supertrend line"; for a sell, "daily close above the Supertrend line".
- **Given** a buy with `st_line` 212.40, **Then** invalidation = `{"level": 212.40, "rule": "daily close below the Supertrend line"}` and the card reads, in substance, "this view is wrong if price closes below 212.40".

#### FR-504: Template narrative
A deterministic template narrative exists for every pick: it leads with the Supertrend state and the Ripster 34/50 cloud bias, then the two largest positive contributions, then the largest opposing factor ("what argues against it"), then the invalidation level. Every number in it appears in the evidence document.
- **Given** the narrative provider is `template`, **When** a run publishes, **Then** every pick has a 3 to 5 sentence narrative with `source: template` and passes the numeric guard.

#### FR-505: LLM narrative
When `SUPERTRENDS_NARRATIVE_PROVIDER=openai_compatible`, a narrative of 3 to 5 sentences is written by an LLM from the evidence document only, through an OpenAI-compatible endpoint (`SUPERTRENDS_LLM_BASE_URL`, `SUPERTRENDS_LLM_MODEL`, optional `SUPERTRENDS_LLM_API_KEY`). The user prompt contains a compact rendering of the evidence document and nothing else. Prompts are versioned files in `src/supertrends/narrative/prompts/`.
- **Given** a reachable endpoint returning a compliant narrative, **When** the run narrates, **Then** the stored narrative has `source: llm`, the model name, and the prompt version.

#### FR-506: System prompt prohibitions
The system prompt forbids any number, level, or claim not present in the evidence document, forbids price targets beyond `next_target`, forbids the words "guaranteed", "will", "can't lose", and forbids advice on position size, options, or leverage.
- **Given** the committed system prompt, **When** a test inspects it, **Then** it contains each prohibition.

#### FR-507: Narrative order
Order: lead with the Supertrend state and the Ripster 34/50 cloud bias, then the two largest positive contributions, then the largest opposing factor, then the invalidation level.
- **Given** an evidence document, **When** the prompt is rendered, **Then** it instructs this order and supplies the Supertrend state, the Ripster 34/50 cloud bias, the top two positive contributions, the largest opposing factor, and the invalidation level in that order.

#### FR-508: Numeric guard
After generation, every number in the narrative is extracted. Each must match a value in the evidence document within rounding (equal after rounding the evidence value to the number of decimals shown in the narrative). Any unmatched number rejects the narrative.
- **Given** a narrative that mentions 250.00 when no evidence value rounds to it, **When** the guard runs, **Then** the narrative is rejected.
- **Given** a narrative mentioning 212.4 when the evidence has 212.40, **Then** it passes.

#### FR-509: Banned phrase and length checks
A narrative containing a banned phrase ("guaranteed", "will", "can't lose", "sure thing", "will go to") or with fewer than 3 or more than 5 sentences is rejected. Output is length-limited.
- **Given** a narrative containing "will rise", **Then** it is rejected.
- **Given** a 6-sentence narrative, **Then** it is rejected.

#### FR-510: Retry and fallback
On rejection, timeout (8 seconds), or endpoint error: retry once at temperature 0, then fall back to the deterministic template narrative. Narrative failures never fail the run.
- **Given** the endpoint is unreachable, **When** the run narrates, **Then** the run publishes with every narrative `source: template`, and `supertrends_narrative_total{source="template",result="fallback"}` increments per pick.
- **Given** the first response is rejected and the retry at temperature 0 passes, **Then** the stored narrative is the retry with `source: llm`.

#### FR-511: Narrative storage
Each narrative row stores `text`, `source` (`llm` or `template`), `model`, `prompt_version`, `tokens_in`, `tokens_out`.
- **Given** any published pick, **Then** its narrative row has every field (model and tokens are null for template narratives).

#### FR-512: Narrative isolation from scoring
The narrative never changes a score, a rank, or a selection.
- **Given** the same run executed with the LLM provider and with the template provider, **When** results are compared, **Then** scores, ranks, and selections are identical.

#### FR-513: Token budget
At most 900 prompt tokens and 220 completion tokens per pick (NFR-012), enforced in code (`max_tokens` = 220; prompt rendering truncates or fails over to template if over budget) and reported as `supertrends_narrative_tokens{kind}`.
- **Given** the fixture evidence set, **When** the CI token budget test renders every prompt, **Then** none exceeds 900 tokens.

#### FR-514: Prompt safety and untrusted output
Provider-supplied strings (company names, news, descriptions) are never placed in the LLM prompt; the prompt contains only numbers and enumerated labels from the evidence document. LLM output is untrusted: validated, length-limited, and rendered as plain text, never as HTML or Markdown with links.
- **Given** a narrative containing `<script>` or a Markdown link, **When** it is rendered in the UI, **Then** it shows as literal text and no link or script is created.

#### FR-515: Narrative evaluation set
`tests/narrative_eval/` holds 30 evidence documents covering every band, both sides, and every flag. A recorded-response test runs in CI. `make narrative-eval` runs against a configured endpoint and reports acceptance rate, mean tokens, and latency; the target acceptance rate on the Stoke model is at or above 90 percent, recorded in `docs/NARRATIVE_EVAL.md`.
- **Given** the recorded responses, **When** CI runs, **Then** no accepted narrative contains an unmatched number.

### 8.7 Track record and backtest (FR-6xx)

#### FR-601: Entry price
For every published pick, `entry_price` = the next session's open, filled once when that session has opened. It is the only field of a recommendation that is ever written after publication.
- **Given** a pick published for 2026-11-13, **When** the run on 2026-11-16 executes, **Then** `entry_price` is the 2026-11-16 open and later runs never change it.

#### FR-602: Forward returns
On later runs, forward returns at 1, 5, 10, and 20 trading days (`track_record.horizons_days`) are computed for the pick and for SPY over the same window (entry at the next session's open, exit at the close of the horizon session), using adjusted prices so splits between entry and exit are handled. An outcome is never computed before its horizon session has closed. Outcomes are append-only per (recommendation, horizon).
- **Given** a pick whose 5-day horizon closes tomorrow, **When** today's run executes, **Then** no 5-day outcome exists yet.
- **Given** fixture prices, **Then** returns match hand-computed values.

#### FR-603: Hit definition
`excess_return = return - benchmark_return` (SPY). A buy is a hit when excess return > 0; a sell is a hit when excess return < 0.
- **Given** a buy return of +2% and SPY +3%, **Then** excess = -1% and it is a miss.
- **Given** a sell return of -1% and SPY +1%, **Then** excess = -2% and it is a hit.

#### FR-604: Statistics
Report hit rate, mean and median excess return, and worst pick, per side, per horizon, overall and by band, with the sample size next to every statistic.
- **Given** a set of outcomes, **When** `GET /api/v1/track-record` is called, **Then** each statistic matches a reference computed with pandas and carries `n`.

#### FR-605: Small sample label
Statistics with fewer than 20 samples (`track_record.small_sample`) are labeled "small sample".
- **Given** 19 outcomes for buys at 20 days, **Then** that cell carries `small_sample: true` and the UI shows "small sample".

#### FR-606: Empty ranges
- **Given** a date range with no picks, **When** the track record is requested, **Then** the response is 200 with zeros and sample size 0, not an error.

#### FR-607: Immutable picks
Picks are never edited or deleted after publication. `recommendations` and `factor_scores` are append-only, enforced by a database trigger that rejects UPDATE and DELETE (except the one-time `entry_price` fill). `outcomes` are append-only.
- **Given** a published recommendation, **When** any process attempts to UPDATE its score or DELETE it, **Then** the database rejects the statement.

#### FR-608: Track record filters
The track record can be filtered by date range, side, band, and config version (`from`, `to`, `side`, `band`, `config`).
- **Given** `config=<hash>`, **Then** only picks produced under that config are included.

#### FR-609: Backtest command
`supertrends backtest --from YYYY-MM-DD --to YYYY-MM-DD --config config/scoring.yaml` replays the daily loop over stored history with no look-ahead: indicators at day t use bars up to t; entries at t+1 open; fundamentals use the value known at t.
- **Given** a fundamentals row with `known_at` after day t, **When** the backtest scores day t, **Then** it does not see that row.
- **Given** a deliberately leaky indicator injected in a test, **Then** the no-look-ahead check catches it.

#### FR-610: Same code, separate storage
The backtest runs through the same factor, composite, and selection code as live runs (no separate implementation), writes to a separate `backtests` schema, and never touches published recommendations.
- **Given** a backtest over the fixture dataset, **When** it covers dates that have live runs with the same config, **Then** it reproduces the live picks for those dates, and the `recommendations` table is unchanged.

#### FR-611: Backtest outputs
Output: the same track-record statistics plus an equity curve for "equal weight the daily buys, hold 5 days", against SPY, as JSON and a Markdown summary.
- **Given** a completed backtest, **Then** JSON and Markdown outputs exist with the statistics and both equity curves.

#### FR-612: Hypothetical label
Backtest results are labeled as hypothetical everywhere they appear (UI tab "Backtest (hypothetical)", CLI output, Markdown summary, API payloads).
- **Given** any backtest figure on any surface, **Then** the word "hypothetical" is shown with it.

#### FR-613: Backtest performance
- **Given** 2 years and 20 tickers on 2 cores, **When** a backtest runs, **Then** it completes in under 3 minutes.

### 8.8 UI (FR-7xx)

The UI is a React single-page app served by the API from the same image. Detailed layouts, tokens, and wireframes live in `docs/DESIGN.md`; this section defines behavior.

#### FR-701: Routes
Routes: `/` (Today), `/ticker/:symbol`, `/watchlist`, `/track-record`, `/runs`, `/settings`, and `/date/:yyyy-mm-dd` (Today for a past date). `/demo` exists only in demo mode. Deep links work after refresh (SPA fallback).
- **Given** a browser refresh on `/ticker/ORCL`, **Then** the Ticker screen for ORCL loads.

#### FR-702: Today screen loads with no interaction
`/` shows the latest published run immediately: header with as-of date, market regime, run status, and data freshness; three buy cards on the first row and two sell cards on the second at desktop width (single column on narrow screens, buys first).
- **Given** a published run, **When** the trader opens `/`, **Then** the picks are visible without any click, and the as-of date is the run's trade date.

#### FR-703: Pick card contents
Each card shows: ticker, side label with shape (up triangle and "Buy", or down triangle and "Sell"), band, ScoreDial with the display score, confidence (with deductions on hover or focus), TrendRibbon (last 60 sessions colored by Supertrend direction, flips marked), "flipped N bars ago", top factor contributions, narrative with its source tag, invalidation level, key levels (support, resistance, Fibonacci, the 34/50 cloud, next target), `expected_1d_move`, flags (`event_risk`, estimated order flow quality), "day N on the list", watchlist groups, and any "also qualified" duplicates.
- **Given** a fixture run, **When** a card renders, **Then** every listed element is present and matches the API payload.

#### FR-704: Fewer cards and the empty side
When fewer picks are published than the maximum, only those cards are shown, with a line "No more qualifying buys" (or sells); an empty side shows "No qualifying buys today" or "No qualifying sells today" with the nearest candidate and the reason it missed.
- **Given** a run with 1 buy and 0 sells, **Then** the screen shows 1 buy card, the "no more qualifying buys" line, and "No qualifying sells today" with the nearest miss and reason.
- **Given** a run with 3 buys and 2 sells, **Then** exactly those 5 cards are shown.

#### FR-705: Group filter on Today
An optional group filter re-ranks within one watchlist group without changing the published overall picks. The filtered view is clearly labeled as a filtered ranking, not the published picks.
- **Given** the group filter set to `semis`, **Then** the view shows the qualifying candidates within `semis` labeled as a group view, and the published picks returned by the API are unchanged.

#### FR-706: Ticker chart
`/ticker/:symbol` shows a candlestick chart (`lightweight-charts`) with overlays: Supertrend line colored by direction with flip markers, SMA 20 / 50 / 200, the Ripster 5/12 and 34/50 clouds (the 8/9, 72/89 and 180/200 clouds are toggles), Fibonacci levels, support and resistance (strength by opacity). Sub-panels: MACD with histogram, RSI with divergence markers, volume with estimated buy / sell split. Only default overlays are on at first load; toggles persist per browser. The chart is keyboard reachable and has a data table alternative.
- **Given** a ticker, **When** the chart loads, **Then** the Supertrend series length and last value equal the bars endpoint values.
- **Given** an overlay toggled off and the page reloaded, **Then** it stays off.

#### FR-707: Ticker right rail
The right rail shows the full factor table (score, weight, contribution, reasons, quality), regime, adjustments with before and after weights, fundamentals summary and quality, earnings countdown, Supertrend state (direction, weekly direction, bars since flip, line, distance in ATR), Ripster state (34/50 bias, stack, bars since stack flip, 34/50 cloud edges), and the history of this ticker's scores and pick appearances.
- **Given** a ticker in a ranging regime, **Then** the rail shows the regime badge and "Weights adjusted: ranging regime" with before and after weights.

#### FR-708: Watchlist and ranking screen
Group filter, sortable ranking table for the selected date (score, band, confidence, Supertrend direction and age, regime, relative volume, data quality) with a TrendRibbon per row, add, remove, and group actions, and a list of excluded and unresolved tickers with reasons.
- **Given** the table sorted by confidence, **Then** sorting is stable (ties keep the published rank order).
- **Given** an invalid symbol added, **Then** the API's problem detail is shown inline.

#### FR-709: Track Record screen
Summary tiles per side and horizon with sample sizes, a table of every past pick with outcome columns, filters (date range, side, band, config version), an excess-return distribution chart, and a separate "Backtest (hypothetical)" tab. Losing picks have the same prominence as winners.
- **Given** a history containing misses, **Then** misses appear in the table with the same styling weight as hits, and no default filter hides them.
- **Given** the backtest tab, **Then** every figure carries the "hypothetical" label.

#### FR-710: Runs screen and manual runs
History with state, duration, exclusions, and a "Run now" button (token required) that shows live progress by polling the run state.
- **Given** no token entered, **When** "Run now" is pressed, **Then** a token prompt appears.
- **Given** a run already in progress, **Then** the button is disabled and shows the running state.

#### FR-711: Settings screen
Read-only view of the active scoring config, its version and hash; theme; API token entry; provider and LLM status. The token is stored in memory by default, with optional localStorage after a warning. No secret is ever rendered.
- **Given** a stored token, **When** Settings renders, **Then** the token value is not displayed.

#### FR-712: Date browsing
`/date/:yyyy-mm-dd` shows exactly what was published for that trading date (the published run for the date, after any supersession), with a link to the config document that produced it.
- **Given** a past date with a published run, **Then** the cards equal the stored recommendations for that run and the config hash link opens that config.
- **Given** a non-trading date or a date with no published run, **Then** an empty state explains why.

#### FR-713: Disclaimer on every recommendation screen
The disclaimer (section 5) is always visible on every screen that shows a recommendation (Today, date view, Ticker when it shows a pick, Watchlist ranking, Track Record).
- **Given** any route that shows a pick, **When** it renders, **Then** the full disclaimer text is present in the DOM and visible without interaction.

#### FR-714: Estimated order flow labeling
Buy/sell volume is labeled "estimated order flow" with its quality level (`intraday`, `daily_estimate`, or `trades`). No copy claims visibility into the real order book.
- **Given** a pick with flow quality `daily_estimate`, **Then** the card shows "estimated order flow" and the `daily_estimate` tag.

#### FR-715: Not color alone
Buy and sell are never distinguished by color alone: every indication pairs color with a text label and a shape. The ribbon has a text alternative (for example "Up 14 sessions, flipped 3 sessions ago").
- **Given** the Today screen in grayscale, **Then** buys and sells remain distinguishable.

#### FR-716: Loading, empty, error, stale states
Every screen has loading, empty, error, and stale states. A 500 from the API renders the ErrorState with a retry, never a blank screen. Stale data shows the as-of date and a stale indicator.
- **Given** the API returns 500, **Then** the ErrorState with a retry action is shown.

#### FR-717: Regime, event, and narrative source display
Regime badges, "weights adjusted" explanation with before and after weights, earnings countdown with the `event_risk` flag for picks with earnings within 5 trading days, fundamentals summary panel, and the narrative source tag (LLM model name or "template").
- **Given** a pick with `days_to_earnings` 3, **Then** the card shows the `event_risk` flag and "earnings in 3 trading days".

#### FR-718: End-of-day honesty in presentation
Every number shows its as-of date. No fake "live" feel; data refreshes in place without layout shifts. No modal dialogs for reading content (modals only confirm destructive or token-gated actions).
- **Given** a refresh of data, **Then** the layout does not shift.

#### FR-719: Prohibited presentation
No confetti, rockets, flames, "to the moon" language, or celebratory animation; no certainty language ("guaranteed", "sure thing", "can't lose", "will go to"); no gradients on data, 3D charts, or pie charts; no green and red as the only signal of direction.
- **Given** a copy lint over UI strings, **Then** no banned phrase is present.

#### FR-720: License notice
The UI footer shows "Copyright Serverless Ventures LLC. Noncommercial use only." with a link to the license (`SUPERTRENDS_SOURCE_URL`). README, DISCLAIMER, and the UI state that the project is software for running your own analysis, provides no signals service, and that each user needs their own market data license.
- **Given** any route, **Then** the footer notice and link are present.

#### FR-721: Demo mode UI
With `SUPERTRENDS_DEMO=1`, every screen shows the banner "DEMO DATA: synthetic prices, not real markets", and `/demo` lists every product function with a link to the screen that shows it and its live PASS or FAIL status. Outside demo mode the banner and route are absent.
- **Given** demo mode, **Then** the banner is on every route. **Given** normal mode, **Then** `/demo` returns the not-found view and no banner appears.

#### FR-722: UI delivery and headers
The API serves `ui/dist` with hashed assets immutable and `index.html` no-cache, an SPA fallback, a strict Content-Security-Policy with no inline scripts or styles and `connect-src 'self'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `frame-ancestors 'none'`. Fonts are self-hosted (no CDN).
- **Given** a request for `/`, **Then** the CSP and security headers are present.

#### FR-723: Accessibility
WCAG 2.2 AA contrast in both themes (dark default, light available); all interactive elements are keyboard reachable.
- **Given** an axe scan on every route, **Then** there are zero serious or critical issues.

### 8.9 API, CLI, and MCP (FR-8xx)

#### FR-801: HTTP endpoints
The API exposes the endpoints listed in section 12.1 under `/api/v1`, plus `/healthz`, `/readyz`, `/metrics`, and `/mcp`. All responses are JSON; an OpenAPI document is committed at `docs/openapi.json`, regenerated by `make openapi`, and CI fails on drift.
- **Given** a change to an endpoint without regenerating `docs/openapi.json`, **When** CI runs, **Then** the drift check fails.

#### FR-802: Latest recommendations payload
`GET /api/v1/recommendations/latest` returns the latest published run: date, run_id, published_at, market_regime, config (version and hash), buys, sells, also_qualified, nearest_miss, excluded, and disclaimer, in the shape shown in section 12.2. `GET /api/v1/recommendations?date=` returns the same shape for a date.
- **Given** a published run, **Then** the payload validates against the schema, has at most 3 buys and at most 2 sells, and each pick has evidence fields (`supertrend`, `invalidation`, `top_factors`, `narrative`, `ribbon`, `flags`, `days_on_list`).
- **Given** no published run exists yet, **Then** the response is 404 problem JSON with a clear detail.

#### FR-803: Disclaimer in payloads
Every API payload that contains picks includes the top-level `"disclaimer"` field with the exact text of section 5.
- **Given** responses from `/recommendations/latest`, `/recommendations?date=`, `/rankings`, `/tickers/{symbol}/analysis`, `/tickers/{symbol}/history`, and `/track-record`, **Then** each contains the disclaimer string.

#### FR-804: Rankings, analysis, bars, history
`GET /api/v1/rankings?date=&limit=&offset=` returns the full ranked watchlist with scores; `GET /api/v1/tickers/{symbol}/analysis?date=` returns the factor table, evidence, levels, regime, adjustments, and narrative; `GET /api/v1/tickers/{symbol}/bars?tf=1d&from=&to=` returns bars plus overlay series (Supertrend with direction, SMAs, Ripster clouds, and levels); `GET /api/v1/tickers/{symbol}/history` returns the ticker's scores and pick appearances over time.
- **Given** 200 scored tickers, **When** rankings are requested with `limit=50&offset=50`, **Then** ranks 51 to 100 are returned with the total count.

#### FR-805: Authentication and rate limiting
Read endpoints need no token inside the network boundary. Write endpoints (`POST /api/v1/runs`, watchlist changes, MCP write tools, `/mcp` over HTTP) require `Authorization: Bearer <SUPERTRENDS_API_TOKEN>`, compared in constant time, and are rate limited.
- **Given** a wrong token, **Then** the write returns 401 problem JSON. **Given** writes above the rate limit, **Then** 429 is returned.

#### FR-806: Validation and errors
Every parameter is validated: symbols match `^[A-Z][A-Z0-9.\-]{0,9}$`, dates are trading dates, pagination is bounded. Errors follow RFC 9457 problem details.
- **Given** `date=2026-11-15` (a Sunday), **Then** the response is 422 problem JSON stating it is not a trading date.
- **Given** `limit=100000`, **Then** the response is 422 or the limit is capped at the documented maximum.

#### FR-807: Manual run trigger
`POST /api/v1/runs` (token) triggers a run for the latest completed session or a given date and returns the run ID and state; it returns 409 if a run is in progress. `GET /api/v1/runs?limit=` and `GET /api/v1/runs/{id}` return history and detail (state, timestamps, exclusions).
- **Given** a run in progress, **When** a second trigger arrives, **Then** the response is 409 with "already running" and the existing run ID.

#### FR-808: Health, readiness, metrics, host allowlist
`/healthz` returns process status, version, and commit (`{"status":"ok", ...}`); `/readyz` returns 503 when the database is unreachable or migrations are not at head; `/metrics` serves Prometheus metrics. Requests whose `Host` header is not in `SUPERTRENDS_ALLOWED_HOSTS` are rejected.
- **Given** the database down, **Then** `/readyz` returns 503 and `/healthz` returns 200.
- **Given** `Host: evil.example`, **Then** the request is rejected with 400.

#### FR-809: Status and config endpoints
`GET /api/v1/status` returns data freshness, latest run, provider and LLM health, and the license notice "Copyright Serverless Ventures LLC. Noncommercial use only." with the source link. `GET /api/v1/config/scoring` returns the active config document, version, and hash.
- **Given** the LLM endpoint unreachable, **Then** status reports LLM health as down and narratives as falling back to template.

#### FR-810: CLI commands
The `supertrends` CLI (Typer) provides: `today [--json]`, `analyze TICKER [--date] [--json]`, `rank [--date] [--top N]`, `watchlist list|add|remove`, `run daily [--date]`, `ingest`, `backtest`, `track-record`, `status`, `serve`, `mcp`, `healthcheck`, `db migrate|backup`, `config show|validate`, and `--version` (prints `supertrends {VERSION} ({commit})` and the license notice). Remote mode uses `--api-url` and `SUPERTRENDS_API_TOKEN`; local mode talks to the database directly.
- **Given** any command, **Then** `--help` prints usage text.
- **Given** `supertrends today --json`, **Then** the output validates against the API schema and equals the `/recommendations/latest` payload for the same run.

#### FR-811: CLI exit codes and disclaimer
Exit codes: 0 ok, 1 error, 2 usage, 3 not ready. Human-readable output that contains a pick ends with the disclaimer; JSON output contains the `disclaimer` field.
- **Given** the database unreachable, **When** `supertrends status` runs, **Then** it exits 3.
- **Given** `supertrends today` with picks, **Then** the disclaimer is printed.

#### FR-812: MCP server transports
The MCP server (official Python SDK) runs over stdio (`supertrends mcp`) and streamable HTTP mounted at `/mcp` on the API (bearer token required).
- **Given** an MCP client over stdio, **When** it lists tools, **Then** all seven tools in section 12.3 are returned.
- **Given** an HTTP MCP request without a token, **Then** it is rejected.

#### FR-813: MCP tools and schemas
Tools: `supertrends_recommend {date?}`, `supertrends_analyze {ticker, date?}`, `supertrends_rank {date?, top?}`, `supertrends_watchlist {action: list|add|remove, ticker?}`, `supertrends_status {}`, `supertrends_track_record {from?, to?, side?}`, `supertrends_run {date?}`. Input schemas are strict (no additional properties). Outputs equal the corresponding API payloads.
- **Given** `supertrends_recommend` with no date, **Then** the result equals `/recommendations/latest` including evidence and disclaimer.
- **Given** an extra property in the input, **Then** the call is rejected with a schema error.

#### FR-814: MCP write authorization
`supertrends_watchlist` add and remove and `supertrends_run` require the token over HTTP.
- **Given** an unauthenticated HTTP call to `supertrends_run`, **Then** an error is returned and no run starts.

#### FR-815: MCP disclaimer and descriptions
Every tool result that contains a pick includes the disclaimer. Every tool description ends with: "Informational market analysis only. Super Trends places no trades and gives no personalized advice."
- **Given** the tool list, **Then** every description ends with that sentence.

#### FR-816: Surface parity
The UI, API, CLI, and MCP return the same picks, scores, and evidence for the same run.
- **Given** a published run, **When** the picks are fetched via API, `supertrends today --json`, and `supertrends_recommend`, **Then** tickers, ranks, display scores, and confidence are identical.

#### FR-817: Pi extension
`integrations/pi/` provides `@stokeai-supertrends/pi-extension` on `pi-agent-core` with TypeBox tool schemas mirroring the MCP tools, slash commands `/supertrends today`, `/supertrends analyze <ticker>`, `/supertrends rank`, and streaming progress for `supertrends_run` through `onUpdate`. It calls the HTTP API.
- **Given** a mocked API, **When** `/supertrends today` runs, **Then** it renders today's picks with the disclaimer.

#### FR-818: Goose, OpenCode, and Claude Code integration
`integrations/goose/toolkit.yaml` (stdio and HTTP variants), `integrations/opencode/README.md`, and `integrations/claude-code/README.md` (`.mcp.json` snippet) configure the MCP server.
- **Given** each config, **When** a validation script starts the stdio server with that config's command line, **Then** the tool list is returned.

#### FR-819: Agent daily-brief skill
`.agent/skills/daily-brief/` documents how an agent fetches today's picks, summarizes them faithfully, and what it must not do (no trade execution, no position sizing, always carry the disclaimer).
- **Given** a running instance, **When** the skill's `run.sh` runs, **Then** it prints today's picks with the disclaimer.

### 8.10 Operations (FR-9xx)

#### FR-901: Run state machine
`supertrends run daily [--date]` runs the state machine `queued -> ingesting -> computing -> scoring -> selecting -> narrating -> published | failed`. Each transition is persisted with a timestamp.
- **Given** a run, **When** `GET /api/v1/runs/{id}` is polled, **Then** the state advances through the sequence and ends `published` or `failed`.

#### FR-902: Atomic publication
Publication writes recommendations and sets `runs.published_at` in a single transaction. A failed or partial run never replaces the last good published result.
- **Given** the process is killed mid-run, **Then** the previous published run remains "latest" and no partial recommendations are visible.
- **Given** fault injection (provider 429 storm, provider outage, database restart, LLM timeout, half-day session, missing intraday data, delisted ticker, split on run day), **Then** each ends in a correct published run or a clean failed run with the previous result still latest.

#### FR-903: Reruns and supersession
One run per trading date is the published one. A rerun for the same date creates a new run row that supersedes the old one only on success (`superseded_by` set on the old run); both remain stored.
- **Given** a published run for date D and a successful rerun for D, **Then** the rerun is the published result for D and the original remains queryable as superseded.
- **Given** a failed rerun, **Then** the original remains the published result.

#### FR-904: Single concurrent run
A database advisory lock prevents concurrent runs.
- **Given** two simultaneous triggers, **Then** one run is created and the other trigger receives "already running".

#### FR-905: Schedule
The daily run is a Kubernetes CronJob with schedule `30 17 * * 1-5`, `timeZone: America/New_York`, and `concurrencyPolicy: Forbid`, calling `supertrends run daily`. On non-trading days the command exits 0 with "market closed" and publishes nothing. Locally, `make run-daily` does the same.
- **Given** a market holiday, **When** the CronJob fires, **Then** the command exits 0, prints "market closed", and no run is published.

#### FR-906: Run summary
Each run stores a summary: tickers scored, tickers excluded with reasons, provider errors, narrative sources, duration, and config hash.
- **Given** a completed run, **Then** `GET /api/v1/runs/{id}` lists exclusions with reasons and the counts.

#### FR-907: Metrics
The service emits: `supertrends_run_duration_seconds`, `supertrends_run_state_total{state}`, `supertrends_tickers_scored`, `supertrends_tickers_excluded{reason}`, `supertrends_data_freshness_seconds`, `supertrends_provider_requests_total{provider,status}`, `supertrends_provider_rate_limited_total`, `supertrends_narrative_total{source,result}`, `supertrends_narrative_tokens{kind}`, `supertrends_picks_published{side}`.
- **Given** a completed run, **When** `/metrics` is scraped, **Then** each metric is present with plausible values.

#### FR-908: Alerts and dashboard
A Grafana dashboard JSON (`deploy/dashboards/`) shows run health, data freshness, and provider errors. PrometheusRule alerts: no published run for the latest completed session by 19:00 ET; data stale; provider error rate above 20 percent for 15 minutes; narrative fallback rate above 50 percent for a run.
- **Given** the rules file, **Then** `promtool check rules` passes, and the dashboard loads in Grafana without errors.

#### FR-909: Structured logs and secret redaction
Logs are JSON lines (structlog) with a request ID. A processor redacts secrets; `provider_calls` stores only path and non-secret params. No secret value is ever logged or returned by an API.
- **Given** a log-scrubbing test that injects a known secret, **Then** no log line contains it.

#### FR-910: Data retention
Intraday bars older than 90 days are deleted; `provider_calls` older than 30 days are deleted; daily bars, recommendations, factor scores, narratives, and outcomes are kept forever. Retention never deletes rows referenced by a recommendation's evidence window.
- **Given** an intraday bar 91 days old that is not in any evidence window, **When** retention runs, **Then** it is deleted.

#### FR-911: Backup and restore
`supertrends db backup` wraps `pg_dump` to a file path; restore is documented.
- **Given** a backup, **When** restored into an empty database, **Then** recommendations and outcomes round-trip.

#### FR-912: Database migrations
`supertrends db migrate` applies Alembic migrations; a migration Job hook runs them on Helm install and upgrade.
- **Given** an empty database, **Then** `alembic upgrade head` and `downgrade base` both succeed.

#### FR-913: Demo mode
`make demo` starts the app, Postgres, and an LLM mock with `SUPERTRENDS_DEMO=1` and the fixture provider, seeds synthetic data, and replays the last 60 trading days through the real run orchestrator. The latest demo run has 3 buys and 2 sells, one ticker in each regime, a fresh Supertrend flip, a divergence, a Fibonacci hold, a breakout, an `event_risk` pick, and one excluded ticker. `make demo-verify` prints one PASS or FAIL line per function in the demo matrix, writes `demo-report/index.html` with a screenshot per screen, and exits non-zero on any FAIL. `make demo-down` cleans up. Demo mode cannot be enabled together with a real provider.
- **Given** a machine with only Docker, **When** `make demo` runs, **Then** it ends with a URL and a populated latest run within 3 minutes, with no API key, network access, or cluster.
- **Given** `SUPERTRENDS_DEMO=1` and `SUPERTRENDS_MARKET_PROVIDER=massive`, **Then** startup fails with a clear message.

#### FR-914: Deployment and rollback
Super Trends deploys to the Stoke k3s cluster through one Flux HelmRelease referencing a signed OCI chart (`oci://ghcr.io/mohnishbasha/charts/stokeai-supertrends`) and the image by digest, with install and upgrade remediation (automatic rollback) and Helm tests. Manual rollback is one command (`helm rollback` with Flux suspended, documented in `docs/DEPLOYMENT.md`). Namespaces: `supertrends-stage` and `supertrends`.
- **Given** a failing upgrade, **Then** Flux remediation rolls back automatically, and a manual rollback restores the previous release with smoke tests passing.

#### FR-915: Environments and configuration
Environments `dev`, `ci`, `stage`, `prod` and the environment variables in section 12.5 configure the service. All settings use the `SUPERTRENDS_` prefix.
- **Given** `SUPERTRENDS_ENV=prod` without a database URL, **Then** startup fails naming the missing variable.

#### FR-916: Outbound network boundary
Zero third-party telemetry. Outbound traffic only to the configured market data provider, fundamentals provider, and LLM endpoint. Provider and LLM base URLs come only from configuration, never from request input.
- **Given** an integration test with egress blocked except to mocks, **Then** no other connection is attempted.

#### FR-917: Secrets
Secrets (market data API key, fundamentals API key, API bearer token, LLM API key if required, database password) come only from environment variables sourced from Kubernetes Secrets (`existingSecret`). They are never in values files, git, logs, metrics, or API responses.
- **Given** the Helm chart schema, **When** a secret value is placed in values, **Then** schema validation fails.

#### FR-918: Personal data and brokerage boundary
Super Trends never asks for or stores holdings, account size, risk tolerance, or goals, has no brokerage integration, and never outputs position sizes, options strikes or expiries, leverage, or order instructions.
- **Given** the database schema and API contract, **Then** no table or field stores personal financial data, and no endpoint accepts it.

#### FR-919: Platform targets
The single image runs `serve`, `run daily`, `mcp`, and other CLI commands on `linux/arm64` and `linux/amd64`, requests no GPU, runs as non-root (UID 10001) with a read-only root filesystem.
- **Given** the Stoke profile rendered with `helm template`, **Then** only ARM64-compatible images appear and no GPU resource is requested.

---

## 9. Non-functional requirements

NFR-001 to NFR-012 are reproduced verbatim from the seed. NFR-013 onward extend them.

| ID | Requirement |
|---|---|
| NFR-001 | A full daily run for the 200-symbol seed watchlist completes in under 10 minutes on the Stoke cluster, excluding vendor rate-limit waits. Indicator and scoring compute for 200 tickers with 3 years of daily bars completes in under 60 seconds on 2 ARM64 cores. |
| NFR-002 | Scoring is deterministic: same bars plus same config hash produces byte-identical factor scores and ranking. The LLM never influences a score. |
| NFR-003 | The Today screen renders its first meaningful paint in under 1.5 seconds on the tailnet with a warm API. |
| NFR-004 | API p95 latency under 200 ms for read endpoints with 200 tickers and 1 year of stored runs. |
| NFR-005 | The product runs on `linux/arm64` (Stoke) and `linux/amd64` (CI, dev). No GPU is requested or required. |
| NFR-006 | A failed or partial run never replaces the last good published result. Publication is atomic. |
| NFR-007 | No look-ahead: an indicator value for bar t uses only data up to and including bar t. Enforced by a property test. |
| NFR-008 | Zero third-party telemetry. No outbound calls except the configured market data provider and the configured LLM endpoint. |
| NFR-009 | All secrets come from Kubernetes Secrets or environment variables. No secret value is ever committed, logged, or returned by an API. |
| NFR-010 | Memory ceiling for the API pod: 512 MiB. For a run job: 1.5 GiB. |
| NFR-011 | Accessibility: WCAG 2.2 AA contrast. Buy and sell are never distinguished by color alone. |
| NFR-012 | Narrative token budget: at most 900 prompt tokens and 220 completion tokens per pick, enforced in code and reported as a metric. A CI test fails if the rendered prompt for the fixture set exceeds the budget. |
| NFR-013 | A backtest over 2 years and 20 tickers completes in under 3 minutes on 2 cores. |
| NFR-014 | `make demo` on a machine with only Docker ends with a URL and a populated latest run within 3 minutes, with no API key, network access, or cluster. |
| NFR-015 | Test coverage: indicator modules at or above 95 percent; scoring and selection at or above 92 percent; thresholds recorded in `.coverage-thresholds.toml` and enforced in CI. |
| NFR-016 | LLM narrative acceptance rate (passing the numeric guard, banned-phrase, and length checks on the first or retry attempt) at or above 90 percent on the Stoke model, measured by `make narrative-eval`. |
| NFR-017 | Containers run as a non-root user (UID 10001) with a read-only root filesystem, all capabilities dropped, `allowPrivilegeEscalation: false`, `seccompProfile: RuntimeDefault`, `automountServiceAccountToken: false`, and resource requests and limits on every container. |
| NFR-018 | No test calls the network. Providers and the LLM are mocked or recorded; CI runs the test step with outbound network blocked. |
| NFR-019 | Images are multi-arch, signed with cosign (keyless), carry SBOM and provenance attestations, and pass a Trivy scan with no high or critical findings. |
| NFR-020 | Narrative generation per pick times out after 8 seconds; narrative failures never fail or delay publication beyond one retry per pick. |

---

## 10. Default scoring configuration (`config/scoring.yaml`)

This is the default configuration. Values match section 7. The schema requires the twelve weights to sum to 100. Any change to weights, thresholds, or formulas bumps `scoring.version` (FR-331).

```yaml
scoring:
  version: 1
min_history_bars: 250
liquidity:
  min_avg_dollar_volume_20d: 20000000
supertrend:
  atr_length: 10
  factor: 3.0
  fresh_flip_bars: 5
  stretch_atr: 4.0
sma:
  periods: [20, 50, 200]
  slope_bars: 5
  cross_lookback: 10
macd:
  fast: 12
  slow: 26
  signal: 9
  cross_lookback: 3
  weekly_disagree_multiplier: 0.75
divergence:
  pivot_width_daily: 5
  pivot_width_weekly: 3
  window_bars: 60
  recency_bars: 15
  points: { rsi: 40, macd_hist: 35, obv: 25 }
  hidden_multiplier: 0.5
  weekly_confirm_multiplier: 1.25
mean_reversion:
  window: 20
  z_cap: 2.5
  rsi_length: 14
  rsi_low: 30
  rsi_high: 70
fibonacci:
  lookback_bars: 120
  min_reversal_pct: 0.08
  min_reversal_atr: 3.0
  near_atr: 0.5
levels:
  lookback_bars: 250
  pivot_width: 5
  cluster_atr: 0.5
  breakout_rel_volume: 1.5
volatility:
  atr_length: 14
  bb_length: 20
  bb_mult: 2.0
  squeeze_rank: 15
  expansion_rank: 85
  extreme_atr_rank: 90
volume:
  osc_short: 5
  osc_long: 10
  obv_slope_bars: 20
flow:
  intraday_timeframe: 5m
  window_sessions: 10
  min_sessions_for_intraday: 8
  cmf_length: 20
  daily_estimate_weight_multiplier: 0.6
fundamentals:
  stale_days: 120
  stale_weight_multiplier: 0.5
ripster:
  source: hl2
  ma_type: ema
  clouds:
    c1: [8, 9]
    c2: [5, 12]
    c3: [34, 50]
    c4: [72, 89]
    c5: [180, 200]
  points: { bias: 30, trend: 20, stack: 20, mid: 10, long: 10, pullback: 10 }
  pullback_lookback_bars: 3
  confidence_stack_conflict_penalty: 10
  selection_bias_gate: true
weights:
  supertrend: 20
  sma: 7
  macd: 8
  divergence: 9
  mean_reversion: 7
  fibonacci: 5
  levels: 7
  volatility: 4
  volume_osc: 6
  flow: 9
  fundamentals: 8
  ripster: 10
regime:
  adx_length: 14
  trending_min: 25
  ranging_max: 20
  multipliers:
    trending:     { supertrend: 1.25, sma: 1.20, macd: 1.10, divergence: 0.90, mean_reversion: 0.50, fibonacci: 1.00, levels: 0.90, ripster: 1.20 }
    ranging:      { supertrend: 0.70, sma: 0.70, macd: 0.90, divergence: 1.20, mean_reversion: 1.60, fibonacci: 1.10, levels: 1.40, ripster: 0.70 }
    transitional: {}
events:
  earnings_window_days: 5
  earnings_fundamentals_multiplier: 1.5
thresholds:
  buy_display_min: 65
  sell_display_max: 35
  min_confidence: 50
  weak_fundamentals_score: -40
  strong_fundamentals_score: 40
  fundamentals_threshold_shift: 5
  market_regime_threshold_shift: 5
selection:
  max_buys: 3
  max_sells: 2
  correlation_window: 60
  correlation_max: 0.9
benchmarks: [SPY, QQQ]
track_record:
  horizons_days: [1, 5, 10, 20]
  small_sample: 20
```

Notes on the configuration:
- Factor IDs in `weights` and `regime.multipliers` are the registry IDs of FR-302. Missing keys under a regime (for example `transitional: {}`, or `volatility` under `trending`) mean a multiplier of 1.00.
- `thresholds.buy_display_min` and `thresholds.sell_display_max` are the base thresholds before the shifts in FR-320 to FR-322.
- `liquidity.min_avg_dollar_volume_20d` is the liquidity floor of FR-401 and FR-402.

---

## 11. Watchlist seed

Extracted on 2026-11-14 from 15 TradingView watchlists. Totals: 229 equity and ETF entries across 14 groups, 200 unique symbols; 72 unique crypto pairs in 2 lists.

Rules for the seed:
- Write the first block to `config/watchlist.seed.yaml` exactly. A symbol may belong to several groups; store membership many-to-many and score each symbol once.
- At first ingest, validate every symbol against the provider's reference data. A symbol that does not resolve is never guessed or silently replaced: it is recorded as `unresolved` with the reason, excluded from scoring, shown on the Watchlist screen, and added to the owner checklist.
- Symbols under `needs_review` start excluded until the owner confirms them, except those whose note says only "may be missing" or "confirm the current symbol", which are attempted and fall back to `unresolved`.
- `VIX` is not scored. Ingest it only if the provider offers the index, and expose it as evidence for the market regime.
- The seed holds 200 unique equity and ETF symbols, so the watchlist cap is 300 to leave room.
- Crypto pairs are extracted and kept in `config/watchlist.crypto.yaml` so nothing is lost, but they are not ingested or scored in v1 (see Out of Scope: crypto trades around the clock on a different calendar and needs a different data feed).
- These lists are the seed only. The owner's later edits live in the database, not in git.

`config/watchlist.seed.yaml`:

```yaml
version: 1
benchmarks: [SPY, QQQ]
groups:
  datacenters:
    tradingview_name: Datacenters
    source: https://www.tradingview.com/watchlists/346453847/
    symbols: [DELL, NBIS, CRWV]
  adam-khoo-megatrends:
    tradingview_name: AdamKhoo-2026-6MegaTrend-Rest5
    source: https://www.tradingview.com/watchlists/319539679/
    symbols: [NVO, LLY, TMO, IDXX, EW, VEEV, IQV, UNH, HCA, XLV, VHT, IHI, V, MA, AXP]
  adam-khoo-ai-robotics:
    tradingview_name: AdamKhoo-2026-6MegaTrends-AIRobotics
    source: https://www.tradingview.com/watchlists/319537378/
    symbols: [TSLA, XPEV, XIACF, NVDA, PTC, KRKNF, ISRG, SYK, MDT, ARAY, PRCT, ROK, CGNX, AMZN, SYM, MBLY,
      OUST, INVZ, SERV, HON, TER, LECO, AVAV, KTOS, RCAT, RR, AIQ, ARTY, ROBO, BOTZ, SHLD]
  whatsapp-group:
    tradingview_name: AustinMarathiGappa
    source: https://www.tradingview.com/watchlists/173086630/
    symbols: [TSLA, APLD, BBAI, CLSK, HUT, COUR, CRNT, SOUN, CLS, SPYG, NBIS, IREN, CBRS]
  bnpl:
    tradingview_name: BNPL
    source: https://www.tradingview.com/watchlists/167402637/
    symbols: [AFRM, PYPL, SQ]
  cnbc:
    tradingview_name: CNBC
    source: https://www.tradingview.com/watchlists/167396731/
    symbols: [APO, BKR, BLK, CG, CIBR, CWEN, JPM, KBE, LYFT, TOST, UBER, WAB]
  from-crypto-lists:
    tradingview_name: CoinMarket50
    source: https://www.tradingview.com/watchlists/167959926/
    symbols: [CFLT]
  country-etfs:
    tradingview_name: CountryETF
    source: https://www.tradingview.com/watchlists/330331417/
    symbols: [SPY, EWZ, EEM, EWY, FXI, IEMG, VEA, VXUS, EWJ, VOO, EWT, INDA, MCHI, VTI, IVV, EWH, ILF,
      EWC, EWG, EWU, EWW, EIDO, ECH, EWS, XIC, EWP, EWL, EPOL, EWQ, INDY, EPHE, EWI, EWD, EWN, TUR, EZA,
      EIS, THD, AFK, ENOR, EWO, EDEN, EWK, EFNL, VNM]
  fab-7:
    tradingview_name: FAB7
    source: https://www.tradingview.com/watchlists/167396259/
    symbols: [META, GOOG, AAPL, AMZN, TSLA, NVDA, MSFT, PLTR]
  index-etf:
    tradingview_name: INDICES
    source: https://www.tradingview.com/watchlists/167396650/
    symbols: [VIX, SPY, SPLG, QQQ, IWR, IWN, IWM, DIA, XLB, XLC, XLE, XLF, XLI, XLK, XLP, XLRE, XLU, XLY,
      XLV, VCX]
  sector-etf:
    tradingview_name: SECTOR
    source: https://www.tradingview.com/watchlists/167399513/
    symbols: [COPX, GLD, IBIT, SLV, SMH, TIP, TLT, UUP, XLB, XLC, XLF, XLI, XLK, XLP, XLRE, XLU, XLV,
      XLY]
  semis:
    tradingview_name: SEMI
    source: https://www.tradingview.com/watchlists/167403824/
    symbols: [AMD, NVDA, REMX, SNDK, QCOM, ARM, INTC, '000660', GFS, MRVL, MU]
  xlk-tech:
    tradingview_name: Tech - XLK
    source: https://www.tradingview.com/watchlists/345550912/
    symbols: [MSFT, AAPL, NVDA, AVGO, ORCL, CRM, PLTR, CSCO, AMD, ACN]
  trump-stocks:
    tradingview_name: Trump Stock Tracker
    source: https://www.tradingview.com/watchlists/167123620/
    symbols: [TSLA, MARA, HUT, MSTR, RIOT, CITI, BTBT, C, JPM, KMI, LMT, COIN, WFC, EVR, DJT, CAT, MS,
      XOM, BAC, GTLS, LHX, BKR, GS, IWO, CVX, KKR, VLO, RTX, MMM, GD, IWM, LAZ, NOC, DE, COP, CXW, BA,
      HON, GEO]
needs_review:
  SQ: Block changed its ticker from SQ to XYZ in 2025; confirm and use the current symbol
  CITI: not a US-listed ticker; Citigroup is C, which is already in this group
  '000660': SK hynix on the Korea Exchange; not a US listing, needs a provider that covers KRX
  VIX: an index, not a tradable security with volume; use as a market-regime input, do not score
  XIACF: OTC (Xiaomi); may be missing from the provider or fail the liquidity floor
  KRKNF: OTC; may be missing from the provider or fail the liquidity floor
  XIC: Toronto-listed ETF; not a US listing
  VCX: could not be identified; confirm what this is
  CBRS: could not be identified; confirm what this is
  SPLG: confirm the current symbol for this S&P 500 ETF with the provider
  CFLT: Confluent stock, found in the crypto list; confirm it is still listed
```

`config/watchlist.crypto.yaml`:

```yaml
version: 1
status: 'deferred: not ingested or scored in v1'
groups:
  coinmarket-top-50:
    tradingview_name: CoinMarket50
    source: https://www.tradingview.com/watchlists/167959926/
    symbols: [PEPEUSD, DOGEUSD, SOLUSD, WIFUSD, BONKUSD, SHIBUSD, XMRUSD, AAVEUSD, ARBUSD, VETUSDC, BNBUSD,
      LINKUSD, HBARUSD, LTCUSD, APTUSD, TRXUSD, UNIUSD, CLVUSD, FETUSD, ETCUSD, ADAUSD, XRPUSD, KASUSD,
      CRVUSD, RENDERUSD, NEARUSD, TONUSD, BTCUSD, DOTUSD, ATOMUSD, XLMUSD, DAIUSD, BCHUSD, FILUSD, SUIUSD,
      USDC, TAOUSD, POLUSD, ICPUSD, TETUSD, CROUSD, AVAXUSD]
  crypto:
    tradingview_name: Crypto
    source: https://www.tradingview.com/watchlists/167576420/
    symbols: [PEPEUSD, BONKUSD, ETHUSD, BONKBTC, ETHBTC, PROUSD, LINKUSD, HBARUSD, CTSIBTC, LTCUSD, CTSIUSD,
      AMPUSD, LINKBTC, LTCBTC, UNIUSD, ETCUSD, ALGOUSD, FETUSD, HBARBTC, VETUSD, XRPUSD, MANAUSD, RENDERUSD,
      RENDERBTC, NEARUSD, SHPINGUSD, JASMYUSD, FETBTC, JASMYBTC, BTCUSD, NEARBTC, DOTUSD, ATOMUSD, XLMUSD,
      DOTBTC, VETBTC, ALGOBTC, BCHUSD, AMPBTC, BCHBTC, ATOMBTC, MATICUSD, MATICBTC, AVAXUSD, AVAXBTC,
      NMRUSD, MANABTC]
```

---

## 12. Product surfaces reference

Full request, response, and error contracts live in `docs/ARCHITECTURE.md` and `docs/openapi.json`. This section fixes the product-level surface.

### 12.1 HTTP API

All responses are JSON. Errors follow RFC 9457. Every payload containing picks includes `"disclaimer"`.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/healthz` | none | Liveness: status, version, commit |
| GET | `/readyz` | none | Readiness: database and migrations |
| GET | `/metrics` | none (cluster-internal) | Prometheus metrics |
| GET | `/api/v1/recommendations/latest` | none | Latest published run: buys, sells, also-qualified, nearest misses, market regime, run summary |
| GET | `/api/v1/recommendations?date=YYYY-MM-DD` | none | Published picks for a date |
| GET | `/api/v1/rankings?date=&limit=&offset=` | none | Full ranked watchlist for a date |
| GET | `/api/v1/tickers/{symbol}/analysis?date=` | none | Factor table, evidence, levels, regime, narrative |
| GET | `/api/v1/tickers/{symbol}/bars?tf=1d&from=&to=` | none | Bars plus overlay series (Supertrend, SMAs, Ripster clouds) |
| GET | `/api/v1/tickers/{symbol}/history` | none | This ticker's scores and pick appearances over time |
| GET | `/api/v1/watchlist` | none | Watchlist and groups |
| POST | `/api/v1/watchlist/items` | token | Add a ticker |
| DELETE | `/api/v1/watchlist/items/{symbol}` | token | Remove a ticker |
| GET | `/api/v1/runs?limit=` | none | Run history |
| GET | `/api/v1/runs/{id}` | none | Run detail, state, exclusions |
| POST | `/api/v1/runs` | token | Trigger a run; 409 if one is in progress |
| GET | `/api/v1/track-record?from=&to=&side=&band=&config=` | none | Statistics and pick outcomes |
| GET | `/api/v1/config/scoring` | none | Active scoring config and hash |
| GET | `/api/v1/status` | none | Data freshness, provider and LLM health |
| POST | `/mcp` | token | MCP streamable HTTP |

### 12.2 Shape of `GET /api/v1/recommendations/latest`

```json
{
  "date": "2026-11-13",
  "run_id": "01JCX...",
  "published_at": "2026-11-13T22:34:10Z",
  "market_regime": "risk_on",
  "config": {"version": 1, "hash": "sha256:..."},
  "buys": [
    {
      "rank": 1, "ticker": "ORCL", "display_score": 78.4, "band": "Buy", "confidence": 71,
      "supertrend": {"dir_d": 1, "dir_w": 1, "bars_since_flip": 3, "line": 212.4},
      "regime": "trending", "flags": [], "days_on_list": 1,
      "invalidation": {"level": 212.4, "rule": "daily close below the Supertrend line"},
      "top_factors": [{"id": "supertrend", "contribution": 23.4}, {"id": "macd", "contribution": 9.1}],
      "narrative": {"text": "...", "source": "llm", "model": "..."},
      "ribbon": "UUUUDDDUUU"
    }
  ],
  "sells": [],
  "also_qualified": [],
  "nearest_miss": {"sell": {"ticker": "XYZ", "display_score": 37.2, "reason": "score above the sell threshold of 35"}},
  "excluded": [{"ticker": "ABC", "reason": "stale"}],
  "disclaimer": "Super Trends output is general market analysis ..."
}
```

`ribbon` encodes the last 60 sessions of daily Supertrend direction (`U` up, `D` down), oldest first; the example is truncated. The `disclaimer` value is the full text of section 5.

### 12.3 MCP tools

| Tool | Input | Output | Auth |
|---|---|---|---|
| `supertrends_recommend` | `{date?}` | picks with evidence and disclaimer | none (stdio), token (HTTP) |
| `supertrends_analyze` | `{ticker, date?}` | factor table, levels, regime, narrative | same |
| `supertrends_rank` | `{date?, top?}` | ranked list | same |
| `supertrends_watchlist` | `{action: list or add or remove, ticker?}` | watchlist | token for add and remove |
| `supertrends_status` | `{}` | latest run, freshness, provider and LLM health | same as read |
| `supertrends_track_record` | `{from?, to?, side?}` | statistics with sample sizes | same as read |
| `supertrends_run` | `{date?}` | run id and state | token |

Every tool description ends with: "Informational market analysis only. Super Trends places no trades and gives no personalized advice."

### 12.4 CLI

| Command | Purpose |
|---|---|
| `supertrends today [--json]` | Latest published picks with evidence and disclaimer |
| `supertrends analyze TICKER [--date] [--json]` | Factor breakdown, levels, regime, narrative |
| `supertrends rank [--date] [--top N]` | Ranked watchlist |
| `supertrends watchlist list\|add\|remove` | Watchlist management (add and remove require the token in remote mode) |
| `supertrends run daily [--date]` | Run the daily loop; exits 0 with "market closed" on non-trading days |
| `supertrends ingest` | Ingestion only |
| `supertrends backtest --from YYYY-MM-DD --to YYYY-MM-DD --config config/scoring.yaml` | Hypothetical replay |
| `supertrends track-record` | Track record statistics |
| `supertrends status` | Latest run, data freshness, provider and LLM health |
| `supertrends serve` | Start the API and UI |
| `supertrends mcp` | Start the MCP server on stdio |
| `supertrends healthcheck` | Container health check |
| `supertrends db migrate\|backup` | Migrations and backups |
| `supertrends config show\|validate` | Show or validate the scoring config |
| `supertrends --version` | `supertrends {VERSION} ({commit})` plus the license notice |

Exit codes: 0 ok, 1 error, 2 usage, 3 not ready.

### 12.5 Environments and environment variables

| Environment | Where | Data provider | LLM | Purpose |
|---|---|---|---|---|
| dev | Host or Compose | fixture (default) or real | mock or any OpenAI-compatible endpoint | Daily development |
| ci | GitHub Actions, kind | fixture | mock | Tests, chart install |
| stage | Stoke, namespace `supertrends-stage` | real | Stoke gateway | Pre-release validation |
| prod | Stoke, namespace `supertrends` | real | Stoke gateway | The owner's daily use |

On Stoke, stage and prod are two namespaces on the same cluster. Super Trends is CPU-only and small, so this costs no GPU capacity. Stage scales to zero replicas outside release weeks (`replicaCount: 0`, CronJob suspended).

### Environment variables

| Name | dev | stage | prod | Notes |
|---|---|---|---|---|
| `SUPERTRENDS_ENV` | `dev` | `stage` | `prod` | |
| `SUPERTRENDS_DATABASE_URL` | `postgresql+psycopg://supertrends:supertrends@localhost:5432/supertrends` | from Secret | from Secret | |
| `SUPERTRENDS_MARKET_PROVIDER` | `fixture` | `massive` | `massive` | `fixture`, `massive`, or the alternate |
| `SUPERTRENDS_FUNDAMENTALS_PROVIDER` | `fixture` | `massive` | `massive` | may differ from the market provider |
| `SUPERTRENDS_MASSIVE_API_KEY` | empty | from Secret | from Secret | |
| `SUPERTRENDS_MASSIVE_BASE_URL` | `https://api.massive.com` | same | same | legacy host also works |
| `SUPERTRENDS_PROVIDER_RATE_PER_MIN` | `5` | per plan | per plan | match the purchased plan |
| `SUPERTRENDS_LLM_BASE_URL` | `http://localhost:8089/v1` (mock) | gateway URL from inventory | same | OpenAI-compatible |
| `SUPERTRENDS_LLM_MODEL` | `mock` | model served on Stoke | same | |
| `SUPERTRENDS_LLM_API_KEY` | empty | from Secret if required | same | |
| `SUPERTRENDS_NARRATIVE_PROVIDER` | `template` | `openai_compatible` | `openai_compatible` | falls back to template |
| `SUPERTRENDS_API_TOKEN` | `dev-token` | from Secret | from Secret | write endpoints |
| `SUPERTRENDS_SCORING_CONFIG` | `config/scoring.yaml` | mounted ConfigMap | mounted ConfigMap | |
| `SUPERTRENDS_RUN_CRON` | n/a | `30 17 * * 1-5` | `30 17 * * 1-5` | America/New_York |
| `SUPERTRENDS_LOG_LEVEL` | `debug` | `info` | `info` | |
| `SUPERTRENDS_SOURCE_URL` | repo URL | repo URL at commit | repo URL at commit | license and source link shown in the UI |
| `SUPERTRENDS_ALLOWED_HOSTS` | `localhost` | `supertrends-stage.openstoke.com` | `supertrends.openstoke.com` | Host header allowlist |
| `SUPERTRENDS_BIND` | `127.0.0.1:8080` | `0.0.0.0:8080` | `0.0.0.0:8080` | |

---

## 13. Glossary

| Term | Definition |
|---|---|
| Supertrend | A trend-following indicator (TradingView built-in, ATR length 10, factor 3.0) that draws a line a multiple of ATR below price in an up trend and above price in a down trend; the line ratchets in the trend direction and the direction flips when price closes through it. Super Trends uses `+1` for up and `-1` for down. Section 7.2. |
| ATR (Average True Range) | The Wilder (RMA) average of the true range, where true range is `max(high-low, |high-prev_close|, |low-prev_close|)`. Supertrend uses ATR(10); other factors use `atr14`. |
| RMA | Wilder's smoothing: seeded with the SMA of the first n values, then `rma[t] = (rma[t-1] * (n-1) + x[t]) / n`. |
| EMA | Exponential moving average with alpha = 2/(n+1), seeded with the SMA of the first n values. |
| SMA | Simple moving average: the arithmetic mean of the last n values. |
| Factor | One of the twelve scoring components (Supertrend, SMA, MACD, Divergences, Mean reversion, Fibonacci, Support and resistance, Volatility, Volume oscillator, Buy / sell volume, Fundamentals, Ripster EMA Clouds). Each returns a factor score from -100 to +100, evidence items, and a quality flag. |
| Factor score | A factor's output in the closed range -100 (max bearish) to +100 (max bullish). |
| Quality | Per-factor data quality: `ok`, `degraded`, or `missing`. Missing factors are excluded from the composite; degraded factors lower confidence. |
| Data quality status | Per-ticker ingestion status: `ok`, `degraded`, `stale`, or `insufficient_history`. Stale and insufficient-history tickers are excluded. |
| Ripster EMA Clouds | Ripster47's TradingView indicator: five bands, each between a short and a long EMA of `hl2` (8/9, 5/12, 34/50, 72/89, 180/200). Super Trends uses the 34/50 cloud as the trend bias and the 8/9 cloud as the pullback zone. Section 7.13. |
| Regime | The per-ticker market character from ADX(14): `trending` (ADX >= 25), `ranging` (ADX < 20), or `transitional`. It changes factor weights. |
| Market regime | The benchmark filter from the daily Supertrend of SPY and QQQ: `risk_on` (both up), `risk_off` (both down), or `neutral` (mixed). It shifts selection thresholds. |
| Weight | A factor's share of the composite after base weights, regime multipliers, event and quality adjustments, and renormalization to 100. |
| Composite | `sum(w_i * s_i) / sum(w_i)` over factors with quality other than missing; range -100 to 100. |
| Contribution | `weight * score / 100` for one factor; contributions sum to the composite. |
| Display score | `round((composite + 100) / 2, 1)`, range 0 to 100; the score shown to the user and used for bands and thresholds. |
| Band | The label for a display score range: Strong Buy, Buy, Neutral leaning up, Neutral leaning down, Sell, Strong Sell (section 7.15). Aligned with TastyStocks. |
| Confidence | A 0 to 100 measure of how much of the weight agrees with the composite's sign, reduced for extreme volatility, degraded data, weekly Supertrend conflict, and event risk. It is not a probability. |
| Threshold | The display score a ticker must reach to be a candidate: 65 for buys and 35 for sells by default, shifted by fundamentals and market regime. |
| Candidate | A ticker meeting all selection rules for a side (section 7.16). |
| Pick | A candidate selected for publication on a side after ranking and the correlation guard. |
| Also qualified | A candidate skipped by the correlation guard because it duplicates an already selected pick. |
| Nearest miss | For a side with fewer picks than the maximum, the scored ticker closest to qualifying, with the reason it missed. |
| Invalidation level | The price at which the view is wrong: the daily Supertrend line. A buy is invalidated by a daily close below it; a sell by a daily close above it. |
| Event risk | The `event_risk` flag set when `days_to_earnings <= 5` trading days. |
| Estimated order flow | Buy and sell volume estimated from bar data (5-minute bars, or daily bars as a fallback) by where the close sits in the bar's range. It is an estimate, not real order book or trade data. |
| Flow quality | The data level behind estimated order flow: `intraday`, `daily_estimate`, or `trades` (optional, future). |
| Entry price | The next session's open after a pick is published; the starting price for its forward returns. |
| Forward return | The pick's return from entry price to the close of the session 1, 5, 10, or 20 trading days later. |
| Excess return | The pick's forward return minus SPY's return over the same window. |
| Hit | A buy with positive excess return, or a sell with negative excess return, at a given horizon. |
| Hit rate | Hits divided by the number of outcomes at that horizon, reported with the sample size. |
| Small sample | A label on any statistic computed from fewer than 20 outcomes. |
| Evidence document | The structured JSON record stored for each pick with scores, weights, contributions, reasons, levels, invalidation, adjustments, flags, and config hash (section 7.17). The only input to the narrative. |
| Narrative | The 3 to 5 sentence justification for a pick, written by an LLM from the evidence document (checked by the numeric guard) or by a deterministic template. |
| Numeric guard | The post-generation check that every number in an LLM narrative matches a value in the evidence document within rounding. |
| Config hash | `sha256:` plus the sha256 of the canonical JSON of `config/scoring.yaml`; recorded with every result to identify the exact config that produced it. |
| Scoring version | The integer `scoring.version` in the config, bumped on any change to weights, thresholds, or formulas. |
| Run | One execution of the daily loop for a trading date, with persisted states from `queued` to `published` or `failed`. |
| Published run | The run whose results are shown for a trading date; publication is atomic. |
| Backtest | A hypothetical replay of the daily loop over stored history with no look-ahead. |
| Look-ahead | Using any data from after bar t to compute a value for bar t. Forbidden everywhere. |
| Pivot | A bar whose low (or high) is lower (or higher) than the `width` bars on each side, confirmed only `width` bars later. |
| Divergence | A disagreement between price pivots and oscillator pivots (regular or hidden, bullish or bearish). |
| ZigZag | A swing detector that marks a new swing only after price reverses by the threshold. |
| Relative volume | `volume / SMA20(volume)`. |
| Dollar volume | Close times volume; the liquidity floor uses its 20-day average. |
| Day N on the list | The count of consecutive published trading days a ticker has been a pick on the same side. |
| Benchmarks | SPY and QQQ, always ingested. |

---

## 14. Out of scope for v1

Each item below becomes a GitHub issue with the `enhancement` label and no milestone.

| Item | Why deferred |
|---|---|
| Brokerage integration and order placement | Hard boundary: Super Trends informs, it does not trade. Also a large security and regulatory surface |
| Options analytics (chains, IV rank, strike or expiry suggestions) | Different data, different risk; would turn general analysis into specific trade ideas |
| Position sizing, portfolio tracking, personal P and L | Requires personal financial data, which Super Trends deliberately does not hold |
| Multi-user accounts, SSO, sharing picks with others, paid tiers | Needs legal review first (see Compliance posture) and an auth system |
| Intraday or real-time signals, streaming quotes | v1 is an end-of-day product; real time needs a paid feed and a different architecture |
| True order-flow data (L2 book, tick-level trade classification) | Costly data; the `trades` capability flag leaves the door open |
| Crypto, futures, forex, non-US equities | Different calendars and data; equities and ETFs first |
| News and social sentiment factor | Unstructured inputs raise prompt-injection and quality risks |
| Machine-learned weights or a neural scoring model | Needs a long track record to train and validate against; v1 stays transparent and rule-based. A natural later use of Stoke GPUs |
| Auto-tuning of `config/scoring.yaml` from backtests | Overfitting risk; v1 keeps tuning manual and versioned |
| Push, email, or chat notifications | Useful, but not needed to prove the core loop |
| Mobile app and desktop app | The responsive web UI is enough for v1 |
| Publishing picks into TastyStocks memos | Cross-product integration after both are stable |
| Multiple watchlists with separate runs | One watchlist with groups covers v1 |
| Public internet exposure | Private by default; needs auth and legal review |

Additional v1 boundaries that follow from the list: no public sharing features of any kind, no crypto ingestion (pairs are kept in `config/watchlist.crypto.yaml` only), no stickiness rule between days, and no `trades` order-flow provider (interface only).

---

## 15. Traceability: user stories to functional requirements

| Story | Functional requirements | NFRs |
|---|---|---|
| US-001 | FR-334, FR-401, FR-402, FR-404, FR-406, FR-702, FR-703, FR-802, FR-902, FR-905 | NFR-003, NFR-006 |
| US-002 | FR-333, FR-501, FR-502, FR-504, FR-505, FR-507, FR-703, FR-707 | NFR-012 |
| US-003 | FR-204, FR-205, FR-206, FR-703, FR-706, FR-804 | NFR-007 |
| US-004 | FR-001 to FR-012, FR-708, FR-810, FR-813 | |
| US-005 | FR-207, FR-224, FR-213, FR-214, FR-706, FR-804 | NFR-011 |
| US-006 | FR-404, FR-708, FR-804 | NFR-004 |
| US-007 | FR-503, FR-703 | |
| US-008 | FR-601 to FR-608, FR-709 | |
| US-009 | FR-317, FR-318, FR-323, FR-707, FR-717 | |
| US-010 | FR-116, FR-319, FR-327, FR-717 | |
| US-011 | FR-710, FR-807, FR-901, FR-904, FR-906 | |
| US-012 | FR-331, FR-332, FR-712, FR-903 | |
| US-013 | FR-316, FR-330, FR-331, FR-332, FR-711 | NFR-002 |
| US-014 | FR-609 to FR-613 | NFR-013 |
| US-015 | FR-812, FR-813, FR-815, FR-816 | |
| US-016 | FR-813, FR-804, FR-816 | |
| US-017 | FR-914, FR-919 | NFR-005, NFR-019 |
| US-018 | FR-907, FR-908 | |
| US-019 | FR-504, FR-510, FR-512 | NFR-020 |
| US-020 | FR-107, FR-108, FR-109, FR-118, FR-412 | |
| US-021 | FR-327, FR-703 | |
| US-022 | FR-407, FR-408, FR-704 | |
| US-023 | FR-409, FR-410, FR-703 | |
| US-024 | FR-217, FR-218, FR-313, FR-714 | |
| US-025 | FR-411, FR-703 | |
| US-026 | FR-001, FR-705, FR-708 | |
| US-027 | FR-007, FR-008, FR-109, FR-708 | |
| US-028 | FR-213, FR-214, FR-311, FR-501, FR-703 | |
| US-029 | FR-115, FR-116, FR-314, FR-315, FR-707 | |
| US-030 | FR-810, FR-811, FR-816 | |
| US-031 | FR-813, FR-814, FR-815 | |
| US-032 | FR-817 | |
| US-033 | FR-907, FR-908 | |
| US-034 | FR-910, FR-911 | |
| US-035 | FR-111, FR-721, FR-913 | NFR-014 |
| US-036 | FR-713, FR-803, FR-811, FR-815 | |
| US-037 | FR-711, FR-809 | |
| US-038 | FR-707, FR-804 | |
| US-039 | FR-604, FR-605, FR-612, FR-709 | |
| US-040 | FR-902, FR-903, FR-904 | NFR-006 |

Every FR in section 8 derives from at least one story, a Signal Engine rule in section 7, or a compliance and security control in section 5. Signal Engine coverage: section 7.1 (FR-101 to FR-103, FR-108, FR-201, FR-203, FR-301), 7.2 (FR-204 to FR-206, FR-303), 7.3 (FR-207, FR-304), 7.4 (FR-208, FR-305), 7.5 (FR-209 to FR-211, FR-306), 7.6 (FR-212, FR-307), 7.7 (FR-213, FR-308, FR-309), 7.8 (FR-214, FR-215, FR-310), 7.9 (FR-212, FR-311), 7.10 (FR-216, FR-312), 7.11 (FR-217 to FR-219, FR-313), 7.12 (FR-115, FR-116, FR-314, FR-315), 7.13 (FR-224, FR-333), 7.14 (FR-220, FR-316 to FR-323), 7.15 (FR-324 to FR-328, FR-335), 7.16 (FR-334, FR-401 to FR-412), 7.17 (FR-501 to FR-515), 7.18 (FR-601 to FR-608), 7.19 (FR-609 to FR-613).

---

## 16. Spec Change Protocol

Any PR that changes user-facing behavior, API contracts, database schema, scoring rules, or architectural decisions must satisfy one of:

- **A, no spec change:** the PR description explicitly states "internal only, no spec change"
- **B, spec updated in same PR:** the relevant `docs/` file is updated alongside the code
- **C, spec issue filed:** a separate GitHub issue is created before the code PR merges, scheduled in the current sprint, and closed within the same sprint

Option C is not a deferral mechanism. Any change to a scoring formula, weight, or threshold is always option B and also bumps `scoring.version` in `config/scoring.yaml`. Formulas, weights, and thresholds are never weakened to make a test pass. If the specification is ambiguous or believed wrong, the most literal reading is implemented, an ADR records the ambiguity and the alternative, and an owner checklist entry is added.

---

## 17. Ambiguities and resolutions

The literal reading of section 7 is implemented. Where it leaves a choice open, the resolution below applies and is recorded as an ADR in `docs/ARCHITECTURE.md` with an owner checklist entry.

| # | Topic | Ambiguity | Resolution in v1 | ADR |
|---|---|---|---|---|
| A-01 | Weight pipeline order | The spec places event adjustments after regime multipliers and before renormalizing, but does not place the quality multipliers (`daily_estimate` x 0.6, stale fundamentals x 0.5) or the removal of `missing` factors. | Order: base weights, regime multipliers, event multiplier, quality multipliers, drop `missing` factors, renormalize to 100. Contributions then sum to the composite (FR-328). | ADR-038 |
| A-02 | Display rounding | `round(x, 1)` does not name a rounding mode; Python's built-in rounds half to even. | Use decimal round half up on the exact composite so 78.45 displays 78.5; covered by a boundary test. | ADR-039 (with ADR-030) |
| A-03 | Divergence weekly multiplier | "If the same divergence type also exists on weekly bars: multiply the total by 1.25" could apply per divergence or to the whole sum, and bullish and bearish divergences can coexist. | Bullish and bearish points are summed with their signs; the 1.25 multiplier applies to the total when at least one daily divergence has a weekly divergence of the same type (regular or hidden, same direction) on the same oscillator. | ADR-040 |
| A-04 | Fibonacci overlapping rules | More than one rule can match at once (for example near 61.8 and near 50.0 when ATR is large relative to the leg), and the spec gives no precedence. | Evaluate in this order and take the first match: close above B (+20), close below 78.6 (-50), near 61.8 and holding (+80), near 50.0 and holding (+70), near 38.2 and holding (+60), otherwise 0. | ADR-041 |
| A-05 | Confidence when composite is 0 | "Same sign as composite" is undefined when composite is exactly 0. | Agreement = 0, so confidence starts at 0. Such a ticker has display 50.0 and cannot be a candidate anyway. | ADR-042 |
| A-06 | Bollinger stdev | The z-score names population stdev; Bollinger Bands do not state which. | Population stdev for both, matching TradingView's `ta.bb`. | ADR-043 |
| A-07 | `daily_estimate` on daily bars | The zero-range rule uses `prev_close`; on daily bars `delta_pct_10` becomes the mean of the daily `delta_pct` values. | Apply the formula per daily bar with the prior daily close, and average over the last 10 sessions. | ADR-044 |
| A-08 | Redundant stale check | Selection requires "data quality not `stale`", but stale tickers are already excluded before scoring. | Both checks stay (defense in depth); a stale ticker never reaches selection. | ADR-045 |
| A-09 | Seed count vs scored count | NFR-001 cites the 200-symbol seed, but VIX is never scored and some `needs_review` symbols start excluded. | NFR-001 is measured on the full seed ingestion set (up to 200 symbols plus benchmarks); scored count is lower and reported. | ADR-046 |
| A-10 | Benchmark return window | "for SPY over the same window" does not state SPY's entry price. | SPY also enters at the next session's open and exits at the same horizon close as the pick. | ADR-036 |
| A-11 | Band boundaries | Bands are stated at one decimal (79.9, 35.1); display scores have one decimal, so there is no gap. | Bands are evaluated on the rounded display score. | ADR-047 |
| A-12 | Correlation returns | "60-day return correlation" does not name the return type. | Pearson correlation of daily close-to-close simple returns over the last 60 sessions both tickers traded. | ADR-048 |
| A-13 | Repository name | The project identity names the repo `stokeai-supertrends` under owner `mohnishbasha`; the repository that already exists (and the working directory) is `stokeai-trading-supertrends`. | BUILD_PROMPT Step 2 says an existing repository is not recreated, and `mohnishbasha/stokeai-trading-supertrends` already exists, so it is used as the GitHub repository. Image, chart, package, CLI, and npm scope keep the Project Identity names (`stokeai-supertrends`, `supertrends`). The owner may rename the repository (OWNER_CHECKLIST item 14). | ADR-017 |
| A-14 | Outbound endpoints | NFR-008 allows only the market data provider and the LLM endpoint; the Security Guidelines also allow the fundamentals provider, which may be a different vendor. | The configured fundamentals provider is an allowed destination (FR-916); NFR-008 is read as covering it. | ADR-049 |
| A-15 | Nearest miss selection | "The nearest candidate" is not defined when several tickers miss for different reasons. | The nearest miss is the scored, non-excluded ticker with the smallest distance between its display score and that side's adjusted threshold; ties use the selection tie-breakers. The reason names the first failing rule in the order of section 7.15. | ADR-050 |
| A-16 | Primitive definitions | The spec does not define the percentile rank window, the RSI of a flat series, or when a ZigZag swing counts as confirmed. | `percentile_rank` is 100 times the share of the window's earlier n-1 values strictly below the current value (ties not counted, trailing window including the current bar). RSI of a window with no gains and no losses is 50. A ZigZag extreme is confirmed on the first close that reverses from it by at least the threshold; the running extreme stays tentative. | ADR-053 |
| A-17 | Supertrend edge cases | The spec leaves open: the line side on the first defined bar, `bars_since_flip` on the first defined bar, and how `st_dir_w` treats the current partial week. | The first defined bar is forced down (spec warm-up rule) and may have the line below close when the factor is under 1; the line-versus-close invariant is asserted for factor >= 1 after that bar. `bars_since_flip` is 0 on the first defined bar. `st_dir_w` on day t is the weekly Supertrend direction with the current week holding only bars up to t (no look-ahead; may differ from the week's final direction). | S2-T02 |
| A-18 | Trend and momentum details | The spec does not say how a cross treats equality, what "slope over 5 bars" is, whether "3 consecutive bars" means 3 values or 3 changes, or how weekly MACD maps to daily bars. | Golden cross at t: `a[t-1] <= b[t-1]` and `a[t] > b[t]` (death mirrored with `>=` and `<`); slope is `sma[t] - sma[t-5]` and only its sign is used; histogram rising or falling means 3 consecutive strict changes (4 values); weekly MACD on day t is computed from completed weeks plus the in-progress week closed at day t's close (no look-ahead). ADX uses the Wilder formulation in ADR-054. | ADR-054 |
| A-19 | Divergence windows | "Within the last 60 bars" and "second pivot within the last 15 bars" do not say whether distances are measured to the pivot bar or its confirmation bar, whether the older pivot must also be inside the 60 bars, or what happens when a newer pivot appears. Weekly windows are not stated. | Distances are measured to the pivot bar: `t - p2 <= 15` and `t - p1 <= 59` (the last 60 bars are `t-59..t`). Only the two most recent confirmed pivots of a kind compare, so a newer confirmed pivot supersedes the pair, and an older pivot outside the window means no divergence. Equal prices or oscillator values are not divergences. Weekly detection uses the same 60 and 15 in weekly bars with pivot width 3. | n/a |
| A-20 | HV20 stdev kind | Spec says "stdev of 20 daily log returns * sqrt(252)" without population or sample. | Population stdev (ddof=0), consistent with the z-score and Bollinger (A-06). Warm-up is 20 returns, so the first value is at bar index 20. | none |
| A-21 | Expansion "bbw rising 3 bars" | Could mean 3 consecutive rises or a net rise over 3 bars. | Literal chain of 3 consecutive rises: bbw[t] > bbw[t-1] > bbw[t-2] > bbw[t-3]. Squeeze and expansion are float flags (1.0 or 0.0, NaN while ranks are in warm-up). | none |
| A-22 | S/R clustering and strength | "Cluster pivots within 0.5 ATR" does not say whether clusters chain (single linkage) or are bounded, and "touches * recency_weight" does not say whether the weight is per touch or per cluster. | Clusters are anchored on their lowest pivot price: a pivot joins while `price - anchor <= 0.5 * atr14`, so all members are within 0.5 ATR of each other; the level is the mean price. Strength is the sum of per-touch recency weights (equal to `touches * mean weight`), weight `1 - 0.7 * age / 250`. Breakout and breakdown compare today's close to the levels as of yesterday. Fibonacci extensions project from A: `A + ratio * (B - A)`. | ADR-055 |
| A-23 | Order flow edge cases | The spec leaves open `prev_close` for a session's first 5-minute bar or the first bar of the data, the delta percent of a zero-volume session, and the clock handling for "regular session 09:30 to 16:00 ET". | The zero-range rule compares with the previous regular-session bar in the input (a session's first bar uses the prior session's last bar); with no previous bar, `close >= prev_close` is taken as true (all buy). A zero-volume session has `delta_pct` NaN and is left out of the 10-session mean. The indicator is clock-free: the caller passes session-local ET bar start times, and bars starting outside [09:30, 16:00) are ignored. `intraday` needs 5-minute bars on at least 8 of the last 10 daily sessions, and the mean is over the finite values of those sessions. | None |
| A-24 | Ripster EMA Clouds fidelity | The seed says to match Ripster47's indicator at default settings but not which price source or EMA seeding, or which bars parity is computed on. | `hl2` and EMA match the TradingView defaults; EMA seeded per section 7.1; parity is computed on the export's own bars; the 72/89 cloud is evidence only. | ADR-051 |
| A-25 | Ripster 8/9 pullback window | The spec says a test of the 8/9 cloud "within the last 3 bars" but not whether the as-of bar counts. | The window is the last `ripster.pullback_lookback_bars` bars including the as-of bar (t-2 to t for 3), each bar's low or high compared with the 8/9 cloud of that same bar. A test 3 bars ago (bar t-3) is outside the window; TS-SCR-196 is read as the oldest bar in the window and S3-T14 confirms it. The snapshot carries the result as `ripster.pullback`. | ADR-059 |
| A-26 | Window counting for crosses and divergence recency | "Within the last 10 bars" (SMA cross), "within the last 3 bars" (MACD cross) and "second pivot within the last 15 bars" do not say whether the as-of bar counts, and the test plan names the boundary "N bars ago". | Crosses: the window is the last N bars including the as-of bar (a cross on the Nth bar counts, the N+1th does not), as `indicators.trend.last_cross` computes it; the factors re-check it as `bars - index <= N`. Divergences: `(bars - 1) - p2 <= recency_bars`, as `detect_divergences`. TS-SCR-038, 039, 057, 058 and 080 read "N bars ago" accordingly. | ADR-060 |
| A-27 | Factor 2 to 4 ties, weekly confirmation, and missing inputs | The spec does not say what a tie (close equal to an SMA, line equal to signal) scores, what "the same divergence type also exists on weekly bars" matches, or what a null input does. | A tie is neither above nor below and adds 0; a level daily or weekly MACD is not a weekly disagreement. "Same type" is the same oscillator, kind (regular or hidden) and side, and applies once to the total only when a counted daily divergence has a weekly match. Null warm-up inputs make the factor `missing`; a null weekly direction or MACD, SMA20 slope, ATR or distance scores that part 0 and marks the factor `degraded`. | ADR-060 |
| A-28 | Fibonacci rules matching more than one level | The spec lists +60, +70 and +80 (near 38.2, 50.0, 61.8 and holding), then -50 and +20, but with `near` within 0.5 ATR two levels can both be near, and a close below the 78.6 level can sit near the 61.8 level on a wide ATR. | Rules are tried in the order listed and the first match wins: 38.2, then 50.0, then 61.8, then the failure rule, then the resume rule. Each hold rule needs its own `holding` test. Down legs mirror this. | ADR-061 |
| A-29 | Support and resistance with an empty side | The spec adds the 52-week high and low as levels and defines `d_s` and `d_r` as `>= 0`, but a close at or beyond the 52-week extreme leaves no level on that side, and `rr` then has no distance. | The distance falls back to the 52-week extreme: `d_r = max(high_52w - close, 0) / atr14`, `d_s = max(close - low_52w, 0) / atr14`. A close at or above the 52-week high therefore gives `d_r = 0`, `rr = 0`, base -40. The breakout flag needs relative volume at least `levels.breakout_rel_volume`, checked again by the factor. | ADR-061 |
