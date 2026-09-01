# PROJECT BRIEF — Flight Risk: a revealed-behavior bilateral geoeconomic indicator

The director's authority ends at the edges of this document: anything not
covered here, or any change to the starred sections after results exist,
becomes a DECISION-PENDING entry rather than an autonomous call. Read the
"Ambition and phasing" section first: the starred definitions below pin
down the *current phase*, not the project's ceiling.

## Research question

Can commercial-flight operating behavior — no trajectories, no text —
identify, date, and quantify bilateral geoeconomic disruptions (airspace
closures, overflight bans, sanction-driven avoidance, risk-priced
rerouting)? The broad program: build a directed, country-pair-level,
high-frequency, language-free indicator of geoeconomic tension from
revealed airline decisions, validate it against physical ground truth, and
establish it as a measurement contribution usable across international
finance and macro. Existing geopolitical-risk measures are textual
(GPR-style news counts): English-language-biased, attention-driven, and
poorly bilateral. Airlines reveal *priced* risk through costly routing
decisions, continuously, in every language.

## Ambition and phasing

The end goal is a top-general-interest measurement paper (AER/QJE-level
standard: a new indicator, validated, with at least one substantive
application). The present work is **Phase 1: a scoped proof of concept**
— medium frequency, a deliberately minimal feature set (directed route,
operating time, operator nationality) — whose purpose is to establish
whether the times-only signal exists and is interpretable before
professionalizing. Later phases are pre-authorized as directions the
director may plan toward and propose (with DECISION-PENDING memos where
they touch starred sections), not scope creep:

- **Phase 2 — validation era.** Daily frequency from ADS-B (OpenSky)
  2019–2022; FIR-transit ground truth; calibration of minutes-of-excess to
  km-of-detour; mandated-vs-discretionary decomposition (actual minus
  scheduled block time).
- **Phase 3 — professionalization.** Richer features when they earn their
  place (aircraft type, scheduled block time, wind reanalysis, fuel
  prices); global coverage beyond US-touching pairs via Eurocontrol,
  commercial OOOI data, or Zenodo flightlists; a country-pair index with
  published construction and release cadence.
- **Phase 4 — applications.** Asset-price, trade, FDI, or sovereign-spread
  responses to the indicator; comparison and horse-race against GPR and
  other text measures; forecasting content.

Nothing in the phase list is binding on sequence. The director may
recommend accelerating a later-phase element if Phase-1 evidence makes it
the natural next step.

## Headline outcomes & sample — current phase (*)

- **Unit of observation:** directed route (origin airport → destination
  airport, kept directional) × operator nationality (ICAO state of
  operator) × month (Phase 1) / × day (Phase 2).
- **Outcome 1 — excess airborne time:** mean actual airborne minutes per
  departure minus baseline, where baseline = median of the same directed
  route × operator-nation cell in the same calendar month over the
  trailing 3 years (≥ 2 obs required; else cell excluded and logged).
  T-100: airborne is headline, ramp-to-ramp is a robustness column.
- **Outcome 2 — disruption indicator:** excess time above threshold
  (default > 2 × within-cell trailing MAD; sensitivity grid 1.5×, 3×)
  persisting ≥ 1 consecutive month (Phase 1) / ≥ 7 consecutive days
  (Phase 2), classified **asymmetric** (operator-nation wedge on the same
  route) vs **symmetric** (all nations shift together).
- **Outcome 3 — bidirectional sum:** excess(A→B) + excess(B→A), the
  wind-cancelling version; headline for corridor-level results.
- **Extensive margin:** route exit/entry logged as its own indicator,
  never silently dropped; exits during flagged episodes are top-coded
  disruption in the index.
- **Sample, Phase 1:** BTS T-100 international segment data, monthly,
  1990–2025, nonstop segments, scheduled passenger + combi (freighters
  as robustness). COVID window 2020-03 to 2021-12 excluded from baseline
  windows and flagged in every event table.
- **Sample, Phase 2:** OpenSky-derived daily panel, 2019-01-01 to
  2022-12-31; corridors US/Europe–East Asia and US–Middle East to start.
- Extending frequency, corridors, or the feature set beyond these is
  expected eventually and is a DECISION-PENDING memo, not a refusal.

## Data sources & access

- `data/raw/t100/` — BTS T-100 international segment CSVs (public,
  downloaded by the human; agents never fetch the web). Missing → BLOCKED.
- `data/raw/opensky/` — parquet extracts pulled via pyopensky/Trino in
  attended sessions; credentials in `~/.config/pyopensky/settings.conf`
  (restored from the secrets volume — see README). Unattended runs treat
  missing extracts as BLOCKED, never query live.
