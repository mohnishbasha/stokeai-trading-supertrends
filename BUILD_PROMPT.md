# SUPER TRENDS MARKET AGENT: Master Build Prompt
## Supertrend market agent for StokeAI infra. Tracks a watchlist, scores every ticker, publishes the top 3 buys and top 2 sells each day, and explains why.

Prompt version: 1.1.0
Generated: 2026-11-14
Updated: 2026-11-15 (1.1.0: added Factor 12, Ripster EMA Clouds, with reweighting, a selection gate, and a confidence rule)
Owner: Mohinish Shaikh, Serverless Ventures LLC

---

## Project Identity

**Name:** `Super Trends Market Agent` (short form: Super Trends)
**GitHub repo:** `stokeai-supertrends` (owner `mohnishbasha`, same home as `stokeai-yojna`; set `GH_OWNER` to change it)
**Primary domain:** `supertrends.openstoke.com`. All StokeAI projects and applications live under `openstoke.com` as `{slug}.openstoke.com`; do not propose or register a separate domain. Staging is `supertrends-stage.openstoke.com`. The owner creates the DNS records; the agent never does.
**Python package:** `supertrends`
**npm scope:** `@stokeai-supertrends`
**Container image:** `ghcr.io/mohnishbasha/stokeai-supertrends`
**Helm chart (OCI):** `oci://ghcr.io/mohnishbasha/charts/stokeai-supertrends`
**Binary / CLI name:** `supertrends`
**Tagline:** *Know which way the tape is leaning.*
**Short description (GitHub About field):** Supertrend market agent that scores a watchlist daily and publishes the top 3 buys and top 2 sells with a written justification.
**Repository visibility:** Public. Source-available under a community license. Not "open source": never use that phrase for this project in any file, because the license forbids commercial use.
**Distribution model:** Source-available, free for noncommercial use. Public source, public signed images and Helm chart on GHCR. The reference deployment is self-hosted on StokeAI infra (k3s on NVIDIA DGX Spark, ARM64), and that running instance stays private to its owner.
**License:** Super Trends Community License, which is the PolyForm Noncommercial License 1.0.0 (SPDX `PolyForm-Noncommercial-1.0.0`), unmodified. Copyright 2026 Serverless Ventures LLC, a Delaware limited liability company formed on November 26, 2024. All rights not expressly granted are reserved by Serverless Ventures LLC. Governing law for the CLA, commercial licenses, and any other legal terms the project writes itself is the State of Delaware (the PolyForm license text is used unmodified and is not edited to add this). Anyone may read, run, modify, and share the software for noncommercial purposes (personal use, study, research, hobby projects, and use by charitable, educational, and government organizations). Any commercial use, including selling it, offering it as a paid or hosted service, or using it inside a for-profit business, requires a separate written commercial license from Serverless Ventures LLC (legal@serverlessvc.com). Outside contributors sign a Contributor License Agreement so all rights to license the project commercially stay with Serverless Ventures LLC.
**Long description (README opening):** Super Trends watches a list of stocks, applies the TradingView Supertrend algorithm together with eleven supporting technical and fundamental factors, including Ripster EMA Clouds,, and turns the result into one composite score per ticker. Every trading day it publishes the three strongest buys and the two strongest sells in a web UI, each with the evidence and a plain-language justification.

**Why this name:** It says what the product does. Supertrend is the lead signal, "market agent" is the job. The full name is used in titles and the README; "Super Trends" is the short form in prose and the UI, and `supertrends` is the slug for the CLI, package, namespaces, and metrics.

**Relationship to the existing portfolio:**
- **TastyStocks** is the long-form, fundamentals-first research memo with an 8-factor 0 to 100 model. Super Trends is the daily, technicals-first signal engine. Super Trends reuses the TastyStocks score bands (80 to 100, 65 to 79, 50 to 64, below 50) for its display score so the two products read the same way. Super Trends does not generate memos and does not replace TastyStocks.
- **Stoke / StokeAI** is the infrastructure Super Trends deploys on. Super Trends is a CPU-only workload that consumes an LLM through the existing Stoke gateway. Super Trends does not deploy models, GPUs, or cluster components.

**What Super Trends is not:** it is not a broker, it places no orders, it holds no brokerage credentials, and it is not personalized investment advice. See "Compliance posture" in Security Guidelines.

---

## EXECUTION ORDER: THIS IS MANDATORY

The first action you take when executing this prompt is to generate the five product specification documents listed in Step 1 below. No GitHub setup, no scaffolding, no code of any kind is written before those documents exist on disk and are committed.

1. **Step 1:** Generate the five spec documents in `docs/` and commit them.
2. **Step 2:** GitHub project setup (repo, branches, protections, labels, milestones, board, templates).
3. **Step 3:** Create every GitHub issue for every sprint from `docs/SPRINT_PLAN.md`.
4. **Step 4 onward:** Execute sprints 0 through 9 in order, straight through, with no stop between them. There is one gate, the Final Gate, after Sprint 9.

If you are about to write code and Step 1 is not complete: stop. Complete Step 1 first.

**Spec documents supersede this prompt.** Once `docs/PRD.md` exists, it is the source of truth for product behavior. Once `docs/ARCHITECTURE.md` exists, it is the source of truth for structure and contracts. This prompt seeds those documents. Where a spec doc and this prompt later disagree, the spec doc wins, provided the change went through the Spec Change Protocol.

**No gates until all sprints are done.** Sprints run back to back. Each sprint ends with a non-blocking sprint checklist: check what passes, and log every item that does not in `docs/GATE_DEBT.md` (sprint, item, reason, plan). Then tag the sprint and start the next one. Never stop, wait, or ask for approval between sprints because a checklist item is unmet. The only hard gate is the Final Gate at the end of Sprint 9: every earlier checklist item checked, `docs/GATE_DEBT.md` empty, and the Sprint 9 list green. What still applies on every PR, because it is ordinary engineering and not a gate: tests written first, CI green before merge, spec docs updated. The only things that stop the run before the end are owner-only actions with nothing unblocked left to do.

**TDD is mandatory.** Failing test first, then implementation. No exceptions for "simple" code. Indicator math in particular is tested against golden fixtures before it is trusted.

**Owner-only actions.** Some actions belong to the owner: registering domains, creating API keys with market data vendors, approving pull requests into `main`, merging into the Stoke GitOps repository, and anything that needs cluster-admin credentials you were not given. When you hit one, record it in `docs/OWNER_CHECKLIST.md` (what is needed, why, exact command or URL, which task is blocked), continue with every task that is not blocked, and stop only when nothing unblocked remains.

---

## Step 1: Product Specification Documents

Generate all five documents in full. They are not outlines. Each must be complete enough that a developer who has never seen this prompt could build the product from the documents alone. Commit them in a single commit: `docs: add product specification documents`.

The sections "Product Definition" and "Signal Engine Specification" below are the seed content. Carry every rule in them into the spec docs. Do not weaken, summarize away, or "simplify" any formula.

### Product Definition (seed for docs/PRD.md)

**Users.** One primary user: an active equity and options trader who runs his own infrastructure and wants a disciplined, repeatable daily read on a watchlist. Secondary users: AI agents (Pi, Goose, OpenCode, Claude Code) that query Super Trends through MCP.

**The core feature.** The Today screen: three buy cards and two sell cards for the latest trading day, each with a score, the Supertrend state, a factor contribution breakdown, key price levels, and a written justification. This screen is the product. Everything else supports it.

**The daily loop.**
1. After the US market close, a scheduled run ingests the day's bars for every watchlist ticker and the benchmarks (SPY, QQQ).
2. The indicator engine computes all indicators on daily and weekly bars, and buy/sell volume from intraday bars.
3. Twelve factor scores are computed per ticker. Regime and fundamentals adjust the weights. A composite score is produced.
4. Tickers are ranked. The top 3 qualifying buys and top 2 qualifying sells are selected.
5. A justification is written for each pick from the computed evidence.
6. Results are stored immutably and shown in the UI, the API, the CLI, and MCP.
7. Later runs measure how earlier picks performed and update the track record.

**Honesty requirements (these are functional requirements, not copy).**
- The algorithm is not always right, and the product says so. Every pick shows a confidence value and an invalidation level ("this view is wrong if price closes below X").
- The Track Record screen shows every past pick and what happened next, including the losers. Picks are never edited or deleted after publication.
- If fewer than 3 tickers qualify as buys or fewer than 2 as sells, Super Trends shows fewer. It never pads the list to hit the count. An empty side shows "No qualifying sells today" with the nearest candidate and the reason it missed.
- Buy/sell volume is an estimate derived from bar data. The UI labels it "estimated order flow" and shows the data quality level. Super Trends never claims to see the real order book.
- Every screen that shows a recommendation carries the disclaimer text defined in Security Guidelines.

**User stories (minimum set, expand in the PRD to at least 24).**

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

**Functional requirements.** Write FR-001 onward in the PRD, at least 60, each with acceptance criteria in Given / When / Then form. Group them: Watchlist (FR-0xx), Ingestion (FR-1xx), Indicators (FR-2xx), Scoring (FR-3xx), Selection (FR-4xx), Justification (FR-5xx), Track record and backtest (FR-6xx), UI (FR-7xx), API / CLI / MCP (FR-8xx), Operations (FR-9xx). Every rule in the Signal Engine Specification below becomes at least one FR.

**Non-functional requirements (minimum, carry into the PRD as NFR-001 onward).**

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

### Signal Engine Specification (seed for docs/PRD.md and docs/ARCHITECTURE.md)

This is the heart of the product. Implement it exactly. All parameters live in `config/scoring.yaml`; the values below are the defaults.

#### Conventions

- Bars are OHLCV, split and dividend adjusted, in exchange time (America/New_York). Daily bars are primary. Weekly bars are resampled from daily (week ending Friday). Intraday bars are 5-minute, regular session only.
- Minimum history to score a ticker: 250 daily bars. Below that the ticker is `insufficient_history` and excluded.
- Every factor returns a **factor score** in the closed range -100 (max bearish) to +100 (max bullish), a list of **evidence items** (name, value, unit, human reason), and a **quality** flag (`ok`, `degraded`, `missing`).
- `clip(x, a, b)` bounds x to [a, b]. `RMA` is Wilder's smoothing: seeded with the SMA of the first n values, then `rma[t] = (rma[t-1] * (n-1) + x[t]) / n`. `EMA` uses alpha = 2/(n+1), seeded with the SMA of the first n values.
- Trend direction convention inside Super Trends: `+1` is up (bullish), `-1` is down (bearish). Note that TradingView's `ta.supertrend` returns the opposite sign (negative means up). Super Trends converts at the boundary and documents it; never mix the two conventions.

#### Factor 1: Supertrend (the lead factor)

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

#### Factor 2: SMA analysis

SMA 20, 50, 200 on daily closes.

```
+30 / -30   close above / below SMA200
+25 / -25   SMA50 above / below SMA200
+20 / -20   close above / below SMA50
+15 / -15   SMA20 slope over 5 bars positive / negative
+10 / -10   golden cross / death cross (SMA50 vs SMA200) within the last 10 bars
score = clip(sum, -100, 100)
```

#### Factor 3: MACD

MACD(12, 26, 9) on daily closes: `line = EMA12 - EMA26`, `signal = EMA9(line)`, `hist = line - signal`.

```
+35 / -35   line above / below signal
+25 / -25   line above / below zero
+25 / -25   hist rising / falling for 3 consecutive bars
+15 / -15   bullish / bearish signal cross within the last 3 bars
score = clip(sum, -100, 100)
```

Weekly MACD is computed and reported as evidence. If weekly `line` vs `signal` disagrees with daily, multiply the factor score by 0.75.

#### Factor 4: Divergences

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

#### Factor 5: Mean reversion

```
z       = (close - SMA20) / stdev20                      (population stdev of 20 closes)
pct_b   = (close - lowerBB) / (upperBB - lowerBB)         (Bollinger 20, 2.0; evidence only)
rsi     = RSI(14)
z_part  = -60 * clip(z / 2.5, -1, 1)                      (stretched up is bearish, stretched down is bullish)
rsi_part= +40 if rsi <= 30; -40 if rsi >= 70; else linear from +40 at 30 to -40 at 70
score   = clip(z_part + rsi_part, -100, 100)
```

This factor fights the trend factors on purpose. The regime weighting below decides who wins.

#### Factor 6: Fibonacci retracement

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

#### Factor 7: Support and resistance

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

#### Factor 8: Volatility

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

#### Factor 9: Volume oscillator

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

#### Factor 10: Buy / sell volume (estimated order flow)

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

#### Factor 11: Fundamentals overlay

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

#### Factor 12: Ripster EMA Clouds

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

#### Regime detection and dynamic weights

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

#### Composite score, confidence, and bands

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

#### Selection rules

A ticker is a **buy candidate** when all hold: display >= 65 (plus any threshold adjustments), `st_dir_d == +1`, `rc_bias >= 0` (close not below the 34/50 cloud), confidence >= 50, data quality not `stale`, average 20-day dollar volume >= 20,000,000.

A ticker is a **sell candidate** when all hold: display <= 35 (minus any threshold adjustments), `st_dir_d == -1`, `rc_bias <= 0` (close not above the 34/50 cloud), confidence >= 50, data quality not `stale`, same liquidity floor.

"Sell" means bearish: reduce, exit, or avoid. Super Trends does not recommend short selling or any specific instrument, size, or expiry.

Ranking: buys by display descending; sells by display ascending. Tie-breakers in order: higher confidence, more recent Supertrend flip, higher relative volume, alphabetical ticker. Publish the top 3 buys and top 2 sells. Counts are config (`selection.max_buys`, `selection.max_sells`).

Correlation guard: the watchlist contains many near-duplicates (several S&P 500 ETFs, sector ETFs and their largest holdings). Walk each side's ranked candidates in order and skip any candidate whose 60-day return correlation with an already selected pick on that side is above 0.9, until the side is full or candidates run out. Skipped tickers are shown as "also qualified" with the pick they duplicate.

Stickiness rule: none in v1. Each day stands alone. A ticker may appear on consecutive days; the UI shows "day N on the list".

#### Justification

For each pick, store a structured evidence document:

```json
{
  "ticker": "ORCL", "date": "2026-11-13", "side": "buy",
  "display_score": 78.4, "confidence": 71, "band": "Buy",
  "regime": "trending", "market_regime": "risk_on",
  "supertrend": {"dir_d": 1, "dir_w": 1, "bars_since_flip": 3, "line": 212.40, "distance_atr": 1.2},
  "ripster": {"bias": 1, "stack": 1, "bars_since_stack_flip": 12, "c2_dir": 1, "c3_dir": 1, "c3_top": 210.8, "c3_bot": 206.3, "dir_w": 1},
  "invalidation": {"level": 212.40, "rule": "daily close below the Supertrend line"},
  "levels": {"support": [215.1, 208.7], "resistance": [229.5, 236.0], "fib": {"61.8": 214.2}, "cloud_34_50": [206.3, 210.8], "next_target": 236.0},
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

#### Track record

For every published pick store `entry_price = next session's open`. On later runs compute forward returns at 1, 5, 10, and 20 trading days, for the pick and for SPY over the same window. A buy "hit" is a positive excess return versus SPY; a sell "hit" is a negative excess return. Report hit rate, mean and median excess return, and worst pick, per side, per horizon, overall and by band, with the sample size next to every statistic. Statistics with fewer than 20 samples are labeled "small sample".

#### Backtest

`supertrends backtest --from YYYY-MM-DD --to YYYY-MM-DD --config config/scoring.yaml` replays the daily loop over stored history with no look-ahead (indicators at day t use bars up to t; entries at t+1 open; fundamentals use the value known at t). Output: the same track-record statistics plus an equity curve for "equal weight the daily buys, hold 5 days", against SPY. Backtest results are labeled as hypothetical everywhere they appear.

### docs/PRD.md

Must contain: product summary, users, the daily loop, all user stories (US-001 onward), all functional requirements with acceptance criteria, all non-functional requirements, the full Signal Engine Specification (formulas verbatim), the honesty requirements, the disclaimer text, a glossary (Supertrend, ATR, RMA, Ripster EMA Clouds, regime, display score, confidence, invalidation level, hit, excess return), and an explicit "Out of scope for v1" list.

### docs/ARCHITECTURE.md

Must contain:
- System overview diagram (ASCII) and component responsibilities.
- Decision log (ADR-001 onward), seeded from Appendix A.
- Data flow for the daily run, a manual run, and a UI read.
- Full database schema (tables, columns, types, indexes, constraints).
- API contract for every HTTP endpoint (method, path, auth, request, response, errors), every CLI command, and every MCP tool.
- Provider interfaces (`MarketDataProvider`, `FundamentalsProvider`, `NarrativeProvider`) with method signatures and capability flags.
- Run state machine and the atomic publication rule.
- Security model and trust boundaries.
- A "Build and Deployment" chapter that mirrors the Build and Deployment section of this prompt, including the Stoke profile and the Flux layout.
- Observability: metrics names, log fields, dashboards, alerts.

### docs/DESIGN.md

Must contain: color tokens, typography, spacing, component inventory with states, ASCII wireframes for every screen (Today, Ticker, Watchlist, Track Record, Runs, Settings), the signature element, chart conventions, empty / loading / error / stale states for every screen, accessibility rules, and anti-patterns. Seed it from the Design System section of this prompt.

### docs/SPRINT_PLAN.md

Must contain: all 10 sprints, every task with ID, title, labels, description, acceptance criteria, estimate (S / M / L), and dependencies, plus each sprint's non-blocking checklist and the Final Gate as unchecked boxes. Seed it from the sprint sections of this prompt. You may add tasks. You may not remove tasks or checklist items.

### docs/TEST_PLAN.md

Must contain: test strategy, the test pyramid for this product, coverage targets, naming convention, the golden-fixture policy for indicators, the no-look-ahead property test, the determinism test, the smoke checklist used after every deploy, and test scenarios for every feature area with a status column (Deferred / Automated / Skipped with reason).

---

## Step 2: GitHub Project Setup

Run these after Step 1 is committed. `GH_OWNER` defaults to `mohnishbasha`.

### Repository initialization

```bash
export GH_OWNER="${GH_OWNER:-mohnishbasha}"
git init -b main
git add docs/ BUILD_PROMPT.md
git commit -m "docs: add product specification documents"
gh repo create "$GH_OWNER/stokeai-supertrends" --public --source=. --remote=origin \
  --description "Supertrend market agent that scores a watchlist daily and publishes the top 3 buys and top 2 sells with a written justification."
git push -u origin main
git checkout -b staging && git push -u origin staging
git checkout -b develop && git push -u origin develop
gh repo edit --default-branch develop --enable-issues --delete-branch-on-merge
gh repo edit --add-topic supertrend --add-topic technical-analysis --add-topic trading --add-topic kubernetes --add-topic mcp
# Public repo hygiene
gh api -X PUT "repos/$GH_OWNER/stokeai-supertrends/vulnerability-alerts"
gh api -X PATCH "repos/$GH_OWNER/stokeai-supertrends" \
  -f "security_and_analysis[secret_scanning][status]=enabled" \
  -f "security_and_analysis[secret_scanning_push_protection][status]=enabled"
# Fork PR workflow approval ("require approval for all external contributors") and private vulnerability
# reporting are repo settings: verify the current API for each, or record them in the owner checklist.
```

If the repository already exists, do not recreate it. Add the remote and continue.

### Branch strategy

```
main      -> production releases only, protected, requires 1 approval
staging   -> staging environment, protected, requires passing CI
develop   -> integration branch, all feature work merges here, requires passing CI
feature/* -> off develop
fix/*     -> off develop (or main for hotfixes)
chore/*   -> non-functional changes
docs/*    -> documentation only
```

Rules:
- No direct commits to `main` or `staging`. Ever.
- All PRs require passing CI before merge.
- Hotfixes branch from `main`, merge to `main`, and back-merge to `develop`.
- `main` is tagged for every release using semantic versioning.

### Branch protection

```bash
protect() { # branch, approvals
  gh api -X PUT "repos/$GH_OWNER/stokeai-supertrends/branches/$1/protection" \
    -H "Accept: application/vnd.github+json" \
    -f "required_status_checks[strict]=true" \
    -f "required_status_checks[contexts][]=ci / lint-and-typecheck" \
    -f "required_status_checks[contexts][]=ci / unit-tests" \
    -F "enforce_admins=false" \
    -F "required_pull_request_reviews[required_approving_review_count]=$2" \
    -F "restrictions=null" -F "allow_force_pushes=false" -F "allow_deletions=false"
}
protect main 1
protect staging 0
protect develop 0
```

`staging` and `develop` require green CI but zero approvals so the unattended runner can keep moving between sprints. `main` requires the owner's approval. When a PR into `main` is waiting, record it in `docs/OWNER_CHECKLIST.md`. If branch protection is unavailable on the account plan, record that in the owner checklist and enforce the same rules by discipline.

### Label taxonomy (create all, minimum 40)

