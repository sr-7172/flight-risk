# PRESENTATION — Flight Risk: a revealed-behavior geoeconomic indicator

HUMAN-OWNED FILE. Edit freely; agents never rewrite content here (a confirmed
filename fix is the only exception). Artifact names you list below drive
MIN_SCRIPTS.md via `code/sync_min_scripts.py` / the sync-min-scripts skill.
Artifacts that don't exist yet are the deck's wish list — the tracer will
flag them UNRESOLVED until a round produces them.

Structure mirrors slides/seminar.tex (motivation → preview → data → raw
picture → strategy → results → threats → conclusion). One `##` per slide
block; bullets are the content; `→` lines name the artifact(s) behind them.

## 1. Motivation (1–2 slides)
- Existing geopolitical-risk measures are textual (GPR, news counts): English-language bias, low frequency, not bilateral, media attention ≠ economic exposure.
- Airlines price geopolitical risk with aircraft, fuel, and insurance — routing is a costly, revealed-preference signal, machine-readable and language-free.
- This paper: a bilateral, high-frequency indicator from *excess airborne time* on directed routes, by operator nationality.

## 2. Preview of results (1 slide)
- The indicator flags documented airspace closures with no text input; carrier-nation asymmetry identifies *bilateral* disruptions.
- → `fig_headline_index_timeline.png`

## 3. Data (1–2 slides)
- Phase 1: BTS T-100 international segments, monthly, 1990–present; airborne time and departures by carrier × directed segment.
- Phase 2 (validation era): OpenSky ADS-B, daily, 2019–2022, with FIR-transit ground truth.
- → `tab_data_coverage.tex`, `desc_sample.csv`

## 4. The raw-data picture (before any regression)
- Air China vs. US carriers, US–East Asia airborne times around Feb 2022: the wedge is visible in raw monthly means.
- → `fig_raw_wedge_useastasia.png`

## 5. Construction (1 slide, "estimating equation")
- Excess time = actual airborne time − trailing 3-year same-calendar-month median (directed route × operator nation).
- Event = excess persists ≥ 1 month; classified symmetric (all nations shift) vs. asymmetric (wedge) — asymmetric is the bilateral signal.
- Bidirectional sum cancels jet-stream regimes (winds are antisymmetric, detours are not).
- → `fig_construction_schematic.png`

## 6. Results, one per slide
- Validation: excess-time events vs. FIR-transit ground truth, 2019–2022 — timing, location, carrier incidence, minutes-per-km-of-detour calibration.
- → `tab_validation_mapping.tex`, `spec_validation.csv`
- Event studies around the documented-closure dictionary (1990–2025).
- → `fig_event_study_closures.png`, `spec_event_study.csv`
- The historical index, 1990–present, with named episodes.
- → `fig_index_1990_2025.png`, `index_monthly.csv`

## 7. Identification threats, each with a defense slide
- Winds/seasonality → bidirectional cancellation + calendar-month baseline. → `fig_wind_placebo.png`
- Fleet/aircraft-type changes → within route × carrier; validation-era type controls. → `spec_fleet_robustness.csv`
- Exit censoring (worst closures kill routes) → extensive-margin indicator alongside. → `fig_exit_margin.png`
- T-100 foreign-carrier reporting gaps → coverage audit by operator nation. → `tab_coverage_audit.tex`

## 8. Conclusion
- A non-textual, bilateral, high-frequency indicator; validated against physical ground truth; extendable to 1990.