- `data/raw/events/closures.csv` — human-curated documented-closure
  dictionary (dates, countries, type, source); volcanic events from the
  Smithsonian GVP list, also human-curated.
- Anticipated later: Eurocontrol R&D archive sample months; Zenodo
  OpenSky flightlists; Cirium/OAG OOOI extracts (purchase decisions are
  the human's); ERA5 winds. Each enters via `data/raw/<source>/` with a
  README noting provenance and date pulled.
- No WRDS in this project.

## Identification menu (*)

Priority-ordered for Phase 1; items 5–8 are pre-authorized for later
phases so the director can plan toward them without a scope question.

1. Raw-data pictures and monthly means: the carrier-nation wedge on
   US–East Asia routes around 2022-02, before any regression.
2. Event studies around the documented-closure dictionary: excess time by
   event month, exposed vs unexposed operator nations (canonical DiD /
   event-study figures).
3. The persistence × symmetry classifier (Outcome 2) run blind over the
   full panel; precision/recall against the closure dictionary, reported
   as a full family across the threshold grid.
4. Validation-era mapping (2019–2022): excess airborne time on
   trajectory-derived detour distance and FIR-avoidance flags; the
   minutes-per-100km calibration and the classifier's confusion matrix
   against FIR ground truth.
5. Alternative-sample corroboration: Eurocontrol sample months, Zenodo
   flightlists, commercial OOOI data (BLOCKED until files exist).
6. Actual-vs-scheduled decomposition (discretionary vs mandated avoidance)
   once scheduled block times are in data/raw/.
7. Feature-expansion tests: does adding aircraft type / winds / fuel price
   change the index materially? Reported as fragility, not as a menu.
8. Applications: responses of sovereign spreads, bilateral trade, or
   equity indices to indicator innovations; horse-race vs GPR.

## Known pitfalls / domain cautions

- **Winds:** jet-stream regimes shift transpacific times ±30–75 min and
  persist for weeks; never interpret single-direction excess as
  disruption without the bidirectional sum or calendar-month baseline.
- **COVID:** 2020–21 breaks every baseline; excluded per above, and any
  event flagged 2020-01–2022-01 carries a COVID-WINDOW flag.
- **T-100 reporting:** foreign-carrier air-time fields have gaps and
  occasional imputation; run the coverage audit (nonmissing airborne
  share by operator nation × year) BEFORE any headline table; cells
  failing coverage gates are excluded and listed, not imputed.
- **Operator nationality** = ICAO state of operator, never marketing
  carrier; codeshares/wet leases misclassify — use the operating-carrier
  code in T-100 and the ICAO operator prefix in OpenSky callsigns.
- **Aircraft-type composition:** type swaps change airborne time; log
  fleet-mix shifts within cell as a diagnostic.
- **Exit censoring:** the worst disruptions kill routes; the extensive
  margin is a first-class output, not missing data.
- **Monthly masking:** Phase-1 frequency cannot date sub-month events;
  never claim daily dating from T-100.
- **US-touching only (Phase 1):** frame all Phase-1 claims accordingly.

## Decision defaults

Directed segments always; winsorize excess time at 1/99 within
route × direction (formulas in desc_outcomes.csv); default clustering by
route; SE menu {HC1, cluster-route, cluster-country-pair, wild bootstrap
over country-pair when pairs < 30}; FE structure route × operator-nation
and calendar-month; missing airborne time never imputed. The
econometrician applies these without asking; deviations need a
task-level instruction in the round file.

## Exploration stance (replaces kill criteria)

There are no kill criteria in this project. Disappointing evidence —
the classifier missing a known episode, a weak validation fit, thin
coverage — is a *finding to characterize*, not a verdict to act on:
document it fully (which thresholds, which corridors, which years), park
the thread with a post-mortem in RESEARCH_LOG.md and the round's
FINDINGS, and keep exploring the menu. Threads are parked, never closed;
the director may reopen any parked thread when new data or a new phase
makes it live again. Standing rule 10 still applies: no re-specification
aimed at manufacturing significance — but variation aimed at
*understanding* a null (where does the signal appear, where doesn't it,
and why) is exactly the exploration this stance wants.

## Out of scope for the director

Data purchases (Cirium/OAG quotes), Eurocontrol/DDR application strategy,
co-author strategy, venue targeting, any live web fetching during
unattended runs. Proposing these is welcome as DECISION-PENDING memos.