```bash
mk() { gh label create "$1" --color "$2" --description "$3" --force; }
# type
mk "type:feature" 1D76DB "New capability";        mk "type:bug" D73A4A "Defect"
mk "type:chore" C5DEF5 "Tooling and upkeep";      mk "type:docs" 0075CA "Documentation"
mk "type:test" BFD4F2 "Tests only";               mk "type:refactor" D4C5F9 "No behavior change"
mk "type:spike" FBCA04 "Time-boxed research";     mk "type:security" B60205 "Security work"
# area
mk "area:data" 0E8A16 "Providers, ingestion, storage"
mk "area:indicators" 0E8A16 "Indicator math"
mk "area:scoring" 0E8A16 "Factors, weights, selection"
mk "area:narrative" 0E8A16 "Justification and LLM"
mk "area:api" 0E8A16 "HTTP API";                  mk "area:ui" 0E8A16 "Web UI"
mk "area:cli" 0E8A16 "CLI";                       mk "area:mcp" 0E8A16 "MCP server and harnesses"
mk "area:track-record" 0E8A16 "Outcomes and backtest"
mk "area:deploy" 0E8A16 "Images, Helm, Flux, Stoke"
mk "area:ci" 0E8A16 "GitHub Actions";             mk "area:observability" 0E8A16 "Metrics, logs, alerts"
# priority
mk "priority:p0" B60205 "Blocks the sprint"; mk "priority:p1" D93F0B "Must ship this sprint"
mk "priority:p2" FBCA04 "Should ship";            mk "priority:p3" C2E0C6 "Nice to have"
# status
mk "status:blocked" 000000 "Waiting on something"; mk "status:owner-action" 5319E7 "Needs the owner"
mk "status:needs-spec" E99695 "Spec update required"; mk "status:in-review" 006B75 "PR open"
# size
mk "size:S" EDEDED "Up to half a day"; mk "size:M" EDEDED "About a day"; mk "size:L" EDEDED "Two to three days"
# sprint
for n in 0 1 2 3 4 5 6 7 8 9; do mk "sprint:$n" 5319E7 "Sprint $n"; done
mk "enhancement" A2EEEF "Deferred past v1"
```

### Milestones

One per sprint, titled exactly as below (the runner reads them). Set due dates one week apart starting from the day Step 2 runs; sprint 3 gets two weeks.

```bash
ms() { gh api "repos/$GH_OWNER/stokeai-supertrends/milestones" -f title="$1" -f description="$2" >/dev/null; }
ms "Sprint 0: Scaffold"            "Tooling, CI, empty shell, image skeleton"
ms "Sprint 1: Data Layer"          "Providers, storage, watchlist, ingestion"
ms "Sprint 2: Indicator Engine"    "All indicators with golden fixtures"
ms "Sprint 3: Scoring and Daily Picks" "The core feature: factors, composite, selection, daily run"
ms "Sprint 4: UI"                  "Design system and every screen on real data"
ms "Sprint 5: Justification and Dynamic Weights" "Narratives, fundamentals, regimes"
ms "Sprint 6: Track Record and Backtest" "Outcomes, statistics, replay"
ms "Sprint 7: CLI, MCP, Harnesses" "supertrends CLI, MCP server, Pi, Goose, OpenCode"
ms "Sprint 8: Packaging and Stoke Deploy" "Full chart, Flux, staging on Stoke"
ms "Sprint 9: Release v1.0.0"      "Hardening, signed release, production"
```

### Project board

Create a GitHub Project named "Super Trends v1" with columns Backlog, In Progress, In Review, Blocked, Done. Enable the built-in automations: item added to project goes to Backlog, PR opened moves the linked issue to In Review, issue closed goes to Done. If the token lacks the `project` scope, record `gh auth refresh -s project` in the owner checklist and track status with labels until it is granted.

### Templates

Create `.github/ISSUE_TEMPLATE/task.md`, `.github/ISSUE_TEMPLATE/bug_report.md`, and `.github/pull_request_template.md`.

Task template body:

```markdown
## Task
<one paragraph: what and why>

## Spec references
- PRD: FR-xxx
- ARCHITECTURE: section
- TEST_PLAN: scenarios

## Acceptance criteria
- [ ] ...

## Dependencies
- #issue

## Out of scope
- ...
```

Pull request template body:

```markdown
## What changed
## Linked issue
Closes #
## Spec change (pick one)
- [ ] A: internal only, no spec change
- [ ] B: spec updated in this PR (list sections)
- [ ] C: spec issue filed: #
## Tests
- [ ] Failing test written first
- [ ] `make check` passes locally
- [ ] TEST_PLAN.md scenarios added or updated
## Deploy impact
- [ ] None  - [ ] Image  - [ ] Chart values  - [ ] Migration
```

---

## Step 3: Create All GitHub Issues

Create one issue per task in `docs/SPRINT_PLAN.md`, for all sprints, before starting Sprint 0.

**Issue creation protocol**
- Title: `[S{n}-T{nn}] {task title}`
- Body: the task template filled in, with acceptance criteria copied exactly from the sprint plan.
- Labels: one `type:`, at least one `area:`, one `priority:`, one `size:`, and `sprint:{n}`.
- Milestone: the sprint's milestone.
- Add to the project board in Backlog.
- Each "Out of Scope for v1" item gets its own issue labeled `enhancement` with no milestone.

**Implementation comment protocol.** Before closing any issue, add a comment containing: what was built, files changed, tests added (names), spec sections updated, how to verify (exact commands), and anything deferred with the follow-up issue number.

**Issue closing protocol.** Close only when the PR is merged to `develop`, CI is green on `develop`, the implementation comment is posted, and every acceptance criterion is checked. Never close an issue to make a checklist item pass.

---

## Step 4 Onward: Sprint Execution

### Sprint Start Protocol
1. Move all sprint issues from Backlog to In Progress on the project board
2. Assign issues to yourself
3. Pull latest `develop` and verify it is up to date with `staging`
4. Pick the highest-priority unblocked issue
5. Read the relevant PRD, ARCHITECTURE, and TEST_PLAN sections before writing code
6. Add test scenarios for this feature to `docs/TEST_PLAN.md` before writing code
7. Create a branch: `git checkout -b feature/s{n}-t{nn}-{short-slug} develop`
8. Write failing tests first (TDD) and confirm they fail for the right reason
9. Implement until tests pass
10. Update `docs/TEST_PLAN.md` to mark new scenarios as Automated
11. Update the relevant spec doc in the same branch if behavior changed
12. Open a PR against `develop`. The PR description must state which spec sections were updated
13. Wait for CI (lint, type-check, unit, integration, coverage threshold)
14. Merge
15. Add the implementation comment and close the issue
16. Pick the next issue

### Spec Change Protocol
Any PR that changes user-facing behavior, API contracts, database schema, scoring rules, or architectural decisions must satisfy one of:

- **A, no spec change:** the PR description explicitly states "internal only, no spec change"
- **B, spec updated in same PR:** the relevant `docs/` file is updated alongside the code
- **C, spec issue filed:** a separate GitHub issue is created before the code PR merges, scheduled in the current sprint, and closed within the same sprint

Option C is not a deferral mechanism. Any change to a scoring formula, weight, or threshold is always option B and also bumps `scoring.version` in `config/scoring.yaml`.

### Test Scenario Generation Protocol
1. Open `docs/TEST_PLAN.md` and add scenarios for the feature before writing code
2. Use the naming convention: `{type}_{module}_{operation}_{scenario}_{outcome}`
3. Mark new scenarios as Deferred until the test is written, then Automated
4. Scenarios too hard to automate: Skipped, with a written reason and a manual step
5. The test file must have a test for every Automated scenario when the feature PR merges

### Sprint End Protocol
1. All sprint issues closed, or moved to the next sprint with an explanation
2. Run the sprint checklist and check each box that passes in `docs/SPRINT_PLAN.md`. Log each unmet item in `docs/GATE_DEBT.md` and carry on; do not stop. In the last sprint this step is the Final Gate and every item, including all earlier debt, must be green
3. Spec doc audit: review all five docs for stale sections and update before proceeding
4. Coverage check: `make coverage`, confirm it meets `.coverage-thresholds.toml`
5. Merge `develop` into `staging` via PR
6. Run the manual smoke checklist from `docs/TEST_PLAN.md` against the staging build (`make up && make smoke`; from Sprint 8 on, also against the Stoke staging namespace)
7. Document the sprint retrospective in `docs/RETROSPECTIVES.md`:
   - What was built (links to closed issues)
   - Spec sections updated
   - Tests added (counts by type)
   - Coverage delta
   - What worked, what did not, what to change
8. Tag the staging build and push the tag. The runner depends on this exact tag name:
   `git tag sprint-{n}-complete && git push origin sprint-{n}-complete`

### Definition of Done

A task is done when:
- [ ] Code implemented; `make build` succeeds
- [ ] Unit tests written first and passing
- [ ] `make check` exits 0 (ruff, ruff format check, mypy strict, eslint, tsc, with 0 warnings)
- [ ] Coverage has not dropped below thresholds
- [ ] PR opened against `develop` with the issue linked
- [ ] CI green
- [ ] Spec doc changes committed in the same PR (or option A / C confirmed)
- [ ] New test scenarios added to TEST_PLAN.md
- [ ] Implementation comment added to the issue before closing

### Coverage thresholds

```toml
# .coverage-thresholds.toml
[python]
"src/supertrends/indicators" = 95
"src/supertrends/scoring" = 92
"src/supertrends/selection" = 92
"src/supertrends/data" = 85
"src/supertrends/narrative" = 85
"src/supertrends/api" = 85
"src/supertrends/mcp" = 80
"src/supertrends/cli" = 80

[typescript]
"ui/src/components" = 75
"ui/src/store" = 85
"ui/src/lib" = 85
"integrations/pi/src" = 70
```

Indicator and scoring thresholds are high on purpose: a silent math error here produces confident wrong picks.

---

## Sprint Overview

| Sprint | Name | Duration | Goal |
|---|---|---|---|
| 0 | Scaffold | 1 week | Tooling, CI, empty shell, image skeleton, agent files |
| 1 | Data Layer | 1 week | Providers, storage, watchlist, ingestion |
| 2 | Indicator Engine | 1 week | Every indicator, golden-tested, no look-ahead |
| 3 | Scoring and Daily Picks | 2 weeks | The core feature: factors, composite, selection, daily run, API. First real image and chart |
| 4 | UI | 1 week | Design system and all screens on real data |
| 5 | Justification and Dynamic Weights | 1 week | Narratives, fundamentals overlay, regimes |
| 6 | Track Record and Backtest | 1 week | Outcomes, statistics, replay |
| 7 | CLI, MCP, Harnesses | 1 week | `supertrends` CLI, MCP server, Pi, Goose, OpenCode |
| 8 | Packaging and Stoke Deploy | 1 week | Full chart, OCI chart, Flux, staging on Stoke, deployment docs |
| 9 | Release v1.0.0 | 1 week | Hardening, QA, signed multi-arch release, production by digest |

Task format: **ID: title** `labels`, then description, **AC** (acceptance criteria), **Deps**.

---

## Sprint 0: Scaffold

**Milestone:** Sprint 0: Scaffold. **Duration:** 1 week.
**Goal:** a repository where `make setup && make build && make check` passes on a clean clone, CI is green, and an empty image builds for both architectures.

**S0-T01: Repository layout and Python project** `type:chore area:ci priority:p0 size:M`
Create the tree in Appendix B. `pyproject.toml` with uv, package `supertrends` under `src/`, Python 3.12, ruff, mypy strict, pytest, pytest-cov, hypothesis. A `supertrends` console entry point that prints version and commit.
**AC:** `uv sync --locked` works on a clean clone; `supertrends --version` prints `supertrends {VERSION} ({commit})`; `mypy --strict src` passes on the empty package.
**Deps:** none.

**S0-T02: UI project** `type:chore area:ui priority:p0 size:S`
`ui/` with Vite, React, TypeScript strict, ESLint, Vitest, Playwright installed. A single placeholder route.
**AC:** `npm --prefix ui ci && npm --prefix ui run build` produces `ui/dist`; `npm --prefix ui run lint` and `type-check` exit 0 with 0 warnings.
**Deps:** none.

**S0-T03: Root Makefile** `type:chore area:ci priority:p0 size:M`
Create the root `Makefile` exactly as specified in Build and Deployment, with `make help`. Targets that depend on later sprints exist now and print "not available until Sprint N" with exit 0.
**AC:** `make help` lists every required target; `make setup`, `make build`, `make check` pass on a clean clone.
**Deps:** S0-T01, S0-T02.

**S0-T04: Version source of truth and scripts** `type:chore area:ci priority:p0 size:S`
Root `VERSION` file containing `0.1.0`. `scripts/check-versions.sh`, `scripts/extract-changelog.sh`, `CHANGELOG.md` with an `[Unreleased]` section. See Versioning.
**AC:** `scripts/check-versions.sh` exits 0; changing `ui/package.json` version alone makes it exit 1 naming that file.
**Deps:** S0-T01, S0-T02.

**S0-T05: CI pipeline** `type:chore area:ci priority:p0 size:M`
`.github/workflows/ci.yml` with jobs `lint-and-typecheck`, `unit-tests`, `coverage`, `integration-tests` (Postgres service container), `e2e-tests` (placeholder until Sprint 4), `build-image` (buildx, amd64 and arm64, no push on PRs). Dependabot for pip, npm, GitHub Actions, and Docker. `pip-audit` and `npm audit --audit-level=high` in CI.
**AC:** CI is green on `develop`; a PR with a lint error fails `lint-and-typecheck`; the image job builds both architectures.
**Deps:** S0-T03.

**S0-T06: Dockerfile skeleton and Compose** `type:chore area:deploy priority:p0 size:M`
Multi-stage `Dockerfile` in the shape given in Build and Deployment, building the placeholder UI and the empty API. `deploy/compose/docker-compose.local.yml` with Postgres and the app.
**AC:** `make image` builds; the container runs as non-root with a read-only root filesystem; `make up` then `curl -fsS localhost:8080/healthz` returns `{"status":"ok"}`; `make down` cleans up.
**Deps:** S0-T03.

**S0-T07: Agent harness files** `type:docs area:ci priority:p1 size:M`
Generate `.gitignore`, `AGENTS.md`, `CLAUDE.md`, `SKILLS.md`, `SOUL.md`, `.agent/skills/run-tests/` and `.agent/skills/check-types/` (each with `SKILL.md` and `run.sh`), per Appendix J. `.gitignore` includes `logs/`.
**AC:** each file contains every required section; both skill `run.sh` scripts exit 0; `runner.mk`, `run-supertrends.sh`, `run-supertrends-status.sh` are untouched and not ignored.
**Deps:** S0-T03.

**S0-T08: License and community files** `type:docs priority:p1 size:S`
`LICENSE` (the unmodified PolyForm Noncommercial License 1.0.0 text, fetched from polyformproject.org, never retyped or edited, preceded only by the line "Required Notice: Copyright 2026 Serverless Ventures LLC (https://serverlessvc.com)"), `COPYRIGHT` (Copyright 2026 Serverless Ventures LLC, a Delaware limited liability company formed on November 26, 2024; the copyright year is the year this software was first published, 2026, not the formation year; all rights reserved except as granted in LICENSE; noncommercial use only; commercial licenses from legal@serverlessvc.com), `COMMERCIAL.md` (plain-language summary: what counts as noncommercial, examples of commercial use that need a license, how to ask for one; states that commercial licenses are governed by Delaware law and that LICENSE controls if the two differ), `CLA.md` (governed by Delaware law; names the company as "Serverless Ventures LLC, a Delaware limited liability company formed on November 26, 2024"; individual contributor license agreement granting Serverless Ventures LLC the right to relicense; base it on a standard template such as the Apache ICLA adapted for this project and flag it in the owner checklist for legal review), a CLA check in CI, SPDX headers on every source file with `scripts/check-spdx.sh`, `CONTRIBUTING.md` (dev setup, TDD and spec rules, Conventional Commits, CLA requirement), `CODE_OF_CONDUCT.md` (Contributor Covenant), `SECURITY.md` (private vulnerability reporting through GitHub Security Advisories, contact legal@serverlessvc.com), `THIRD_PARTY_LICENSES.md` generated by `scripts/gen-third-party-licenses.sh` from the Python and npm lock files, `DISCLAIMER.md` with the text from Security Guidelines.
**AC:** files exist; the license script runs in CI and fails if a dependency has a license outside the allowlist (MIT, BSD, Apache-2.0, ISC, PSF, MPL-2.0, and LGPL for unmodified libraries such as psycopg), and fails on GPL, AGPL, SSPL, or unknown, because strong-copyleft dependencies cannot be combined with a noncommercial license; `scripts/check-spdx.sh` fails on a source file without the SPDX header; a PR from a non-owner account without a signed CLA is blocked.
**Deps:** S0-T01, S0-T02.

**S0-T09: Config and settings skeleton** `type:feature area:scoring priority:p1 size:S`
`config/scoring.yaml` with every default from the Signal Engine Specification, a pydantic settings model, a JSON schema export, and a `config_hash` function (sha256 of the canonical JSON).
**AC:** loading the default file succeeds; an unknown key or out-of-range weight fails with a message naming the key; the hash is stable across key order.
**Deps:** S0-T01.

**S0-T10: Stoke inventory script** `type:chore area:deploy priority:p1 size:S`
`scripts/stoke-inventory.sh` that, given a kubeconfig, writes `private/STOKE_INVENTORY.md` (git-ignored: it describes a real cluster and must never be committed to this public repository) classifying each dependency as REUSE, UPGRADE, INSTALL, or NOT NEEDED (see Build and Deployment, Stoke profile). It is read-only: `kubectl get` and `flux get` only.
**AC:** with no kubeconfig it writes the table with every row "UNKNOWN: run against the cluster" and exits 0; `shellcheck` passes; the owner checklist has an entry asking the owner to run it.
**Deps:** S0-T03.

**Sprint 0 checklist (non-blocking; unmet items go to `docs/GATE_DEBT.md`)**
- [ ] `make setup && make build && make check` pass on a clean clone (proven in CI)
- [ ] CI green on `develop` and `staging`
- [ ] Image builds for `linux/amd64` and `linux/arm64` in CI
- [ ] `make up`, `/healthz`, `make down` work
- [ ] All agent harness files and legal files present
- [ ] `scripts/check-versions.sh` passes
- [ ] Five spec docs audited and current
- [ ] Retrospective written; tag `sprint-0-complete` pushed

---

## Sprint 1: Data Layer

**Milestone:** Sprint 1: Data Layer. **Duration:** 1 week.
**Goal:** bars and fundamentals for a watchlist land in Postgres, correctly adjusted, with quality flags, from a pluggable provider.

**S1-T01: Database schema and migrations** `type:feature area:data priority:p0 size:M`
SQLAlchemy 2 models and Alembic migrations for: `tickers`, `watchlists`, `watchlist_items`, `bars_daily`, `bars_intraday`, `fundamentals`, `earnings_calendar`, `runs`, `indicator_snapshots`, `factor_scores`, `recommendations`, `narratives`, `outcomes`, `config_versions`, `provider_calls`. Composite primary keys on (ticker, ts) for bars. `recommendations` and `factor_scores` are append-only (enforced by a trigger that rejects UPDATE and DELETE).
**AC:** `alembic upgrade head` and `downgrade base` both succeed on an empty database; the append-only trigger rejects an UPDATE in an integration test.
**Deps:** S0-T01.

**S1-T02: Provider interfaces** `type:feature area:data priority:p0 size:S`
`MarketDataProvider` (daily bars, intraday bars, splits and dividends, capability flags `intraday`, `trades`, `adjusted`), `FundamentalsProvider` (quarterly financials, forward estimates if available, earnings dates), both as Protocols with typed results. A registry selects providers from settings.
**AC:** a fake provider passes the shared contract test suite; an unknown provider name fails at startup with a clear message.
**Deps:** S0-T09.

**S1-T03: Fixture provider** `type:feature area:data priority:p0 size:M`
A deterministic synthetic generator (seeded geometric Brownian motion with regime switches, gaps, a split, and volume patterns) that produces 3 years of daily and 30 days of 5-minute bars for 12 synthetic tickers plus `SPY` and `QQQ` stand-ins. No vendor data is committed to the repository. This provider powers dev, CI, kind, and the smoke suite.
**AC:** same seed produces identical bars; the dataset includes at least one trending, one ranging, and one reversing ticker by construction, asserted in tests.
**Deps:** S1-T02.

**S1-T04: Massive (formerly Polygon.io) provider** `type:feature area:data priority:p0 size:L`
REST adapter for daily aggregates, 5-minute aggregates, splits, dividends, and financials. Base URL is configurable (`https://api.massive.com` default; `https://api.polygon.io` is the legacy host). Token-bucket rate limiter with a configurable calls-per-minute (default 5, the free-tier limit; verify the current plan limits at implementation time), exponential backoff with jitter on 429 and 5xx, response caching by (endpoint, params), and every call recorded in `provider_calls`. The seed watchlist has about 200 symbols, so daily updates must use the grouped daily bars endpoint (one call returns the whole market for a date) with per-ticker calls only for backfill, corporate actions, and intraday bars; record in the owner checklist that a paid plan is likely needed for 5-minute bars on 200 symbols. Tests use recorded, scrubbed fixtures; no test calls the network.
**AC:** contract tests pass; a 429 sequence is retried and succeeds; the API key never appears in logs, errors, or `provider_calls`; with no key configured the provider reports `unconfigured` and the app still starts on the fixture provider.
**Deps:** S1-T02.

