# DECISIONS (director, append-only)

One entry per judgment call: the fork, the options, the choice, the
reasoning, and its state (DECIDED or DECISION-PENDING (human)).

NOTE ON TYPED NUMBERS: entries below cite result numbers inline with
`(file.csv, row/spec)`-style traces because a decision packet needs its
evidence in front of the decider. Standing rule 5's sanctioned exception
names only ROUND_NN_FINDINGS.md and PROJECT_STATE.md; whether it extends
to this file and RESEARCH_LOG.md is itself D-06 below. If the human
rules no, the numbers will be replaced by pointers.

---

## D-01 — Which reading of G7 (mapping precision gate) governs; lookup replacement — DECISION-PENDING (human)

**Fork.** G7 requires a departures-weighted carrier→nation match rate
≥ 0.90 among foreign carriers. Two defensible readings disagree on this
drop: the *coverage* reading (code resolved to some candidate) passes at
0.9021; the *precision-adjusted* reading (mapped nation plausible given
the carrier's own observed traffic) fails at 0.8631 (0.8440 stricter)
(carrier_nation_matchrate.csv, row `foreign`). The coverage pass is
knife-edge: margin 41,643 departures, smaller than the 47,345 departures
carried by the `icao` tier whose home-zero share is 0.4938; excluding
that tier alone flips the verdict (carrier_nation_gate_sensitivity.csv;
carrier_nation_tier_precision.csv).

**Options.** (a1) G7 = coverage → FIX-02 unblocks, accepting in writing
that mapped RU/IR are built on Canadian carriers (KV, RV) and ~4–6% of
matched foreign departures sit on implausible codes. (a2) G7 = precision
→ FIX-02 stays blocked until the lookup is replaced or dated.
(a3) coverage gate with named low-precision strata excluded (icao tier;
home-zero codes) and the exclusion logged — the option the evidence best
supports, per the overseer. Note: part of (a3) is already in force
downstream as a conservative default — the shipped FIX-04 panel drops
the `icao` tier (347 rows; panel_filter_log.csv, row `icao_tier_dropped`)
under the overseer's ruling. That default does not resolve the gate and
does not pre-commit the human's answer. Independent second question: may a dated
carrier-nationality source (ICAO Doc 8585, BTS carrier decode, OAG)
replace `data/raw/lookups/airlines.csv` (2014 OpenFlights, undated,
corrupted `country` values, direct cause of every defect found)?

**Choice.** None — standing rule 4 forbids agents picking between
disagreeing readings of a gate; three review cycles were exhausted making
the blocked package decision-grade. **Conservative continuation applied:**
downstream tasks built on matched carriers only, icao tier dropped,
precision flags carried, nation-level reporting embargoed, RU/IR labelled
MATCH-SENSITIVE, corridor 1 / ICN computed but not reported.

**State.** DECISION-PENDING (human). Evidence packet:
carrier_nation_*.csv in `rounds/round-1-t100-panel/`.

---

## D-02 — Phase-1 re-scope given that T-100 has no foreign airborne time — DECISION-PENDING (human)

**Fork.** The round established that the Phase-1 headline outcome (excess
airborne time by operator nationality) is structurally unobservable for
every non-US operator in T-100: 0 of 1,133,545 foreign-carrier-group rows
1990–2025 report positive airborne time, with zero nulls
(coverage_by_carrier_group.csv); 0 of 908 non-US anchor-corridor cells
pass G6, treated and placebo alike (coverage_by_corridor.csv). This is a
BTS reporting-schedule property, independent of and larger than D-01: a
perfect mapping changes nothing. The Phase-1 design as written in
PROJECT.md's starred sections cannot be executed on this source.

**Options (all touch starred PROJECT.md sections; none pickable by an
agent under rule 11):**
- **(A) Extensive-margin re-scope.** Foreign carriers fully report
  volume (departures share_gt0 1.0, seats 0.8404, passengers 0.8355;
  coverage_column_availability.csv). The wedge could be redefined on
  service volume / entry-exit. Cost: changes the headline outcome; the
  raw entry/exit flags are ~79% seasonality and need a spell-based
  definition first (extensive_margin_churn.csv).
- **(B) US-only route-exposure DiD.** US carriers' airborne time is
  nearly complete (raw level 72/72 months on the East Asia and Europe
  placebo corridors; raw_wedge_by_corridor.csv); compare US routes by
  exposure to closed airspace. Cost: changes the identifying comparison
  from carrier-nation to route-exposure; loses the bilateral-index
  framing; excess outcome blacked out 2022-03+ (D-04).
- **(C) Accelerate Phase 2: OpenSky ADS-B as the primary Phase-1
  source.** ADS-B observes every operator's airborne time regardless of
  BTS forms; PROJECT.md pre-authorizes planning toward it. Cost:
  2019–2022 window only, attended extract work, T1–T9 discipline.
- **(D) Acquire a source with foreign-carrier block time** (Cirium/OAG
  OOOI, Eurocontrol). Purchase decisions are explicitly the human's
  (PROJECT.md, out of scope for the director).

**Choice.** None — recorded as DECISION-PENDING with the evidence above.
**Conservative default in force:** continue on what is observable
(US-side construction, availability documentation, volume-side
diagnostics), claim nothing beyond it, and treat the wedge thread as
PARKED, not dead. Director's note, not a decision: (C) is the natural
next step on the evidence — it is the only option that recovers the
project's central object — and starting the attended extract request is
recommended in ROUND_01_FINDINGS.md next steps regardless of which of
(A)/(B)/(D) is also chosen.

**State.** DECISION-PENDING (human).

---

## D-03 — Close Round 1 with FIX-02 blocked; adopt overseer embargo rulings — DECIDED

**Fork.** Whether to hold the round open on FIX-02 or close with it
BLOCKED-NEEDS-HUMAN after the maximum 3 cycles.

**Choice.** Close. Standing rule 7 sets the 3-cycle terminal state; the
overseer's rulings (FIX-03/04/05 may build on matched carriers with
exclusions logged; nation-level reporting embargoed; NEW-06 reduced to a
documented-availability deliverable) were followed and are ratified as
the round's operating constraints. All six other tasks are terminal with
PASS verdicts; nothing an agent can do unblocks FIX-02.

