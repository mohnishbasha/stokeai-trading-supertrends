# Super Trends Design System and Screen Specification

Version: 1.0.0
Date: 2026-11-14
Status: Seeded from the Design System section of BUILD_PROMPT.md. Contrast ratios were computed against the token values below (WCAG 2.2 relative luminance formula). Where a token from the seed failed AA, it was adjusted and the change is recorded in section 2.4.

Super Trends is source-available software, free for noncommercial use. Copyright Serverless Ventures LLC. Noncommercial use only.

---

## 1. Principles

The feel is a calm trading terminal. Dense where data is dense, quiet everywhere else. The dark theme is the default.

1. **End of day, not live.** Super Trends is an end-of-day product. Every number carries its as-of date. Nothing pulses, ticks, or pretends to stream.
2. **The Today screen is the product.** Three buy cards and two sell cards, readable in under 30 seconds (US-002). Every other screen supports it.
3. **Honest by layout.** Confidence, the invalidation level, the "estimated order flow" label, and the disclaimer are part of the card, not hidden behind a click. Misses are as visible as hits.
4. **Never pad.** If fewer than 3 buys or 2 sells qualify, fewer cards are shown, with the nearest candidate and the reason it missed.
5. **No color-only meaning.** Every direction pairs color with a word and a shape.
6. **Data refreshes in place.** No layout shifts when data loads or refreshes. Skeletons reserve the final size.
7. **Reading is not modal.** Content is read in the page. Modals are used only to confirm destructive or token-gated actions.
8. **Plain language.** No hype words, no certainty language about markets, no em dashes in UI copy.
9. **Estimates are labeled as estimates.** Buy and sell volume is "estimated order flow". Backtests are "hypothetical". Samples under 20 are "small sample".
10. **No secret is ever rendered.** The API token is entered, held in memory, and never echoed back.

---

## 2. Color tokens

Both themes are defined as CSS custom properties on `:root[data-theme="dark"]` and `:root[data-theme="light"]`. Dark is the default. The theme choice is stored in UI state (Zustand) and persisted per browser. If the user has not chosen, the theme follows `prefers-color-scheme`, falling back to dark.

### 2.1 Dark theme (default)

Contrast is computed against the stated background. "Text AA" requires 4.5:1 for body text, "UI AA" requires 3:1 for non-text components and large text (WCAG 1.4.11, 1.4.3).

| Token | Value | Usage | Contrast vs --bg-0 / --bg-1 / --bg-2 / --bg-3 | Result |
|---|---|---|---|---|
| `--bg-0` | `#0B0E13` | App background | n/a | n/a |
| `--bg-1` | `#121722` | Cards | 1.1 vs --bg-0 (surface step only) | decorative |
| `--bg-2` | `#1A2130` | Raised, hover | surface step | decorative |
| `--bg-3` | `#242D40` | Inputs, selected | 1.3 vs --bg-1 (surface step) | decorative |
| `--line` | `#2A3347` | Borders, grid | 1.53 vs --bg-0 | decorative only, see 2.5 |
| `--text-0` | `#E8ECF3` | Primary text | 16.31 / 15.13 / 13.59 / 11.63 | Text AA pass (AAA) |
| `--text-1` | `#A9B3C6` | Secondary text | 9.16 / 8.49 / 7.63 / 6.53 | Text AA pass (AAA at most) |
| `--text-2` | `#818CA2` (seed `#6E7A91`) | Tertiary text, axis labels | 5.71 / 5.30 / 4.76 / 4.07 | Text AA pass on bg-0, bg-1, bg-2. Not allowed on --bg-3 |
| `--up` | `#2FBF8F` | Bullish text, ribbon, candles | 8.26 / 7.66 / 6.88 / 5.88 | Text AA pass on all |
| `--up-soft` | `#153A30` | Bullish tint (dial third, badge fill) | `--up` on it: 5.34; `--text-0` on it: 10.55 | Text AA pass |
| `--down` | `#F16773` (seed `#F0616D`) | Bearish text, ribbon, candles | 6.38 / 5.91 / 5.31 / 4.54 | Text AA pass on all |
| `--down-soft` | `#45202A` | Bearish tint | `--down` on it: 4.64; `--text-0` on it: 11.87 | Text AA pass |
| `--neutral` | `#8A94A8` | Neutral state, S/R lines | 6.33 / 5.88 / 5.28 / 4.51 | Text AA pass on all |
| `--accent` | `#E0A93B` | Saffron: direction needle, focus, links, SMA 200 | 9.12 / 8.46 / 7.60 / 6.50 | Text AA pass |
| `--accent-soft` | `#3D3118` | Accent tint (event risk chip fill) | `--accent` on it: 6.00; `--text-0` on it: 10.74 | Text AA pass |
| `--warn` | `#E0A93B` | Warnings, stale banner border | same as --accent | Text AA pass |
| `--info` | `#5B9BF0` | Informational, SMA 20 | 6.80 / 6.31 / 5.67 / 4.85 | Text AA pass |
| `--focus` | `#E0A93B` | Focus ring | 9.12 vs --bg-0, 8.46 vs --bg-1, 7.60 vs --bg-2 | UI AA pass (3:1 needed) |

### 2.2 Light theme

| Token | Value | Usage | Contrast vs --bg-0 / --bg-1 / --bg-2 / --bg-3 | Result |
|---|---|---|---|---|
| `--bg-0` | `#F6F7F9` | App background | n/a | n/a |
| `--bg-1` | `#FFFFFF` | Cards | surface step | decorative |
| `--bg-2` | `#EEF1F5` | Raised, hover | surface step | decorative |
| `--bg-3` | `#E3E8EF` | Inputs, selected | surface step | decorative |
| `--line` | `#D5DBE5` | Borders, grid | 1.30 vs --bg-0 | decorative only, see 2.5 |
| `--text-0` | `#121722` | Primary text | 16.72 / 17.93 / 15.82 / 14.56 | Text AA pass (AAA) |
| `--text-1` | `#45506A` | Secondary text | 7.51 / 8.05 / 7.11 / 6.54 | Text AA pass (AAA at most) |
| `--text-2` | `#5E687B` (seed `#6E7A91`) | Tertiary text, axis labels | 5.24 / 5.61 / 4.95 / 4.56 | Text AA pass on all |
| `--up` | `#0C7755` (seed `#0E8A63`) | Bullish text, ribbon, candles | 5.18 / 5.55 / 4.90 / 4.51 | Text AA pass on all |
| `--up-soft` | `#DDF3EB` | Bullish tint | `--up` on it: 4.78; `--text-0` on it: 15.45 | Text AA pass |
| `--down` | `#BF3242` (seed `#C93545`) | Bearish text, ribbon, candles | 5.22 / 5.60 / 4.94 / 4.55 | Text AA pass on all |
| `--down-soft` | `#FBE3E6` | Bearish tint | `--down` on it: 4.60; `--text-0` on it: 14.71 | Text AA pass |
| `--neutral` | `#5E687B` (seed `#6E7A91`) | Neutral state, S/R lines | 5.24 / 5.61 / 4.95 / 4.56 | Text AA pass on all |
| `--accent` | `#8B5F0C` (seed `#A8730F`) | Saffron: direction needle, focus, links, SMA 200 | 5.24 / 5.61 / 4.96 / 4.56 | Text AA pass |
| `--accent-soft` | `#F6EBD3` | Accent tint | `--accent` on it: 4.74; `--text-0` on it: 15.15 | Text AA pass |
| `--warn` | `#8B5F0C` (seed `#A8730F`) | Warnings | same as --accent | Text AA pass |
| `--info` | `#2A64C2` (seed `#2D6CD1`) | Informational, SMA 20 | 5.29 / 5.68 / 5.01 / 4.61 | Text AA pass |
| `--focus` | `#8B5F0C` (seed `#A8730F`) | Focus ring | 5.24 vs --bg-0, 5.61 vs --bg-1, 4.96 vs --bg-2 | UI AA pass (3:1 needed) |

### 2.3 Token reference as CSS

```css
:root[data-theme="dark"] {
  --bg-0: #0B0E13;  --bg-1: #121722;  --bg-2: #1A2130;  --bg-3: #242D40;
  --line: #2A3347;
  --text-0: #E8ECF3;  --text-1: #A9B3C6;  --text-2: #818CA2;
  --up: #2FBF8F;    --up-soft: #153A30;
  --down: #F16773;  --down-soft: #45202A;
  --neutral: #8A94A8;
  --accent: #E0A93B;  --accent-soft: #3D3118;
  --warn: #E0A93B;  --info: #5B9BF0;  --focus: #E0A93B;
}
:root[data-theme="light"] {
  --bg-0: #F6F7F9;  --bg-1: #FFFFFF;  --bg-2: #EEF1F5;  --bg-3: #E3E8EF;
  --line: #D5DBE5;
  --text-0: #121722;  --text-1: #45506A;  --text-2: #5E687B;
  --up: #0C7755;    --up-soft: #DDF3EB;
  --down: #BF3242;  --down-soft: #FBE3E6;
  --neutral: #5E687B;
  --accent: #8B5F0C;  --accent-soft: #F6EBD3;
  --warn: #8B5F0C;  --info: #2A64C2;  --focus: #8B5F0C;
}
```

### 2.4 Recorded adjustments to the seed values

The seed required every text and background pair to meet AA and any failing value to be adjusted and recorded. Pairs that failed in the seed, and the change made. Each change is the smallest shift (toward white in dark, toward black in light) that clears 4.5:1 on every surface the token is allowed on.

| Theme | Token | Seed | Adopted | Seed failure | Result after change |
|---|---|---|---|---|---|
| dark | `--text-2` | `#6E7A91` | `#818CA2` | 4.47 on --bg-0, 4.15 on --bg-1, 3.72 on --bg-2 | 5.71 / 5.30 / 4.76 |
| dark | `--down` | `#F0616D` | `#F16773` | 4.35 on --bg-3; 4.44 on --down-soft | 4.54 on --bg-3; 4.64 on --down-soft |
| light | `--text-2` | `#6E7A91` | `#5E687B` | 4.03 on --bg-0, 4.32 on --bg-1, 3.82 on --bg-2 | 5.24 / 5.61 / 4.95 |
| light | `--neutral` | `#6E7A91` | `#5E687B` | same as --text-2 | same as --text-2 |
| light | `--up` | `#0E8A63` | `#0C7755` | 4.05 on --bg-0, 4.34 on --bg-1, 3.74 on --up-soft | 5.18 / 5.55 / 4.78 |
| light | `--down` | `#C93545` | `#BF3242` | 4.18 on --bg-3 | 4.55 on --bg-3 |
| light | `--accent`, `--warn`, `--focus` | `#A8730F` | `#8B5F0C` | 3.82 on --bg-0, 4.10 on --bg-1, 3.46 on --accent-soft | 5.24 / 5.61 / 4.74 |
| light | `--info` | `#2D6CD1` | `#2A64C2` | 4.08 on --bg-3 | 4.61 on --bg-3 |

Unchanged seed values that already pass: dark `--up`, `--neutral`, `--accent`, `--info`; all `--text-0` and `--text-1` in both themes.

The automated axe check (S4-T01) must keep passing in both themes. If a future token change fails any pair in sections 2.1 or 2.2, the change is recorded in this table.

### 2.5 Color rules

- `--line` is decorative (card borders, grid lines). It does not meet 3:1 and must never be the only boundary of an interactive control. Inputs, selects, and toggles use a 1 px border in `--text-2` (at least 4.07:1 in dark on --bg-3, 4.56:1 in light on --bg-3) so the control boundary meets WCAG 1.4.11.
- `--text-2` is not allowed on `--bg-3` in the dark theme (4.07:1). Placeholder and helper text inside inputs uses `--text-1`.
- `--up` and `--down` differ from each other by hue only (about 1.3:1 in dark, about 1.0:1 in light). They are never the sole carrier of meaning. See section 7.
- `--accent` (saffron) is reserved for: the direction needle, focus rings, links, trend flip ticks, and the SMA 200 line. It is the only saffron shape on a pick card (the needle). Flip ticks on the ribbon and the focus ring are allowed because they are 1 px marks, not shapes.
- `--warn` shares the saffron value. A warning is always accompanied by an icon and a word, so it is not confused with the needle.
- Soft tints (`--up-soft`, `--down-soft`, `--accent-soft`) are fills only. Text on a soft fill uses `--text-0`, or the matching strong token where the table above shows 4.5:1 or better.
- No gradients on data (see section 12). Gradients are not used anywhere in the UI.

---

## 3. Typography

- **UI face:** `Inter`, falling back to the system sans stack: `Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`.
- **Number face:** `JetBrains Mono` with tabular figures (`font-variant-numeric: tabular-nums`), falling back to `ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`.
- Both faces are self-hosted in the image. No font CDN, no external font request (zero telemetry, CSP `connect-src 'self'`).
- **Scale (px):** 12, 13, 14 (body), 16, 20, 28, 40 (score).
- **Weights:** 400 body, 500 labels, 600 headings and scores. No weight above 600.
- **Mono rule:** all prices, scores, percentages, dates in tables, counts, and hashes use the mono face and tabular figures so columns align. Prose, labels, and ticker symbols in headings use the UI face. Ticker symbols inside tables use the mono face.

| Role | Face | Size | Weight | Line height | Color |
|---|---|---|---|---|---|
| Score (dial center) | mono | 40 | 600 | 44 | `--text-0` |
| Page title | UI | 28 | 600 | 34 | `--text-0` |
| Section heading | UI | 20 | 600 | 28 | `--text-0` |
| Card ticker | UI | 20 | 600 | 28 | `--text-0` |
| Card subhead, tab label | UI | 16 | 500 | 24 | `--text-0` |
| Body, narrative | UI | 14 | 400 | 22 | `--text-0` (narrative), `--text-1` (secondary) |
| Table cell number | mono | 14 | 400 | 20 | `--text-0` |
| Label, column header | UI | 13 | 500 | 18 | `--text-1` |
| Caption, axis label, as-of stamp | UI or mono | 12 | 400 | 16 | `--text-2` |
| Disclaimer | UI | 12 | 400 | 18 | `--text-1` |

Rules:
- Minimum text size is 12 px. The disclaimer and captions use 12 px but never smaller.
- Text must reflow and stay readable at 200 percent zoom and with user text spacing overrides (WCAG 1.4.4, 1.4.12). Layout uses `rem` for type and spacing in components; the pixel values above are at the default 16 px root.
- Line length for narratives is capped at 72 characters (`max-width: 72ch`).
- Sentence case for all labels and headings. No all-caps except the ticker symbol and the words "DEMO DATA" in the demo banner.
- No italics for emphasis. Emphasis is weight 500 or 600.

---