**S1-T05: Second provider adapter** `type:feature area:data priority:p2 size:M`
One alternate provider behind the same interface so the product is not tied to a single vendor. Choose between Alpaca Market Data and Tiingo by reading their current docs and terms at implementation time; record the choice as an ADR. Fundamentals may come from a different vendor than bars (for example Financial Modeling Prep); the registry allows mixing.
**AC:** contract tests pass with recorded fixtures; switching `SUPERTRENDS_MARKET_PROVIDER` changes the active provider with no code change.
**Deps:** S1-T02.

**S1-T06: Ingestion service** `type:feature area:data priority:p0 size:L`
`supertrends ingest` and an internal function used by runs: incremental fetch per ticker (from last stored bar), upsert, corporate-action handling (on a new split, refetch the full adjusted history for that ticker), weekly resample, and a data-quality pass that sets `ok`, `degraded`, `stale` (latest daily bar older than the last completed session), or `insufficient_history`. Trading calendar from `exchange_calendars` (XNYS), including half days and holidays.
**AC:** re-running ingestion is idempotent; a simulated split triggers a full refetch; a holiday does not mark tickers stale; a ticker with a gap of more than 3 sessions is flagged `degraded`.
**Deps:** S1-T01, S1-T03.

**S1-T07: Watchlist service and API** `type:feature area:api priority:p0 size:M`
CRUD for one default watchlist plus named groups. Symbol validation against the provider's reference data (or a permissive regex on the fixture provider). Seed on first start: the 14 groups and 200 unique symbols in Appendix L, written to `config/watchlist.seed.yaml`, following the seed rules there (many-to-many group membership, provider validation, `unresolved` and `needs_review` handling, VIX not scored, crypto file kept but not ingested). Hard cap 300 tickers. `SPY` and `QQQ` are always ingested as benchmarks even if removed from the watchlist.
**AC:** endpoints in the API contract behave as specified; adding ticker 301 returns 422; the seed loads all 14 groups; a symbol in three groups is stored once with three memberships; an unresolvable seed symbol is recorded as `unresolved` with a reason and excluded, never substituted; write endpoints require the bearer token; read endpoints do not.
**Deps:** S1-T01.

**S1-T08: API skeleton and observability base** `type:feature area:api priority:p1 size:M`
FastAPI app with `/healthz` (process up), `/readyz` (database reachable, migrations at head), `/metrics` (Prometheus), structured JSON logs via structlog with a request ID, and RFC 9457 problem responses. Settings from environment with the `SUPERTRENDS_` prefix.
**AC:** `/readyz` returns 503 when the database is down; logs are valid JSON lines; no log line contains a secret (tested by a log-scrubbing unit test).
**Deps:** S1-T01.

**Sprint 1 checklist (non-blocking; unmet items go to `docs/GATE_DEBT.md`)**
- [ ] `supertrends ingest` on the fixture provider fills the database; a second run changes nothing
- [ ] Provider contract tests pass for fixture, Massive, and the alternate provider
- [ ] Watchlist API works end to end against Postgres in CI
- [ ] No test touches the network (CI runs with outbound network blocked for the test step)
- [ ] `make up && make smoke` pass
- [ ] Coverage thresholds met; spec docs audited
- [ ] Retrospective written; tag `sprint-1-complete` pushed

---

## Sprint 2: Indicator Engine

**Milestone:** Sprint 2: Indicator Engine. **Duration:** 1 week.
**Goal:** every indicator in the Signal Engine Specification implemented as pure, vectorized, tested functions with no look-ahead.

All indicator functions live in `src/supertrends/indicators/`, take a pandas DataFrame or numpy arrays, return arrays of the same length with NaN during warm-up, and have no I/O.

**S2-T01: Primitives** `type:feature area:indicators priority:p0 size:M`
`sma`, `ema`, `rma`, `stdev`, `true_range`, `atr`, `rsi`, `obv`, `percentile_rank`, `linreg_slope`, `pivots` (confirmed, width parameter), `zigzag`, `resample_weekly`.
**AC:** each matches a hand-computed fixture to 1e-9; `pivots` never marks a pivot fewer than `width` bars from the end.
**Deps:** S1-T03.

**S2-T02: Supertrend with TradingView parity** `type:feature area:indicators priority:p0 size:L`
Implement Factor 1's formula exactly. Golden fixtures: (a) a hand-computed 40-bar case covering both flip directions and band ratcheting; (b) TradingView parity files. For (b), add an owner checklist entry: export from TradingView, for two tickers on the daily chart, a CSV with OHLCV plus the built-in Supertrend (10, 3) columns, and place them in `tests/golden/tradingview/`. Until they exist the parity test is skipped with a visible reason, and the sprint checklist records that. When present, the test asserts the line matches within 0.01 and the direction matches on every bar after a 100-bar warm-up.
**AC:** hand-computed fixture passes; parity test passes or is skipped pending owner files; property test: direction is always +1 or -1 after warm-up, and the line is below close when up and above close when down.
**Deps:** S2-T01.

**S2-T03: Trend and momentum indicators** `type:feature area:indicators priority:p0 size:M`
SMA 20 / 50 / 200 with slope and cross detection, MACD (12, 26, 9) daily and weekly, ADX(14) with +DI and -DI.
**AC:** fixtures match to 1e-6; cross detection reports the bar index of the cross.
**Deps:** S2-T01.

**S2-T04: Divergence detector** `type:feature area:indicators priority:p0 size:L`
Regular and hidden, bullish and bearish, for RSI, MACD histogram, and OBV, on daily and weekly, using confirmed pivots only. Returns typed divergence records with both pivot bars, prices, and oscillator values.
**AC:** constructed fixtures for each of the four types are detected; a divergence whose second pivot is not yet confirmed is not reported; no false detection on a monotonic series.
**Deps:** S2-T01.

**S2-T05: Mean reversion and volatility indicators** `type:feature area:indicators priority:p0 size:M`
Bollinger (20, 2), %B, bandwidth and its percentile rank, z-score, ATR%, ATR% rank, HV20, squeeze and expansion flags.
**AC:** fixtures match; rank functions use only trailing windows.
**Deps:** S2-T01.

**S2-T06: Fibonacci and support / resistance** `type:feature area:indicators priority:p0 size:L`
ZigZag leg selection, retracement and extension levels, level clustering with strength, nearest support and resistance, breakout and breakdown detection, 52-week high and low.
**AC:** on a constructed up-leg-then-pullback fixture, the 61.8 level is within 1e-6 of the expected price; clusters merge pivots within 0.5 ATR; a breakout is only flagged on the bar it happens.
**Deps:** S2-T01.

**S2-T07: Volume indicators and estimated order flow** `type:feature area:indicators priority:p0 size:M`
Volume oscillator (5, 10), relative volume, CMF(20), accumulation and distribution days, intraday buy / sell split and daily delta, with the `intraday` and `daily_estimate` quality paths.
**AC:** buy plus sell equals volume for every bar; the zero-range bar rule is covered; the daily fallback is used and flagged when intraday bars are missing.
**Deps:** S2-T01.

**S2-T10: Ripster EMA Clouds with TradingView parity** `type:feature area:indicators priority:p0 size:M`
Implement Factor 12's clouds exactly: the five EMA pairs on `hl2`, cloud top, bottom and direction, `pos`, `stack`, `rc_bars_since_stack_flip`, the 8/9 pullback test, and the weekly 34/50 direction. Golden fixtures: (a) a hand-computed case covering a stack flip in each direction, close inside a cloud, and a held and a failed 8/9 pullback; (b) TradingView parity files. For (b), add an owner checklist entry: export, for the same two tickers as S2-T02, a daily CSV with OHLCV plus the Ripster EMA Clouds plots at default settings, into `tests/golden/tradingview/`. Until they exist the parity test is skipped with a visible reason. When present, the test computes on the export's own bars and asserts each EMA matches within 0.01 and each cloud direction matches on every bar after a 200-bar warm-up.
**AC:** hand-computed fixture passes; parity test passes or is skipped pending owner files; property test: `top >= bot` always, and `stack` is nonzero only when the 5/12 and 34/50 clouds do not overlap.
**Deps:** S2-T01.

**S2-T08: No-look-ahead and determinism harness** `type:test area:indicators priority:p0 size:M`
A hypothesis property test applied to every public indicator: computing on `bars[:t]` yields the same values for indexes below `t - confirm_lag` as computing on the full series. A determinism test hashes all outputs for the fixture dataset and compares to a committed hash. A benchmark test enforces NFR-001's compute budget.
**AC:** all indicators are registered with the harness (a test fails if a public indicator function is missing from the registry); the benchmark passes in CI on 2 cores.
**Deps:** S2-T02 through S2-T07, S2-T10.

**S2-T09: Indicator snapshot persistence** `type:feature area:data priority:p1 size:S`
Compute-all function producing one snapshot row per ticker per date (JSONB of indicator values plus levels), stored in `indicator_snapshots` with the config hash.
**AC:** snapshot for the fixture dataset round-trips; recomputing with the same inputs produces an identical JSON document.
**Deps:** S2-T08, S1-T01.

**Sprint 2 checklist (non-blocking; unmet items go to `docs/GATE_DEBT.md`)**
- [ ] Every indicator in the specification is implemented and registered with the no-look-ahead harness
- [ ] Supertrend hand-computed fixture passes; TradingView parity passes, or is skipped with the owner checklist entry open
- [ ] Ripster EMA Clouds hand-computed fixture passes; TradingView parity passes, or is skipped with the owner checklist entry open
- [ ] Determinism hash committed and checked in CI
- [ ] Indicator coverage at or above 95 percent
- [ ] Compute benchmark within budget
- [ ] `make up && make smoke` pass; spec docs audited
- [ ] Retrospective written; tag `sprint-2-complete` pushed

---

## Sprint 3: Scoring and Daily Picks (the core feature)

**Milestone:** Sprint 3: Scoring and Daily Picks. **Duration:** 2 weeks.
**Goal:** a scheduled or manual run produces the top 3 buys and top 2 sells with structured evidence, served by the API. The real image and a minimal Helm chart install on kind in CI.

**S3-T01: Factor framework** `type:feature area:scoring priority:p0 size:M`
A `Factor` protocol (`id`, `compute(snapshot, context) -> FactorResult`), `FactorResult` (score, evidence list, quality), a registry, and reason templates. Scores are validated to be within -100 to 100.
**AC:** a factor returning 101 raises in tests; every factor ID in `config/scoring.yaml` maps to a registered factor and the reverse.
**Deps:** S2-T09.

**S3-T02: Factors 1 to 4 (Supertrend, SMA, MACD, Divergences)** `type:feature area:scoring priority:p0 size:L`
Implement the scoring rules exactly as specified, each with table-driven tests covering every branch and both signs.
**AC:** one test row per rule line in the specification; boundary values (for example `bars_since_flip` 5 and 6) are covered.
**Deps:** S3-T01.

**S3-T03: Factors 5 to 8 (Mean reversion, Fibonacci, Support / resistance, Volatility)** `type:feature area:scoring priority:p0 size:L`
Same standard as S3-T02.
**AC:** one test row per rule line; the mirror rules for down legs are covered.
**Deps:** S3-T01.

**S3-T04: Factors 9 and 10 (Volume oscillator, Buy / sell volume)** `type:feature area:scoring priority:p0 size:M`
Same standard, including the quality-based weight multiplier for `daily_estimate`.
**AC:** one test row per rule line; sign logic for rising volume on a falling price is covered.
**Deps:** S3-T01.

**S3-T14: Factor 12 (Ripster EMA Clouds)** `type:feature area:scoring priority:p0 size:M`
Same standard as S3-T02, plus the Ripster parts of confidence (`rc_stack` opposing `st_dir_d`) and selection (`rc_bias` gate on both sides), and the `ripster` block of the evidence document.
**AC:** one test row per rule line, both signs; `pos(c3) == 0` (close inside the 34/50 cloud) scores 0 for `bias` and passes both selection gates; a buy candidate closing below the 34/50 cloud is rejected with the reason recorded; the pullback rule is covered for held, failed, and stale (4 bars ago) tests.
**Deps:** S3-T01, S2-T10.

**S3-T05: Composite, confidence, bands** `type:feature area:scoring priority:p0 size:M`
Weighted composite over non-missing factors with weight redistribution, display score, band, confidence. In this sprint all regime multipliers are 1.0 and fundamentals is `missing` (both arrive in Sprint 5); the code paths exist and are tested with injected values.
**AC:** contributions sum to the composite within 1e-9; removing a factor redistributes weight proportionally; display score of composite 0 is 50.0.
**Deps:** S3-T02, S3-T03, S3-T04, S3-T14.

**S3-T06: Selection** `type:feature area:scoring priority:p0 size:M`
Candidate rules, ranking with the full tie-breaker chain, max counts, correlation guard, "also qualified" list, and the nearest-miss record for an empty side.
**AC:** with 1 qualifying buy the result has 1 buy, not 3; ties resolve in the documented order; the correlation guard never lets two picks with correlation above 0.9 onto the same side (tested with SPY, VOO, and IVV stand-ins all qualifying: only the top one is picked).
**Deps:** S3-T05.

**S3-T07: Run orchestrator and atomic publication** `type:feature area:scoring priority:p0 size:L`
`supertrends run daily [--date]`: state machine `queued -> ingesting -> computing -> scoring -> selecting -> narrating -> published | failed`. Each state transition is persisted. Publication writes recommendations and flips `runs.published_at` in a single transaction. A failed run leaves the previous published run as "latest". One run per trading date is the published one; a rerun for the same date creates a new run row that supersedes the old one only on success, and both remain stored. An advisory lock prevents concurrent runs. Tickers with `stale` or `insufficient_history` are excluded and listed in the run summary.
**AC:** killing the process mid-run leaves the previous run as latest; two simultaneous triggers produce one run and one "already running" response; the run summary lists exclusions with reasons.
**Deps:** S3-T06, S1-T06.

**S3-T08: Evidence document and template narrative** `type:feature area:narrative priority:p0 size:M`
Build the evidence document per pick and a deterministic template narrative (lead with Supertrend and the 34/50 cloud bias, top two contributions, top opposing factor, invalidation level). The LLM path arrives in Sprint 5.
**AC:** the evidence JSON validates against a committed JSON schema; every number in the template narrative appears in the evidence document.
**Deps:** S3-T06.

**S3-T09: Read API** `type:feature area:api priority:p0 size:M`
`GET /api/v1/recommendations/latest`, `GET /api/v1/recommendations?date=`, `GET /api/v1/rankings?date=`, `GET /api/v1/tickers/{symbol}/analysis?date=`, `GET /api/v1/tickers/{symbol}/bars`, `GET /api/v1/runs`, `GET /api/v1/runs/{id}`, `POST /api/v1/runs` (token required), `GET /api/v1/config/scoring`. OpenAPI document committed at `docs/openapi.json` and diffed in CI. Every recommendation payload includes the disclaimer string.
**AC:** contract tests cover every endpoint and error; `docs/openapi.json` is regenerated by `make openapi` and CI fails on drift.
**Deps:** S3-T07, S1-T08.

**S3-T10: Scheduling** `type:feature area:deploy priority:p1 size:S`
The daily run is a Kubernetes CronJob (`30 17 * * 1-5`, time zone `America/New_York`) that calls `supertrends run daily`. The command exits 0 with "market closed" on non-trading days. Locally, `make run-daily` does the same.
**AC:** on a holiday date the command exits 0 and publishes nothing; the CronJob template sets `concurrencyPolicy: Forbid` and `timeZone`.
**Deps:** S3-T07.

**S3-T11: Real image, minimal chart, kind install in CI** `type:feature area:deploy priority:p0 size:L`
Complete the Dockerfile for the real app. Create the minimal chart (API Deployment, Service, run CronJob, migration Job hook, bundled Postgres StatefulSet for kind, `values-kind.yaml`). Add `kind-up`, `kind-load`, `helm-install`, `helm-test`, `kind-down`. Add the CI job `kind-e2e` that runs the whole loop with the fixture provider, triggers a run, and runs the smoke suite against the cluster.
**AC:** `make kind-up image kind-load helm-install helm-test smoke` passes locally and in CI; the smoke suite asserts that `/api/v1/recommendations/latest` returns at most 3 buys and at most 2 sells with evidence.
**Deps:** S3-T09, S3-T10.

**S3-T12: Smoke suite** `type:test area:deploy priority:p0 size:M`
`tests/smoke/` driven by `SMOKE_BASE_URL`: health, readiness, trigger run and wait, latest recommendations shape, analysis for one ticker, watchlist round trip. One suite reused by Compose, kind, and Stoke.
**AC:** the same command passes against `make up` and against the kind install.
**Deps:** S3-T09.

**S3-T13: Demo mode** `type:feature area:deploy priority:p0 size:M`
Implement `make demo`, `make demo-verify`, and `make demo-down` as specified in Build and Deployment, "Demo mode". In this sprint the demo covers ingestion, scoring, selection, the API, and the CLI; later sprints extend it as they add functions.
**AC:** on a machine with only Docker, `make demo` ends with a URL and a populated latest run within 3 minutes; `make demo-verify` prints one PASS or FAIL line per function and exits non-zero on any FAIL; no API key, network access, or cluster is needed.
**Deps:** S3-T11, S3-T12.

**Sprint 3 checklist (non-blocking; unmet items go to `docs/GATE_DEBT.md`)**
- [ ] `make demo && make demo-verify` passes and the demo matrix covers the functions added this sprint
- [ ] `supertrends run daily` on the fixture dataset publishes picks; the result is identical across two clean runs (determinism)
- [ ] Every scoring rule line in the specification has a test row
- [ ] Atomic publication and concurrency tests pass
- [ ] API contract tests pass; `docs/openapi.json` current
- [ ] Image builds, chart installs on kind, smoke suite passes against it (in CI)
- [ ] Scoring and selection coverage at or above 92 percent
- [ ] Spec docs audited
- [ ] Retrospective written; tag `sprint-3-complete` pushed

---

## Sprint 4: UI

**Milestone:** Sprint 4: UI. **Duration:** 1 week.
**Goal:** every screen in DESIGN.md, on real API data, served by the same image.

**S4-T01: Design tokens and base components** `type:feature area:ui priority:p0 size:M`
CSS custom properties from the Design System section, light and dark themes, and components: Button, Card, Badge, ScoreDial, TrendRibbon, FactorBar, LevelList, DataQualityTag, Disclaimer, EmptyState, ErrorState, Skeleton.
**AC:** component tests for every state; contrast checks pass AA in both themes (automated with axe).
**Deps:** S0-T02.

**S4-T02: App shell, routing, data layer** `type:feature area:ui priority:p0 size:M`
Routes: `/` (Today), `/ticker/:symbol`, `/watchlist`, `/track-record`, `/runs`, `/settings`, plus `/date/:yyyy-mm-dd`. TanStack Query for server state, Zustand for UI state (theme, selected date, token). A typed API client generated from `docs/openapi.json`.
**AC:** the client is regenerated by `make openapi`; a 500 from the API renders the ErrorState with a retry, never a blank screen.
**Deps:** S4-T01, S3-T09.

**S4-T03: Today screen** `type:feature area:ui priority:p0 size:L`
Header with the as-of date, market regime, run status and data freshness. Three buy cards and two sell cards: ticker, band, ScoreDial, confidence, TrendRibbon (last 60 sessions colored by Supertrend direction), "flipped N bars ago", top factor contributions, narrative, invalidation level, key levels, flags (`event_risk`, `estimated order flow` quality), "day N on the list". Fewer cards when fewer qualify, with the nearest-miss line. Each card shows the watchlist groups the ticker belongs to; an optional group filter re-ranks within one group without changing the published overall picks. Disclaimer always visible.
**AC:** e2e: with a fixture run of 3 buys and 2 sells the screen shows exactly those; with 1 buy it shows 1 card and the "no more qualifying buys" line; buy and sell are distinguishable in grayscale.
**Deps:** S4-T02.

**S4-T04: Ticker screen with chart** `type:feature area:ui priority:p0 size:L`
Candlestick chart using `lightweight-charts` with overlays: Supertrend line (colored by direction), SMA 20 / 50 / 200, Fibonacci levels, support and resistance. Sub-panels: MACD with histogram, RSI with divergence markers, volume with estimated buy / sell split. Right rail: full factor table (score, weight, contribution, reasons), regime, adjustments, fundamentals summary, history of this ticker's scores.
**AC:** overlays match API values (e2e asserts the Supertrend series length and last value); toggling an overlay persists per browser; the chart is keyboard reachable and has a data table alternative.
**Deps:** S4-T02.

**S4-T05: Watchlist and ranking screen** `type:feature area:ui priority:p0 size:M`
Group filter (the watchlist groups from the seed, such as semis, fab-7, country-etfs) and a sortable ranking table for the selected date (score, band, confidence, Supertrend direction and age, regime, relative volume, data quality) with TrendRibbon per row. Add, remove, and group tickers.
**AC:** sorting is stable; adding an invalid symbol shows the API's message inline; excluded tickers are listed with their reason.
**Deps:** S4-T02.

