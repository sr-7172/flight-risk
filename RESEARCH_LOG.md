# RESEARCH LOG (director, append-only)

NOTE ON TYPED NUMBERS (explicit, per the round-close audit): this file
cites result numbers inline, each with a `(file.csv, row/spec)` trace.
Standing rule 5's sanctioned exception names only ROUND_NN_FINDINGS.md
and PROJECT_STATE.md; whether that exception extends to this file and
DECISIONS.md (with the same inline-trace requirement) is
DECISION-PENDING for the human (DECISIONS.md D-06). If the human rules
no, the numbers here will be replaced by pointers to the FINDINGS
sections that carry them.

## Round 1 — T-100 panel foundations and the raw wedge (closed 2026-09-02)

Tasks: FIX-00, FIX-01, FIX-03, FIX-04, FIX-05, NEW-06 DONE (overseer
PASS); FIX-02 BLOCKED-NEEDS-HUMAN (DEGENERATE-GATE, 3 cycles). Round
folder: `rounds/round-1-t100-panel/`. Narrative: `ROUND_01_FINDINGS.md`.

### Established

1. **Foreign carriers never report airborne time in T-100.** 0 of
   1,133,545 foreign-carrier-group rows 1990–2025 have `AIR_TIME > 0` or
   `RAMP_TO_RAMP > 0`; 0 nulls — literal zeros in all 36 files
   (coverage_by_carrier_group.csv, `carrier_group == 0` rows, summed).
   Volume fields are populated (departures share_gt0 1.0, distance 1.0,
   seats 0.8404, passengers 0.8355; coverage_column_availability.csv,
   `(foreign, *)` rows). US carriers in the same files: AIR_TIME
   share_gt0 0.9964 (row `(us, AIR_TIME)`). Verified from raw files via
   BTS's own CARRIER_GROUP, independent of the blocked mapping, and
   download-independent (reproduced by the overseer straight from the
   vendor files). The attribution to BTS's T-100(f) reporting schedule
   is an inference pending an attended check of the form's published
   data-element list. Consequence: Outcome 1 (excess airborne time) is
   structurally unobservable for every non-US operator; a perfect
   carrier-nation mapping changes nothing.
2. **Coverage gate G6 fails at maximal scale:** 2,213 of 2,249
   nation × year cells fail, all at exactly 0.0; the 36 passing cells are
   all US (coverage_audit.csv); 0 of 908 non-US anchor-corridor cells
   pass, treated and placebo identically (coverage_by_corridor.csv).
3. **G7 is split (FIX-02, unresolved by design):** coverage reading
   foreign 0.9021 passes, precision-adjusted 0.8631 (0.8440 at < 0.01)
   fails (carrier_nation_matchrate.csv, row `foreign`); class-F: 0.9303
   vs 0.8911 (row `foreign_classF`). Knife-edge: pass margin 41,643
   departures vs 47,345 departures on the icao tier at 0.4938
   home-zero share; excluding that tier alone → 0.8997, a fail
   (carrier_nation_gate_sensitivity.csv; carrier_nation_tier_precision.csv).
   Named mis-mappings: KV→RU (222,939 dep, home share 0.0), RV→IR
   (191,266, 0.0), TA→CR (347,572, 0.0038), VX(1)/B0/WO→US (35,168
   combined, 0.0), N0/Z0→AR, WPT→CA
   (carrier_nation_precision_audit.csv). Unmatched: 244 codes, 1,931,914
   departures, incl. Asiana OZ 204,972 → ICN foreign match 0.6753
   (carrier_nation_unmatched.csv; carrier_nation_corridor_coverage.csv).
   Reassuring null: 0 verified cross-border code reissues among 80
   name-churning codes (carrier_nation_flips.csv).
4. **US-only panel and outcomes built clean:** 1,026,729 cells, 517,076
   cell_ok, 100% US, 4,133 routes; structural-zero guard mutation-tested
   (panel_filter_log.csv; desc_sample.csv). Excess: 393,148 cells,
   winsorized median 0.011 / mean 0.035 / sd 8.20 min; bidir 389,446
   (desc_outcomes.csv, `decade == all`). Pooled mean is a
   near-cancellation of decade means (−0.111/+0.752/−0.412/−0.053;
   excess_speed_screen_sensitivity.csv, screen 50, decade rows) — not
   headline material.
5. **Two ten-month blackouts in the event window:** n_excess_computed = 0
   for every month 2022-03…2022-12 and 2023-03…2023-12; Jan/Feb of both
   years survive (1,156/1,162/1,169/1,170 cells); recovery 2024 (15,712)
   and 2025 (17,253) (baseline_failures.csv, month and year rows).
   Mechanical consequence of trailing-3yr + COVID bar + ≥2 obs. Rules not
   relaxed; rule-11 DECISION-PENDING (D-04).
6. **Fragilities on the record:** speed screen — dropping <150 mph cells
   removes 0.30% of cells and 58.7% of the outcome's sum (mean 0.0347 →
   0.0144; excess_speed_screen_sensitivity.csv, naive rows 50 vs 150);
   117 cells >700 mph unscreened. excess_z NOT-FOR-USE (5,904 cells
   |z|>100; excess_construction_diagnostics.csv). Extensive-margin flags
   ~79% seasonality (extensive_margin_churn.csv).
7. **NEW-06 is a documented null about the data:** 358 of 5,824 family
   rows have airborne values, all US; all 5,460 non-US rows empty with
   per-row reasons; diffs table all-NaN in 364/364 including the placebo
   (raw_wedge_by_corridor.csv; raw_wedge_diffs.csv). Raw US airborne
   level nearly complete (72/72 months on East Asia and Europe
   corridors) — raw material for a US-only event design.

### Threads parked (post-mortems)

- **Carrier-nation wedge on T-100 (menu item 1 as commissioned):** parked.
  Cause of death for this source: outcome absent for the entire
  comparison population, verified independently of the mapping; placebo
  equally empty, confirming a data property, not a behavioral null.
  Reopens if/when a source with foreign airborne time exists (OpenSky
  Phase 2, or purchased OOOI data).
- **Persistence × symmetry classifier (menu item 3):** parked twice over —
  the symmetry axis needs foreign times, and its MAD denominator
  (excess_z) is degenerate off ≤3 observations. Reopens with a
  commissioned dispersion measure and/or Phase-2 data.
- **Raw-flag extensive-margin event studies:** parked pending a
  spell-based exit definition (~79% of flagged exits re-enter).

### Binding uncertainty now

The human's rulings: (a) which G7 reading governs / lookup replacement
(D-01); (b) Phase-1 re-scope A–D given the missing foreign air time
(D-02); (c) baseline rule for the 2022–23 blackouts (D-04);
(d) speed-screen threshold (D-05). Until then the conservative default
holds: build only what is observable, report nothing nation-level, no
headline from this round. The single highest-value action available is
starting the attended Phase-2 OpenSky extract — ADS-B observes every
operator's airborne time regardless of BTS forms.