## 4. Spacing and layout

### 4.1 Spacing scale

4 px base: **4, 8, 12, 16, 24, 32, 48**. No other spacing values.

| Token | px | Typical use |
|---|---|---|
| `--s-1` | 4 | Icon to label gap, ribbon to caption gap |
| `--s-2` | 8 | Chip padding, inline gaps |
| `--s-3` | 12 | Row gaps inside a card |
| `--s-4` | 16 | Card padding, grid gap on phone |
| `--s-5` | 24 | Grid gap on desktop, section spacing |
| `--s-6` | 32 | Page gutters on desktop |
| `--s-7` | 48 | Page top and bottom padding, empty state padding |

### 4.2 Surfaces

- Card padding 16. Card radius 10. Border 1 px `--line`. Card background `--bg-1`.
- Raised or hover surface `--bg-2`. Selected row and inputs `--bg-3`.
- Chips and badges radius 6. Buttons radius 8. The ribbon cells have radius 0 so they read as a continuous strip.
- Shadows: none. Elevation is expressed with background steps and borders.

### 4.3 Grid and breakpoints

- Maximum content width 1440 px, centered. Page gutters 32 px at desktop, 24 px at tablet, 16 px at phone.
- 12-column grid at desktop with 24 px gap; 8 columns at tablet with 24 px gap; 4 columns at phone with 16 px gap.

| Name | Width | Layout |
|---|---|---|
| Desktop wide | 1200 px and up | Today: 3 buy cards on row 1, 2 sell cards on row 2. Ticker: chart plus right rail (chart 8 columns, rail 4). Tables full width. |
| Desktop | 960 to 1199 px | Same as wide. Ticker rail drops below the chart if the chart would be narrower than 640 px. |
| Tablet | 600 to 959 px | Today: 2 columns, buys first then sells; a lone last card spans the row. Ticker: single column, rail below chart. Tables scroll horizontally with a sticky first column. |
| Phone | below 600 px | Single column, buys first then sells. Tables become stacked row cards (see 4.5). Navigation becomes a bottom tab bar. |

### 4.4 Today screen grid

- Desktop: a 5-card grid. Row 1 holds the 3 buys, row 2 holds the 2 sells. Each row is introduced by a section heading ("Top buys", "Top sells") with the count shown, for example "Top buys (3 of 3)".
- A row with fewer than its maximum cards is not stretched. Cards keep the same width as in a full row; the remaining space holds the "no more qualifying" line (see 9.1).
- Narrow screens: single column, buys first, then sells.
- Card minimum width 320 px; card height is content-driven but the ribbon, dial, and score block are fixed-size so cards align across a row.

### 4.5 Phone behavior

- Navigation: a fixed bottom tab bar with 5 items (Today, Watchlist, Track record, Runs, Settings). Ticker is reached from cards and rows, with a Back control in the header.
- Touch targets are at least 44 by 44 CSS px (above the 24 px WCAG 2.2 minimum).
- Tables (Watchlist, Runs, Track Record outcomes) render each row as a stacked card: ticker and band on the first line, score and confidence on the second, the ribbon on the third, and secondary fields behind a "Details" disclosure inside the row.
- The ticker chart takes the full width at a fixed 4:3 aspect ratio; sub-panels (MACD, RSI, volume) are collapsed by default and opened with toggles. Pinch zoom on the page is never disabled.
- The disclaimer stays visible: it is shown in full at the bottom of the Today screen and a short form ("Not investment advice. Algorithm output can be wrong. Details below.") is pinned in the sticky header region only when the full text is out of view. The full text is always one scroll away and never behind a modal.
- Landscape and portrait both work; no horizontal page scroll at 320 px width.

---

## 5. Signature element: the trend ribbon and the direction needle

Two linked elements give every pick a recognizable, honest, glanceable shape. Both are drawn as inline SVG (no canvas, no images) so they scale, theme, and print.

### 5.1 Trend ribbon

**What it shows.** The daily Supertrend direction for each of the last 60 sessions, so a reader sees how long the current trend has run and how choppy the ticker has been.

**Geometry.**
- A strip 6 px tall and the full width of its container.
- 60 equal-width cells, one per session, oldest on the left, most recent on the right. Cells have no gaps and no rounding.
- Data source: the `ribbon` string in the recommendation payload, one character per session: `U` for an up Supertrend day, `D` for a down day. The string is ordered oldest to newest. If fewer than 60 characters are returned (the ticker has less history), the missing cells on the left are drawn empty (`--bg-3`, no fill) and the text alternative reports the actual count.

**Color and non-color encoding.**
- An up cell is filled `--up` and is the full 6 px tall. A down cell is filled `--down` and is 3 px tall, aligned to the bottom edge of the strip, above a transparent top half. This height difference carries direction in grayscale and for color-blind readers. (This is an addition to the seed, which specified color only. It satisfies the rule that color is never the sole signal.)
- A flip point is a day whose direction differs from the previous day. It is marked by a 1 px `--accent` vertical tick, 10 px tall, centered on the boundary between the two cells and extending 2 px above and 2 px below the strip.
- The most recent cell has a 1 px `--text-0` outline so the reader sees where "today" is.

**Where it appears.** On every pick card, on every watchlist row, and on the Ticker header. Never more than one ribbon per row or card.

**Behavior.**
- Static. It does not animate on load, on hover, or on refresh.
- Hover or focus on a cell shows a tooltip with the date and direction ("2026-11-05, Supertrend up"). The ribbon is focusable (`tabindex="0"`); when focused, Left and Right arrow keys move a cell cursor and the tooltip text is announced through an `aria-live="polite"` region.
- On phone, tap a cell to show the same tooltip text beneath the ribbon.

**Text alternative.** The ribbon has `role="img"` and an `aria-label` generated from the string, in this form: "Up 14 sessions, flipped 3 sessions ago". Generation rules:
- Current run: the direction of the last character and the count of consecutive identical characters at the end. "Up 14 sessions" or "Down 6 sessions".
- Flip clause: "flipped N sessions ago" where N is `bars_since_flip` from the API (N is 1 for the most recent flip day when the last character differs from the one before it). If there is no flip within the 60 sessions, use "no flip in the last 60 sessions".
- Choppiness clause: append ", N flips in 60 sessions" when N is 3 or more.
- Singular: "1 session".
- Example full label: "Up 14 sessions, flipped 3 sessions ago, 4 flips in 60 sessions".

The visible caption under the ribbon on cards reads "Supertrend up, flipped 3 bars ago" so the information is also plain text for everyone.

### 5.2 Direction needle (ScoreDial)

**What it shows.** The display score from 0 to 100, with its band.

**Geometry.**
- A half-circle gauge (180 degrees, opening downward, flat edge at the bottom), 160 px wide and 88 px tall at default size. A compact variant 96 px wide is used in table rows only if a dial is needed there (the Watchlist uses a numeric score instead; see 9.3).
- Scale: 0 at the far left, 100 at the far right, 50 at the top.
- The left third (0 to 33.3) is tinted `--down-soft`. The right third (66.7 to 100) is tinted `--up-soft`. The middle third has no tint (`--bg-1`). The arc track has a 1 px `--line` outline.
- Small band tick marks at 20, 35, 50, 65, 80 (the band boundaries) drawn in `--text-2` as 4 px ticks, with no labels except "0", "50", "100" in 12 px `--text-2`.
- The numeric score sits below the needle pivot, centered, in the mono face at 40 px, weight 600, `--text-0`, with one decimal (for example "78.4").
- Beneath the number, the band name in 13 px weight 500 `--text-1` (for example "Buy").
- The needle is a 2 px line from the pivot to 4 px inside the arc, `--accent`, with a 6 px `--accent` circular hub. **The needle is the only saffron shape on a card.**

**Non-color encoding.** The left third carries a small down-pointing triangle glyph and the text "Sell" at its outer edge; the right third carries an up-pointing triangle and "Buy". The tints are reinforcement only.

**Behavior.**
- Needle angle is `-90 + (display / 100) * 180` degrees from vertical.
- Static on first paint (drawn at its final angle). When the displayed date changes, the needle rotates to the new angle over 200 ms with an ease-out. When `prefers-reduced-motion: reduce` is set, the needle jumps with no transition. No bounce, overshoot, or celebratory motion for any score.
- The dial has `role="img"` and an `aria-label`: "Score 78.4 out of 100, band Buy".
- Dial and ribbon never change their size when data refreshes.

### 5.3 How the two work together

The dial says how strong the combined evidence is today. The ribbon says how long the Supertrend has held and how often it has flipped. Together they answer "how strong, and how durable" without text. A card with a high score but a ribbon that shows many recent flips is visibly different from one with a long clean run.

---

## 6. Chart conventions

The Ticker screen uses `lightweight-charts` for the candlestick chart and its sub-panels. Charts are drawn on a canvas, so each chart needs a keyboard path and a data table alternative (section 11.5).

### 6.1 Series and overlays

| Element | Style | Color tokens | Default on first load |
|---|---|---|---|
| Candles | Up bodies `--up`, down bodies `--down`; wicks in the same color as the body. Same in light and dark themes. | `--up`, `--down` | On |
| Supertrend line | 2 px; `--up` when the line is below price, `--down` when above; a marker at each flip (up triangle for flip up, down triangle for flip down, 8 px) | `--up`, `--down` | On |
| SMA 20 | 1 px line | `--info` | Off |
| SMA 50 | 1 px line | `--text-1` | Off |
| SMA 200 | 1 px line | `--accent` | Off |
| Fibonacci levels | Dashed 1 px, right-edge labels (for example "61.8%  214.20") | `--text-2` | Off |
| Support | Solid 1 px; strength shown by opacity (0.35 weakest to 1.0 strongest) | `--neutral` | Off |
| Resistance | Solid 1 px; strength shown by opacity (0.35 to 1.0) | `--neutral` | Off |
| Invalidation level | Dashed 1 px with a "Invalidation" right-edge label, drawn only when the displayed date has a pick on this ticker | `--text-0` | On when present |
| Volume (sub-panel) | Bars; up and down split of estimated order flow drawn as stacked bars, labeled "estimated" | `--up`, `--down` | On |
| MACD (sub-panel) | MACD and signal lines 1 px (`--text-0`, `--text-1`); histogram bars `--up` above zero and `--down` below | per series | Off |
| RSI (sub-panel) | 1 px line `--text-0`, reference lines at 30 and 70 dashed `--text-2`; divergence markers as 8 px triangles with a text tooltip | per series | Off |

Rules:
- **Default overlays on first load:** candles, Supertrend line, volume sub-panel, and the invalidation level when present. Everything else is a toggle. Never more than the default overlays on first load.
- Toggle state persists per browser (local UI state), keyed by overlay id. A "Reset overlays" control returns to the defaults.
- Supertrend flip markers always carry a shape (triangle) in addition to the line color change, so flips do not rely on color.
- Support and resistance lines use opacity for strength, so each line also carries a right-edge label with the level and a strength word ("strong", "moderate", "weak").
- Every right-edge label is 12 px mono `--text-2` on a `--bg-1` plate for readability, with 4.5:1 contrast per section 2.
- Axis labels use `--text-2`. Gridlines use `--line` at 1 px. The crosshair is `--text-1`, dashed.
- Time axis shows trading sessions only (no gaps for weekends). The right edge is the as-of date; there is no live-updating last bar. The chart footer states "End-of-day data, as of 2026-11-13".
- Candles use daily bars by default. A timeframe control offers 1d and 1w (the API `tf` parameter). Intraday timeframes are not offered.
- The legend sits above the chart, one entry per visible series, each with a swatch, a line-style sample (solid or dashed), and the name. Legend entries are buttons that toggle the series (see OverlayToggles, section 8).
- The tooltip on hover or keyboard cursor shows: date, open, high, low, close, volume, Supertrend value and direction, and the value of each visible SMA. Numbers are mono.
- No gradients, no area fills under lines, no 3D, no pie charts anywhere. Track record uses bar charts and tables only.
- Equity curve (backtest only) is a 1.5 px line, strategy in `--text-0`, SPY in `--text-2` dashed, labeled "Hypothetical" in the chart title and watermark-free. It is never drawn without that label.
- Chart animation: none on load. Pan and zoom follow the pointer without easing. Reduced-motion has no additional effect because there is no ornamental motion.
- Charts keep their size while data refreshes. Overlay series are replaced in place.

### 6.2 Data table alternative

Each chart has a "View as table" control that renders the visible range as a real HTML table (date, open, high, low, close, volume, Supertrend value, direction, and each visible overlay), with a caption stating the date range and the as-of date. It is the accessible equivalent, not a hidden element.

---

## 7. Buy and sell without relying on color

Every buy or sell indication pairs color with a text label and a shape.

| Indication | Shape | Word | Color |
|---|---|---|---|
| Buy | Up triangle (filled) | "Buy" | `--up` |
| Sell | Down triangle (filled) | "Sell" | `--down` |
| Neutral | Horizontal bar (filled) | "Neutral" | `--neutral` |
| Supertrend up | Up triangle | "Up" | `--up` |
| Supertrend down | Down triangle | "Down" | `--down` |

Rules:
- The shape and the word appear together in the BuySellMark, the Badge, table cells, chart markers, and card headers. Color is reinforcement.
- Bands read as words: "Strong Buy", "Buy", "Neutral, leaning up", "Neutral, leaning down", "Sell", "Strong Sell". A band badge always includes the shape that matches its side. Neutral bands use the horizontal bar plus a small up or down chevron for "leaning".
- Ribbon: direction is carried by cell height (up full height, down half height) as well as color, plus the text alternative "Up 14 sessions, flipped 3 sessions ago".
- Buy cards and sell cards are in separate, headed sections ("Top buys", "Top sells"), so side is conveyed by position and heading as well.
- Factor bars (FactorBar): positive contributions extend to the right of a center axis and negative to the left; the sign is also printed ("+9.1", "-4.2"). Printed sign uses the ASCII hyphen-minus.
- Outcomes in Track Record: "Hit" or "Miss" in words, with a check shape or a cross shape, never color alone.
- Every screen must remain fully usable in a grayscale rendering. Playwright runs a grayscale screenshot check for Today (S4-T03 AC).
- The theme must pass a simulated deuteranopia and protanopia check for the ribbon and the buy and sell marks.

---

## 8. Component inventory

States key: **D** default, **H** hover, **F** focus, **X** disabled, **L** loading, **E** empty, **R** error, **S** stale. "n/a" means the state does not apply. Components 1 to 12 are the base set required by S4-T01; each has a component test for every listed state.