**S4-T06: Runs and Settings screens** `type:feature area:ui priority:p1 size:M`
Runs: history with state, duration, exclusions, and a "Run now" button (token required) with live progress by polling. Settings: read-only view of the active scoring config and its hash, theme, API token entry (stored in memory only by default, optional localStorage with a warning), provider and LLM status.
**AC:** "Run now" without a token prompts for it; a run already in progress disables the button; no secret is ever rendered.
**Deps:** S4-T02.

**S4-T07: Serve UI from the API image** `type:feature area:deploy priority:p0 size:S`
FastAPI serves `ui/dist` with correct cache headers (hashed assets immutable, `index.html` no-cache) and SPA fallback. Strict Content-Security-Policy with no inline scripts and `connect-src 'self'`.
**AC:** the built image serves the UI at `/`; CSP header present and tested; deep links work after refresh.
**Deps:** S4-T03.

**S4-T08: End-to-end tests** `type:test area:ui priority:p0 size:M`
Playwright against `make up`: e2e_US-001 through e2e_US-007, US-011, US-012. Runs in CI in the `e2e-tests` job.
**AC:** all listed stories have a passing e2e test; screenshots are uploaded as CI artifacts on failure.
**Deps:** S4-T03 through S4-T07.

**S4-T09: Demo tour and visual report** `type:feature area:ui priority:p0 size:M`
A `/demo` route, shown only when `SUPERTRENDS_DEMO=1`, that lists every product function with a link to the screen that shows it and its live PASS or FAIL status. A persistent "DEMO DATA: synthetic prices, not real markets" banner on every screen in demo mode. `make demo-verify` now also drives the UI with Playwright and writes `demo-report/index.html` with a screenshot per screen.
**AC:** the tour lists every function in the demo matrix; the report opens offline and shows one screenshot per screen; the banner is present on every route in demo mode and absent otherwise.
**Deps:** S3-T13, S4-T03.

**Sprint 4 checklist (non-blocking; unmet items go to `docs/GATE_DEBT.md`)**
- [ ] `make demo && make demo-verify` passes and the demo matrix covers the functions added this sprint
- [ ] Every screen in DESIGN.md exists with loading, empty, error, and stale states
- [ ] e2e suite green in CI
- [ ] axe reports zero serious or critical issues on every route
- [ ] Today screen first meaningful paint under 1.5 seconds against the kind install (measured with Playwright)
- [ ] Image builds, chart installs on kind, smoke suite passes against it
- [ ] Spec docs audited
- [ ] Retrospective written; tag `sprint-4-complete` pushed

---

## Sprint 5: Justification and Dynamic Weights

**Milestone:** Sprint 5: Justification and Dynamic Weights. **Duration:** 1 week.
**Goal:** LLM-written narratives that cannot invent numbers, the fundamentals overlay, and regime-driven weights.

**S5-T01: Narrative provider and prompt** `type:feature area:narrative priority:p0 size:M`
`NarrativeProvider` protocol with two implementations: `template` (from Sprint 3) and `openai_compatible` (httpx, `SUPERTRENDS_LLM_BASE_URL`, `SUPERTRENDS_LLM_MODEL`, optional `SUPERTRENDS_LLM_API_KEY`). The system prompt and user prompt template live in `src/supertrends/narrative/prompts/` and are versioned. The user prompt contains a compact rendering of the evidence document only.
**AC:** token budget test (NFR-012) passes on the fixture set; the prompt version is stored with each narrative.
**Deps:** S3-T08.

**S5-T02: Numeric guard and fallback** `type:feature area:narrative priority:p0 size:M`
Implement the numeric guard, banned-phrase check, length check (3 to 5 sentences), retry once at temperature 0, then template fallback. Timeouts and errors never fail the run.
**AC:** a narrative containing a number not in the evidence is rejected; a banned phrase is rejected; with the endpoint unreachable the run publishes with `source: template`; metrics count accepted, rejected, and fallback narratives.
**Deps:** S5-T01.

**S5-T03: Narrative evaluation set** `type:test area:narrative priority:p1 size:M`
`tests/narrative_eval/`: 30 evidence documents covering every band, both sides, every flag. A recorded-response test runs in CI. A live evaluation command `make narrative-eval` runs against a configured endpoint and reports acceptance rate, mean tokens, and latency; target acceptance at or above 90 percent on the Stoke model. Record the result in `docs/NARRATIVE_EVAL.md`.
**AC:** CI test green on recorded responses; the live command works against a local OpenAI-compatible mock.
**Deps:** S5-T02.

**S5-T04: Fundamentals ingestion and factor 11** `type:feature area:scoring priority:p0 size:L`
Ingest quarterly financials and earnings dates through `FundamentalsProvider`, store point-in-time (each row has `known_at`, so backtests never see a number early), compute the sub-scores and factor score, handle ETFs and stale data.
**AC:** one test row per sub-score rule; a backtest date before `known_at` does not see the row; QQQ gets quality `missing` and its weight is redistributed.
**Deps:** S3-T05, S1-T04.

**S5-T05: Regime detection and dynamic weights** `type:feature area:scoring priority:p0 size:M`
Per-ticker regime from ADX, market regime from the benchmarks, the multiplier table, event and fundamentals adjustments, threshold adjustments, renormalization, and the stored list of adjustments that fired.
**AC:** weights always sum to 100 after adjustment; each multiplier cell in the table has a test; threshold adjustments stack as specified; the evidence document lists adjustments.
**Deps:** S5-T04.

**S5-T06: Surface regimes and fundamentals in the UI** `type:feature area:ui priority:p1 size:M`
Regime badges, "weights adjusted" explanation with before and after weights, earnings countdown and `event_risk` flag, fundamentals summary panel, narrative source tag (LLM model name or template).
**AC:** e2e for US-009 and US-010 pass.
**Deps:** S5-T05, S4-T04.

**S5-T07: Config versioning** `type:feature area:scoring priority:p1 size:S`
Every distinct config hash is stored in `config_versions` with the full document. `scoring.version` must be bumped when weights, thresholds, or formulas change; a CI check compares the hash of `config/scoring.yaml` on the PR against `develop` and fails if the hash changed without a version bump.
**AC:** the CI check fails on a weight change without a bump; any past recommendation can display the exact config that produced it.
**Deps:** S0-T09.

**Sprint 5 checklist (non-blocking; unmet items go to `docs/GATE_DEBT.md`)**
- [ ] `make demo && make demo-verify` passes and the demo matrix covers the functions added this sprint
- [ ] Runs publish LLM narratives against a mock endpoint and template narratives when it is down
- [ ] Numeric guard tests pass; no narrative in the evaluation set contains an unmatched number
- [ ] Fundamentals are point-in-time; ETFs handled
- [ ] Dynamic weights sum to 100 in every tested combination
- [ ] Image builds, chart installs on kind, smoke suite passes against it
- [ ] Spec docs audited (PRD scoring section matches the code and `config/scoring.yaml`)
- [ ] Retrospective written; tag `sprint-5-complete` pushed

---

## Sprint 6: Track Record and Backtest

**Milestone:** Sprint 6: Track Record and Backtest. **Duration:** 1 week.
**Goal:** the product measures itself and shows the result, good or bad.

**S6-T01: Outcome tracker** `type:feature area:track-record priority:p0 size:M`
On each run, fill `entry_price` for picks whose next session has opened and compute forward returns at 1, 5, 10, 20 trading days for the pick and SPY. Outcomes are append-only per (recommendation, horizon).
**AC:** returns match hand-computed values on the fixture dataset; splits between entry and exit are handled through adjusted prices; an outcome is never computed before its horizon has closed.
**Deps:** S3-T07.

**S6-T02: Statistics service and API** `type:feature area:track-record priority:p0 size:M`
`GET /api/v1/track-record?from=&to=&side=&band=`: hit rate, mean and median excess return, worst pick, sample size, per horizon; "small sample" flag below 20.
**AC:** statistics match a reference computed with pandas in the test; empty ranges return zeros with sample size 0, not errors.
**Deps:** S6-T01.

**S6-T03: Backtest engine** `type:feature area:track-record priority:p0 size:L`
`supertrends backtest` as specified: replays the daily loop over stored history through the same factor, composite, and selection code (no separate implementation), with point-in-time fundamentals and next-open entries. Writes results to a separate `backtests` schema and never touches published recommendations. Outputs JSON and a Markdown summary.
**AC:** a backtest over the fixture dataset reproduces the live run's picks for the same dates; a deliberately leaky indicator injected in a test is caught by the no-look-ahead check; runtime for 2 years and 20 tickers under 3 minutes on 2 cores.
**Deps:** S6-T01, S5-T05.

**S6-T04: Track Record screen** `type:feature area:ui priority:p0 size:M`
Summary tiles per side and horizon with sample sizes, a table of every past pick with outcome columns, filters by date range, side, band, and config version, an excess-return distribution chart, and a clearly separated "Backtest (hypothetical)" tab.
**AC:** e2e for US-008 passes; losing picks are shown with the same prominence as winners; backtest figures are never shown without the "hypothetical" label.
**Deps:** S6-T02.

**S6-T05: Observability** `type:feature area:observability priority:p1 size:M`
Metrics: `supertrends_run_duration_seconds`, `supertrends_run_state_total{state}`, `supertrends_tickers_scored`, `supertrends_tickers_excluded{reason}`, `supertrends_data_freshness_seconds`, `supertrends_provider_requests_total{provider,status}`, `supertrends_provider_rate_limited_total`, `supertrends_narrative_total{source,result}`, `supertrends_narrative_tokens{kind}`, `supertrends_picks_published{side}`. A Grafana dashboard JSON in `deploy/dashboards/` and PrometheusRule alerts: no published run for the latest completed session by 19:00 ET, data stale, provider error rate above 20 percent for 15 minutes, narrative fallback rate above 50 percent for a run.
**AC:** metrics are emitted and scraped in the kind install (ServiceMonitor optional there); the dashboard JSON loads in Grafana without errors; alert rules pass `promtool check rules`.
**Deps:** S3-T07.

**S6-T06: Data retention and backup notes** `type:chore area:data priority:p2 size:S`
Retention job: intraday bars older than 90 days are deleted; daily bars, recommendations, and outcomes are kept forever. `supertrends db backup` wraps `pg_dump` to a file path. Document restore.
**AC:** retention never deletes rows referenced by a recommendation's evidence window; backup and restore round-trip in an integration test.
**Deps:** S1-T01.

**Sprint 6 checklist (non-blocking; unmet items go to `docs/GATE_DEBT.md`)**
- [ ] `make demo && make demo-verify` passes and the demo matrix covers the functions added this sprint
- [ ] Outcomes and statistics verified against reference computations
- [ ] Backtest reproduces live picks on the fixture dataset
- [ ] Track Record screen shows winners and losers with sample sizes
- [ ] Metrics, dashboard, and alert rules validated
- [ ] Image builds, chart installs on kind, smoke suite passes against it
- [ ] Spec docs audited
- [ ] Retrospective written; tag `sprint-6-complete` pushed

---

## Sprint 7: CLI, MCP, Harnesses

**Milestone:** Sprint 7: CLI, MCP, Harnesses. **Duration:** 1 week.
**Goal:** agents and the terminal get the same answers as the UI.

**S7-T01: CLI** `type:feature area:cli priority:p0 size:M`
Typer CLI in the same package. Commands: `supertrends today [--json]`, `supertrends analyze TICKER [--date] [--json]`, `supertrends rank [--date] [--top N]`, `supertrends watchlist list|add|remove`, `supertrends run daily [--date]`, `supertrends ingest`, `supertrends backtest`, `supertrends track-record`, `supertrends status`, `supertrends serve`, `supertrends mcp`, `supertrends healthcheck`, `supertrends db migrate|backup`, `supertrends config show|validate`. Remote mode with `--api-url` and `SUPERTRENDS_API_TOKEN`; local mode talks to the database directly.
**AC:** every command has `--help` text and a test; `--json` output validates against the API schemas; exit codes: 0 ok, 1 error, 2 usage, 3 not ready.
**Deps:** S3-T09, S6-T02.

**S7-T02: MCP server** `type:feature area:mcp priority:p0 size:L`
MCP server using the official Python SDK, exposed two ways: stdio (`supertrends mcp`) and streamable HTTP mounted at `/mcp` on the API (bearer token required). Tools:
- `supertrends_recommend` (date optional): today's picks with evidence
- `supertrends_analyze` (ticker, date optional): full factor breakdown and levels
- `supertrends_rank` (date optional, top N): ranked watchlist
- `supertrends_watchlist` (action list / add / remove, ticker): watchlist management; add and remove require the token
- `supertrends_status`: latest run, data freshness, provider and LLM health
- `supertrends_track_record` (range, side): statistics
- `supertrends_run` (date optional): trigger a run; requires the token
Every tool result that contains a pick includes the disclaimer. Tool descriptions tell the calling agent that results are informational and that Super Trends places no trades.
**AC:** an MCP client integration test lists the tools and calls each; schemas are strict (no additional properties); unauthenticated HTTP calls to write tools return an error.
**Deps:** S7-T01.

**S7-T03: Pi extension** `type:feature area:mcp priority:p1 size:M`
`integrations/pi/` package `@stokeai-supertrends/pi-extension` built on `pi-agent-core` with TypeBox tool schemas mirroring the MCP tools, slash commands `/supertrends today`, `/supertrends analyze <ticker>`, `/supertrends rank`, and streaming progress for `supertrends_run` through `onUpdate`. It calls the HTTP API. Verify the current `pi-agent-core` package name and API at implementation time.
**AC:** unit tests with a mocked API; README with install and config; coverage at or above 70 percent.
**Deps:** S7-T02.

**S7-T04: Goose and OpenCode integration** `type:feature area:mcp priority:p1 size:S`
`integrations/goose/toolkit.yaml` pointing at the MCP server (stdio and HTTP variants). `integrations/opencode/README.md` with the config snippet. `integrations/claude-code/README.md` with the `.mcp.json` snippet.
**AC:** each config is validated by a script that starts the stdio server and lists tools using that config's command line.
**Deps:** S7-T02.

**S7-T05: Harness smoke tests** `type:test area:mcp priority:p2 size:S`
CI job `harness-smoke-tests` on `staging` and release tags: start the API with the fixture provider, run an MCP client through all read tools, and assert shape.
**AC:** job green on `staging`.
**Deps:** S7-T04.

**S7-T06: Agent skill for operating Super Trends** `type:docs area:mcp priority:p2 size:S`
`.agent/skills/daily-brief/` skill: how an agent should fetch today's picks, summarize them faithfully, and what it must not do (no trade execution, no position sizing, always carry the disclaimer).
**AC:** skill listed in `SKILLS.md`; `run.sh` prints today's picks from a running instance.
**Deps:** S7-T01.

**Sprint 7 checklist (non-blocking; unmet items go to `docs/GATE_DEBT.md`)**
- [ ] `make demo && make demo-verify` passes and the demo matrix covers the functions added this sprint
- [ ] CLI commands tested; `supertrends today --json` matches the API payload
- [ ] MCP tools callable over stdio and HTTP; write tools require the token
- [ ] Pi, Goose, OpenCode, and Claude Code integration files validated
- [ ] Image builds, chart installs on kind, smoke suite passes against it
- [ ] Spec docs audited
- [ ] Retrospective written; tag `sprint-7-complete` pushed

---

## Sprint 8: Packaging and Stoke Deploy

**Milestone:** Sprint 8: Packaging and Stoke Deploy. **Duration:** 1 week.
**Goal:** the complete chart, published as an OCI artifact, deployed to a staging namespace on Stoke through Flux, with deployment docs.

**S8-T01: Complete the Helm chart** `type:feature area:deploy priority:p0 size:L`
Everything in Build and Deployment, Path 4: all templates, `values.schema.json`, the four profiles, probes, graceful shutdown, PodDisruptionBudget, NetworkPolicy, security contexts, HPA for the API, ServiceMonitor, PrometheusRule, dashboard ConfigMap, Helm tests.
**AC:** `helm lint` and `helm template` pass for every profile; schema negative tests fail as expected (a secret value in values, an invalid cron, weights that do not sum to 100 in an override).
**Deps:** S3-T11, S6-T05.

**S8-T02: Stoke inventory and profile** `type:feature area:deploy priority:p0 size:M`
Run (or ask the owner to run) `scripts/stoke-inventory.sh`. From `private/STOKE_INVENTORY.md`, finalize the Stoke profile. The public `values-stoke.yaml` carries only generic, non-identifying settings (architecture selector, resources, feature toggles) and documented placeholders. Cluster-specific values (LLM gateway URL and model name, hostnames, storage class, ServiceMonitor labels, secret mechanism) go into a values patch that lives only in the owner's Stoke GitOps repository; write it to `private/stoke-values.yaml` for the owner to copy. Anything classified INSTALL needs an ADR explaining why it cannot be avoided; the default answer is to reuse what Stoke already runs.
**AC:** `private/stoke-values.yaml` resolves every placeholder, or each unresolved one has an owner checklist entry; nothing under `private/` is tracked by git; `helm template` with the Stoke profile renders only ARM64-compatible images and requests no GPU.
**Deps:** S8-T01, S0-T10.

**S8-T03: OCI image and chart publishing** `type:feature area:deploy priority:p0 size:M`
`release-images.yml` and `release-chart.yml`: multi-arch build, push to GHCR, cosign keyless signing, SBOM and provenance attestations, Trivy scan failing on high or critical, `helm package` and `helm push` to `oci://ghcr.io/mohnishbasha/charts`, chart signed with cosign. `sha-` tags on every merge to `staging`.
**AC:** a merge to `staging` produces a signed `sha-` image and chart; `cosign verify` with the documented command succeeds; a seeded critical CVE fails the scan in a test branch.
**Deps:** S8-T01.

**S8-T04: Flux manifests** `type:feature area:deploy priority:p0 size:M`
`deploy/flux/` with base and overlays for `supertrends-stage` and `supertrends` namespaces: Namespace, OCIRepository (chart, with cosign verification), HelmRelease (values from the Stoke profile, image by digest, install and upgrade remediation with automatic rollback, Helm tests enabled), and a Kustomization. Secrets follow the mechanism found in the inventory (SOPS or External Secrets); no secret values in git.
**AC:** `kustomize build` succeeds for both overlays; `flux build` (or `kubeconform` with Flux CRD schemas) validates them in CI; the manifests are ready to be copied or referenced by the Stoke GitOps repository.
**Deps:** S8-T03.

**S8-T05: Staging deploy on Stoke** `type:feature area:deploy priority:p0 size:M`
Open a PR to the Stoke GitOps repository adding the `supertrends-stage` overlay (owner merges it), or, if the owner provided direct access, apply it. After reconciliation: `helm test`, `make smoke SMOKE_BASE_URL=...`, trigger a run on the fixture provider, then on the real provider once the owner has created the API key secret.
**AC:** staging namespace healthy on Stoke; smoke suite passes against it; a real-provider run publishes picks; rollback tested once (`flux suspend`, `helm rollback`, resume) and recorded. If cluster access is not available, everything up to the PR is complete and the remaining steps are in the owner checklist with exact commands.
**Deps:** S8-T04, S8-T02.

**S8-T06: Upgrade, rollback, and air-gap tests** `type:test area:deploy priority:p1 size:M`
CI job on kind: install the previous chart version, upgrade to the current one with a database migration, run smoke, roll back, run smoke. Document the air-gapped install for the self-host profile (mirror images and chart with `oras` or `skopeo`, set `global.imageRegistry`).
**AC:** upgrade and rollback job green; the air-gap procedure is exercised once on kind with a local registry.
**Deps:** S8-T01.

**S8-T07: docs/DEPLOYMENT.md** `type:docs area:deploy priority:p0 size:M`
Local build, local deploy, images, chart, kind loop, Stoke through Flux, secrets, upgrades, rollback, backup and restore, troubleshooting (provider rate limits, stale data, LLM gateway down, CronJob time zone), and the verification command for every step.
**AC:** a second agent session following only DEPLOYMENT.md brings up kind from a clean clone; every command in the doc is exercised by CI or marked "owner, cluster only".
**Deps:** S8-T05.

**Sprint 8 checklist (non-blocking; unmet items go to `docs/GATE_DEBT.md`)**
- [ ] `make demo && make demo-verify` passes and the demo matrix covers the functions added this sprint
- [ ] Chart complete; lint, template, and schema tests pass for all four profiles
- [ ] Signed multi-arch image and OCI chart published from `staging`; `cosign verify` succeeds
- [ ] Flux overlays validate in CI
- [ ] Staging on Stoke healthy and smoke-tested, or blocked only on recorded owner actions
- [ ] Upgrade and rollback test green
- [ ] `docs/DEPLOYMENT.md` complete and `docs/ARCHITECTURE.md` deployment chapter matches it
- [ ] Retrospective written; tag `sprint-8-complete` pushed

---

## Sprint 9: Release v1.0.0

**Milestone:** Sprint 9: Release v1.0.0. **Duration:** 1 week.
**Goal:** a hardened, signed v1.0.0 running in the production namespace on Stoke, deployed by digest.