**State.** DECIDED (director, within STANDING_RULES; the underlying gate
question remains D-01).

---

## D-04 — Baseline-window rule vs the 2022–23 blackouts — DECISION-PENDING (human)

**Fork.** The trailing-3-year, COVID-excluded, ≥2-observation baseline
mechanically yields zero computable excess cells for every month in
2022-03…2022-12 and 2023-03…2023-12 (two ten-month blocks; Jan/Feb of
both years survive — baseline_failures.csv, month rows). The paper's
motivating event (2022-02) sits at the edge of the first block.

**Options.** Keep the rule and run any 2022 design on raw airborne
levels or the 2024–25 recovery; or adopt a modified baseline (longer
trailing window, donor months, pre-COVID reference years) — which is a
change to a headline outcome's construction after results are known
(rule 11).

**Choice.** None by agents; the rule was enforced, not relaxed, and the
blackout made visible and traceable. Conservative default: raw levels
for any event-window description, no modified baseline.

**State.** DECISION-PENDING (human).

---

## D-05 — Implied-speed screen threshold — DECISION-PENDING (human)

**Fork.** The shipped screen excludes cells implying < 50 mph. Dropping
cells implying < 150 mph removes 0.30% of cells carrying 58.7% of the
outcome's sum (pooled mean 0.0347 → 0.0144; full re-run 0.0209 —
excess_speed_screen_sensitivity.csv); the screen is also one-sided (117
cells > 700 mph unscreened). Threshold choice materially moves pooled
moments, so it is a gate-value change reserved to the human (rule 4 /
direction rule 4: proposing a changed gate value is a DECISIONS entry,
applied only in a future round).

**Options.** Keep 50 mph; adopt a two-sided physical-plausibility screen
(e.g. 150–700 mph) applied from the next round; or route-specific bounds.

**Choice.** None; the 50 mph screen ships with the full sensitivity
family reported. Director proposes evaluating a two-sided screen next
round *as a reported sensitivity*, adoption pending the human.

**State.** DECISION-PENDING (human).

---

## D-06 — May result numbers appear (with inline traces) in DECISIONS.md and RESEARCH_LOG.md? — DECISION-PENDING (human)

**Fork.** Standing rule 5 permits typed result numbers only in
ROUND_NN_FINDINGS.md and human-readable/PROJECT_STATE.md (with inline
CSV traces). This file and RESEARCH_LOG.md currently cite numbers
inline — every one audited correct and file-traced at round close — on
the reasoning that a decision packet needs its evidence in front of the
decider, and a research log needs magnitudes to be a usable record.
That is an extension of the sanctioned exception, not an application of
it, and it should not continue silently.

**Options.** (i) Extend the rule-5 exception to DECISIONS.md and
RESEARCH_LOG.md under the identical inline-trace requirement (a
STANDING_RULES.md wording change — human-owned). (ii) Rule no: numbers
in these two files are replaced by pointers to the FINDINGS sections and
CSVs that carry them, now and in future rounds.

**Choice.** None by the director — rule 5 is a standing rule and cannot
be weakened or extended by an agent. Current state disclosed in both
files' headers; the Round-1 entries stand as written pending the ruling
(replacing them is mechanical if the ruling is (ii)).

**State.** DECISION-PENDING (human).