Global state rules:
- **Focus (F):** every interactive element shows a 2 px `--focus` outline with a 2 px offset, never removed, visible on every surface (3:1 or better, see section 2). Focus is shown for keyboard use (`:focus-visible`) and never clipped by overflow.
- **Hover (H):** a `--bg-2` surface step on rows and buttons; links gain an underline (links are always underlined). Hover never conveys information that is unavailable by focus.
- **Disabled (X):** `aria-disabled="true"` with reduced emphasis (`--text-2` text where allowed, on `--bg-0`, `--bg-1`, or `--bg-2`) and a visible reason in an adjacent hint or tooltip reachable by keyboard ("A run is already in progress"). Disabled is never expressed by opacity alone.
- **Loading (L):** Skeleton at the final size. No spinner that changes layout. After 400 ms a skeleton gains a text label for screen readers ("Loading").
- **Stale (S):** data older than the last completed session is shown with its as-of date and a StaleBanner. Stale data is not hidden; it is labeled.
- **Error (R):** ErrorState with the problem title from the RFC 9457 response, a plain sentence, and a Retry button. Never a blank area.

### 8.1 Base set

**C-01 Button**
- Purpose: trigger an action. Variants: primary (`--accent` fill, `--bg-0` text), secondary (`--bg-3` fill, `--text-0`), quiet (text only, underlined on hover), destructive-confirm (`--down` text and border, shape: a down-pointing caution glyph is not used; the label states the action).
- Props: `label`, `variant`, `onClick`, `disabled`, `loading`, `iconLeft`, `describedBy`.
- States: D filled by variant, 44 px min height on phone, 32 px on desktop; H one surface step; F focus ring; X `aria-disabled` plus hint; L label replaced by "Working" with the width preserved; E n/a; R n/a (errors are shown by the caller next to the button); S n/a.
- Primary button text `--bg-0` on `--accent` is 9.12:1 (dark) and, in light, `#FFFFFF` on `#8B5F0C` is 5.6:1 (verified by the axe check).

**C-02 Card**
- Purpose: grouping container for a pick, tile, or panel.
- Props: `as` (section, article, li), `heading`, `headingLevel`, `children`, `padding`.
- States: D `--bg-1`, 1 px `--line`, radius 10, padding 16; H n/a unless the card is a link, then `--bg-2`; F focus ring on the card when it is a link; X n/a; L skeleton variant of the same size; E renders EmptyState inside; R renders ErrorState inside; S shows StaleBanner strip at the top of the card.

**C-03 Badge**
- Purpose: short status text with a shape (band, side, regime, state).
- Props: `kind` (buy, sell, neutral, info, warn), `label`, `showShape`.
- States: D soft fill with matching shape and word (shape is mandatory for buy, sell, neutral); H, F n/a (not interactive; if interactive it is a Button); X n/a; L Skeleton pill; E n/a; R n/a; S n/a.
- Examples: up triangle "Strong Buy"; down triangle "Sell"; bar "Neutral, leaning up".

**C-04 ScoreDial**
- Purpose: show the display score as in section 5.2.
- Props: `score` (0 to 100, one decimal), `band`, `size`.
- States: D as specified; H n/a; F n/a (static, labeled by its parent card); X n/a; L Skeleton of the same size with an empty arc; E "Score unavailable" with an empty arc and no needle (used when a ticker is excluded); R n/a (the parent shows the error); S dimmed needle is not used; staleness is shown by the card's StaleBanner and the as-of stamp.

**C-05 TrendRibbon**
- Purpose: show 60 sessions of Supertrend direction as in section 5.1.
- Props: `ribbon` (string of `U` and `D`, oldest first), `barsSinceFlip`, `asOf`.
- States: D as specified; H per-cell tooltip; F ribbon is focusable, arrow keys move the cell cursor; X n/a; L Skeleton 6 px strip; E ribbon string shorter than 60: left cells drawn empty and the label states the real length; with an empty string: a 6 px `--bg-3` strip and the text "No trend history"; R n/a; S n/a (the date is in the as-of stamp).

**C-06 FactorBar**
- Purpose: one factor's contribution to the composite.
- Props: `factorId`, `label`, `contribution` (signed number), `score` (-100 to 100), `weight`, `quality` (ok, degraded, missing), `reasons` (list).
- Layout: label, a horizontal bar centered on a zero axis (positive right in `--up`, negative left in `--down`), the signed contribution in mono ("+23.4", "-4.2"), and an optional chevron to reveal the reasons list.
- States: D bar plus printed value; H row surface step and tooltip with score and weight; F the chevron button is focusable and toggles the reasons (disclosure, `aria-expanded`); X n/a; L Skeleton bar; E when `quality` is missing: label with "Not available" and an empty bar, and the weight shown as 0; R n/a; S n/a.
- Bars scale to the largest absolute contribution in the same card. A `degraded` quality adds a small "degraded" text tag. A negative bar has a hatch-free solid fill plus the printed minus sign.

**C-07 LevelList**
- Purpose: key price levels for a pick.
- Props: `support` (list), `resistance` (list), `fib` (map), `nextTarget`, `invalidation` ({level, rule}), `expected1dMove` (required on a pick).
- Layout: a compact two-column list. Invalidation first and emphasized: "Invalidation 212.40: daily close below the Supertrend line". Then "Expected 1-day move: plus or minus 4.10 (14-day ATR, an estimate from recent volatility, not a forecast)", shown on every pick card including on phone. Then "Next target 236.00", "Resistance 229.50, 236.00", "Support 215.10, 208.70", "Fib 61.8%: 214.20". Numbers in mono, two decimals.
- States: D as above; H n/a; F n/a (static list); X n/a; L Skeleton rows; E missing groups are omitted, not shown as zero; if there is no level data the list shows "No key levels computed"; R n/a; S n/a.

**C-08 DataQualityTag**
- Purpose: show data quality for a ticker or for estimated order flow.
- Props: `kind` (`order_flow` or `bars`), `level` (`intraday`, `daily_estimate`, `trades`, or `ok`, `degraded`, `stale`, `insufficient_history`).
- Wording: order flow tags read "Estimated order flow: intraday", "Estimated order flow: daily estimate" (weight multiplied by 0.6 is explained in the tooltip), "Estimated order flow: trades". Bars tags read "Data: ok", "Data: degraded", "Data: stale", "Data: insufficient history".
- States: D tag with an icon shape (circle for ok, triangle for degraded, square for stale and insufficient history) plus words; H tooltip with a one-sentence meaning; F focusable when it has a tooltip, with the tooltip text available via `aria-describedby`; X n/a; L Skeleton pill; E n/a; R n/a; S stale is its own level.
- The words "order flow" never appear without the word "estimated" next to them.

**C-09 Disclaimer**
- Purpose: show the compliance text. The exact text is in section 10.1.
- Props: `variant` (full, short), `payloadDisclaimer` (the text from the API payload).
- Behavior: the full variant renders the `disclaimer` string from the API payload verbatim, falling back to the compiled-in copy if the payload has none. The text is plain text, never collapsed behind a control, never in a tooltip.
- States: D 12 px `--text-1` on `--bg-0` or `--bg-1` inside a bordered block with an info icon; H, F n/a (the block is not interactive; the license link in the footer is); X n/a; L the text is static copy, never a skeleton, and renders immediately; E n/a; R n/a; S n/a.

**C-10 EmptyState**
- Purpose: explain an empty list or missing result and offer the next step.
- Props: `title`, `body`, `action` (optional Button), `icon`.
- States: D centered block with a 48 px padding, a neutral icon, a title (16 px, 500), a body sentence (14 px, `--text-1`), and an optional action; H, F as for its Button; X n/a; L n/a; E this is the empty state; R n/a; S n/a.
- Empty states are quiet: no illustration beyond a simple icon, no cheerfulness.

**C-11 ErrorState**
- Purpose: render a failed request.
- Props: `title`, `detail` (problem detail from RFC 9457, plain text), `status`, `requestId`, `onRetry`.
- States: D warning icon, title, detail, "Request ID: ..." in mono 12 px, and a Retry button; H, F as for Button; X Retry is disabled with a visible "Retrying" label while in flight; L n/a; E n/a; R this is the error state; S n/a.
- Rules: renders in the same region as the failed content with the same minimum height; a 500 never produces a blank screen (S4-T02 AC). The text is plain text and never exposes stack traces, secrets, or internal hostnames.

**C-12 Skeleton**
- Purpose: reserve space while loading.
- Props: `shape` (line, block, pill, dial, ribbon, table-row), `width`, `height`, `label`.
- States: D `--bg-2` block with no shimmer when `prefers-reduced-motion: reduce`; otherwise a 1.2 s opacity pulse between 0.6 and 1.0 (no gradient sweep); L this is the loading state; others n/a.
- Rules: skeleton dimensions equal the final content dimensions so nothing shifts when data arrives. The container has `aria-busy="true"` while any skeleton is shown.

### 8.2 Shell and page-level components

**C-13 AppShell**
- Purpose: header, primary navigation, content region, footer.
- Props: `route`, `theme`, `demo` (boolean).
- Layout: header with the product name, primary navigation (Today, Watchlist, Track record, Runs, Settings) as links (desktop: top bar; phone: bottom tab bar), the ThemeToggle, and the AsOfStamp. A "Skip to main content" link is the first focusable element. Footer carries the license notice "Copyright Serverless Ventures LLC. Noncommercial use only." with a link to the license (`SUPERTRENDS_SOURCE_URL`), the app version, and the text "Software for running your own analysis. No signals service. Each user needs their own market data license."
- States: D; H nav items surface step; F focus ring; the current page link has `aria-current="page"` plus a 2 px `--accent` underline; X n/a; L the shell renders immediately and never waits on data; E n/a; R n/a; S n/a (the StaleBanner is a child of the page).

**C-14 AsOfStamp**
- Purpose: state the data date everywhere a number appears.
- Props: `date` (trade date), `publishedAt`, `runId`.
- Copy: "As of 2026-11-13 close. Published 2026-11-13 22:34 UTC." Dates are ISO format in mono. Times show the local time zone abbreviation with the UTC value available in the tooltip.
- States: D; H tooltip with run ID and config hash; F focusable when the tooltip exists; X n/a; L Skeleton line; E "No published run"; R "As-of date unavailable"; S the stamp turns to `--warn` text with a warning icon and reads "As of 2026-11-12 close (one session behind)".

**C-15 StaleBanner**
- Purpose: a persistent, in-flow notice that the page shows data older than the latest completed session or that the latest run is missing, failed, or running.
- Props: `kind` (`behind`, `run_failed`, `run_in_progress`, `provider_degraded`, `llm_down`), `asOf` (payload `date`), `latestCompletedSession` (`/api/v1/status` field `last_completed_session`), `detail`. The kind is derived from `/api/v1/status` fields as stated in section 9 ("Data layer rules common to all screens").
- Layout: a bordered strip (1 px `--warn`, `--accent-soft` fill) with an icon, a bold lead sentence, and one detail sentence. It sits above the page content and pushes it down only on first render of the page (reserved space is not used; the banner is part of the initial layout and does not appear after paint). If the banner is added by a later refresh, it appears in a reserved 56 px slot that exists on all pages, so nothing shifts.
- Copy by kind: see 9.x screens and 10.4.
- States: D; H n/a; F link inside the banner is focusable; X n/a; L the slot shows nothing while the status request is loading; E n/a; R if status cannot be loaded: "Data freshness unknown. The status service did not answer." with a Retry link; S this is the stale component.
- Announced to assistive technology with `role="status"` (polite).

**C-16 DemoBanner**
- Purpose: label demo mode (`SUPERTRENDS_DEMO=1`).
- Copy: "DEMO DATA: synthetic prices, not real markets". Persistent on every route in demo mode, absent otherwise. Sticky at the top, 32 px tall, `--accent-soft` fill, `--text-0` text. Not dismissible.
- States: D only; others n/a.

**C-17 ThemeToggle**
- Purpose: switch between dark and light.
- Props: `theme` (dark, light, system).
- Control: a three-option segmented control (Dark, Light, System) with a visible text label in Settings and an icon button in the header that cycles the choice with an `aria-label` of "Theme: dark. Activate to switch to light."
- States: D; H surface step; F focus ring; X n/a; L n/a (local state); E n/a; R n/a; S n/a.

**C-18 BuySellMark**
- Purpose: the shape plus word for a side (section 7).
- Props: `side` (buy, sell, neutral), `size`, `label` (optional override such as "Strong Buy").
- States: D shape plus word in the side color; others n/a. The component never renders color without the shape and word.

**C-19 PickCard**
- Purpose: the core unit of the product. One buy or sell pick on the Today screen.
- Data (from `GET /api/v1/recommendations/latest`, `buys[]` or `sells[]`, enriched by the analysis endpoint when a detail is expanded): `rank`, `ticker`, `side`, `display_score`, `band`, `confidence`, `supertrend` (`dir_d`, `dir_w`, `bars_since_flip`, `line`), `regime`, `flags`, `days_on_list`, `invalidation`, `expected_1d_move` (always present, always rendered), `top_factors`, `narrative` (`text`, `source`, `model`), `ribbon`, watchlist groups.
- Layout (top to bottom): 1) header row: rank number, ticker (20 px), company or ETF name if available (13 px `--text-1`), BuySellMark with the band; 2) ScoreDial at left with Confidence beside it ("Confidence 71 of 100" and a short bar); 3) TrendRibbon with the caption "Supertrend up (daily), up (weekly), flipped 3 bars ago"; 4) "Day 1 on the list" (or "Day N on the list"); 5) factor contribution breakdown: top 3 FactorBars (the `top_factors`, the two largest positive and the largest opposing factor when known), with a "Show all 11 factors" disclosure that expands the full list in place (not a modal); 6) NarrativeBlock; 7) LevelList with the invalidation level first; 8) flags row: FlagChip for event risk, DataQualityTag for estimated order flow, regime chip ("Trending", "Ranging", "Transitional"), watchlist group chips; 9) footer: "Details" link to `/ticker/:symbol?date=...`. The Disclaimer is page-level on Today (section 10), not repeated in every card.
- Interactions: the whole card is not a link. The ticker symbol and the "Details" link navigate to the Ticker screen. The factor disclosure is a button with `aria-expanded`. Expand state persists in session UI state only.
- States: D as above; H subtle `--bg-2` on header row only; F each interactive child shows focus; X n/a; L a card-shaped skeleton with all blocks at final size; E not applicable per card (an empty side uses NearestMissLine); R the card is replaced in place by ErrorState if the whole recommendations call fails (not per card); S a stale strip at the top of the card when its data date is behind ("Data for this pick is one session old").
- Reading order in the DOM follows the visual order: header, score, ribbon, factors, narrative, levels, flags.