**S9-T01: Security review** `type:security priority:p0 size:M`
Walk the Security Guidelines section line by line and record evidence for each item in `docs/SECURITY_REVIEW.md`. Run `pip-audit`, `npm audit`, Trivy (image and chart config), `gitleaks` over the full history, and a check that no response, log, or metric contains a secret.
**AC:** zero high or critical findings open; any accepted medium has a written rationale.
**Deps:** all prior.

**S9-T02: Resilience tests** `type:test priority:p0 size:M`
Fault injection in integration tests: provider 429 storm, provider outage mid-run, database restart mid-run, LLM timeout, half-day session, missing intraday data, a ticker delisted mid-history, a split on run day.
**AC:** each scenario ends in either a correct published run or a clean failed run with the previous result still latest; none ends in a partial publication.
**Deps:** S3-T07.

**S9-T03: Performance pass** `type:chore priority:p1 size:M`
Measure NFR-001, 003, 004, 010 on the Stoke staging namespace and in CI. Fix regressions. Record results in `docs/PERFORMANCE.md`.
**AC:** all four NFRs met or an ADR explains the gap and the plan.
**Deps:** S8-T05.

**S9-T04: Full QA pass** `type:test priority:p0 size:M`
Run every scenario in TEST_PLAN.md. Run the manual smoke checklist on staging. Confirm the TradingView parity test is passing (not skipped); if the owner files are still missing, this is a release blocker recorded in the owner checklist.
**AC:** no Deferred scenarios remain; Skipped ones each have a reason and a manual result.
**Deps:** all prior.

**S9-T05: Documentation pass** `type:docs priority:p1 size:M`
README from the template, `docs/USER_GUIDE.md` (how to read a card, what each factor means, what confidence and invalidation mean, how to tune `config/scoring.yaml`, how to read the track record), `docs/RUNBOOK.md` (alerts and what to do), CHANGELOG for 1.0.0.
**AC:** every factor in the UI links to its section in the user guide; the runbook covers every alert rule.
**Deps:** all prior.

**S9-T06: Release** `type:chore area:deploy priority:p0 size:M`
Follow the Release Checklist in Versioning: bump `VERSION` to `1.0.0`, PR `staging` to `main` (owner approval), annotated tag `v1.0.0`, release workflow publishes signed multi-arch images and the chart, GitHub Release body from `scripts/extract-changelog.sh`.
**AC:** `ghcr.io/mohnishbasha/stokeai-supertrends:1.0.0` exists for both architectures and verifies with cosign; the chart `1.0.0` is pullable from the OCI registry.
**Deps:** S9-T01 through S9-T05.

**S9-T07: Production deploy by digest** `type:chore area:deploy priority:p0 size:S`
Update the `supertrends` overlay to chart `1.0.0` and the image digest from the release, through the Stoke GitOps repository. After reconciliation: Helm tests, smoke suite, first production run, dashboard and alerts confirmed.
**AC:** production namespace healthy; the first scheduled run publishes; post-release actions from Versioning completed.
**Deps:** S9-T06.

**Final Gate (the only hard gate)**
- [ ] Every checklist item from Sprints 0 to 8 is checked and `docs/GATE_DEBT.md` is empty
- [ ] `make demo && make demo-verify` passes with every function PASS
- [ ] Security review complete with zero high or critical findings
- [ ] Resilience scenarios pass
- [ ] NFRs measured and met
- [ ] TradingView parity test passing
- [ ] v1.0.0 tagged, signed, published; chart published
- [ ] Production on Stoke running by digest; first scheduled run published
- [ ] All five spec docs final and consistent with the code
- [ ] Retrospective written; tag `sprint-9-complete` pushed

---

## Versioning, Changelog, and Release

### Semantic versioning

`MAJOR.MINOR.PATCH`. MAJOR: breaking change to the HTTP API, MCP tool schemas, CLI flags, database schema without an automatic migration, or the meaning of a score. MINOR: new capability, backward compatible. PATCH: fixes only. Pre-1.0 versions are `0.{sprint}.{patch}` and carry no compatibility promise.

The scoring config has its own integer `scoring.version`. Any change to weights, thresholds, or formulas bumps it and is called out in the changelog under a "Scoring" heading, because it changes what the picks mean.

### Version source of truth

The root `VERSION` file (one line, no `v` prefix). Everything else derives from it or is checked against it:

| File | Field | How |
|---|---|---|
| `pyproject.toml` | `project.version` | dynamic, read from `VERSION` by the build backend |
| `ui/package.json` | `version` | checked |
| `integrations/pi/package.json` | `version` | checked |
| `deploy/helm/stokeai-supertrends/Chart.yaml` | `version` and `appVersion` | checked |
| Container labels | `org.opencontainers.image.version` | build arg from `VERSION` |
| `supertrends --version`, `/healthz` | version, commit | read at build time |

### scripts/check-versions.sh

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
CANONICAL="$(tr -d '[:space:]' < VERSION)"
if ! [[ "$CANONICAL" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.]+)?$ ]]; then
  echo "x VERSION is not semver: '$CANONICAL'"; exit 1
fi
check() {
  local actual="$1" file="$2"
  if [[ "$actual" != "$CANONICAL" ]]; then
    echo "x Version mismatch in $file: expected $CANONICAL, got $actual"
    exit 1
  fi
  echo "ok $file: $CANONICAL"
}
check "$(jq -r .version ui/package.json)" "ui/package.json"
check "$(jq -r .version integrations/pi/package.json)" "integrations/pi/package.json"
check "$(awk '/^version:/{print $2}' deploy/helm/stokeai-supertrends/Chart.yaml | tr -d '"')" "Chart.yaml version"
check "$(awk '/^appVersion:/{print $2}' deploy/helm/stokeai-supertrends/Chart.yaml | tr -d '"')" "Chart.yaml appVersion"
echo "All versions consistent: $CANONICAL"
```

Runs in CI on every PR to `staging` and `main`. Files that do not exist yet in early sprints are skipped with a guard you add, and the guard is removed in the sprint that creates the file.

### Version bump process

1. On a branch off `develop`: edit `VERSION`, then run `make version-sync` (writes the checked files).
2. Move the `[Unreleased]` changelog entries under a new `## [X.Y.Z] - YYYY-MM-DD` heading and leave an empty `[Unreleased]`.
3. Run `scripts/check-versions.sh` and `make check`.
4. Commit as `chore: release X.Y.Z`, open the PR.

### Changelog protocol

`CHANGELOG.md` follows Keep a Changelog. `[Unreleased]` is always present. Every PR that changes behavior adds a line under Added, Changed, Deprecated, Removed, Fixed, Security, or Scoring. CI fails a PR labeled `type:feature` or `type:bug` that does not touch `CHANGELOG.md`.

### scripts/extract-changelog.sh

```bash
#!/usr/bin/env bash
set -euo pipefail
VERSION="${1:?Usage: $0 <version>}"
awk "/^## \\[${VERSION}\\]/{found=1; next} found && /^## \\[/{exit} found{print}" CHANGELOG.md
```

### Git tagging strategy

- Releases: annotated tags on `main`: `git tag -a vX.Y.Z -m "Super Trends vX.Y.Z"`.
- Sprints: lightweight tags on `staging`: `sprint-N-complete`. The runner depends on these.
- Never move or delete a pushed tag.

### Release workflow (CI)

```
tag vX.Y.Z pushed
  -> check-versions (tag must equal VERSION)
  -> full test suite
  -> build images linux/amd64 + linux/arm64 (buildx)
  -> Trivy scan (fail on HIGH, CRITICAL)
  -> push ghcr.io/mohnishbasha/stokeai-supertrends:X.Y.Z and :sha-<short>
  -> cosign sign (keyless), attach SBOM (SPDX) and SLSA provenance
  -> helm package (version X.Y.Z, appVersion X.Y.Z), helm push to oci://ghcr.io/mohnishbasha/charts, cosign sign
  -> create GitHub Release, body from scripts/extract-changelog.sh, attach SBOM and image digests
```

### Release checklist

Pre-release
- [ ] Final Gate green (all sprint checklists checked, `docs/GATE_DEBT.md` empty); no open `priority:p0` or `priority:p1` issues in the milestone
- [ ] `scripts/check-versions.sh` passes; changelog section written
- [ ] Security review complete

Staging validation
- [ ] `sha-` image and chart deployed to `supertrends-stage` on Stoke by digest
- [ ] Helm tests and smoke suite pass on staging
- [ ] One full real-provider run reviewed by the owner

Release
- [ ] PR `staging` to `main` approved by the owner and merged
- [ ] Annotated tag pushed; release workflow green
- [ ] `cosign verify` succeeds for the image and the chart
- [ ] Production overlay updated to the new chart version and image digest

### Post-release actions

- Back-merge `main` into `develop`.
- Bump `VERSION` on `develop` to the next patch with a `-dev` suffix.
- Confirm the first scheduled production run published.
- Close the milestone; open the next one.
- Record the release in `docs/RETROSPECTIVES.md`.

---

## Coding Standards

### Python

- Python 3.12. `mypy --strict` with no `Any` in public signatures and no `# type: ignore` without a reason comment.
- `ruff` for lint and format; zero warnings.
- Indicator, factor, and selection code is pure: no I/O, no clock, no randomness, no globals. Time and data are passed in.
- Numeric code uses numpy and pandas vector operations. A Python loop over bars is allowed only for recursive indicators (Supertrend band ratchet, RMA) and must be covered by the benchmark test.
- Floats are never compared with `==` in logic except against values produced by the same assignment (the Supertrend `st[t-1] == final_up[t-1]` case stores a direction flag instead of comparing floats).
- Money and prices are floats in computation and rounded only at presentation. Scores are rounded to 1 decimal at the API boundary.
- No `print`. Use structlog. Never log secrets, tokens, or full provider URLs with keys.
- Exceptions: domain errors subclass `SuperTrendsError`; nothing is swallowed silently; every `except` either handles, re-raises, or records and fails the run cleanly.
- pydantic v2 models at every boundary (API, config, provider responses, evidence documents).
- SQL through SQLAlchemy 2 typed queries. No string-built SQL.
- Public functions have docstrings that state units and warm-up behavior.

### TypeScript / React

- `strict: true`, no `any`, no non-null assertions without a comment, no `console.log` in committed code.
- Function components, hooks, no class components. Server state in TanStack Query, UI state in Zustand, no prop drilling beyond two levels.
- The API client is generated from `docs/openapi.json`; no hand-written fetch calls to the API.
- Every component that renders a number formats it through `ui/src/lib/format.ts`.
- Components have tests for loading, empty, error, and populated states.

### General

- No magic numbers: every threshold, period, and weight comes from `config/scoring.yaml` or a named constant.
- TODO format: `TODO(#issue): text`. A TODO without an issue fails lint.
- Conventional Commits:

```
feat:     new feature
fix:      bug fix
chore:    maintenance, tooling, dependencies
docs:     documentation only
test:     testing infrastructure or coverage
refactor: code improvement, no behavior change
perf:     performance improvement
ci:       GitHub Actions and pipelines
```

- No em dashes in prose, comments, UI copy, or generated narratives. No "game-changer" or "revolutionary" in any copy.
- Shell scripts: `set -euo pipefail`, pass `shellcheck`.

---

## Security Guidelines

### Compliance posture

Super Trends produces general, impersonal market analysis for its owner. It is not a registered investment adviser and does not give personalized advice. Build these controls in:

- The disclaimer appears on every screen, API payload, CLI output, and MCP result that contains a pick:
  > Super Trends output is general market analysis generated by an algorithm from technical and fundamental data. It is not investment advice, not a recommendation tailored to you, and not an offer to buy or sell any security. The algorithm can be and often is wrong. Past and backtested performance does not predict future results. You are responsible for your own decisions.
- Super Trends never asks for or stores a user's holdings, account size, risk tolerance, or goals, and never outputs position sizes, options strikes or expiries, leverage, or order instructions.
- Super Trends has no brokerage integration and holds no brokerage credentials. This is a hard boundary for v1.
- The source code is public; a running instance and its picks are not. The default deployment is private (tailnet only). Record in the owner checklist: "Before giving anyone else access to Super Trends, sharing its picks publicly, or charging for them, talk to a securities lawyer. Publishing buy and sell signals to others can bring investment adviser rules into play." The agent does not make this decision and does not add public sharing features.
- Market data vendor terms: display and redistribution rights differ by plan. Super Trends shows data only to its owner by default. Record in the owner checklist to confirm the chosen plan permits the intended use.

### Public repository rules

The repository is public from the first commit. Treat every file, commit message, issue, PR, CI log, and release note as published.

- Never commit: secrets, API keys, tokens, kubeconfigs, tailnet names or IPs, node hostnames, internal service URLs, the Stoke inventory, real run output, the owner's actual watchlist changes, brokerage or account details, or vendor market data. `private/` and `logs/` are git-ignored and stay local.
- `docs/OWNER_CHECKLIST.md` is public: describe actions generically ("create the API key secret"), never paste values or cluster identifiers into it.
- Published picks are not committed to the repository, attached to releases, or posted in issues. The code is open; the output of the owner's instance is private.
- CI for outside contributions: workflows use `pull_request` (never `pull_request_target`), fork PRs get no secrets and no package write permission, first-time contributors need approval before workflows run, and publishing jobs run only on pushes to `staging` and tags in the main repository.
- GitHub secret scanning with push protection, Dependabot alerts, and private vulnerability reporting are enabled; `gitleaks` scans the full history in CI.
- Recorded provider fixtures are synthetic or scrubbed to the minimum shape needed, with no real prices from a licensed feed.
- README, DISCLAIMER, and the UI state that the project is software for running your own analysis, that it provides no signals service, and that each user needs their own market data license.
- Contributions require a signed Contributor License Agreement (`CLA.md`) that grants Serverless Ventures LLC the right to license the contribution under any terms, including commercial ones. A CI check blocks PRs from outside contributors until the CLA is signed. Do not merge any outside contribution without it: one unsigned contribution would stop the owner from granting commercial licenses.
- The license notice travels with the software: the UI footer, `supertrends --version`, and `GET /api/v1/status` show "Copyright Serverless Ventures LLC. Noncommercial use only." with a link to the license (`SUPERTRENDS_SOURCE_URL`, default the public repository). The license requires anyone who shares the software to pass along the license terms and the Required Notice line; never remove it.
- Every source file starts with: `SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0` and `Copyright 2026 Serverless Ventures LLC`. A CI check fails on a source file without them.
- Dependencies must be permissively licensed (MIT, BSD, ISC, PSF, Apache-2.0, MPL-2.0). LGPL is allowed only for unmodified libraries used through their public API (psycopg is LGPL-3.0); never vendor or modify LGPL code. GPL and AGPL dependencies are not allowed, because their terms conflict with a noncommercial restriction. Unknown licenses fail the check.
- Wording: describe the project as "source-available" and "free for noncommercial use". Never call it open source, in the README, docs, UI, package metadata, or GitHub topics.

### Application security

- Authentication: read endpoints are open inside the cluster network boundary; write endpoints (`POST /runs`, watchlist changes, MCP write tools, `/mcp` HTTP) require `Authorization: Bearer` with a token from a Kubernetes Secret. Compare tokens in constant time. Rate-limit write endpoints.
- Hostname: `supertrends.openstoke.com` is the canonical URL (README, docs, CSP, allowed hosts, TLS certificate from the issuer found in the inventory). A public DNS name does not mean public access: the record resolves to a private entry point, and the API rejects requests whose `Host` header is not in `SUPERTRENDS_ALLOWED_HOSTS`.
- The service binds to `0.0.0.0` inside the container but is exposed only through the tailnet or the cluster ingress chosen in the Stoke inventory. No public LoadBalancer in any default profile.
- Strict CSP, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `frame-ancestors 'none'`. No inline scripts or styles.
- Input validation on every parameter (symbols match `^[A-Z][A-Z0-9.\-]{0,9}$`, dates are trading dates, pagination is bounded).
- The narrative path treats LLM output as untrusted text: it is validated, length-limited, and rendered as plain text, never as HTML or Markdown with links.
- Prompt injection: provider-supplied strings (company names, news, descriptions) are never placed in the LLM prompt. The prompt contains only numbers and enumerated labels from the evidence document.
- SSRF: `SUPERTRENDS_LLM_BASE_URL` and provider base URLs come only from configuration, never from request input.

### Secrets

- Secrets: market data API key, fundamentals API key, API bearer token, LLM API key (if the gateway requires one), database password. All from environment variables sourced from Kubernetes Secrets (`existingSecret`), never from values files or git.
- `.env` files are git-ignored; `.env.example` lists names with empty values.
- `gitleaks` runs in CI on every PR.
- Secrets are redacted in logs by a structlog processor and in `provider_calls` by storing only the path and non-secret params.

### Dependency and supply chain security

- `uv.lock` and `package-lock.json` are committed; installs use `--locked` / `npm ci`.
- `pip-audit`, `npm audit`, and Trivy in CI; Dependabot weekly.
- Base images pinned by digest. Images signed with cosign; SBOM and provenance attached. Flux verifies the chart signature before installing.
- GitHub Actions pinned by commit SHA, with `permissions:` set to the minimum per job.

### Container and cluster security

- Non-root user (UID 10001), read-only root filesystem, all capabilities dropped, `allowPrivilegeEscalation: false`, `seccompProfile: RuntimeDefault`.
- NetworkPolicy: default deny; allow ingress to the API from the ingress controller or tailnet proxy and from Prometheus; allow egress to Postgres, DNS, the LLM gateway service, and the market data provider hosts on 443.
- `automountServiceAccountToken: false`. Super Trends needs no Kubernetes API access.
- Resource requests and limits on every container.

### Privacy and network

- Zero telemetry. Outbound traffic only to the configured market data provider, fundamentals provider, and LLM endpoint. An integration test runs the app with egress blocked except to mocks and asserts no other connection is attempted.
- On Stoke the LLM endpoint is the in-cluster gateway, so evidence documents do not leave the cluster.

---

## Design System

Seed for `docs/DESIGN.md`. The feel: a calm trading terminal. Dense where data is dense, quiet everywhere else. Dark theme is the default.

### Color tokens

```css
:root[data-theme="dark"] {
  --bg-0: #0B0E13;        /* app background */
  --bg-1: #121722;        /* cards */
  --bg-2: #1A2130;        /* raised, hover */
  --bg-3: #242D40;        /* inputs, selected */
  --line: #2A3347;        /* borders, grid */
  --text-0: #E8ECF3;      /* primary */
  --text-1: #A9B3C6;      /* secondary */
  --text-2: #6E7A91;      /* tertiary, axis labels */
  --up: #2FBF8F;          /* bullish */
  --up-soft: #153A30;
  --down: #F0616D;        /* bearish */
  --down-soft: #45202A;
  --neutral: #8A94A8;
  --accent: #E0A93B;      /* saffron: the direction needle, focus, links */
  --accent-soft: #3D3118;
  --warn: #E0A93B;
  --info: #5B9BF0;
  --focus: #E0A93B;
}
:root[data-theme="light"] {
  --bg-0: #F6F7F9; --bg-1: #FFFFFF; --bg-2: #EEF1F5; --bg-3: #E3E8EF;
  --line: #D5DBE5; --text-0: #121722; --text-1: #45506A; --text-2: #6E7A91;
  --up: #0E8A63; --up-soft: #DDF3EB; --down: #C93545; --down-soft: #FBE3E6;
  --neutral: #6E7A91; --accent: #A8730F; --accent-soft: #F6EBD3;
  --warn: #A8730F; --info: #2D6CD1; --focus: #A8730F;
}
```

Verify every text and background pair meets AA in both themes; adjust values if a pair fails and record the change in DESIGN.md.

### Typography

- UI: `Inter`, falling back to the system sans stack. Numbers: `JetBrains Mono` with tabular figures. Both self-hosted in the image; no font CDN.
- Scale (px): 12, 13, 14 (body), 16, 20, 28, 40 (score). Weights: 400 body, 500 labels, 600 headings and scores. No weight above 600.
- All prices, scores, and percentages use the mono face and tabular figures so columns align.

### Spacing and layout

- 4 px base: 4, 8, 12, 16, 24, 32, 48. Card padding 16. Card radius 10. Border 1 px `--line`.
- Today screen: a 5-card grid, 3 buys on the first row and 2 sells on the second at desktop width; single column on narrow screens with buys first.
- Maximum content width 1440 px.

### Signature element: the trend ribbon and the direction needle

- **Trend ribbon:** a 6 px strip of 60 cells, one per session, colored `--up` or `--down` by that day's Supertrend direction, with the flip points marked by a 1 px `--accent` tick. It appears on every pick card and every watchlist row. At a glance it shows how long the current trend has run and how choppy the ticker has been.
- **Direction needle:** the ScoreDial is a half-circle gauge from 0 to 100 with a saffron needle. Left third tinted `--down-soft`, right third `--up-soft`. The numeric score sits under the needle in the mono face. The needle is the only saffron shape on a card.

### Chart conventions

- Candles: `--up` and `--down` bodies; wicks in the same color. In light and dark themes alike.
- Supertrend line: 2 px, `--up` when below price, `--down` when above, with a marker at each flip.
- SMA 20 / 50 / 200: 1 px lines in `--info`, `--text-1`, `--accent` with a legend.
- Ripster EMA Clouds: the 5/12 and 34/50 clouds as fills at 15 percent opacity, `--up-soft` when the cloud is bullish and `--down-soft` when bearish, no edge lines. Shown on the ticker chart by default; the 8/9, 72/89 and 180/200 clouds are toggles. Never on the pick card sparkline.
- Fibonacci levels: dashed 1 px `--text-2` with right-edge labels. Support and resistance: solid 1 px `--neutral` with strength shown by opacity.
- Never more than the default overlays on first load; everything else is a toggle.

