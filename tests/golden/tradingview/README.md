# TradingView parity exports

The owner places TradingView CSV exports here (owner checklist item 3 in
`docs/OWNER_CHECKLIST.md`; policy in `docs/TEST_PLAN.md` sections 1.1 and 5). Until at least one
`*.csv` exists, `tests/golden/test_tradingview_parity.py` is skipped with the reason
"TradingView export not yet provided (owner checklist item open)" (TS-IND-021, TS-IND-022).

## How to export

Daily chart, two tickers, add the built-in Supertrend (ATR length 10, factor 3), then
"Export chart data". Export enough history for more than 100 bars after the first bar.

## Columns

TradingView writes `time, open, high, low, close, Volume, ...` followed by the indicator plots.
The parser (`tests/golden/tradingview_support.py`) lowercases header names and accepts either
variant:

1. `Up Trend` and `Down Trend` (the built-in indicator's plots). On each bar exactly one is
   filled and the other is empty or NaN; the filled one gives the line, and Up Trend means up.
2. `Supertrend` plus `Direction` (a TradingView-sign direction: negative is up, positive is
   down). Converted only by `tv_direction_to_internal`.

The test compares our line within 0.01 and our direction exactly on every bar after the first
100 bars. Other columns are ignored.