**C-20 NarrativeBlock**
- Purpose: show the written justification (3 to 5 sentences) and its source.
- Props: `text`, `source` (`llm` or `template`), `model`.
- Behavior: rendered as plain text, never as HTML or Markdown, never with links. The source label sits under the text at 12 px `--text-2`: "Written by a language model (model-name) from the computed evidence" or "Template text (the language model was unavailable or its draft was rejected)".
- States: D; H n/a; F n/a; X n/a; L three Skeleton lines; E "No narrative stored for this pick" (should not occur for a published pick); R n/a; S n/a.
- When `source` is `template`, a small "Template" Badge with an info icon is shown beside the label.

**C-21 FlagChip**
- Purpose: show a risk flag.
- Props: `flag` (`event_risk` and any future flag), `detail` (for example the earnings date).
- Copy: "Event risk: earnings in 3 trading days" with a warning triangle glyph, `--accent-soft` fill, `--text-0` text. Other flags use a neutral chip with the flag name in words.
- States: D; H tooltip with detail; F focusable when it has a tooltip; X n/a; L n/a (arrives with the card); E not rendered when there are no flags; R n/a; S n/a.

**C-22 NearestMissLine**
- Purpose: when a side has fewer than its maximum picks, show the nearest candidate and why it missed.
- Props: `side`, `ticker`, `display_score`, `reason`, `count` (how many picks are shown), `max`.
- Copy: for an empty side: "No qualifying sells today." then "Nearest candidate: XYZ, score 37.2. Reason: score above the sell threshold of 35." For a partial side: "No more qualifying buys today. Showing 1 of 3." then the nearest-miss line.
- States: D; H n/a; F the ticker is a link to the Ticker screen; X n/a; L Skeleton line; E when there is no nearest candidate at all: "No candidate came close. Every ticker on the watchlist was excluded or scored far from the threshold."; R n/a; S n/a.

**C-23 AlsoQualified**
- Purpose: list tickers that qualified but were skipped by the correlation guard, with the pick each duplicates.
- Props: `items` ({ticker, display_score, duplicates, correlation}), `side`.
- Copy: "Also qualified (skipped as near-duplicates): QQQM, score 74.1, duplicates QQQ (60-day correlation 0.97)". Rendered as a collapsed-by-default list under each side with the count in the summary ("Also qualified (2)"), using a disclosure (not a modal).
- States: D; H row surface step; F ticker links and the disclosure; X n/a; L Skeleton line; E not rendered when empty; R n/a; S n/a.

**C-24 GroupChips and GroupFilter**
- Purpose: show a ticker's watchlist groups and filter by group.
- Props (GroupFilter): `groups`, `selected`, `onChange`.
- Behavior on Today: an optional filter above the cards, "Group: All, semis, fab-7, country-etfs, ...". Selecting a group re-ranks within that group and shows a persistent note "Showing a group view. Published picks for all tickers are unchanged." with a "Show published picks" button. The published overall picks are never altered.
- States: D "All" selected; H surface step; F segmented control or listbox with arrow-key support; X n/a; L Skeleton chips; E "No groups yet. Add a group on the Watchlist screen."; R chips not shown, filter hidden, ErrorState not needed (the page still works); S n/a.

**C-25 DateNavigator**
- Purpose: browse any past date (US-012).
- Props: `date`, `min`, `max`, `onChange`.
- Controls: previous trading day, a date field (typed ISO date, with a calendar picker), next trading day, and "Latest". Dates that are not trading dates are rejected with an inline message ("2026-11-14 is not a trading date. Closest earlier trading date: 2026-11-13."). Route: `/date/:yyyy-mm-dd`.
- States: D; H surface step; F focus ring on each control; X "Next" disabled at the latest date with a hint, "Previous" disabled at the earliest stored date; L controls render immediately; E when there is no stored run for the date, the page shows EmptyState (see 9.1); R invalid date format shows an inline field error; S n/a.
- A past-date view carries a banner "Historical view: exactly what was published on 2026-10-02, with config version 1 (sha256:abc...)". The banner is informational, not a warning.

**C-26 PriceChart**
- Purpose: the Ticker screen candlestick chart with overlays and sub-panels (section 6).
- Props: `bars`, `overlays` (Supertrend, SMAs, fib, support and resistance), `invalidation`, `tf`, `visible` (overlay ids), `onVisibleChange`.
- States: D defaults per 6.1; H crosshair and tooltip; F the chart region is focusable; Left and Right move the cursor one session, Shift plus Left or Right moves 5 sessions, Home and End jump to ends, the tooltip text is mirrored in an `aria-live="polite"` region; X n/a; L Skeleton block at the final chart height; E "No price history for this ticker"; R ErrorState inside the chart region keeping its height; S the footer line turns `--warn` and the chart title reads "Data is one session behind".

**C-27 ChartLegend and OverlayToggles**
- Purpose: legend entries that also toggle overlays.
- Props: `series` (id, name, style, color, visible), `onToggle`.
- Behavior: each entry is a toggle button (`aria-pressed`) with a swatch, a line-style sample, and the name. A "Reset overlays" quiet button restores defaults. Overlay and sub-panel state persists per browser.
- States: D; H surface step; F focus ring; X an overlay with no data (for example SMA 200 with fewer than 200 bars) is `aria-disabled` with the hint "Needs 200 sessions of history"; L Skeleton chips; E n/a; R n/a; S n/a.

**C-28 ChartDataTable**
- Purpose: accessible table alternative for the chart (6.2).
- Props: `rows`, `columns`, `caption`.
- States: D a standard table with a caption and sticky header, scrollable, newest row first; H row surface step; F the scroll region is focusable; X n/a; L Skeleton rows; E "No rows in this range"; R ErrorState; S caption includes "End-of-day data, as of ...".

**C-29 FactorTable**
- Purpose: full factor table on the Ticker right rail.
- Props: `factors` (id, label, score, weight, contribution, quality, reasons).
- Columns: Factor, Score (-100 to 100), Weight, Contribution, Quality, Reasons (expand). A footer row shows "Composite" and "Display score". All 11 factors are always listed, including ones with quality `missing` ("Not available", weight shown as 0). Contributions sum to the composite and the footer states it.
- States: D; H row surface step; F reasons disclosure per row; X n/a; L Skeleton rows; E "No factor data for this date"; R ErrorState; S as-of stamp in the caption.

**C-30 RegimePanel**
- Purpose: show the ticker regime, market regime, and the adjustments that fired.
- Props: `regime` (trending, ranging, transitional), `marketRegime` (risk_on and others), `adjustments` (list of strings), `weights` (base and adjusted).
- Copy: "Weights adjusted: trending regime, earnings in 3 days". If none: "No weight adjustments fired."
- States: D; H n/a; F disclosure for the base-versus-adjusted weights table; X n/a; L Skeleton; E "No regime data for this date"; R ErrorState; S n/a.

**C-31 FundamentalsSummary**
- Purpose: fundamentals overlay summary on the Ticker right rail.
- Props: `summary` (sub-scores and key metrics), `quality`, `knownAt`.
- States: D; H n/a; F n/a; X n/a; L Skeleton; E for ETFs and tickers with quality `missing`: "No fundamentals for this ticker. Its weight was redistributed across the other factors."; R ErrorState; S when fundamentals are older than 120 days: "Fundamentals are older than 120 days (known since 2026-06-30). Their weight is halved."

**C-32 ScoreHistory**
- Purpose: show this ticker's scores and pick appearances over time (`/history`).
- Props: `points` (date, display_score, band, picked side or none).
- Rendering: a table by default (date, score, band, "Pick: buy day N" or "Not picked") with an optional line chart of display score using 1.5 px `--text-0` and 50 as a dashed reference line. Pick days carry shape markers (up or down triangle).
- States: D; H row surface step; F rows and chart cursor keyboard reachable; X n/a; L Skeleton; E "This ticker has no stored scores yet"; R ErrorState; S as-of stamp.

**C-33 RankingTable**
- Purpose: the sortable ranked watchlist (US-006).
- Props: `rows` (rank, ticker, display_score, band, confidence, supertrend dir and age, regime, relative volume, data quality, ribbon, groups), `sort`, `onSort`, `date`.
- Columns: Rank, Ticker, Score, Band, Confidence, Supertrend (direction shape, word, and bars since flip), Ribbon, Regime, Rel. volume, Data quality, Groups. Excluded tickers appear in a separate "Excluded" section below the table with their reason.
- Behavior: column headers are buttons with `aria-sort`; sorting is stable (ties keep the prior order, then alphabetical); sort state is local UI state. Rows that are published picks carry a "Pick: buy" or "Pick: sell" Badge. Pagination or "Load more" is bounded (`limit` and `offset`, default 50 rows).
- States: D; H row surface step; F each row's ticker link and each sort button; X n/a; L Skeleton rows; E "No ranked tickers for this date"; R ErrorState; S StaleBanner above the table and the date in the caption.
- Phone: rows become stacked cards (section 4.5).

**C-34 WatchlistEditor and TickerInput**
- Purpose: add, remove, and group tickers (US-004). Writes need the API token.
- Props: `groups`, `items`, `onAdd`, `onRemove`, `onRegroup`.
- Behavior: a TickerInput (label "Add ticker", pattern `^[A-Z][A-Z0-9.\-]{0,9}$`, input is uppercased) with an optional group select and an "Add" button. An invalid symbol shows the API's message inline under the field. Remove is a quiet button per row; removal asks for confirmation in a small confirmation dialog because it is a destructive, token-gated action (this is one of the permitted modals). Without a token, any write opens the token prompt (C-41).
- States: D; H; F; X "Add" is disabled while the field is empty or a request is in flight, with the reason available; L Skeleton rows; E "Your watchlist is empty. Seed it from the default list." with a "Seed default list" button (token required); R inline error under the field for validation errors (RFC 9457 detail), ErrorState for load failures; S n/a.

**C-35 StatTile**
- Purpose: one track record statistic with its sample size.
- Props: `label`, `value`, `unit`, `n`, `horizon`, `side`.
- Layout: label, value in mono at 28 px, and always "n = 47" beside or under it. When `n` is less than 20, the tile adds a "Small sample" Badge and the value is shown in `--text-1`, not `--text-0`.
- States: D; H tooltip defining the statistic; F focusable for the tooltip; X n/a; L Skeleton; E "No outcomes yet" with n = 0 and value "n/a" (never "0.0%"); R n/a; S shows "Outcomes through 2026-11-06" when the last horizon is incomplete.

**C-36 OutcomeTable**
- Purpose: every past pick and what happened next, including the losers (US-008, honesty requirement).
- Props: `rows` (date, ticker, side, band, display_score, confidence, entry price, forward returns and excess returns at 1, 5, 10, 20 days, hit or miss per horizon, status).
- Rules: all picks are listed with no truncation of misses; the default sort is date descending; a "Worst picks" shortcut sorts by excess return ascending. Misses are never dimmed, collapsed, or placed after hits. Pending horizons show "Pending (3 of 5 sessions)". Outcomes are shown in words and shapes: "Hit" with a check mark, "Miss" with a cross mark.
- States: D; H row surface step; F rows and sort buttons; X n/a; L Skeleton rows; E "No past picks yet. Outcomes appear after the first published pick has had at least one session."; R ErrorState; S "Outcomes through 2026-11-13 (latest computed)".

**C-37 HorizonTabs and TrackFilters**
- Purpose: choose horizon (1, 5, 10, 20 trading days), side, band, date range, and config version.
- Props: `horizon`, `side`, `band`, `from`, `to`, `config`.
- Behavior: a tab list for horizon (`role="tablist"`, arrow keys); selects for side and band; date inputs; a config version select ("All versions" by default; a specific hash filters). Values are written to the URL query string so a view is shareable inside the private deployment.
- States: D; H; F; X a horizon with no computed outcomes is `aria-disabled` with the hint "No outcomes at this horizon yet"; L n/a; E n/a; R invalid date range shows an inline message; S n/a.

**C-38 BacktestLabel**
- Purpose: mark anything derived from a backtest as hypothetical.
- Copy: "Hypothetical: backtested, not real trading. Entries at the next open, no costs or slippage." Shown as a bordered strip with a flask or document icon above every backtest statistic and equity curve, and repeated in the chart title.
- States: D only; others n/a.

**C-39 RunTable and RunRow**
- Purpose: run history (state, duration, exclusions).
- Props: `runs` (id, trade_date, state, started_at, finished_at, published_at, superseded_by, config_hash, summary: picks published, tickers scored, excluded).
- Columns: Trade date, State (Badge with shape), Started, Duration, Picks (buys and sells), Excluded (count, expandable to a reasons list), Config, Published. Superseded runs are shown with "Superseded by <id>". Failed runs show the failing state and a short error summary and are never hidden.
- States: D; H; F; X n/a; L Skeleton rows; E "No runs yet. Use Run now to create the first run."; R ErrorState; S StaleBanner when no published run exists for the latest completed session.
- Run state Badges: queued, ingesting, computing, scoring, selecting, narrating, published (up triangle is not used; a check shape), failed (cross shape).

**C-40 RunProgress and RunNowButton**
- Purpose: trigger a run (token required) and show progress by polling (`GET /api/v1/runs/{id}`, every 2 seconds, no faster).
- Props: `state`, `runId`, `onRun`.
- Behavior: a stepper lists `queued, ingesting, computing, scoring, selecting, narrating, published`, with the current step marked by a filled circle and the word "current", completed steps by a check and the word "done", pending by an empty circle. The region is `aria-live="polite"` and announces each transition once.
- States: D "Run now"; H; F; X disabled with the hint "A run is already in progress" while a run is queued or active (also when the API answers 409); L the stepper shows the current state; E n/a; R "The run failed in the scoring step. The previous published result is still the latest." with the problem detail and a link to the run row; S n/a.
- A run without a token opens the token prompt (C-41). A new run replaces the latest published result only on success, and the UI states this.

**C-41 TokenField and TokenPrompt**
- Purpose: enter the API bearer token for write actions.
- Props: `value` (never rendered back), `remember` (memory only by default, optional localStorage), `onSubmit`.
- Behavior: a password-type input (label "API token"), a "Remember in this browser" checkbox with the warning "Stored tokens persist in this browser's local storage. Anyone with access to this browser can use them. Leave unchecked on shared computers.", and Save and Clear buttons. After save, only "Token set (memory only)" or "Token set (stored in this browser)" is shown, never the token or a prefix. The token prompt is a confirmation-style dialog, shown only when a token-gated action is attempted without a token (a permitted modal).
- States: D; H; F; X Save is disabled when the field is empty; L n/a; E "No token set. Read-only mode: you can view everything but cannot run, add, or remove."; R a rejected token shows "The token was not accepted. Check it and try again." and does not clear existing text; S n/a.