### Buy and sell without relying on color

Every buy or sell indication pairs color with a text label and a shape: an up triangle and the word "Buy", a down triangle and the word "Sell". The ribbon has an accessible text alternative ("Up 14 sessions, flipped 3 sessions ago").

### Anti-patterns (must not appear)

- Green and red as the only signal of direction.
- Confetti, rockets, flames, "to the moon" language, or any celebratory animation on a pick.
- Certainty language: "guaranteed", "sure thing", "can't lose", "will go to".
- Hidden losers: any view of past picks that omits or de-emphasizes the misses.
- Gradients on data, 3D charts, pie charts for anything.
- Auto-refreshing layout shifts. Data refreshes in place.
- Modal dialogs for reading content. Modals only confirm destructive or token-gated actions.
- A fake "live" feel. Super Trends is an end-of-day product; every number shows its as-of date.

---

## Environment Model

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

## Build and Deployment

This section is mandatory and explicit. `docs/ARCHITECTURE.md` must mirror it, and Sprint 8 produces `docs/DEPLOYMENT.md` from it. The root `Makefile` is the only documented way to build and deploy.

Super Trends is a CPU-only product. There are no GPU requests, no NVIDIA device plugin dependencies, and no model storage. It reaches an LLM over HTTP through the gateway Stoke already runs. Everything GPU-related in the general deployment template is intentionally dropped.

Super Trends is a server product with a web UI, not a desktop app. "Local binary" for Super Trends means the `supertrends` CLI installed from the built wheel.

### Single entry point: root Makefile

Create this in Sprint 0 (S0-T03). Targets not yet implementable print a notice and exit 0 until their sprint.

```makefile
SHELL := /bin/bash
GH_OWNER ?= mohnishbasha
VERSION  := $(shell tr -d '[:space:]' < VERSION)
COMMIT   := $(shell git rev-parse --short HEAD 2>/dev/null || echo unknown)
CREATED  := $(shell date -u +%Y-%m-%dT%H:%M:%SZ)
IMAGE    ?= ghcr.io/$(GH_OWNER)/stokeai-supertrends
CHART    := deploy/helm/stokeai-supertrends
CHART_REPO ?= oci://ghcr.io/$(GH_OWNER)/charts
KIND_CLUSTER ?= supertrends
NAMESPACE ?= supertrends
PROFILE  ?= kind
SMOKE_BASE_URL ?= http://localhost:8080
PLATFORMS ?= linux/amd64,linux/arm64
BUILD_ARGS := --build-arg VERSION=$(VERSION) --build-arg COMMIT=$(COMMIT) --build-arg CREATED=$(CREATED)

.DEFAULT_GOAL := help
.PHONY: help setup build build-release check test coverage dev up down smoke demo demo-verify demo-down run-daily openapi \
        version-sync image image-multiarch image-push image-scan image-verify \
        helm-lint helm-package helm-push kind-up kind-load helm-install helm-test helm-uninstall kind-down

help: ## Show this help
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-18s %s\n", $$1, $$2}'

setup: ## Check prerequisites and install dependencies
	@./scripts/check-prereqs.sh
	uv sync --locked
	npm --prefix ui ci

build: ## Build the UI and the Python wheel
	npm --prefix ui run build
	uv build --wheel

build-release: ## Reproducible release build (locked, clean)
	rm -rf dist ui/dist
	npm --prefix ui ci && npm --prefix ui run build
	uv sync --locked --no-dev && uv build --wheel

check: ## Lint, format check, type-check (Python and TypeScript)
	uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src
	npm --prefix ui run lint && npm --prefix ui run type-check
	./scripts/check-versions.sh

test: ## Unit tests
	uv run pytest tests/unit -q
	npm --prefix ui run test -- --run

coverage: ## Coverage with thresholds
	uv run pytest tests/unit tests/integration --cov=src/supertrends --cov-report=term --cov-report=xml
	npm --prefix ui run test -- --run --coverage
	uv run python scripts/check_coverage.py .coverage-thresholds.toml

dev: ## Native dev: Postgres in Compose, API and UI on the host with reload
	docker compose -f deploy/compose/docker-compose.dev.yml up -d postgres llm-mock
	uv run supertrends db migrate
	( uv run uvicorn supertrends.api.app:create_app --factory --reload --port 8080 & \
	  npm --prefix ui run dev ; kill %1 )

up: ## Run the built image with Compose
	docker compose -f deploy/compose/docker-compose.local.yml up -d --wait

down: ## Stop Compose and remove volumes
	docker compose -f deploy/compose/docker-compose.local.yml down -v

smoke: ## Smoke suite against SMOKE_BASE_URL
	SMOKE_BASE_URL=$(SMOKE_BASE_URL) uv run pytest tests/smoke -q

demo: image ## Local demo: full product on synthetic data, no keys needed
	SUPERTRENDS_DEMO=1 docker compose -f deploy/compose/docker-compose.demo.yml up -d --wait
	@echo "Demo ready: http://localhost:8080   tour: http://localhost:8080/demo   (make demo-verify to check every function)"

demo-verify: ## Check every product function against the running demo, write demo-report/
	SMOKE_BASE_URL=http://localhost:8080 uv run python scripts/demo_verify.py --report demo-report

demo-down: ## Stop the demo and remove its data
	docker compose -f deploy/compose/docker-compose.demo.yml down -v

run-daily: ## Trigger the daily run locally
	uv run supertrends run daily

openapi: ## Regenerate docs/openapi.json and the UI client
	uv run supertrends config export-openapi > docs/openapi.json
	npm --prefix ui run gen:api

version-sync: ## Write VERSION into the checked files
	./scripts/version-sync.sh

image: ## Build the image for the local architecture
	docker buildx build $(BUILD_ARGS) -t $(IMAGE):$(VERSION) -t $(IMAGE):sha-$(COMMIT) --load .

image-multiarch: ## Build for linux/amd64 and linux/arm64 (no push)
	docker buildx build $(BUILD_ARGS) --platform $(PLATFORMS) -t $(IMAGE):$(VERSION) .

image-push: ## Build multi-arch, push, sign, attach SBOM and provenance
	docker buildx build $(BUILD_ARGS) --platform $(PLATFORMS) \
	  --sbom=true --provenance=mode=max \
	  -t $(IMAGE):$(VERSION) -t $(IMAGE):sha-$(COMMIT) --push .
	cosign sign --yes $(IMAGE)@$$(docker buildx imagetools inspect $(IMAGE):$(VERSION) --format '{{json .Manifest.Digest}}' | tr -d '"')

image-scan: ## Vulnerability scan, fails on HIGH or CRITICAL
	trivy image --exit-code 1 --severity HIGH,CRITICAL --ignore-unfixed $(IMAGE):$(VERSION)

image-verify: ## Verify the image signature
	cosign verify $(IMAGE):$(VERSION) \
	  --certificate-identity-regexp '^https://github.com/$(GH_OWNER)/stokeai-supertrends/' \
	  --certificate-oidc-issuer https://token.actions.githubusercontent.com

helm-lint: ## Lint and template every profile
	@for p in kind stoke selfhost hosted; do \
	  helm lint $(CHART) -f $(CHART)/values-$$p.yaml || exit 1; \
	  helm template supertrends $(CHART) -f $(CHART)/values-$$p.yaml > /dev/null || exit 1; \
	done

helm-package: ## Package the chart at the current version
	helm package $(CHART) --version $(VERSION) --app-version $(VERSION) -d dist/charts

helm-push: helm-package ## Push the chart to the OCI registry
	helm push dist/charts/stokeai-supertrends-$(VERSION).tgz $(CHART_REPO)

kind-up: ## Create the local kind cluster
	kind create cluster --name $(KIND_CLUSTER) --config deploy/kind/cluster.yaml

kind-load: ## Load the local image into kind
	kind load docker-image $(IMAGE):$(VERSION) --name $(KIND_CLUSTER)

helm-install: ## Install or upgrade the chart with PROFILE (default kind)
	helm upgrade --install supertrends $(CHART) -n $(NAMESPACE) --create-namespace \
	  -f $(CHART)/values-$(PROFILE).yaml \
	  --set image.repository=$(IMAGE) --set image.tag=$(VERSION) \
	  --atomic --wait --timeout 5m

helm-test: ## Run Helm tests
	helm test supertrends -n $(NAMESPACE) --logs

helm-uninstall: ## Uninstall the release
	helm uninstall supertrends -n $(NAMESPACE)

kind-down: ## Delete the kind cluster
	kind delete cluster --name $(KIND_CLUSTER)
```

### Path 1: Local build

Prerequisites, checked by `scripts/check-prereqs.sh` (called from `make setup`; prints what is missing and how to install it):

| Tool | Minimum | Used for |
|---|---|---|
| Python | 3.12 | backend |
| uv | 0.5 | Python env and lock |
| Node.js | 22 LTS | UI build |
| Docker with buildx | 27 | images, Compose |
| make, jq, git | any recent | tooling |
| kind, kubectl, helm | kind 0.24, kubectl 1.31, helm 3.16 | cluster paths |
| cosign, trivy | current | release paths only |

Verify the latest stable versions at implementation time and pin what you use in `docs/ARCHITECTURE.md`.

```bash
git clone git@github.com:mohnishbasha/stokeai-supertrends.git && cd stokeai-supertrends
make setup
make build
```

Build outputs:

| Output | Path | Built by |
|---|---|---|
| Python wheel (includes the CLI) | `dist/supertrends-{VERSION}-py3-none-any.whl` | `uv build --wheel` |
| UI bundle | `ui/dist/` | `npm --prefix ui run build` |
| Container image | `ghcr.io/mohnishbasha/stokeai-supertrends:{VERSION}` | `make image` |
| Helm chart package | `dist/charts/stokeai-supertrends-{VERSION}.tgz` | `make helm-package` |
| Pi extension | `integrations/pi/dist/` | `npm --prefix integrations/pi run build` |

Rules: a clean clone must build with `make setup && make build`, and CI proves it on every PR. Release builds use `make build-release` (locked dependencies, pinned toolchain through `.python-version` and `.nvmrc`). The CLI and `/healthz` report version and commit.

Verification:

```bash
uv run supertrends --version          # supertrends 0.1.0 (abc1234)
make check && make test
```

### Path 2: Local deploy

**Native run for development**

```bash
make dev                         # Postgres and an LLM mock in Compose, API on :8080 with reload, UI on :5173
uv run supertrends ingest              # fixture provider by default
uv run supertrends run daily
curl -fsS localhost:8080/api/v1/recommendations/latest | jq '.buys[].ticker, .sells[].ticker'
uv run supertrends today
```

**Native install of the release CLI**

```bash
make build-release
uv tool install dist/supertrends-*.whl
supertrends --version
SUPERTRENDS_DATABASE_URL=postgresql+psycopg://... supertrends db migrate
supertrends serve --bind 127.0.0.1:8080 &
supertrends healthcheck --url http://127.0.0.1:8080     # exit 0 when ready
```

Provide `deploy/systemd/supertrends.service` and `deploy/systemd/supertrends-daily.timer` (17:30 America/New_York, weekdays) for a single-host install without Kubernetes, with `scripts/install.sh` that installs the wheel into `/opt/supertrends`, writes an environment file with mode 0600, and enables the units.

**Compose run from the built image**

```bash
make image
make up                          # app + Postgres from deploy/compose/docker-compose.local.yml
make smoke                       # same suite as kind and Stoke
make down
```

**Demo mode (local run to see and verify the product)**

```bash
make demo           # builds the image, starts everything, seeds data, prints the URL
make demo-verify    # one PASS / FAIL line per function, plus demo-report/index.html with screenshots
make demo-down
```

Demo mode exists so the owner can look at the product and confirm it works without API keys, a cluster, or real market data. Requirements:
- `deploy/compose/docker-compose.demo.yml`: the app, Postgres, and the LLM mock, with `SUPERTRENDS_DEMO=1`, the fixture provider, and a one-shot seed service.
- The seed loads the synthetic dataset, then replays the last 60 trading days through the real run orchestrator, so the Today screen, date browsing, rankings, and the Track Record all have data. The synthetic tickers are constructed so the latest run has 3 buys and 2 sells, one ticker in each regime, a fresh Supertrend flip, a divergence, a Fibonacci hold, a breakout, an `event_risk` pick, and one excluded ticker.
- Every screen shows the banner "DEMO DATA: synthetic prices, not real markets". Demo mode cannot be enabled together with a real provider.
- The `/demo` tour lists each function, links to where it is shown, and displays its status.
- `scripts/demo_verify.py` checks the demo matrix below through the API, the CLI, MCP, and (from Sprint 4) the UI with Playwright, prints a table, writes `demo-report/index.html` with one screenshot per screen, and exits non-zero on any FAIL.
- `make demo` followed by `make demo-verify` runs in CI on every PR from Sprint 3 on.

Demo matrix (extend it in the same PR as any new function):

| Function | Verified by | Added in |
|---|---|---|
| Ingest and data quality flags | API status, excluded ticker shown with reason | 3 |
| All 12 factors scored, contributions sum to the composite | analysis endpoint for 3 tickers | 3 (fundamentals and regimes in 5) |
| Top 3 buys and top 2 sells, duplicate guard | latest recommendations | 3 |
| Supertrend line, direction, flip age | bars endpoint and chart overlay | 3, chart in 4 |
| Today, Ticker, Watchlist, Runs, Settings screens | Playwright screenshots | 4 |
| Narrative with numeric guard and template fallback | one LLM-mock narrative, one forced fallback | 5 |
| Dynamic weights and event risk | a trending and a ranging ticker, an earnings-window pick | 5 |
| Track record and backtest | statistics for the 60 replayed days | 6 |
| CLI and MCP parity with the API | `supertrends today --json`, MCP tool calls | 7 |
| Watchlist groups and add / remove | API round trip and UI | 3, UI in 4 |

`docker-compose.local.yml`: the app image (read-only root filesystem, non-root, health check using `supertrends healthcheck`), Postgres with a named volume and health check, a one-shot `migrate` service, a one-shot `seed` service (fixture ingest and one run), and an LLM mock. `docker-compose.prod.yml`: pinned image digests, resource limits, no published database port, an internal network, and secrets from an env file outside the repository.

### Path 3: Containerization using OCI

One deployable, one multi-stage Dockerfile. The same image runs the API (`supertrends serve`), the daily job (`supertrends run daily`), migrations (`supertrends db migrate`), and the stdio MCP server (`supertrends mcp`).

Dockerfile shape (pin every `FROM` by digest when you write it):

```dockerfile
# syntax=docker/dockerfile:1

# ---- stage 1: UI dependencies and build ----
FROM --platform=$BUILDPLATFORM node:22-bookworm-slim AS ui
WORKDIR /ui
COPY ui/package.json ui/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY ui/ ./
RUN npm run build

# ---- stage 2: Python dependencies (cached layer) ----
FROM python:3.12-slim-bookworm AS deps
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /app
COPY pyproject.toml uv.lock VERSION ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-install-project

# ---- stage 3: build and install the project ----
FROM deps AS build
COPY src/ ./src/
COPY config/ ./config/
COPY alembic.ini ./
COPY migrations/ ./migrations/
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev

# ---- stage 4: minimal runtime ----
FROM python:3.12-slim-bookworm AS runtime
ARG VERSION=0.0.0
ARG COMMIT=unknown
ARG CREATED=unknown
LABEL org.opencontainers.image.title="Super Trends Market Agent" \
      org.opencontainers.image.description="Supertrend market agent: daily top buys and sells with justification" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${COMMIT}" \
      org.opencontainers.image.created="${CREATED}" \
      org.opencontainers.image.source="https://github.com/mohnishbasha/stokeai-supertrends" \
      org.opencontainers.image.vendor="Serverless Ventures LLC" \
      org.opencontainers.image.licenses="PolyForm-Noncommercial-1.0.0"
RUN groupadd -g 10001 supertrends && useradd -u 10001 -g 10001 -M -s /usr/sbin/nologin supertrends
ENV PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    SUPERTRENDS_VERSION=${VERSION} SUPERTRENDS_COMMIT=${COMMIT} SUPERTRENDS_UI_DIR=/app/ui
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY --from=build /app/src /app/src
COPY --from=build /app/config /app/config
COPY --from=build /app/alembic.ini /app/alembic.ini
COPY --from=build /app/migrations /app/migrations
COPY --from=ui /ui/dist /app/ui
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD ["supertrends", "healthcheck", "--url", "http://127.0.0.1:8080"]
ENTRYPOINT ["supertrends"]
CMD ["serve", "--bind", "0.0.0.0:8080"]
```

Requirements:
- OCI image format, multi-arch `linux/amd64` and `linux/arm64` through buildx. ARM64 is the production architecture (DGX Spark). Confirm that every wheel in `uv.lock` has an `aarch64` build (numpy, pandas, psycopg binary); if one does not, build it in the `deps` stage and record it in an ADR. CI runs the unit test suite inside the ARM64 image under QEMU at least on `staging`.
- Replace `ghcr.io/astral-sh/uv:latest` and both base images with digest-pinned references. Evaluate a distroless or Chainguard Python runtime; adopt it if numpy and pandas run on it for both architectures, otherwise keep slim and record why.
- Non-root, read-only root filesystem (the app writes only to `/tmp`, mounted as `emptyDir`), a health check that needs no shell (exec form of the CLI).
- Standard `org.opencontainers.image.*` labels wired to `VERSION` and the commit, as above.
- Tagging: immutable `{VERSION}` on release, `sha-{short}` on every merge to `staging`, never `latest`. Deployments reference the digest.
- Registry: GHCR.
- Signing and supply chain: cosign keyless, SBOM (SPDX) and SLSA provenance attached by buildx, Trivy failing on high or critical.
- Non-image OCI artifacts: the Helm chart is pushed with `helm push` to `oci://ghcr.io/mohnishbasha/charts`. Super Trends ships no models or large assets, so `oras` is used only in the air-gap mirror procedure.

Commands:

```bash
make image                 # local arch, loaded into Docker
make image-multiarch       # both arches, proves the build
make image-scan
make image-push            # CI only: build, push, SBOM, provenance, cosign sign
make image-verify          # what a consumer runs:
cosign verify ghcr.io/mohnishbasha/stokeai-supertrends:1.0.0 \
  --certificate-identity-regexp '^https://github.com/mohnishbasha/stokeai-supertrends/' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

### Path 4: Helm chart for a Kubernetes cluster

Chart tree:

```
deploy/helm/stokeai-supertrends/
  Chart.yaml
  values.yaml
  values.schema.json
  values-kind.yaml          # local kind, bundled Postgres, fixture provider, LLM mock
  values-stoke.yaml         # existing k3s ARM64 cluster on DGX Spark (stage and prod)
  values-selfhost.yaml      # any single cluster, bundled Postgres, template narratives by default
  values-hosted.yaml        # AWS: external Postgres, ALB ingress, External Secrets
  templates/
    _helpers.tpl
    configmap-scoring.yaml
    deployment-api.yaml
    service.yaml
    cronjob-daily-run.yaml
    job-migrate.yaml              # pre-install, pre-upgrade hook
    statefulset-postgres.yaml     # when postgres.enabled
    service-postgres.yaml
    pvc.yaml
    ingress.yaml
    hpa.yaml
    pdb.yaml
    networkpolicy.yaml
    serviceaccount.yaml
    servicemonitor.yaml
    prometheusrule.yaml
    configmap-dashboard.yaml
    externalsecret.yaml           # when externalSecrets.enabled
    NOTES.txt
    tests/
      test-health.yaml
      test-api.yaml
```

Seed `values.yaml` (no secret values in any committed file):

```yaml
image:
  repository: ghcr.io/mohnishbasha/stokeai-supertrends
  tag: ""            # defaults to .Chart.AppVersion
  digest: ""         # when set, wins over tag
  pullPolicy: IfNotPresent
imagePullSecrets: []

replicaCount: 1
env: prod

api:
  port: 8080
  resources:
    requests: { cpu: 100m, memory: 256Mi }
    limits: { cpu: "1", memory: 512Mi }
  terminationGracePeriodSeconds: 30

dailyRun:
  enabled: true
  schedule: "30 17 * * 1-5"
  timeZone: America/New_York
  suspend: false
  activeDeadlineSeconds: 3600
  backoffLimit: 1
  resources:
    requests: { cpu: 500m, memory: 512Mi }
    limits: { cpu: "2", memory: 1536Mi }

providers:
  market: massive          # fixture | massive | alternate
  fundamentals: massive
  massiveBaseUrl: https://api.massive.com
  ratePerMinute: 5

llm:
  narrativeProvider: openai_compatible   # template | openai_compatible
  baseUrl: ""              # set per profile; empty means template narratives
  model: ""
  timeoutSeconds: 8

secrets:
  existingSecret: supertrends-secrets   # keys: SUPERTRENDS_API_TOKEN, SUPERTRENDS_MASSIVE_API_KEY, SUPERTRENDS_LLM_API_KEY, SUPERTRENDS_DATABASE_URL
