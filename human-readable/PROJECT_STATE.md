# PROJECT STATE — read this first (written for an undergrad RA)

AGENT-MAINTAINED: the director rewrites this file at every round close, in
this register — plain language, no jargon without a one-line explanation,
no result numbers typed by hand (numbers below are transcribed from round
CSVs, each with its source file named; the CSVs remain ground truth).

Last updated: 2026-09-02, at the close of Round 1
(`rounds/round-1-t100-panel/` — full story in `ROUND_01_FINDINGS.md`).

## What this project is, in one paragraph

When countries get into conflicts, they sometimes close their airspace to
each other's airlines — like when Russia banned US/EU airlines from flying
over Siberia in February 2022, so their Asia flights suddenly needed huge
detours and got hours longer, while Chinese airlines on the same routes
did not. Our idea: you can *measure* international tension by watching
flight times. If one country's airlines suddenly take longer on a route
and another country's airlines on the same route don't, something
political happened between specific countries. That gap, tracked over
time, is a "tension index" that updates constantly and doesn't depend on
reading news articles.

## How the measurement works (plain words)

1. For each route (like Chicago→Tokyo, direction kept) and each airline's
   home country, compute the normal flight time: the median over the past
   three years, same calendar month (winds are seasonal), skipping COVID
   months (March 2020–December 2021), and requiring at least two past
   observations.
2. "Excess time" = this month's average flight time minus that normal.
3. To cancel winds, add the excess of the return leg in the same month
   (the "bidirectional sum") — a headwind one way is a tailwind back.
4. Routes that *disappear* (airlines quitting a market) are tracked
   separately — the worst disruptions kill routes rather than lengthen
   them.

## What Round 1 found — the big one first

**The US government dataset we planned Phase 1 around cannot support the
core comparison.** The monthly BTS "T-100" data covers every flight
touching the US back to 1990, and US airlines report flight times almost
always. But foreign airlines **never report flight time: out of
1,133,545 foreign-carrier rows across all 36 years, exactly 0 contain a
positive airborne time** — every value is a literal zero, verified
straight from the raw files using BTS's own US/foreign field
(`coverage_by_carrier_group.csv`, the 36 rows with `carrier_group == 0`,
columns `n_rows` and `n_air_gt0` summed); volume fields like flights and
seats ARE reported. So "US airlines got slower on this route and Chinese
airlines didn't" is *unanswerable in this dataset* — not hard,
structurally absent. The pattern itself is beyond doubt and independent
of our download (re-downloading would return the same zeros); our
working explanation — that BTS's foreign-carrier reporting form simply
doesn't collect flight time — still needs to be checked against the
form's published spec in an attended web session.
Important nuance: our planned placebo (US–Europe routes, where no ban
applied) is exactly as empty as the treated routes — which tells us the
emptiness is about the data source, not about airline behavior.

What we DID build, all clean and reviewed:

- A verified ingest of all 36 years (2,662,470 rows, zero dropped —
  `ingest_rowcounts.csv`, columns `rows_read`/`rows_written`/
  `rows_dropped` summed over the 36 file rows).
- A route × airline-home-country × month panel, US-side flight times
  complete, with a guard ensuring foreign cells show "missing" and never
  a fake zero-minute flight (`panel_filter_log.csv`).
- The excess-time outcome for US carriers: well-centred (median
  winsorized excess 0.011 minutes — `desc_outcomes.csv`, row
  `excess_min_w`, `decade == all`, column `p50`), with every screening
  and clipping choice documented in its own CSV.
- A complete "who is observable where" map of the four corridors we care
  about, with a reason attached to every empty cell
  (`raw_wedge_by_corridor.csv`).

## The main problems now on the human's desk (full list in DECISIONS.md)

1. **Carrier nationality mapping is stuck on a split gate.** Mapping
   airline codes to home countries via the 2014 OpenFlights lookup
   passes our quality bar if you count "resolved to *some* country"
   (foreign match rate 0.9021) but fails it if you require the mapped
   country to be plausible (0.8631) (`carrier_nation_matchrate.csv`, row
   `category == foreign`, columns `match_rate_weighted` and
   `precision_adjusted_match_rate_home0`) — and the pass is knife-edge,
   resting on the least reliable matching tier
   (`carrier_nation_gate_sensitivity.csv`, rows
   `coverage_margin_over_g7_min` and `coverage_excl_icao_tier`).
   Real errors found: Air Canada rouge mapped to "Iran", a Canadian
   regional mapped to "Russia", Norse Atlantic mapped to "Argentina",
   and Asiana not mapped at all. The human must pick which reading
   governs, or supply a better, dated lookup.
2. **What is Phase 1 now?** Four options, none pickable by agents because
   each changes the paper's stated sample/outcome: (A) re-scope the
   T-100 work to the extensive margin and volume (foreign carriers do
   report those); (B) a US-only design comparing US carriers' routes by
   exposure to the closed airspace; (C) accelerate Phase 2 — the OpenSky
   plane-tracking data, which observes *everyone's* airborne time
   regardless of BTS forms — to be the primary source; (D) buy/acquire a
   data source with foreign flight times. Conservative default until the
   human rules: keep building what is observable, claim nothing beyond it.
3. **The excess measure blacks out during the event itself.** The
   three-year, COVID-skipping baseline can't be computed for
   March–December of 2022 *and* of 2023 (two ten-month gaps — January and
   February of each year survive; `baseline_failures.csv`,
   `granularity == 'month'` rows for 2022–2023, column
   `n_excess_computed` = 0 in all 20 blackout months). Fixing this
   means changing the baseline rule, which is a human call, not ours.

## Dead ends and parked threads (so you don't redo them)

- **Foreign flight times in T-100:** parked permanently for time-based
  outcomes; no mapping fix, estimator, or re-download helps. Volume
  fields are fine.
- **The carrier-nation wedge at monthly frequency:** parked until a
  source with foreign times exists (OpenSky is the candidate).
- **The z-scored excess (`excess_z`):** unusable — its denominator is a
  spread estimated from at most 3 numbers, so it explodes at random
  (5,904 cells with |z| > 100; `excess_construction_diagnostics.csv`,
  row `n_excess_z_abs_gt_100`). Needs a redesigned dispersion
  measure before the disruption classifier can run.
- **Raw entry/exit flags as "market exit":** 78.8% of flagged exits
  are followed by re-entry on the same route — it's mostly seasonal
  schedules, not exits (`extensive_margin_churn.csv`, row
  `share_exits_reentering_ever` = 0.788126). Use a
  consecutive-months ("spell") definition before any event study.
- **Naive means over raw T-100 `AIR_TIME`:** the source writes zeros, not
  blanks, for foreign carriers — any unguarded average silently invents
  zero-minute flights. The panel's guard exists for this reason.

## What's next

- The human answers the three decisions above (the round folder holds all
  the evidence; nothing more is needed to decide).
- Most pressing agent-side recommendation: start the attended OpenSky
  extract request (Phase-2 data) — it is now the only path to the
  project's central comparison.
- Plannable meanwhile: spell-based exit measures, US-only raw corridor
  pictures around February 2022, and a list of small figure/caption
  fixes before anything enters the paper.
- Full prioritized list: `rounds/round-1-t100-panel/ROUND_01_FINDINGS.md`,
  section "Suggested next steps".