**C-42 ConfigViewer**
- Purpose: read-only view of the active scoring config and its hash (Settings).
- Props: `config` (version, hash, document).
- Behavior: shows version and the full `sha256:` hash in mono with a Copy button, then the config document in a read-only, scrollable, preformatted block with a text search. The document is plain text. Editing is by file (`config/scoring.yaml`); the screen says so.
- States: D; H; F scroll region focusable, Copy button; X n/a; L Skeleton block; E n/a (a config always exists); R ErrorState; S n/a.

**C-43 ProviderStatus**
- Purpose: show market data provider, fundamentals provider, and LLM endpoint health with data freshness.
- Props: `status` (from `/api/v1/status`).
- Rows: Market data provider (`providers.market.name`, `providers.market.last_success_at`, `providers.market.status`), Fundamentals provider (`providers.fundamentals.*`, same fields), LLM (`llm.model`, `llm.status`, `llm.template_fallback_last_run`), Data freshness (`data_freshness.latest_bar_date`, `last_completed_session`). State Badges use shape and word: "Healthy" (check), "Degraded" (triangle), "Down" (cross), "Unknown" (circle outline). No keys, URLs with credentials, or internal hostnames are shown.
- States: D; H; F; X n/a; L Skeleton rows; E n/a; R "Status unavailable" with Retry; S the data freshness row shows `--warn` text "Latest bar 2026-11-12, one session behind".

**C-44 DisclosureSection**
- Purpose: in-page expand and collapse for reasons, all factors, also qualified, and details (never a modal).
- Props: `summary`, `open`, `children`.
- States: D collapsed or expanded; H; F button focus ring, Enter and Space toggle, `aria-expanded` and `aria-controls`; X n/a; L n/a; E n/a; R n/a; S n/a.

**C-45 Tooltip**
- Purpose: short supplementary text. Never the only place a required fact appears.
- Behavior: opens on hover and focus, closes on Escape, dismissible without moving the pointer, stays open while the pointer is over it (WCAG 1.4.13). Text is plain.
- States: D hidden; H and F visible; others n/a.

**C-46 ConfirmDialog**
- Purpose: confirm a destructive or token-gated action (remove ticker, token prompt). The only modal pattern in the product.
- Behavior: `role="dialog"` with `aria-modal="true"`, labelled by its title, focus moves into the dialog on open and returns to the trigger on close, Escape cancels, focus is trapped, the default focus is on the cancel button for destructive actions.
- States: D; H; F; X the confirm button is disabled while a request is in flight; L the confirm label becomes "Working"; E n/a; R the error shows inside the dialog and it stays open; S n/a.

**C-47 Toast (status message)**
- Purpose: confirm a completed action ("Ticker added", "Run queued").
- Behavior: `role="status"`, polite, shown for 6 seconds at the bottom, never covering the disclaimer, dismissible, never used for errors that need a decision (those use inline errors or ErrorState). Hover and focus pause the timer. With reduced motion there is no slide, only a fade of 0 ms.

**C-48 Footer**
- Purpose: license notice and project statement.
- Copy: "Copyright Serverless Ventures LLC. Noncommercial use only." with a link to the license; "Super Trends is software for running your own analysis. It provides no signals service. Each user needs their own market data license."; app version and commit. The project is described only as source-available and free for noncommercial use.
- States: D; H link underline; F; others n/a.

Total components in this inventory: 48 (12 base, 36 additional).

---

## 9. Screens

Routes: `/` (Today), `/date/:yyyy-mm-dd` (Today for a past date), `/ticker/:symbol`, `/watchlist`, `/track-record`, `/runs`, `/settings`, plus `/demo` when `SUPERTRENDS_DEMO=1`. Unknown routes render an ErrorState with the title "Page not found", the sentence "That address does not match a Super Trends screen.", and a link to Today.

Data layer rules common to all screens:
- Server state uses TanStack Query. UI state (theme, selected date, token, overlay toggles) uses Zustand.
- A failed request renders ErrorState in the affected region with a Retry button; a 500 is never a blank screen.
- Refetch happens in place: the previous data stays on screen until the new data arrives, then swaps without changing layout. Background refetch never shows a spinner that moves content.
- Every screen header shows the AsOfStamp. Every screen that shows a recommendation shows the Disclaimer (Today, Ticker, Watchlist, Track Record). Runs and Settings show the short form in the footer region.
- Staleness is determined from `GET /api/v1/status` (field names as defined in docs/ARCHITECTURE.md section 6.1) and the as-of date of the payload on screen. The payload is stale (StaleBanner kind `behind`) when its `date` is earlier than `last_completed_session`. Kind `run_failed` when `latest_run.state` is `failed`; kind `run_in_progress` when `active_run` is not null (the "Current step" copy is `active_run.state`); kind `provider_degraded` when `providers.market.status` or `providers.fundamentals.status` is `degraded` or `unreachable`; kind `llm_down` when `llm.status` is `unreachable`. The data freshness row reads `data_freshness.latest_bar_date` and `last_completed_session`; the excluded-for-stale count reads `data_freshness.stale_tickers`.

### 9.1 Today

**Purpose.** Show the latest trading day's top 3 buys and top 2 sells, each with the evidence to understand and challenge it in under 30 seconds (US-001, US-002, US-007, US-010). This screen is the product.

**Data sources.**
- `GET /api/v1/recommendations/latest` (or `GET /api/v1/recommendations?date=` for `/date/:yyyy-mm-dd`): `date`, `run_id`, `published_at`, `market_regime`, `config`, `buys`, `sells`, `also_qualified`, `nearest_miss`, `excluded`, `disclaimer`.
- `GET /api/v1/status`: `last_completed_session`, `data_freshness`, `latest_run`, `active_run`, `providers`, `llm`.
- `GET /api/v1/watchlist`: group names for the optional group filter.
- `GET /api/v1/tickers/{symbol}/analysis?date=`: only when a card's "Show all 11 factors" is opened, to fetch the full factor list for that ticker.

**Header band.** As-of date, market regime (for example "Market regime: risk on"), run status ("Published 2026-11-13 22:34 UTC", config version and short hash), data freshness ("Data through 2026-11-13"), count of excluded tickers with a link to the details ("3 tickers excluded: stale or insufficient history"). Market regime uses shape plus word (up triangle "Risk on", down triangle "Risk off", bar "Mixed").

**Wireframe, desktop (1200 px and up).**

```
+------------------------------------------------------------------------------------------------+
| SUPER TRENDS   Today  Watchlist  Track record  Runs  Settings            [Theme] As of 2026-11-13|
+------------------------------------------------------------------------------------------------+
| [!] banner slot: StaleBanner / run status (reserved 56 px, empty when data is current)         |
+------------------------------------------------------------------------------------------------+
| Today, 2026-11-13 close                                    Group: [All v]  [Date: < 2026-11-13 >]|
| Market regime: ^ Risk on | Published 2026-11-13 22:34 UTC | Config v1 sha256:3f9a... | 2 excluded |
+------------------------------------------------------------------------------------------------+
| Top buys (3 of 3)                                                                              |
| +----------------------------+ +----------------------------+ +----------------------------+  |
| | 1  ORCL      ^ Buy         | | 2  NVDA      ^ Strong Buy | | 3  MSFT      ^ Buy         |  |
| |    Oracle Corp             | |    NVIDIA Corp             | |    Microsoft Corp          |  |
| |   .-------.                | |   .-------.                | |   .-------.                |  |
| |  / \  |  / \  Confidence   | |  / \  |  / \  Confidence   | |  / \  |  / \  Confidence   |  |
| | | Sell\|/Buy | 71 of 100   | | | Sell\|/Buy | 82 of 100   | | | Sell\|/Buy | 66 of 100   |  |
| |   78.4  Buy   [=====  ]    | |   84.0  Strong Buy [====] | |   70.2  Buy   [====   ]    |  |
| | [UUUU DDD UUUUUUUUUUUUUUU] | | [UUUUUUUUUUUUUUUUUUUUUUUU] | | [DDDDUUUUUUUUUUUUUUUUUUUU] |  |
| |  ribbon (60 sessions)      | |  ribbon (60 sessions)      | |  ribbon (60 sessions)      |  |
| | Supertrend up, flipped 3   | | Supertrend up, flipped 41  | | Supertrend up, flipped 22  |  |
| | bars ago. Day 1 on list.   | | bars ago. Day 4 on list.   | | bars ago. Day 2 on list.   |  |
| | Why: Supertrend  +23.4 ==> | | Why: Supertrend  +22.0 ==> | | Why: Supertrend  +21.5 ==> |  |
| |      MACD         +9.1 =>  | |      Buy/sell vol +10.2 => | |      SMA analysis +8.8 =>  |  |
| |  Against: RSI     -4.2 <=  | |  Against: Volatility -5.0 <| |  Against: Fundam.  -3.1 <= |  |
| |  [Show all 11 factors v]   | |  [Show all 11 factors v]   | |  [Show all 11 factors v]   |  |
| | Narrative (3 to 5 sentences| | Narrative text ...         | | Narrative text ...         |  |
| | ...). Written by a language| |                            | |                            |  |
| | model (model-name).        | |                            | |                            |  |
| | Invalidation 212.40: daily | | Invalidation 118.90: ...   | | Invalidation 401.20: ...   |  |
| | close below the Supertrend | |                            | |                            |  |
| | line.                      | |                            | |                            |  |
| | Next target 236.00         | | Next target ...            | | Next target ...            |  |
| | Resist 229.50 236.00       | |                            | |                            |  |
| | Support 215.10 208.70      | |                            | |                            |  |
| | [Event risk: earnings in 3 | | [Est. order flow: intraday]| | [Est. order flow: daily    |  |
| |  trading days]             | | [Trending] [semis]         | |  estimate] [Trending]      |  |
| | [Est. order flow: intraday]| |                            | |                            |  |
| | [Trending] [semis]         | |                            | |                            |  |
| | Details >                  | | Details >                  | | Details >                  |  |
| +----------------------------+ +----------------------------+ +----------------------------+  |
| Also qualified (1) v   QQQM, score 74.1, duplicates QQQ (60-day correlation 0.97)              |
|                                                                                                |
| Top sells (2 of 2)                                                                             |
| +----------------------------+ +----------------------------+                                  |
| | 1  XYZ       v Sell        | | 2  ABC       v Strong Sell |                                  |
| |   (same card layout as buy | |   (same card layout)       |                                  |
| |    with a down Supertrend) | |                            |                                  |
| +----------------------------+ +----------------------------+                                  |
| Also qualified (0)                                                                             |
|                                                                                                |
| +--------------------------------------------------------------------------------------------+ |
| | (i) Super Trends output is general market analysis generated by an algorithm from ...      | |
| |     (full disclaimer text, section 10.1)                                                   | |
| +--------------------------------------------------------------------------------------------+ |
| Copyright Serverless Ventures LLC. Noncommercial use only. License | v1.0.0                     |
+------------------------------------------------------------------------------------------------+
```

Notes on the wireframe: `^` is the up triangle and `v` is the down triangle; "==>" shows a positive bar to the right of the center axis and "<=" a negative bar to the left. In the real UI these are SVG bars. The needle is drawn in the ScoreDial; the ASCII dial is schematic only.

**Wireframe, phone (below 600 px).**

```
+--------------------------------+
| SUPER TRENDS         [Theme]   |
| As of 2026-11-13 close         |
+--------------------------------+
| (banner slot, 56 px reserved)  |
+--------------------------------+
| Today                          |
| Market regime: ^ Risk on       |
| Group: [All v]  [< date >]     |
+--------------------------------+
| Top buys (3 of 3)              |
| +----------------------------+ |
| | 1  ORCL           ^ Buy    | |
| |    Oracle Corp             | |
| |       .-------.            | |
| |      / needle  \           | |
| |         78.4   Buy         | |
| |  Confidence 71 of 100      | |
| | [UUUU DDD UUUUUUUUUUUUUUU] | |
| | Supertrend up, flipped 3   | |
| | bars ago. Day 1 on list.   | |
| | Why: Supertrend +23.4 ==>  | |
| |      MACD        +9.1 =>   | |
| |  Against: RSI    -4.2 <=   | |
| | [Show all 11 factors v]    | |
| | Narrative ...              | |
| | Invalidation 212.40: daily | |
| | close below the Supertrend | |
| | line.                      | |
| | Expected 1-day move: +/-   | |
| | 4.10 (14-day ATR)          | |
| | [Event risk: earnings in 3 | |
| |  trading days]             | |
| | [Est. order flow: intraday]| |
| | Details >                  | |
| +----------------------------+ |
| (cards 2 and 3 follow)         |
| Also qualified (1) v           |
| Top sells (2 of 2)             |
| (sell cards follow)            |
+--------------------------------+
| (i) Disclaimer, full text      |
+--------------------------------+
| Today | Watch | Track | Runs | S|
+--------------------------------+
```

On phone the factor breakdown shows the same top 3 bars; the level list shows invalidation, expected 1-day move, and next target by default with "More levels" as a disclosure. Phone cards reorder nothing: the DOM order matches the visual order.

**Interactions.**
- Click or press Enter on a ticker or "Details" to open `/ticker/:symbol?date=...`.
- Group filter: re-ranks within the group, shows the note "Showing a group view. Published picks for all tickers are unchanged." with a "Show published picks" button. The published overall picks stay the source of truth and the URL records `?group=semis`.
- DateNavigator moves through stored trading days (`/date/:yyyy-mm-dd`). A historical view shows the banner "Historical view: exactly what was published on <date>, with config version <n> (sha256:<short>)".
- "Show all 11 factors" expands in place. "Also qualified" expands in place.
- Keyboard: Tab order is skip link, navigation, theme, group filter, date controls, then each card in DOM order (ticker link, factor disclosure, details link), then the also-qualified disclosures, then the footer.
- Refresh: the screen refetches on window focus and every 5 minutes in place. It does not animate when data changes. If a newer run was published, the AsOfStamp updates and a Toast reads "Newer results published for 2026-11-14", with no layout shift.

**Card field checklist (every PickCard shows these).** rank, ticker, band with side mark, display score (dial and number), confidence, Supertrend state (daily and weekly direction), bars since flip, TrendRibbon, factor contribution breakdown (top factors plus all on demand), key levels (support, resistance, Fibonacci, next target), invalidation level and rule, event risk flag when set, estimated order flow quality label, regime, watchlist groups, "Day N on the list", narrative with source label (llm or template). Expected 1-day move is shown unconditionally on every PickCard (BUILD_PROMPT Factor 8: `expected_1d_move = atr14`, "shown on every card"). It reads the Pick field `expected_1d_move` (always present, price units; docs/ARCHITECTURE.md section 6.1) and renders in the key levels block as "Expected 1-day move: plus or minus 4.10 (14-day ATR, an estimate from recent volatility, not a forecast)". A Pick without this field is a contract error, not a reason to hide the line.