externalSecrets:
  enabled: false
  secretStoreRef: { name: "", kind: ClusterSecretStore }

postgres:
  enabled: true            # bundled single-instance Postgres
  image: { repository: postgres, tag: "17", digest: "" }
  storage: { size: 10Gi, storageClass: "" }
  resources:
    requests: { cpu: 100m, memory: 256Mi }
    limits: { cpu: "1", memory: 1Gi }
  existingSecret: supertrends-postgres   # key: POSTGRES_PASSWORD
externalDatabase:
  enabled: false           # when true, SUPERTRENDS_DATABASE_URL comes from secrets.existingSecret

scoring:
  config: {}               # empty means the default config baked into the image; otherwise rendered to a ConfigMap

ingress:
  enabled: false
  className: ""
  host: ""                 # Stoke profile: supertrends.openstoke.com (stage: supertrends-stage.openstoke.com)
  annotations: {}
  tls: []

autoscaling:
  enabled: false
  minReplicas: 1
  maxReplicas: 3
  targetCPUUtilizationPercentage: 70

pdb:
  enabled: false
  minAvailable: 1

networkPolicy:
  enabled: true
  ingressFrom: []          # namespace and pod selectors allowed to reach the API
  llmEgress: []            # selectors for the LLM gateway
  providerEgressCIDRs: ["0.0.0.0/0"]   # 443 only; narrow where the CNI supports FQDN policy

metrics:
  serviceMonitor: { enabled: false, labels: {} }
  prometheusRule: { enabled: false, labels: {} }
  dashboard: { enabled: false, labels: { grafana_dashboard: "1" } }

nodeSelector: {}
tolerations: []
affinity: {}

podSecurityContext:
  runAsNonRoot: true
  runAsUser: 10001
  runAsGroup: 10001
  fsGroup: 10001
  seccompProfile: { type: RuntimeDefault }
securityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities: { drop: ["ALL"] }
```

Chart rules:
- `Chart.yaml` `version` and `appVersion` equal `VERSION` (checked by `check-versions.sh`).
- `values.schema.json` validates every key, rejects unknown keys, rejects any key named `password`, `token`, or `apiKey` that carries a literal value, and validates the cron expression format.
- API Deployment: `RollingUpdate` with `maxUnavailable: 0`, `maxSurge: 1`; startup, readiness (`/readyz`), and liveness (`/healthz`) probes; `preStop` sleep of 5 seconds and SIGTERM handling so in-flight requests finish; `/tmp` as `emptyDir`.
- The daily run is a CronJob with `concurrencyPolicy: Forbid`, `timeZone`, `startingDeadlineSeconds: 3600`, and history limits. Because the run is a CronJob, the API is stateless and can scale horizontally.
- Migration Job runs as a `pre-install,pre-upgrade` hook with `hook-delete-policy: before-hook-creation,hook-succeeded`. Migrations are backward compatible for one version so rollback works.
- Bundled Postgres is a single-replica StatefulSet with a PVC. With `externalDatabase.enabled` it is not rendered.
- PodDisruptionBudget and HPA are rendered only when enabled and only make sense with more than one replica; the hosted profile enables both.
- NetworkPolicy default deny with the allowances listed in Security Guidelines.
- Helm tests: `test-health` (calls `/readyz`), `test-api` (calls `/api/v1/recommendations/latest` and accepts 200 or a well-formed 404 "no run yet").

Profiles:

| Profile | Database | Provider | LLM | Exposure | Notes |
|---|---|---|---|---|---|
| `values-kind.yaml` | bundled | fixture | in-chart mock (`llmMock.enabled`) | port-forward | CI and local loop; seeds data and triggers a run with a post-install Job |
| `values-stoke.yaml` | bundled on `local-path` (or the class found in the inventory) | massive | Stoke gateway | `supertrends.openstoke.com` (stage: `supertrends-stage.openstoke.com`) through the tailnet service or the existing ingress found in the inventory; reachable only privately | `nodeSelector: {kubernetes.io/arch: arm64}`, ServiceMonitor and dashboard on, no GPU |
| `values-selfhost.yaml` | bundled | massive | template (LLM optional) | ingress off by default | air-gap friendly: `global.imageRegistry` override |
| `values-hosted.yaml` | external (AWS RDS Postgres) | massive | any OpenAI-compatible endpoint | ALB ingress with TLS | External Secrets from AWS Secrets Manager, HPA 2 to 3, PDB on, amd64 or arm64 (Graviton) |

**Stoke profile and inventory.** Stoke already runs a platform. Super Trends reuses it and installs nothing cluster-wide. `scripts/stoke-inventory.sh` (read-only) writes `private/STOKE_INVENTORY.md` (git-ignored) with one row per dependency:

| Component | Expected on Stoke | Super Trends needs | Expected class |
|---|---|---|---|
| Kubernetes (k3s, ARM64) | yes | a namespace | REUSE |
| Flux v2 (source, helm, kustomize controllers) | yes | OCIRepository, HelmRelease, Kustomization | REUSE |
| LLM gateway in front of vLLM (AIBrix) | yes | an OpenAI-compatible base URL and a model name | REUSE |
| kube-prometheus-stack | yes | ServiceMonitor, PrometheusRule, dashboard ConfigMap | REUSE |
| Storage class | k3s `local-path` or other | a 10Gi PVC for Postgres | REUSE |
| Ingress or tailnet exposure | Traefik (k3s default) and Tailscale | one HTTP route, private | REUSE |
| Secret management (SOPS or External Secrets) | find out | 2 Secrets per namespace | REUSE if present, else plain Secrets created by the owner |
| NetworkPolicy enforcement | depends on CNI | default deny plus allowances | REUSE if enforced, else document the gap |
| Postgres operator | probably none | none: the bundled StatefulSet is enough | NOT NEEDED |
| GPU Operator, KubeRay | yes | nothing | NOT NEEDED |

The script records the gateway's in-cluster service URL and the served model names (from the gateway's `/v1/models`) so `values-stoke.yaml` can be filled without guessing. If a model must be chosen, prefer a small instruct model already served; Super Trends's narrative task is short and structured. Record the choice and the measured acceptance rate in `docs/NARRATIVE_EVAL.md`. Do not deploy a model for Super Trends.

Local cluster loop:

```bash
make kind-up
make image
make kind-load
make helm-install                 # PROFILE=kind
make helm-test
kubectl -n supertrends port-forward svc/supertrends 8080:8080 &
make smoke
make helm-uninstall && make kind-down
```

Remote install from the OCI chart (any cluster, without Flux):

```bash
helm upgrade --install supertrends oci://ghcr.io/mohnishbasha/charts/stokeai-supertrends \
  --version 1.0.0 -n supertrends --create-namespace \
  -f values-stoke.yaml \
  --set image.digest=sha256:<digest-from-release> \
  --atomic --wait --timeout 10m
helm test supertrends -n supertrends --logs
helm history supertrends -n supertrends
helm rollback supertrends <revision> -n supertrends --wait
```

Secrets the owner creates once per namespace (values never enter git):

```bash
kubectl -n supertrends create secret generic supertrends-postgres --from-literal=POSTGRES_PASSWORD="$(openssl rand -hex 24)"
kubectl -n supertrends create secret generic supertrends-secrets \
  --from-literal=SUPERTRENDS_API_TOKEN="$(openssl rand -hex 32)" \
  --from-literal=SUPERTRENDS_MASSIVE_API_KEY="<key>" \
  --from-literal=SUPERTRENDS_LLM_API_KEY="" \
  --from-literal=SUPERTRENDS_DATABASE_URL="postgresql+psycopg://supertrends:<same password>@supertrends-postgres:5432/supertrends"
```

**Stoke through Flux (the production path).** Stoke uses Flux for GitOps. Super Trends ships manifests that the Stoke GitOps repository references:

```
deploy/flux/
  base/
    namespace.yaml
    ocirepository.yaml      # chart source, cosign-verified
    helmrelease.yaml
    kustomization.yaml
  overlays/
    stage/                  # namespace supertrends-stage, sha- chart or prerelease, replicas may be 0
      kustomization.yaml
      patch-helmrelease.yaml
    prod/                   # namespace supertrends, released chart version, image by digest
      kustomization.yaml
      patch-helmrelease.yaml
```

Shape of the two key objects (confirm API versions against the Flux version found in the inventory):

```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: OCIRepository
metadata:
  name: stokeai-supertrends
  namespace: supertrends
spec:
  interval: 10m
  url: oci://ghcr.io/mohnishbasha/charts/stokeai-supertrends
  ref:
    semver: "1.x"
  verify:
    provider: cosign
    matchOIDCIdentity:
      - issuer: "^https://token.actions.githubusercontent.com$"
        subject: "^https://github.com/mohnishbasha/stokeai-supertrends/.*$"
---
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: supertrends
  namespace: supertrends
spec:
  interval: 10m
  chartRef:
    kind: OCIRepository
    name: stokeai-supertrends
  install:
    remediation: { retries: 2 }
  upgrade:
    remediation: { retries: 2, strategy: rollback }
  test:
    enable: true
  rollback:
    cleanupOnFail: true
  values:
    env: prod
    image:
      digest: sha256:REPLACE_WITH_RELEASE_DIGEST
    nodeSelector:
      kubernetes.io/arch: arm64
    llm:
      baseUrl: REPLACE_FROM_STOKE_INVENTORY
      model: REPLACE_FROM_STOKE_INVENTORY
    metrics:
      serviceMonitor: { enabled: true }
      prometheusRule: { enabled: true }
      dashboard: { enabled: true }
```

The GHCR image and chart packages are public, so no pull secret is needed; after the first publish, record in the owner checklist that the package visibility must be set to public. The manifests in this public repository keep the `REPLACE_` placeholders; real cluster values are patched in the Stoke GitOps repository. Promotion is a pull request to the Stoke GitOps repository that changes the chart version and image digest in the overlay. Rollback is reverting that pull request, or in an emergency:

```bash
flux suspend helmrelease supertrends -n supertrends
helm rollback supertrends <revision> -n supertrends --wait
# fix forward in git, then
flux resume helmrelease supertrends -n supertrends
```

Chart verification in CI:
- `helm lint` and `helm template` for every profile (`make helm-lint`), output validated with `kubeconform`.
- Schema negative tests: a values file with a literal secret, an invalid cron, and an unknown key must each fail.
- `kind-e2e`: kind install with the kind profile, post-install seed and run, Helm tests, smoke suite.
- Upgrade and rollback test: previous released chart to current, smoke, rollback, smoke.
- `kustomize build` and schema validation for both Flux overlays.

Air-gapped install (self-host profile): mirror the image and chart into a private registry with `oras copy` or `skopeo copy --all`, set `global.imageRegistry` and the chart URL, and use the `fixture` or an internally reachable provider. `DEPLOYMENT.md` carries the exact commands.

### CI and CD pipeline map

| Workflow | Trigger | What it does |
|---|---|---|
| `ci.yml` | PR and push to `develop`, `staging`, `main` | lint, type-check, unit, coverage thresholds, integration (Postgres service), e2e (Playwright on Compose), image build for both architectures, `helm-lint`, version and changelog checks, gitleaks, audits |
| `kind-e2e.yml` | PR touching `src/`, `deploy/`, `Dockerfile`; push to `staging` | kind install, Helm tests, smoke suite, upgrade and rollback test |
| `release-images.yml` | push to `staging` (sha tag), tag `v*` (version tag) | multi-arch build, Trivy, push to GHCR, cosign sign, SBOM and provenance |
| `release-chart.yml` | same as above | `helm package`, `helm push` to OCI, cosign sign |
| `release.yml` | tag `v*` | version check, full suite, calls the two workflows above, creates the GitHub Release |
| `harness-smoke.yml` | push to `staging`, tag `v*` | MCP client against the API with fixture data |
| `flux-validate.yml` | PR touching `deploy/flux/` | `kustomize build`, schema validation |
| `nightly.yml` | schedule | full suite inside the ARM64 image under QEMU, dependency audit, determinism hash check |

Deployment to Stoke is pull-based through Flux. CI never holds cluster credentials.

### Which sprint delivers which part

| Sprint | Build and deployment deliverable |
|---|---|
| 0 | Makefile, prerequisites script, Dockerfile skeleton, Compose, CI building both architectures, inventory script |
| 1 | Compose with Postgres and migrations, smoke suite skeleton |
| 3 | Real image, minimal chart, kind loop, `kind-e2e` in CI, CronJob, full smoke suite |
| 3 to 9 | Demo mode (`make demo`, `make demo-verify`), extended every sprint |
| 4 to 7 | Every sprint checklist: image builds, chart installs on kind, smoke suite passes against it |
| 6 | ServiceMonitor, PrometheusRule, dashboard |
| 8 | Complete chart and schema, four profiles, signed `sha-` images and OCI chart, Flux overlays, staging on Stoke, upgrade and rollback test, air-gap notes, `docs/DEPLOYMENT.md` |
| 9 | Signed multi-arch `1.0.0` image and chart, production on Stoke by digest |

---

## Dependency Versions

Verify the latest stable version of each at implementation time, pin exact versions in the lock files, and record them in `docs/ARCHITECTURE.md`. The constraints below are floors, not targets.

### Python (pyproject.toml)

| Package | Constraint | Purpose |
|---|---|---|
| python | `>=3.12,<3.13` | runtime |
| fastapi | `>=0.115` | HTTP API |
| uvicorn[standard] | `>=0.32` | ASGI server |
| pydantic, pydantic-settings | `>=2.9` | models and settings |
| sqlalchemy | `>=2.0.36` | ORM and queries |
| alembic | `>=1.14` | migrations |
| psycopg[binary] | `>=3.2` | Postgres driver |
| numpy | `>=2.1` | numeric core |
| pandas | `>=2.2` | bar frames, resampling |
| exchange-calendars | `>=4.5` | trading calendar |
| httpx | `>=0.27` | provider and LLM clients |
| tenacity | `>=9.0` | retries |
| typer | `>=0.13` | CLI |
| structlog | `>=24.4` | logging |
| prometheus-client | `>=0.21` | metrics |
| mcp | current stable | MCP server SDK |
| pyyaml | `>=6.0` | config |
| dev: pytest, pytest-cov, pytest-asyncio, hypothesis, respx, ruff, mypy, pip-audit, testcontainers | current stable | tests and tooling |

Do not add a technical-analysis library (TA-Lib, pandas-ta) as a runtime dependency. The indicators are implemented in-house so the formulas match the specification and TradingView exactly, and so the ARM64 image has no native build surprises. A TA library may be used in tests only, as an independent cross-check.

### TypeScript (ui/package.json)

| Package | Constraint | Purpose |
|---|---|---|
| react, react-dom | `^19` | UI |
| vite | `^6` | build |
| typescript | `^5.6` | language |
| react-router | `^7` | routing |
| @tanstack/react-query | `^5` | server state |
| zustand | `^5` | UI state |
| lightweight-charts | `^5` | financial charts (Apache-2.0, by TradingView) |
| openapi-typescript, openapi-fetch | current stable | generated API client |
| vitest, @testing-library/react, @axe-core/playwright, @playwright/test, eslint | current stable | tests and lint |

`integrations/pi`: `pi-agent-core` and `@sinclair/typebox`, current stable; confirm package names at implementation time.

### Infrastructure

| Component | Version |
|---|---|
| PostgreSQL | 17 |
| Helm | 3.16 or later |
| kind node image | match the Stoke k3s minor version found in the inventory |
| Flux | the version running on Stoke |

---

## Out of Scope for v1

Create one GitHub issue per item with the `enhancement` label and no milestone.

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

---

## README Template

```markdown
# Super Trends Market Agent

*Know which way the tape is leaning.*

Super Trends watches a list of stocks, applies the TradingView Supertrend algorithm together with ten
supporting technical and fundamental factors, and turns the result into one score per ticker.
Every trading day it publishes the three strongest buys and the two strongest sells, each with
the evidence and a plain-language justification.

> Super Trends output is general market analysis generated by an algorithm. It is not investment
> advice. The algorithm can be and often is wrong. See DISCLAIMER.md.

## What it does

- Scores every watchlist ticker from 0 to 100 using 12 factors: Supertrend, SMA analysis, MACD,
  divergences, mean reversion, Fibonacci retracement, support and resistance, volatility,
  volume oscillator, estimated buy / sell volume, a fundamentals overlay, and Ripster EMA Clouds
- Adjusts factor weights by regime (trending, ranging) and by fundamentals and earnings proximity
- Publishes the top 3 buys and top 2 sells daily, never padding the list
- Explains each pick: factor contributions, key levels, the level that invalidates the view
- Keeps an honest track record of every past pick against SPY
- Serves a web UI, an HTTP API, a CLI, and an MCP server for agents

## Requirements

- Python 3.12, Node.js 22, Docker with buildx, make
- Your own market data API key (Massive, formerly Polygon.io) for real data. The fixture provider needs none
- Optional: an OpenAI-compatible LLM endpoint for narratives

## Quick start (demo mode, synthetic data, no keys)

    make demo
    open http://localhost:8080        # tour of every function: /demo
    make demo-verify                  # PASS / FAIL per function, report in demo-report/
    make demo-down

## Build from source

    make setup && make build && make check && make test

## Deploy

- Local cluster: `make kind-up image kind-load helm-install helm-test`
- StokeAI (k3s on DGX Spark) through Flux: see docs/DEPLOYMENT.md

## CLI

    supertrends today
    supertrends analyze ORCL
    supertrends rank --top 10
    supertrends backtest --from 2025-01-01 --to 2026-06-30

## Agents

MCP server over stdio (`supertrends mcp`) or HTTP (`/mcp`). Integration files for Pi, Goose,
OpenCode, and Claude Code are in `integrations/`.

## Documentation

docs/PRD.md, docs/ARCHITECTURE.md, docs/DESIGN.md, docs/USER_GUIDE.md, docs/DEPLOYMENT.md,
docs/RUNBOOK.md

## License

Super Trends Community License (PolyForm Noncommercial 1.0.0). Copyright 2026 Serverless Ventures LLC.
All rights not expressly granted are reserved.

Free to use, modify, and share for noncommercial purposes. Commercial use of any kind requires a
separate license from Serverless Ventures LLC: legal@serverlessvc.com. See LICENSE and COMMERCIAL.md.
This project is source-available, not open source.

This is software for running your own analysis. It is not a signals service, and you need your own
market data license. See DISCLAIMER.md.

## Contributing

See CONTRIBUTING.md. Contributions require a signed CLA (CLA.md). Report security issues privately as described in SECURITY.md.
```

---

## Implementation Notes for the Executing Agent

1. Your first action is Step 1: generate all five spec documents. Not the repository, not the scaffold. The documents.
2. After Step 1, the spec docs are the source of truth. Keep them current in the same PR as the code (Spec Change Protocol).
3. `runner.mk`, `run-supertrends.sh`, `run-supertrends-status.sh`, and `logs/` belong to the operator. Do not edit, move, or delete them. Add `logs/` to `.gitignore`. Every sprint ends by creating and pushing the tag `sprint-N-complete`, because the runner depends on it.
4. This prompt is saved in the project folder as `BUILD_PROMPT.md`. Commit it. Do not edit it; changes go into the spec docs.
5. Never weaken a formula, weight, or threshold from the Signal Engine Specification to make a test pass. If the specification is ambiguous or you believe it is wrong, implement the most literal reading, write an ADR describing the ambiguity and the alternative, and add an owner checklist entry.
6. The Supertrend implementation must match TradingView. The sign convention differs (Super Trends: +1 is up; TradingView: negative is up). Convert only at the import boundary of the parity test.
7. Scores are deterministic and the LLM never touches them. If you find yourself passing LLM output into scoring, ranking, or selection: stop.
8. No look-ahead, anywhere. Pivots confirm late; fundamentals are point-in-time; backtest entries are next open. The property test is the judge.
9. Never pad the picks. Fewer than 3 buys or 2 sells is a valid, expected result.
10. Never commit vendor market data. Tests use the synthetic fixture provider and scrubbed, minimal recorded responses.
11. The repository is public. Follow the Public repository rules in Security Guidelines on every commit, issue, and PR. Never commit, log, or echo a secret. Never put a secret value in a values file, a manifest, a test, or a comment.
12. No test may call the network. Providers and the LLM are mocked or recorded.
13. Super Trends is CPU-only. Do not request GPUs, do not deploy models, do not install cluster-wide components on Stoke. Reuse what the inventory finds.
14. Stoke is ARM64. Every image must run on `linux/arm64`. Prove it in CI, not by assumption.
15. You do not have, and must not ask for, cluster-admin credentials in CI. Deployment to Stoke is through Flux and the owner's GitOps repository.
16. Owner-only actions go in `docs/OWNER_CHECKLIST.md` with exact commands. Keep working on everything unblocked. Stop only when nothing unblocked remains.
17. Build and deployment are built incrementally. From Sprint 3 on, each sprint checklist includes "image builds, chart installs on kind, smoke suite passes, demo passes". If one of these fails, fix it in the sprint if you can; otherwise log it in `docs/GATE_DEBT.md` and keep going.
18. Verify current versions and current vendor API shapes at implementation time by reading the official docs. Market data vendors change endpoints, limits, and names. Record what you verified and when in the relevant ADR.
19. No em dashes in any file you write. No hype words in copy. No certainty language about markets, ever.
20. The disclaimer travels with every pick on every surface. A surface that shows a pick without it is a bug with `priority:p0`.
21. When uncertain between a clever design and a plain one, choose the plain one. The owner asked for a simple agent. The complexity budget goes to correctness of the signals, not to infrastructure.
22. There are no gates between sprints. Finish the sprint's tasks, run its checklist, log unmet items in `docs/GATE_DEBT.md`, tag `sprint-N-complete`, and start the next sprint. Only Sprint 9 is different: do not tag `sprint-9-complete` until the Final Gate is fully green.
23. Keep the demo working. `make demo` is how the owner sees the product; a sprint that breaks it has a `priority:p0` bug.

---

## Appendix A: Architecture and Integration Decisions

Seed for the decision log in `docs/ARCHITECTURE.md`. Each becomes an ADR with context, decision, alternatives, and consequences.

| ADR | Decision | Why | Alternatives rejected |
|---|---|---|---|
| 001 | Web service with a browser UI, not a desktop app | It runs on Stoke and is reached over the tailnet from any device; a scheduled server job is the product's heartbeat | Tauri desktop app (no server to schedule runs, harder to reach from phone) |
| 002 | Python 3.12 for the backend | Quant and indicator work is fastest and most verifiable in numpy and pandas; one language for engine, API, CLI, and MCP keeps a simple product simple | Go (matches other Stoke tools, but weaker numeric ecosystem and more code for the same math); Rust (highest effort for no user-visible gain at this scale) |
| 003 | Indicators implemented in-house, no TA library at runtime | Exact TradingView parity, explicit warm-up and look-ahead behavior, clean ARM64 builds | TA-Lib (native build on ARM64, formulas differ in seeding), pandas-ta (maintenance risk) |
| 004 | PostgreSQL, bundled single instance by default | Append-only history, JSONB evidence, concurrent API and job access; trivial to run on k3s | SQLite on a PVC (blocks the CronJob and API from sharing safely); TimescaleDB (not needed at this volume) |
| 005 | Daily run as a Kubernetes CronJob calling the CLI | Stateless API, native scheduling, retries and history from the platform | In-process scheduler (ties run lifetime to the API pod, breaks with replicas) |
| 006 | One image, several commands | One artifact to build, sign, scan, and mirror | Separate API, worker, and UI images (more supply chain surface for no benefit) |
| 007 | UI served by the API | Single origin, simple CSP, one Service | Separate nginx image |
| 008 | LLM used only for narrative, through an OpenAI-compatible endpoint, with a numeric guard and template fallback | Explanations in plain language without letting a model invent numbers or move scores; works with the Stoke gateway and with no LLM at all | LLM-in-the-loop scoring (non-deterministic, unverifiable); no LLM (drier justifications) |
| 009 | Pluggable market data and fundamentals providers; Massive (formerly Polygon.io) as the first adapter | Vendor independence; one vendor covers daily bars, intraday bars, corporate actions, and financials | Unofficial scraping libraries (unreliable, terms risk) |
| 010 | Estimated order flow from 5-minute bars | True order flow needs L2 and tick data that v1 does not buy; the estimate is cheap, explainable, and labeled as an estimate | Skip the factor (loses the volume-pressure read the owner relies on); buy tick data (cost) |
| 011 | Rule-based, transparent scoring with a versioned config | Every pick can be explained and reproduced; the owner tunes it by hand | Learned weights (no track record yet to train on) |
| 012 | Flux HelmRelease from a signed OCI chart for Stoke | Matches how Stoke deploys everything else; pull-based, no cluster credentials in CI | `helm install` from CI (credentials in CI), Argo CD (not what Stoke runs) |
| 013 | MCP server (stdio and HTTP) as the main agent interface, plus a thin Pi extension | One server covers Goose, OpenCode, Claude Code, and others; Pi gets slash commands and streaming | Per-harness plugins (duplicated work) |
| 014 | CLI in Python (Typer), not a separate Bun binary | The CLI shares the engine; a second language and binary would add surface with no benefit for a server product | TypeScript CLI compiled with bun |
| 015 | Deployments private by default (the code is public, an instance is not), token on writes, no user accounts | Single owner on a tailnet; accounts and public access are deferred with the legal review | Clerk auth now (unneeded complexity) |
| 016 | Community license: PolyForm Noncommercial 1.0.0, with a CLA | The owner wants public source, no commercial use by others, and all rights kept by Serverless Ventures LLC. A standard, lawyer-drafted text is safer than a home-made license, and the CLA keeps commercial licensing in one pair of hands | AGPL-3.0 (allows commercial use); Apache-2.0 or MIT (allow everything); a custom-written license (untested wording); BUSL (time-limited, converts to open source later) |

Harness integration summary:

| Harness | Integration | Why |
|---|---|---|
| Pi | `@stokeai-supertrends/pi-extension` on `pi-agent-core` with TypeBox tools | Slash commands, streaming run progress |
| Goose | `integrations/goose/toolkit.yaml` pointing at the MCP server | Goose speaks MCP natively |
| OpenCode | Config snippet and README | OpenCode speaks MCP natively |
| Claude Code | `CLAUDE.md`, `AGENTS.md`, `.mcp.json` snippet | Native file-based context plus MCP |

---

## Appendix B: Repository Structure

```
stokeai-supertrends/
  BUILD_PROMPT.md
  VERSION
  Makefile
  Dockerfile
  pyproject.toml
  uv.lock
  alembic.ini
  README.md  CHANGELOG.md  LICENSE  COPYRIGHT  COMMERCIAL.md  CLA.md  DISCLAIMER.md  THIRD_PARTY_LICENSES.md
  CONTRIBUTING.md  CODE_OF_CONDUCT.md  SECURITY.md
  private/                                            # git-ignored: Stoke inventory and cluster values
  AGENTS.md  CLAUDE.md  SKILLS.md  SOUL.md
  .gitignore  .python-version  .nvmrc  .coverage-thresholds.toml  .env.example
  runner.mk  run-supertrends.sh  run-supertrends-status.sh        # operator files, do not edit
  .agent/skills/
    run-tests/      SKILL.md  run.sh
    check-types/    SKILL.md  run.sh
    daily-brief/    SKILL.md  run.sh
  .github/
    workflows/      ci.yml  kind-e2e.yml  release.yml  release-images.yml  release-chart.yml
                    harness-smoke.yml  flux-validate.yml  nightly.yml
    ISSUE_TEMPLATE/ task.md  bug_report.md
    pull_request_template.md  dependabot.yml
  config/
    scoring.yaml
    watchlist.seed.yaml
  docs/
    PRD.md  ARCHITECTURE.md  DESIGN.md  SPRINT_PLAN.md  TEST_PLAN.md
    RETROSPECTIVES.md  OWNER_CHECKLIST.md  GATE_DEBT.md  DEPLOYMENT.md
    USER_GUIDE.md  RUNBOOK.md  SECURITY_REVIEW.md  PERFORMANCE.md  NARRATIVE_EVAL.md
    openapi.json
    adr/
  migrations/
  src/supertrends/
    __init__.py  version.py  settings.py  errors.py  logging.py
    indicators/     primitives.py  supertrend.py  ripster_clouds.py  trend.py  momentum.py  divergence.py
                    meanrev.py  volatility.py  fibonacci.py  levels.py  volume.py  flow.py  registry.py
    scoring/        factor.py  factors/ (one module per factor)  regime.py  weights.py
                    composite.py  confidence.py  config.py
    selection/      candidates.py  ranking.py  correlation.py
    narrative/      evidence.py  template.py  llm.py  guard.py  prompts/
    data/           models.py  repo.py  ingest.py  calendar.py  quality.py
                    providers/  base.py  fixture.py  massive.py  alternate.py  registry.py
    runs/           orchestrator.py  state.py  publish.py
    trackrecord/    outcomes.py  stats.py  backtest.py
    api/            app.py  deps.py  routes/  schemas.py  security.py  static.py
    mcp/            server.py  tools.py
    cli/            main.py  commands/
    observability/  metrics.py
  ui/
    package.json  vite.config.ts  tsconfig.json  index.html
    src/  main.tsx  routes/  components/  store/  lib/  api/ (generated)  styles/tokens.css
    tests/  e2e/
  integrations/
    pi/  goose/  opencode/  claude-code/
  deploy/
    compose/   docker-compose.dev.yml  docker-compose.local.yml  docker-compose.prod.yml
    helm/stokeai-supertrends/
    flux/      base/  overlays/stage/  overlays/prod/
    kind/      cluster.yaml
    systemd/   supertrends.service  supertrends-daily.timer
    dashboards/ supertrends.json
  scripts/
    check-prereqs.sh  check-versions.sh  version-sync.sh  extract-changelog.sh
    check_coverage.py  gen-third-party-licenses.sh  stoke-inventory.sh  validate-fixtures.sh  install.sh
  tests/
    unit/  integration/  smoke/  regression/  golden/  narrative_eval/  fixtures/
```

---

## Appendix C: API Contract (seed)

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
| GET | `/api/v1/tickers/{symbol}/bars?tf=1d&from=&to=` | none | Bars plus overlay series (Supertrend, SMAs) |
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

Shape of `GET /api/v1/recommendations/latest`:

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

---

## Appendix D: Database Schema (seed)

| Table | Key columns | Notes |
|---|---|---|
| `tickers` | `symbol` PK, `name`, `type` (stock, etf), `active`, `avg_dollar_volume_20d` | |
| `watchlists` / `watchlist_items` | `watchlist_id`, `symbol`, `group_name`, `added_at` | one default watchlist |
| `bars_daily` | (`symbol`, `date`) PK, `open`, `high`, `low`, `close`, `volume`, `adjusted_at` | adjusted prices |
| `bars_intraday` | (`symbol`, `ts`) PK, OHLCV | 5-minute, 90-day retention |
| `fundamentals` | (`symbol`, `period_end`, `known_at`) PK, metrics JSONB | point-in-time |
| `earnings_calendar` | (`symbol`, `date`) PK, `confirmed` | |
| `config_versions` | `hash` PK, `version`, `document` JSONB, `first_seen_at` | |
| `runs` | `id` PK (ULID), `trade_date`, `state`, `started_at`, `finished_at`, `published_at`, `superseded_by`, `config_hash`, `summary` JSONB | one published run per date |
| `indicator_snapshots` | (`run_id`, `symbol`) PK, `values` JSONB | |
| `factor_scores` | (`run_id`, `symbol`, `factor_id`) PK, `score`, `weight`, `contribution`, `quality`, `evidence` JSONB | append-only |
| `recommendations` | `id` PK, `run_id`, `symbol`, `side`, `rank`, `display_score`, `confidence`, `band`, `evidence` JSONB, `entry_price` | append-only except `entry_price` filled once |
| `narratives` | `recommendation_id` PK, `text`, `source`, `model`, `prompt_version`, `tokens_in`, `tokens_out` | |
| `outcomes` | (`recommendation_id`, `horizon_days`) PK, `return`, `benchmark_return`, `excess_return`, `computed_at` | append-only |
| `provider_calls` | `id`, `provider`, `endpoint`, `status`, `duration_ms`, `ts` | no secrets, 30-day retention |

Indexes: `runs(trade_date, published_at)`, `recommendations(run_id, side, rank)`, `factor_scores(symbol, run_id)`, `bars_daily(date)`.

---

## Appendix E: config/scoring.yaml (seed)

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

The schema requires the twelve weights to sum to 100.

---

## Appendix F: MCP Tools (seed)

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

---

## Appendix G: Test Infrastructure and Maintenance

| Type | When | Runner | Location |
|---|---|---|---|
| Unit | Pure logic, no I/O | pytest, vitest | `tests/unit/`, `ui/src/**/*.test.tsx` |
| Golden | Indicator and factor math against fixed expected values | pytest | `tests/golden/` |
| Property | No look-ahead, bounds, invariants | pytest with hypothesis | `tests/unit/` |
| Integration | Real Postgres, mocked providers and LLM | pytest with testcontainers | `tests/integration/` |
| Smoke | Minimal end-to-end sanity against any deployment | pytest | `tests/smoke/` |
| E2E | Full user flows through the UI | Playwright | `ui/tests/e2e/` |
| Narrative eval | Guard and prompt quality | pytest plus `make narrative-eval` | `tests/narrative_eval/` |
| Regression | Every fixed bug | pytest, vitest | `tests/regression/` |

Naming:

```
Unit:        test_{module}_{function}_{scenario}_{expected_outcome}
Integration: it_{component}_{operation}_{scenario}
Smoke:       smoke_{feature}_{minimal_assertion}
E2E:         e2e_{user_story_id}_{scenario}
Regression:  regression_{gh_issue_number}_{what_was_broken}
```

Regression test lifecycle:

```
Bug reported -> GitHub issue created (type:bug)
  -> reproduction confirmed -> regression test written (FAILS)
  -> fix implemented -> regression test passes
  -> PR: regression test and fix in the same commit
  -> merged -> issue closed -> test runs in CI forever
```

Regression tests are never deleted.

Golden fixture policy: golden files change only in a PR that also changes `scoring.version` or fixes a proven math bug, and the PR description shows the before and after values and the reason. `scripts/validate-fixtures.sh` checks that recorded provider responses still match the provider models and that the synthetic dataset hash matches the committed hash.

Smoke checklist (automated in `tests/smoke`, also run by hand after each Stoke deploy):
1. `/healthz` and `/readyz` return 200 and the expected version
2. Latest recommendations return at most 3 buys and 2 sells, each with evidence, narrative, invalidation, and disclaimer
3. Analysis for one watchlist ticker returns 12 factors (or fewer with a stated reason) and contributions that sum to the composite
4. Watchlist add and remove round trip (with token), and is rejected without it
5. A triggered run reaches `published` or reports "market closed"
6. Track record endpoint responds with sample sizes
7. UI root loads and shows the as-of date and the disclaimer

---

## Appendix H: Complete Sprint Overview

| Sprint | Name | Weeks | Tasks | Checklist highlights |
|---|---|---|---|---|
| 0 | Scaffold | 1 | 10 | Clean-clone build, CI, both-arch image, agent files |
| 1 | Data Layer | 1 | 8 | Idempotent ingestion, provider contracts, no network in tests |
| 2 | Indicator Engine | 1 | 9 | All indicators, no look-ahead, TradingView parity |
| 3 | Scoring and Daily Picks | 2 | 13 | Deterministic picks, atomic publish, kind install in CI |
| 4 | UI | 1 | 9 | All screens, e2e, accessibility |
| 5 | Justification and Dynamic Weights | 1 | 7 | Numeric guard, point-in-time fundamentals, regime weights |
| 6 | Track Record and Backtest | 1 | 6 | Honest statistics, backtest equals live on fixtures |
| 7 | CLI, MCP, Harnesses | 1 | 6 | CLI and MCP parity with the API |
| 8 | Packaging and Stoke Deploy | 1 | 7 | Signed OCI artifacts, Flux, staging on Stoke |
| 9 | Release v1.0.0 | 1 | 7 | Security, resilience, production by digest |

Total: 11 weeks of sprint time, 82 tasks. Sprints run straight through; the only hard gate is the Final Gate after Sprint 9.

---

## Appendix I: Modularity Principles

1. **The engine is a library.** `indicators`, `scoring`, and `selection` import nothing from `api`, `cli`, `mcp`, `data`, or `runs`. They take arrays and config and return values. This is enforced by an import-linter contract in CI.
2. **One implementation of the daily loop.** Live runs and backtests call the same functions. There is no second scoring path.
3. **Providers behind protocols.** Adding a market data vendor is one new file and one registry line.
4. **Factors are plugins.** A new factor is one module with a `Factor` implementation, an entry in `config/scoring.yaml`, reason templates, and tests. Nothing else changes.
5. **Surfaces are thin.** API, CLI, and MCP are adapters over the same service functions and share the same pydantic schemas.
6. **Config over code.** Every period, weight, and threshold is in `config/scoring.yaml`, versioned and hashed.
7. **Evidence is the contract.** The UI, narratives, CLI, and MCP all render from the stored evidence document. Nothing recomputes scores for display.
8. **The narrative layer is replaceable.** Swapping the LLM, or removing it, changes no score and no pick.

---

## Appendix J: Agent Repository Files

Generate these in Sprint 0 (S0-T07).

**`.gitignore`** sections: Python (`__pycache__/`, `.venv/`, `dist/`, `*.egg-info/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`), TypeScript (`node_modules/`, `ui/dist/`, `*.tsbuildinfo`), environment (`.env`, `.env.*`, with `.env.example` committed), test and coverage (`coverage/`, `.coverage`, `coverage.xml`, `playwright-report/`, `test-results/`), database (`*.db`, `*.dump`), agent sessions (`.pi/sessions/`, `.agent/sessions/`, `CLAUDE.local.md`), runner (`logs/`), demo output (`demo-report/`), local cluster data (`private/`), OS (`.DS_Store`, `Thumbs.db`), editor (`.vscode/settings.json`, `.idea/`). `uv.lock` and `package-lock.json` are tracked.

**`AGENTS.md`** must contain: product name and one-line description; all build, run, and test commands (the Makefile targets, copy-pasteable); the repository tree; Python and TypeScript style rules; NEVER and ALWAYS rules in imperative form; versioning (the `VERSION` file and `check-versions.sh`); boundaries (never touch runner files, never commit secrets or vendor data, never change a scoring rule without a spec update and version bump, never let the LLM affect scores, never call the network in tests, never add trade execution).

**`CLAUDE.md`** must contain: `@import AGENTS.md` as the first line; the memory model (which doc to read for what); a key entry points table (directory to purpose); the before-writing-any-code checklist; the PR checklist with runnable commands (`make check`, `make test`, `make coverage`, `scripts/check-versions.sh`); Claude-specific rules.

**`SKILLS.md`** must contain: a skills index table (name, directory, when to use); the skill format; how to add a skill; Pi skill loading notes.

**`.agent/skills/run-tests/`** and **`.agent/skills/check-types/`**: each with `SKILL.md` and `run.sh` (`make test` and `make check`).

**`SOUL.md`** must contain: identity (the agent maintains Super Trends, a source-available Serverless Ventures project, free for noncommercial use, that gives a trader a disciplined daily read from their own instance); what the project values (correct math over clever features, honesty about uncertainty, spec first, tests permanent, simplicity); at least eight hard constraints as NEVER rules (never overstate certainty, never pad picks, never hide losing picks, never let a model set a score, never introduce look-ahead, never store personal financial data, never add order execution, never commit secrets, vendor data, or cluster details to the public repository); what good work looks like; what to do when uncertain (literal reading, ADR, owner checklist); tone (plain, precise, calm). It must not contain build commands or file paths.

---

## Appendix K: docs/OWNER_CHECKLIST.md (seed)

Create this file in Step 1 with these entries, and append to it as you go. Each entry: status, what, why, exact command or URL, blocked task.

| # | Action | Blocks |
|---|---|---|
| 1 | Create DNS records for `supertrends.openstoke.com` and `supertrends-stage.openstoke.com` pointing at the private Stoke entry point chosen in the inventory (tailnet address or internal ingress). Do not expose the instance to the public internet | S8-T05 hostname, S9-T07 |
| 2 | Create a Massive (formerly Polygon.io) account and API key on a plan whose terms and rate limits fit personal use of daily and 5-minute bars and financials; confirm display terms | S8-T05 real-provider run |
| 3 | Export two TradingView daily charts with the built-in Supertrend (10, 3) and the Ripster EMA Clouds indicator (default settings) as CSV into `tests/golden/tradingview/` | S2-T02 and S2-T10 parity, release |
| 4 | Run `scripts/stoke-inventory.sh` with the Stoke kubeconfig ; the output stays in git-ignored `private/` and is never committed | S8-T02 |
| 5 | Create the `supertrends-stage` and `supertrends` namespaces' Secrets on Stoke (commands in Build and Deployment) | S8-T05, S9-T07 |
| 6 | After the first publish, set the GHCR image and chart packages to public, and confirm fork PR approval, secret scanning, and private vulnerability reporting are on in repo settings | S8-T05 |
| 7 | Merge the Super Trends overlay pull request in the Stoke GitOps repository | S8-T05, S9-T07 |
| 8 | Approve the `staging` to `main` pull request for v1.0.0 | S9-T06 |
| 9 | Review the first real-provider run on staging and the narrative evaluation result | S9-T06 |
| 10 | Before sharing Super Trends or its picks with anyone else, or charging for them, consult a securities lawyer | any sharing feature |
| 11 | Have a lawyer review `CLA.md` before accepting the first outside contribution | merging outside PRs |
| 12 | Have a lawyer confirm the license choice (PolyForm Noncommercial 1.0.0) and `COMMERCIAL.md` before the repository is announced | public announcement |
| 13 | Review the `needs_review` and `unresolved` watchlist symbols (SQ, CITI, 000660, VIX, XIACF, KRKNF, XIC, VCX, CBRS, SPLG, CFLT) and confirm or replace each | those symbols being scored |

---

## Appendix L: Watchlist Seed (from the owner's TradingView watchlists)

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