**States.**

| State | Appearance and exact copy |
|---|---|
| Loading | Header band skeleton lines; two rows of card-shaped skeletons (3 and 2) at final card size; the disclaimer text renders immediately. Region has `aria-busy="true"`. After 400 ms the region label reads "Loading today's picks". |
| Empty: no published run at all | EmptyState. Title: "No results yet". Body: "Super Trends has not published a run. The first run is created after a US market close, or you can start one now." Action: "Go to Runs" (link). Disclaimer still shown. |
| Empty: past date with no run | Title: "Nothing was published on 2026-10-04". Body: "That date has no stored run. It may be a weekend, a holiday, or a day before the first run." Action: "Show latest" and the DateNavigator with the nearest earlier date: "Closest earlier trading date with a run: 2026-10-02." |
| Empty: a side has no picks | Section stays, with count "Top sells (0 of 2)". NearestMissLine: "No qualifying sells today." and "Nearest candidate: XYZ, score 37.2. Reason: score above the sell threshold of 35." The side never shows placeholder cards and never fills with lower-ranked names. |
| Partial: fewer than the maximum | Cards shown; then "No more qualifying buys today. Showing 1 of 3." and the nearest-miss line. |
| Error | ErrorState in place of the cards. Title: "Could not load today's picks". Body: the API problem detail, or "The Super Trends API did not return a result. Your last view is not shown because it could not be confirmed." Retry button. Request ID in mono. The Disclaimer is still shown. |
| Stale: data one or more sessions behind | StaleBanner (kind `behind`). Lead: "These picks are not from the latest session." Detail: "Showing 2026-11-12. The latest completed session is 2026-11-13. A run may be late or may have failed. See Runs." Cards stay visible with a stale strip: "Data is one session old". |
| Stale: latest run failed | StaleBanner (kind `run_failed`). Lead: "The latest run failed." Detail: "Showing the last good result from 2026-11-12. Nothing from the failed run was published." Link: "View the run". |
| Stale: run in progress | StaleBanner (kind `run_in_progress`). Lead: "A run is in progress." Detail: "Showing 2026-11-12 until the new run is published. Current step: scoring." |
| Degraded: LLM unavailable | Info strip: "The language model was unavailable. Written justifications use template text. Scores and picks are not affected." Cards carry the "Template" Badge. |
| Degraded: some tickers excluded | Header link: "3 tickers excluded". Expands in place: "ABC: stale. DEF: insufficient history." Excluded tickers are never scored on bad data. |

### 9.2 Ticker

**Purpose.** For one ticker, show the chart with Supertrend, SMAs, Fibonacci levels, support and resistance, and the full factor table, regime, adjustments, fundamentals summary, and the ticker's score history (US-003, US-005, US-009).

**Data sources.**
- `GET /api/v1/tickers/{symbol}/analysis?date=`: factor table, evidence, levels, regime, narrative.
- `GET /api/v1/tickers/{symbol}/bars?tf=1d&from=&to=`: bars and overlay series (Supertrend, SMAs).
- `GET /api/v1/tickers/{symbol}/history`: scores and pick appearances over time.
- `GET /api/v1/watchlist`: group membership.

**Wireframe, desktop.**

```
+------------------------------------------------------------------------------------------------+
| SUPER TRENDS   Today  Watchlist  Track record  Runs  Settings            [Theme] As of 2026-11-13|
+------------------------------------------------------------------------------------------------+
| < Back to Today                                                                                |
| ORCL  Oracle Corp   [semis] [software]        ^ Buy (day 1 on the list)   Score 78.4   Conf 71  |
| Supertrend: ^ Up daily, ^ Up weekly, flipped 3 bars ago   [UUUU DDD UUUUUUUUUUUUUUUUUUUUUUUU]   |
+----------------------------------------------------------------+-------------------------------+
| Timeframe: (o) 1d ( ) 1w     [View as table]  [Reset overlays] | Factors (11)                  |
| Overlays: [x]Candles [x]Supertrend [ ]SMA 20 [ ]SMA 50 [ ]SMA 200  | Factor     Scr  Wt  Contrib|
|           [ ]Fibonacci [ ]Support/Resistance [x]Invalidation       | Supertrend 100 23.4  +23.4 |
| +------------------------------------------------------------+ | MACD        81 11.2   +9.1 |
| |                                      invalidation 212.40 --| | ...                        |
| |   candles + Supertrend line with flip markers (^ v)        | | Composite             +56.8 |
| |                                                            | | Display score          78.4 |
| |                                                            | +-----------------------------+
| |                                                            | | Regime                      |
| +------------------------------------------------------------+ | Trending. Market: ^ Risk on |
| | Volume (estimated buy / sell split)    [Est. order flow:   ]| | Weights adjusted: trending  |
| |                                          intraday          | | regime, earnings in 3 days. |
| +------------------------------------------------------------+ | [Show base vs adjusted v]   |
| | MACD (toggle)      | RSI (toggle) with divergence markers  | +-----------------------------+
| +------------------------------------------------------------+ | Fundamentals                |
| End-of-day data, as of 2026-11-13                              | (summary, quality, known at)|
+----------------------------------------------------------------+-----------------------------+
| Narrative (llm or template, 3 to 5 sentences)                                                  |
| Key levels: Invalidation 212.40 | Next target 236.00 | Resist 229.50 236.00 | Support 215.10 ... |
| Score history for ORCL   Date        Score  Band   Pick                                        |
|                          2026-11-13  78.4   Buy    Pick: buy, day 1                            |
|                          2026-11-12  66.0   Buy    Not picked                                  |
+------------------------------------------------------------------------------------------------+
| (i) Disclaimer, full text                                                                      |
+------------------------------------------------------------------------------------------------+
```

**Phone layout.** Header block, ribbon, then the chart (full width, 4:3) with a compact overlay toggle row that scrolls horizontally, then a stack of DisclosureSections: Factors, Regime and adjustments, Fundamentals, Key levels, Narrative, Score history, each closed by default except Narrative and Key levels. Sub-panels (volume, MACD, RSI) are toggles, off by default on phone except volume.

**Interactions.**
- Overlay toggles persist per browser. "Reset overlays" restores the defaults.
- Timeframe toggle switches 1d and 1w.
- "View as table" swaps the canvas for ChartDataTable (and back) in place, preserving scroll and focus.
- Keyboard chart navigation per C-26. The Escape key returns focus from the chart region to the toolbar.
- Date: the page follows the selected date (`?date=`). A date with no analysis shows the empty state below.
- Factor rows expand to show their deterministic reasons (for example "Daily Supertrend flipped up 3 bars ago").
- The symbol in the URL is validated (`^[A-Z][A-Z0-9.\-]{0,9}$`); an invalid symbol shows the not-found state.

**States.**

| State | Appearance and exact copy |
|---|---|
| Loading | Header skeleton, chart Skeleton at its final height, rail skeleton rows. Disclaimer shown immediately. |
| Empty: ticker not found | Title: "Ticker not found". Body: "BADSYM is not on the watchlist and has no stored analysis." Actions: "Go to Watchlist", "Back to Today". |
| Empty: no analysis for the date | Title: "No analysis for 2026-11-13". Body: "This ticker was not scored on that date. It may have been excluded or added later." If excluded, the reason is shown: "Excluded: stale data." Chart still shows available bars. |
| Empty: no bars | Chart region: "No price history for this ticker." The rail shows what exists. |
| Empty: not a pick | The header omits the side mark and shows the band and score only; text: "Not a published pick on this date." |
| Error: analysis | ErrorState in the rail and header: "Could not load the analysis for ORCL", detail, Retry. Chart can still render if bars loaded. |
| Error: bars | ErrorState inside the chart region at the chart's height: "Could not load price bars for ORCL", detail, Retry. The factor table can still render. |
| Stale | StaleBanner (kind `behind`) and the chart footer: "End-of-day data, as of 2026-11-12. The latest completed session is 2026-11-13." Ticker-level stale data (data quality `stale`): header tag "Data: stale. This ticker is excluded from picks until fresh bars arrive." |
| Degraded order flow | DataQualityTag "Estimated order flow: daily estimate" with tooltip "Intraday bars were not available for enough sessions. The estimate uses daily bars and its weight is multiplied by 0.6." |

### 9.3 Watchlist

**Purpose.** Show the full ranked watchlist with scores so the user can look past the top 5, and manage the list (US-004, US-006).

**Data sources.**
- `GET /api/v1/rankings?date=&limit=&offset=`: ranked rows with score, band, confidence, Supertrend direction and age, regime, relative volume, data quality, ribbon, and excluded tickers with reasons.
- `GET /api/v1/watchlist`: items and groups.
- `POST /api/v1/watchlist/items` (token): add. `DELETE /api/v1/watchlist/items/{symbol}` (token): remove.
- `GET /api/v1/recommendations?date=`: which rows are published picks.

**Wireframe, desktop.**

```
+------------------------------------------------------------------------------------------------+
| SUPER TRENDS   Today  Watchlist  Track record  Runs  Settings            [Theme] As of 2026-11-13|
+------------------------------------------------------------------------------------------------+
| Watchlist, ranked for 2026-11-13   Group: [All v]  [Date: < 2026-11-13 >]  200 tickers          |
| Add ticker: [ NVDA     ] Group: [semis v] [Add]   (needs API token)       [Manage groups]      |
|   Inline message area (API validation text appears here)                                       |
+------------------------------------------------------------------------------------------------+
| # | Ticker | Score v | Band        | Conf | Supertrend      | Ribbon (60)      | Regime  | RelV |Data|
|---+--------+---------+-------------+------+-----------------+------------------+---------+------+----|
| 1 | NVDA   |  84.0   | ^ Strong Buy|  82  | ^ Up, 41 bars   | [UUUUUUUUUUUUUU] | Trend.  | 1.4  | ok |
| 2 | ORCL   |  78.4   | ^ Buy       |  71  | ^ Up, 3 bars    | [UUUU DDD UUUUU] | Trend.  | 1.2  | ok |
| 3 | MSFT   |  70.2   | ^ Buy       |  66  | ^ Up, 22 bars   | [DDDDUUUUUUUUUU] | Trend.  | 0.9  | ok |
| 4 | QQQM   |  74.1   | ^ Buy       |  68  | ^ Up, 20 bars   | [UUUUUUUUUUUUUU] | Trend.  | 1.0  | ok |
|   |        |         |  (also qualified, duplicates QQQ)                                         |
| ...                                                                                             |
|52 | KO     |  50.3   | = Neutral up|  44  | v Down, 2 bars  | [UUUUDDUDDUDDDD] | Ranging | 0.8  | ok |
| ...                                                                                             |
|199| XYZ    |  22.0   | v Sell      |  63  | v Down, 18 bars | [DDDDDDDDDDDDDD] | Trend.  | 1.1  | ok |
+------------------------------------------------------------------------------------------------+
| Excluded (3)  v                                                                                |
| ABC: stale (latest bar older than the last completed session)                                  |
| DEF: insufficient history (fewer than 250 daily bars)                                          |
| GHI: degraded data, scored with reduced confidence   [Remove]                                  |
+------------------------------------------------------------------------------------------------+
| Rows 1 to 50 of 197  [Load more]                                                               |
| (i) Disclaimer, full text                                                                      |
+------------------------------------------------------------------------------------------------+
```

Columns are sortable with the header buttons (`aria-sort`). Phone: rows become stacked cards (ticker, band, score, confidence; ribbon; "Details" disclosure with regime, relative volume, data quality, groups).

**Interactions.**
- Group filter shows tickers in one group (semis, fab-7, country-etfs, and so on); the rank column shows the overall rank, with the group rank in parentheses when a group is selected.
- Sort by any column. Sorting is stable: ties keep the previous order, then alphabetical by ticker.
- Add ticker: validates the pattern client side and shows the API's message inline on rejection ("NVD1 is not a symbol the data provider knows." is an example of an API message; the UI shows whatever the API returns, as plain text). Requires the token; without one the token prompt appears.
- Remove: quiet button in the row actions menu, with a ConfirmDialog ("Remove ORCL from the watchlist? Stored history for ORCL is kept.").
- Group edit: change a ticker's group from the row menu or in "Manage groups".
- Row ticker link opens the Ticker screen at the same date.
- Published picks are marked "Pick: buy" or "Pick: sell". Ranked rows are not otherwise highlighted.
- A ticker excluded for stale or insufficient data is listed under Excluded with its reason, never scored and never silently dropped.

**States.**

| State | Appearance and exact copy |
|---|---|
| Loading | Table header with 10 Skeleton rows of final height; group filter skeleton chips. |
| Empty: watchlist has no tickers | Title: "Your watchlist is empty". Body: "Add a ticker above, or seed the list from the default set." Action: "Seed default list" (token required). |
| Empty: no ranking for the date | Title: "No ranking for 2026-10-04". Body: "That date has no published run." Action: "Show latest". |
| Empty: group has no tickers | Title: "No tickers in this group". Body: "Move a ticker into semis, or choose another group." |
| Error | ErrorState: "Could not load the ranking", detail, Retry. The add form stays usable if the watchlist loaded. |
| Error: write rejected | Inline under the form: the API detail as plain text. For 401: "The token was not accepted. Open Settings to enter a valid token." For 429: "Too many changes in a short time. Wait a moment and try again." |
| Stale | StaleBanner (kind `behind`) above the table: "This ranking is not from the latest session. Showing 2026-11-12; the latest completed session is 2026-11-13." Caption repeats the as-of date. Ticker-level `stale` rows are in Excluded. |

### 9.4 Track Record

**Purpose.** Show every past pick and what happened next, including the losers, and aggregate statistics with sample sizes and a clear "small sample" label (US-008). Backtest results are labeled hypothetical wherever they appear.

**Data sources.**
- `GET /api/v1/track-record?from=&to=&side=&band=&config=`: statistics (hit rate, mean and median excess return, worst pick; by side, horizon, overall and by band, with `n`) and pick outcomes.
- `GET /api/v1/config/scoring`: for the config version filter.
- Backtest output (equity curve) comes from the same endpoint when a backtest result is selected, flagged hypothetical.

**Wireframe, desktop.**

```
+------------------------------------------------------------------------------------------------+
| SUPER TRENDS   Today  Watchlist  Track record  Runs  Settings            [Theme] As of 2026-11-13|
+------------------------------------------------------------------------------------------------+
| Track record                       Outcomes through 2026-11-13                                 |
| From [2025-11-14] To [2026-11-13]  Side [All v]  Band [All v]  Config [All versions v]         |
| Horizon: [1 day] [5 days] [10 days] [20 days]                                                  |
+------------------------------------------------------------------------------------------------+
| Buys at 5 trading days, versus SPY                                                             |
| +----------------+ +----------------+ +----------------+ +------------------------------------+|
| | Hit rate       | | Mean excess    | | Median excess  | | Worst pick                         ||
| | 54.0 percent   | | +0.4 percent   | | +0.2 percent   | | ABC  -14.2 percent  2026-03-09     ||
| | n = 150        | | n = 150        | | n = 150        | | (link to the pick)                 ||
| +----------------+ +----------------+ +----------------+ +------------------------------------+|
| Sells at 5 trading days, versus SPY                                                            |
| +----------------+ +----------------+ +----------------+ +------------------------------------+|
| | Hit rate       | | Mean excess    | | Median excess  | | Worst pick                         ||
| | 48.0 percent   | | -0.1 percent   | | -0.3 percent   | | XYZ  +11.0 percent  2026-05-20     ||
| | n = 100        | | n = 100        | | n = 100        | | (sell hit means negative excess)   ||
| +----------------+ +----------------+ +----------------+ +------------------------------------+|
| By band (5 trading days)                                                                       |
| Band          | Side | n   | Hit rate | Mean excess | Median excess | Worst                       |
| Strong Buy    | buy  | 31  | 58.1     | +0.9        | +0.7          | -8.0                        |
| Buy           | buy  | 119 | 52.9     | +0.3        | +0.1          | -14.2                       |
| Sell          | sell | 18  | 44.4     | +0.1  [Small sample]  ...                                  |
| Strong Sell   | sell | 4   | -        | -     [Small sample]  ...                                  |
+------------------------------------------------------------------------------------------------+
| All picks and what happened next (newest first)  [Sort: worst excess first]                    |
| Date       Ticker Side  Band    Score Conf Entry   1d     5d     10d    20d    Outcome (5d)     |
| 2026-11-06 ABC    ^Buy  Buy     72.1  63   101.20  -2.1   -4.8   Pend.  Pend.  X Miss           |
| 2026-11-05 DEF    vSell Sell    31.0  58   54.10   -0.4   +1.0   Pend.  Pend.  X Miss           |
| 2026-11-04 GHI    ^Buy  S.Buy   83.5  77   220.00  +1.2   +3.4   Pend.  Pend.  V Hit            |
| (every pick is listed, hits and misses alike, in the same style)                               |
+------------------------------------------------------------------------------------------------+
| Hypothetical: backtested, not real trading. Entries at the next open, no costs or slippage.    |
| Backtest (hypothetical): equal weight the daily buys, hold 5 days, versus SPY                   |
| [line chart: strategy (solid) and SPY (dashed)]                                                |
+------------------------------------------------------------------------------------------------+
| (i) Disclaimer, full text (includes "Past and backtested performance does not predict ...")    |
+------------------------------------------------------------------------------------------------+
```

In the real UI the Outcome column shows a check shape with "Hit" and a cross shape with "Miss". Hit means a positive excess return versus SPY for buys and a negative excess return for sells. The summary line above the stats states this: "A buy counts as a hit when it beat SPY over the horizon. A sell counts as a hit when it trailed SPY."

**Interactions.**
- Horizon tabs, side, band, date range, and config filters update the statistics and the table; the filters are written to the URL.
- Statistics with fewer than 20 samples show "Small sample" and `--text-1` values. Zero samples show "n/a" with "n = 0", never a percentage.
- Entry price is "next session's open". The column header tooltip states this.
- Pending horizons show "Pending (N of H sessions)".
- The table is sortable; "Sort: worst excess first" is a visible shortcut. Misses are never hidden, collapsed by default, or placed after hits.
- Row click or Enter opens the pick on the Ticker screen at that pick's date.
- The backtest section appears only when a backtest result exists, and always carries the BacktestLabel.

**States.**

| State | Appearance and exact copy |
|---|---|
| Loading | Four StatTile skeletons per side, band table skeleton rows, outcome table skeleton rows. Disclaimer rendered immediately. |
| Empty: no past picks | Title: "No track record yet". Body: "Outcomes appear after a published pick has had at least one session. Every pick is recorded, including the ones that miss." |
| Empty: filters match nothing | Title: "No picks match these filters". Body: "Widen the date range or clear the side and band filters." Action: "Clear filters". |
| Empty: horizon has no outcomes | Tiles show "n/a" with "n = 0" and the line "No picks have reached 20 trading days yet." |
| Empty: no backtest | The backtest section is omitted. A quiet line reads: "No backtest has been run. Use the supertrends backtest command to create one." |
| Error | ErrorState: "Could not load the track record", detail, Retry. The disclaimer remains. |
| Stale | StaleBanner (kind `behind`): "Outcomes are computed after each run. The latest run is for 2026-11-12; outcomes shown are through that date." The caption "Outcomes through 2026-11-12" appears beside the title. |
| Small sample | Statistic with `n` below 20: Badge "Small sample" next to the value and the sentence in the tooltip "Fewer than 20 samples. Treat this number as anecdotal." |

### 9.5 Runs

**Purpose.** Show run history with state, duration, and exclusions, and let the user start a run and watch its progress (US-011, US-018 as seen from the UI).

**Data sources.**
- `GET /api/v1/runs?limit=`: history.
- `GET /api/v1/runs/{id}`: detail and polling for the active run.
- `POST /api/v1/runs` (token): trigger a run; a 409 means one is already in progress.
- `GET /api/v1/status`: data freshness and provider health.

**Wireframe, desktop.**

```
+------------------------------------------------------------------------------------------------+
| SUPER TRENDS   Today  Watchlist  Track record  Runs  Settings            [Theme] As of 2026-11-13|
+------------------------------------------------------------------------------------------------+
| Runs                                                                [ Run now ] (needs token)   |
| Latest completed session: 2026-11-13.  Latest published run: 2026-11-13 22:34 UTC.             |
+------------------------------------------------------------------------------------------------+
| Active run 01JCX...  Trade date 2026-11-14                                                     |
| (o) queued -> (o) ingesting -> (*) computing [current] -> ( ) scoring -> ( ) selecting         |
|            -> ( ) narrating -> ( ) published         Polling every 2 seconds                   |
+------------------------------------------------------------------------------------------------+
| Trade date | State        | Started   | Duration | Picks      | Excluded | Config   | Published  |
|------------+--------------+-----------+----------+------------+----------+----------+------------|
| 2026-11-13 | V published  | 22:30 UTC | 4m 12s   | 3 buys 2 s | 2  v     | v1 3f9a  | 22:34 UTC  |
| 2026-11-12 | V published  | 22:30 UTC | 4m 02s   | 3 buys 1 s | 0        | v1 3f9a  | 22:34 UTC  |
| 2026-11-11 | X failed     | 22:30 UTC | 1m 40s   | none       | -        | v1 3f9a  | not published |
|            |  Failed in scoring. The previous published result stayed latest.                  |
| 2026-11-10 | V published  | superseded by 01JCW...                                              |
+------------------------------------------------------------------------------------------------+
| Excluded in the selected run (2): ABC: stale.  DEF: insufficient history.                      |
| (i) Short disclaimer: Not investment advice. Algorithm output can be wrong. Full text on Today. |
+------------------------------------------------------------------------------------------------+
```

Phone: rows become stacked cards (trade date and state first; duration, picks, excluded, and config behind "Details"). The "Run now" button is full width and at least 44 px tall.

**Interactions.**
- "Run now" requires the token. Without a token the token prompt appears. With a run in progress the button is disabled and the hint reads "A run is already in progress". A 409 response sets that state and shows the same hint.
- After a successful trigger, the stepper appears and polls `GET /api/v1/runs/{id}` every 2 seconds. When the state becomes `published`, a Toast reads "Run published for 2026-11-14" and the table refetches in place. When it becomes `failed`, the failed row appears and the failed-run text below is shown.
- Row click or Enter expands the run detail in place: exclusions list with reasons, timings per step if available, superseding run if any, config hash.
- A rerun for the same date appears as a new row; the older row shows "Superseded by <id>". Both remain visible.

**States.**

| State | Appearance and exact copy |
|---|---|
| Loading | Skeleton rows (8). The "Run now" button renders at once but is disabled with the hint "Checking run status" until the history loads. |
| Empty: no runs | Title: "No runs yet". Body: "Runs are created automatically after the US market close, or you can start one now." Action: "Run now" (token required). |
| Empty: no exclusions | In the run detail: "No tickers were excluded." |
| Error | ErrorState: "Could not load run history", detail, Retry. "Run now" stays visible; if status is unknown it is disabled with "Run status unknown". |
| Error: run failed | Strip under the stepper: "The run failed in the scoring step. The previous published result is still the latest. Nothing from this run was published." plus the problem detail and a "Try again" button (token required). |
| Error: 401 on Run now | "The token was not accepted. Open Settings to enter a valid token." |
| Error: 429 on Run now | "Too many run requests. Wait a moment and try again." |
| Stale | StaleBanner (kind `behind` or `run_failed`): "No published run exists for the latest completed session (2026-11-13). The latest published run is for 2026-11-12." with a link to "Run now". If the API poll fails mid-run: "Lost contact with the run status. The run may still be going. Retrying." The stepper keeps its last known state and is marked with the time of the last update. |

### 9.6 Settings

**Purpose.** Read-only view of the active scoring config and hash, theme choice, API token entry, and provider and LLM status (S4-T06). Settings changes to scoring are made in `config/scoring.yaml`, not in the UI.

**Data sources.**
- `GET /api/v1/config/scoring`: active config document, version, and hash.
- `GET /api/v1/status`: data freshness, provider and LLM health, app version and license notice.

**Wireframe, desktop.**

```
+------------------------------------------------------------------------------------------------+
| SUPER TRENDS   Today  Watchlist  Track record  Runs  Settings            [Theme] As of 2026-11-13|
+------------------------------------------------------------------------------------------------+
| Settings                                                                                       |
+------------------------------------------------------------------------------------------------+
| Appearance                                                                                     |
| Theme: (o) Dark   ( ) Light   ( ) System                                                       |
+------------------------------------------------------------------------------------------------+
| API token                                                                                      |
| Needed to run, add, or remove. Never shown after you save it.                                  |
| Token: [**********************]   [Save] [Clear]                                               |
| [ ] Remember in this browser. Stored tokens persist in this browser's local storage. Anyone    |
|     with access to this browser can use them. Leave unchecked on shared computers.             |
| Status: Token set (memory only)                                                                |
+------------------------------------------------------------------------------------------------+
| Scoring config (read only)                                                                     |
| Version 1   Hash sha256:3f9a...c1d2  [Copy]    Edit config/scoring.yaml and re-run to change.  |
| [ Search config ]                                                                              |
| +--------------------------------------------------------------------------------------------+ |
| | scoring:  version: 1  min_history_bars: 250 ... (plain preformatted text, scrollable)       | |
| +--------------------------------------------------------------------------------------------+ |
+------------------------------------------------------------------------------------------------+
| Providers and language model                                                                   |
| Market data       V Healthy    last call 2026-11-13 22:31 UTC                                  |
| Fundamentals      V Healthy    last call 2026-11-13 22:32 UTC                                  |
| Language model    ! Degraded   model-name, 62 percent of narratives used template text in the  |
|                                latest run                                                      |
| Data freshness    V Latest bar 2026-11-13 (latest completed session 2026-11-13)               |
+------------------------------------------------------------------------------------------------+
| About                                                                                          |
| Super Trends v1.0.0 (commit abc1234). Copyright Serverless Ventures LLC. Noncommercial use     |
| only. License. Software for running your own analysis. No signals service. Each user needs     |
| their own market data license.                                                                 |
| (i) Short disclaimer. Full text on Today.                                                      |
+------------------------------------------------------------------------------------------------+
```

**Interactions.**
- Theme change applies immediately and persists per browser.
- Token: Save stores it in memory only by default. Checking "Remember in this browser" stores it in `localStorage` and shows the warning above. Clear removes it from both. The token is never displayed, never put in a URL, and never sent anywhere except the `Authorization: Bearer` header to the same origin.
- Config: Copy copies the hash. Search highlights matches in the read-only text.
- No secret is ever rendered in this screen. Provider rows show names and states, never keys, credentials, or internal hostnames.

**States.**

| State | Appearance and exact copy |
|---|---|
| Loading | Skeleton blocks for the config and provider sections. Theme and token sections render immediately because they are local. |
| Empty: no token | Status line: "No token set. Read-only mode: you can view everything but cannot run, add, or remove." |
| Empty: provider status unknown | Row text: "Unknown. No call has been recorded yet." with an outlined circle shape. |
| Error: config | ErrorState inside the config section: "Could not load the scoring config", detail, Retry. |
| Error: status | Providers section: "Status unavailable. The status service did not answer." with Retry. |
| Error: token rejected | Shown after a write action fails: "The token was not accepted. Check it and try again." The field keeps its text. |
| Stale | In the providers section, data freshness row in `--warn` with a triangle: "Latest bar 2026-11-12. The latest completed session is 2026-11-13. Data is one session behind." If the config shown differs from the config hash of the run on Today: "The active config changed after the latest run. Today shows results from config sha256:1a2b...; the active config is sha256:3f9a... Results update after the next run." |

### 9.7 Demo (only when SUPERTRENDS_DEMO=1)

The `/demo` route lists every product function with a link to the screen that shows it and its live PASS or FAIL status. The DemoBanner ("DEMO DATA: synthetic prices, not real markets") appears on every route in demo mode and on no route otherwise. The demo tour uses the same components and states as the screens above and adds no visual styles of its own.

---

## 10. Copy and disclaimer placement

### 10.1 Disclaimer text (verbatim)

This is the exact text from the Security Guidelines. It is shown in full wherever a pick appears. The UI renders the `disclaimer` string from the API payload; the compiled-in copy below is the fallback and must match it.

> Super Trends output is general market analysis generated by an algorithm from technical and fundamental data. It is not investment advice, not a recommendation tailored to you, and not an offer to buy or sell any security. The algorithm can be and often is wrong. Past and backtested performance does not predict future results. You are responsible for your own decisions.

Short form (used only on Runs, Settings, and as the phone sticky reminder; always paired with a path to the full text on the same page or on Today): "Not investment advice. Algorithm output can be wrong. Full disclaimer on the Today screen."

### 10.2 Placement

| Screen | Disclaimer |
|---|---|
| Today (and `/date/...`) | Full text, always visible, in a bordered block directly under the last card section, above the footer. On phone it is also reachable by a pinned "Disclaimer" link that scrolls to it. It is never collapsed, never in a modal, never in a tooltip. |
| Ticker | Full text under the narrative and score history, above the footer. |
| Watchlist | Full text under the table, above the footer. |
| Track Record | Full text under the outcome table and backtest section, above the footer. |
| Runs | Short form above the footer. |
| Settings | Short form in the About section. |
| Demo | Full text on any demo view that shows a pick. |

Rules:
- Any view that shows a pick, a score, a band, or a backtest carries the full disclaimer on that same page.
- The disclaimer uses 12 px `--text-1` on `--bg-0` or `--bg-1` (at least 8:1 in dark and 7.5:1 in light). It is not styled to look de-emphasized below that contrast.
- Super Trends never asks for or stores holdings, account size, risk tolerance, or goals. No UI element asks for them. No UI element shows position sizes, option strikes or expiries, leverage, or order instructions. There is no brokerage connection and no "trade" button.
- The footer carries the license notice "Copyright Serverless Ventures LLC. Noncommercial use only." with a link to the license, and the statement that the software is for running your own analysis, provides no signals service, and requires each user's own market data license.

### 10.3 Required labels and exact wording

| Concept | Wording | Where |
|---|---|---|
| Fewer picks than the maximum | "No more qualifying buys today. Showing 1 of 3." | Today, under a partial side |
| Empty side | "No qualifying sells today." then "Nearest candidate: XYZ, score 37.2. Reason: score above the sell threshold of 35." | Today, in place of cards on an empty side |
| Empty side, no candidate | "No qualifying sells today." then "No candidate came close. Every ticker on the watchlist was excluded or scored far from the threshold." | Today |
| Buy-side nearest miss reasons | Wording follows the API `reason` (for example "score below the buy threshold of 65", "daily Supertrend is not up", "confidence below 50", "average dollar volume below 20,000,000"). The UI shows the API's reason string as plain text. | Today |
| Small sample | "Small sample" Badge plus tooltip "Fewer than 20 samples. Treat this number as anecdotal." | Track Record statistics |
| Sample size | "n = 47" beside every statistic | Track Record |
| Hypothetical | "Hypothetical: backtested, not real trading. Entries at the next open, no costs or slippage." | Above every backtest statistic and equity curve; repeated in the chart title |
| Estimated order flow | "Estimated order flow: intraday" or "Estimated order flow: daily estimate" (or "trades"), with tooltip "Buy and sell volume is an estimate derived from bar data. Super Trends does not see the real order book." | Pick cards, Ticker volume panel |
| Confidence | "Confidence 71 of 100" with tooltip "How much of the weighted evidence agrees with the direction of the score, reduced for high volatility, degraded data, weekly disagreement, and event risk. It is not a probability of profit." | Pick cards, Ticker header |
| Invalidation | "Invalidation 212.40: daily close below the Supertrend line" (for sells, the rule is the API's, for example "daily close above the Supertrend line") | Pick cards, Ticker, chart |
| Event risk | "Event risk: earnings in 3 trading days" | Pick cards |
| Narrative source | "Written by a language model (model-name) from the computed evidence" or "Template text (the language model was unavailable or its draft was rejected)" | Under each narrative |
| Day count | "Day 1 on the list", "Day N on the list" | Pick cards |
| Also qualified | "Also qualified (skipped as near-duplicates): QQQM, score 74.1, duplicates QQQ (60-day correlation 0.97)" | Today |
| Weight adjustments | "Weights adjusted: trending regime, earnings in 3 days" | Ticker, expanded card |
| Entry price | "Entry: next session's open" | Track Record column tooltip |
| Hit definition | "A buy counts as a hit when it beat SPY over the horizon. A sell counts as a hit when it trailed SPY." | Track Record |
| Meaning of Sell | "Sell means bearish: reduce, exit, or avoid. Super Trends does not recommend short selling or any specific instrument, size, or expiry." | Tooltip on the Sell badge and on the Today "Top sells" heading, and in the Track Record legend |
| End of day | "End-of-day data, as of 2026-11-13" | Chart footers, table captions |

Word choice:
- Use "bearish", "bullish", "the view is wrong if", "argues against", "qualified", "score", "band".
- Do not use "guaranteed", "sure thing", "can't lose", "will go to", "will" as a prediction, "to the moon", "winner", "must buy", "best", "top pick" as a promise of performance, or any celebratory language. "Top buys" is the section heading (rank by score), not a claim about outcome.
- Use plain text for LLM output, no links, no Markdown.
- No em dashes anywhere in UI copy. Ranges use the word "to".

### 10.4 Stale and status banner copy

| Kind | Lead sentence | Detail |
|---|---|---|
| `behind` | "These results are not from the latest session." | "Showing 2026-11-12. The latest completed session is 2026-11-13. A run may be late or may have failed. See Runs." |
| `run_failed` | "The latest run failed." | "Showing the last good result from 2026-11-12. Nothing from the failed run was published." |
| `run_in_progress` | "A run is in progress." | "Showing 2026-11-12 until the new run is published. Current step: scoring." |
| `provider_degraded` | "The market data provider is having problems." | "Some tickers may be excluded or flagged. See Settings for provider status." |
| `llm_down` | "The language model was unavailable." | "Written justifications use template text. Scores and picks are not affected." |
| Status unknown | "Data freshness unknown." | "The status service did not answer." |

### 10.5 Error copy rules

- The title names what failed ("Could not load today's picks"). The body is the API problem detail as plain text. If the API gives no detail: "The Super Trends API did not return a result."
- Never blame the user. Never show stack traces, secrets, tokens, query strings with credentials, or internal hostnames.
- Always provide Retry. Always show the Request ID in mono when the API supplied one.

---

## 11. Accessibility rules

Target: WCAG 2.2 level AA on every route. Automated check: axe reports zero serious or critical issues on every route in both themes, in CI.

### 11.1 Contrast and color
- Every text and background pair meets 4.5:1 (3:1 for text of 24 px and larger or 19 px and bold). Values are in section 2 and are checked in both themes.
- Non-text elements that carry meaning (focus ring, control borders, ribbon cells, dial needle, chart lines and markers, flip ticks) meet 3:1 against their adjacent surface.
- Buy and sell are never distinguished by color alone (section 7). Hit and miss, healthy and down, up and down all pair color with a word and a shape.
- Color-blind and grayscale checks are part of the Playwright suite for Today.

### 11.2 Keyboard
- Everything is operable by keyboard with a logical order that follows the visual and DOM order. No keyboard traps (the ConfirmDialog traps focus by design and releases on close).
- A "Skip to main content" link is the first focusable element on every route.
- Interactive elements: links activate with Enter; buttons with Enter and Space; disclosures with Enter and Space; tabs and segmented controls with arrow keys; sortable column headers are buttons.
- Chart: the chart region is focusable; arrow keys move the cursor by one session; Shift plus arrow moves 5; Home and End jump to the first and last session in view; Escape returns focus to the toolbar. A "View as table" alternative is always present.
- Ribbon: focusable, arrow keys move the cell cursor.
- Shortcut keys are not defined in v1. If any are added later, they can be turned off and do not use single printable characters without a modifier (WCAG 2.1.4).
- Dragging is never required (WCAG 2.5.7). Chart pan and zoom also have keyboard and button alternatives ("Zoom in", "Zoom out", "Earlier", "Later").
- Pointer targets are at least 24 by 24 CSS px on desktop (WCAG 2.5.8) and at least 44 by 44 on phone.

### 11.3 Focus
- Focus ring: 2 px solid `--focus` with a 2 px offset, on every interactive element, never removed (`outline: none` is not allowed without an equivalent replacement). The ring is not clipped by overflow containers.
- Focus is not obscured by sticky headers or the bottom tab bar (WCAG 2.4.11): scroll padding equals the sticky header height and the tab bar height.
- On route change, focus moves to the page `h1` and the title of the document updates (for example "Today, 2026-11-13 | Super Trends").
- When a disclosure opens, focus stays on its button. When a dialog opens, focus moves into it; on close it returns to the trigger.
- Focus order is not changed by data loading; skeleton regions are not focusable and are replaced in place.

### 11.4 Motion
- The product has almost no motion by design. The only motions are: the dial needle rotation (200 ms ease-out, on date change), the skeleton pulse (1.2 s opacity), and the Toast fade.
- With `prefers-reduced-motion: reduce`: the needle jumps, skeletons are static, and the Toast appears and disappears without a fade. No parallax, no auto-playing animation, and no animation lasts more than 5 seconds.
- There are no flashes (nothing flickers more than three times per second).
- No celebratory animation on a pick, ever.

### 11.5 Screen readers and semantics
- Landmarks: `header` (banner), `nav` (primary), `main`, `footer` (contentinfo). One `h1` per route; headings do not skip levels. Each card is an `article` (or list item in a list) labeled by its ticker heading.
- Page title and `lang="en"` are set. Numbers keep their format in text: "78.4", "212.40".
- Labels:
  - Ribbon: `role="img"`, `aria-label` such as "Up 14 sessions, flipped 3 sessions ago" (rules in 5.1).
  - ScoreDial: `role="img"`, `aria-label` such as "Score 78.4 out of 100, band Buy".
  - BuySellMark: the shape is `aria-hidden="true"` and the word is real text, so the label is read once.
  - FactorBar: a text row such as "Supertrend, contribution plus 23.4, score 100, weight 23.4". The bar graphic is `aria-hidden`; the printed value is the accessible content. The minus sign is announced as "minus" using visually hidden text ("minus 4.2") alongside the visible "-4.2".
  - Data tables use `<table>`, `<caption>`, `<th scope>`; sortable headers expose `aria-sort`; stacked phone cards use `role="list"` and `listitem`.
  - Chart: the canvas has `role="application"` with `aria-label` "Price chart for ORCL, daily, end of day data as of 2026-11-13. Press Tab to reach the table alternative." plus the live region mirror of the cursor tooltip, and the "View as table" button directly before the chart.
  - Icons are decorative (`aria-hidden`) when a word accompanies them; otherwise they have an `aria-label`.
- Live regions:
  - StaleBanner and Toast use `role="status"` (polite).
  - Run progress uses `aria-live="polite"` and announces each state change once ("Run state: scoring").
  - Errors in forms use `aria-describedby` on the field and `role="alert"` only for validation errors after a submit.
  - Loading regions use `aria-busy="true"`.
- Tooltips are available on focus and do not hold information found nowhere else (WCAG 1.4.13: dismissible, hoverable, persistent).
- Disclosures use real buttons with `aria-expanded` and `aria-controls`.
- Links have descriptive text ("Details for ORCL", not "Details" alone, via visually hidden text where the visible text is short).
- Language: reading level is plain; abbreviations are expanded on first use per page or via `<abbr>` (ATR, RSI, MACD, SMA).

### 11.6 Forms and input
- Every input has a visible label (not placeholder only). Required and format hints are text. Errors are text, identify the field, and say how to fix it. Autocomplete attributes are set where relevant (the token field uses `autocomplete="off"`).
- Redundant entry is avoided: the selected date and group persist across screens within a session.
- Authentication has no cognitive test: the token field supports paste and password managers (WCAG 3.3.8).

### 11.7 Responsive and zoom
- Content reflows at 320 CSS px wide with no horizontal scroll for the page (tables use their stacked phone layout or a labeled scroll region). Zoom to 200 percent works at every breakpoint. Text spacing overrides do not break layout. Pinch zoom is never disabled. Orientation is not locked.

### 11.8 Verification
- axe (jest-axe in component tests, Playwright axe in e2e) on every route, both themes.
- Playwright: keyboard-only walkthrough of Today, Ticker, Watchlist, Runs; grayscale screenshot comparison for Today; reduced-motion run; 200 percent zoom run; 320 px width run.
- Manual: a screen reader pass (one desktop, one mobile) at each release.

---

## 12. Anti-patterns

### 12.1 From the seed (must not appear)

- Green and red as the only signal of direction.
- Confetti, rockets, flames, "to the moon" language, or any celebratory animation on a pick.
- Certainty language: "guaranteed", "sure thing", "can't lose", "will go to".
- Hidden losers: any view of past picks that omits or de-emphasizes the misses.
- Gradients on data, 3D charts, pie charts for anything.
- Auto-refreshing layout shifts. Data refreshes in place.
- Modal dialogs for reading content. Modals only confirm destructive or token-gated actions.
- A fake "live" feel. Super Trends is an end-of-day product; every number shows its as-of date.

### 12.2 Additions

Honesty and compliance:
- Padding a side to reach 3 buys or 2 sells, or showing a "top 5" when fewer qualify.
- A confidence value, invalidation level, or disclaimer that is hidden, collapsed, in a tooltip, or reduced below its stated contrast.
- Showing "order flow" without the word "estimated", or implying the real order book is visible.
- Showing a statistic without its sample size, or a sample under 20 without "Small sample".
- Showing backtest numbers without the "Hypothetical" label.
- Showing a probability of profit, a price target beyond the evidence's next target, a "conviction" meter, star ratings, or a "win rate" headline without the horizon, benchmark, and sample size.
- Any "Buy now", "Trade", "Place order", or brokerage button; any position size, options strike or expiry, leverage, stop size, or account field.
- Asking for holdings, account size, risk tolerance, or goals.
- Editing, deleting, re-sorting by default away from, or re-ranking published picks. The group filter re-ranks a view, never the published picks.
- Showing a narrative as authoritative when it is template text, or hiding which source wrote it.
- Displaying scores for tickers excluded for stale or insufficient data.
- Any public sharing feature, social share button, or export of picks.
- Calling the project anything other than source-available and free for noncommercial use.

Visual and interaction:
- A second saffron shape on a pick card besides the needle (focus rings and 1 px flip ticks excepted).
- Red-to-green gradients, heat-map fills on score tables, glow, drop shadows, or neon.
- Flashing, ticking, or blinking values; countdown timers; "last updated 2 seconds ago".
- Skeletons or spinners that differ in size from the final content; content jumping when data arrives.
- Toasts that cover the disclaimer, auto-dismiss errors, or are the only place an error appears.
- Infinite scroll on tables (use bounded "Load more").
- Disabling pinch zoom, locking orientation, or text under 12 px.
- Rendering LLM output as HTML or Markdown, or linking from narratives.
- Rendering any secret, token, or key, or echoing a saved token back into a field.
- Loading fonts, scripts, images, or analytics from any external origin.
- Truncating tickers, scores, or levels with ellipses when space is tight. Reflow instead.
- Icon-only controls without an accessible name.
- Hover-only information.
- Dark patterns around the token prompt or the "Remember in this browser" option (it is unchecked by default).

Language:
- Hype words ("game-changer", "revolutionary", "explosive", "skyrocketing", "crushing it") and em dashes in any UI copy or generated narrative.
- Predictive phrasing in static copy ("will rise", "expected to rally"). Use conditional, evidence-based wording such as "the Supertrend is up and the view is wrong if price closes below 212.40".
