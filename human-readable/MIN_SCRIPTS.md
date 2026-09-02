# MIN_SCRIPTS — generated 2026-09-02 06:01:45 by code/sync_min_scripts.py

Minimum set of python scripts needed to reconstruct every artifact
named in human-readable/PRESENTATION.md. Do not hand-edit; rerun
`uv run python code/sync_min_scripts.py` (or invoke the
sync-min-scripts skill) after editing PRESENTATION.md.

## Minimal script set (pipeline order)

- `code/utils.py`
- `code/01_ingest/00_bootstrap_manifest.py`
- `code/01_ingest/01_ingest_t100.py`
- `code/02_build/02_carrier_nation.py`
- `code/03_audit/03_coverage_audit.py`
- `code/04_panel/04_build_panel.py`
- `code/05_outcomes/05_build_excess.py`
- `code/06_wedge/06_wedge_availability.py`

## Per-artifact trace

### `fig_headline_index_timeline.png`
- located: **NOT FOUND under rounds/**
- producer script(s): **NONE FOUND**

### `tab_data_coverage.tex`
- located: **NOT FOUND under rounds/**
- producer script(s): **NONE FOUND**

### `desc_sample.csv`
- located: `rounds/round-1-t100-panel/desc_sample.csv`
- producer script(s): `code/04_panel/04_build_panel.py`
- upstream: `code/01_ingest/00_bootstrap_manifest.py`, `code/01_ingest/01_ingest_t100.py`, `code/02_build/02_carrier_nation.py`, `code/03_audit/03_coverage_audit.py`, `code/05_outcomes/05_build_excess.py`, `code/06_wedge/06_wedge_availability.py`

### `fig_raw_wedge_useastasia.png`
- located: **NOT FOUND under rounds/**
- producer script(s): `code/06_wedge/06_wedge_availability.py`
- upstream: `code/01_ingest/00_bootstrap_manifest.py`, `code/01_ingest/01_ingest_t100.py`, `code/02_build/02_carrier_nation.py`, `code/03_audit/03_coverage_audit.py`, `code/04_panel/04_build_panel.py`, `code/05_outcomes/05_build_excess.py`

### `fig_construction_schematic.png`
- located: **NOT FOUND under rounds/**
- producer script(s): **NONE FOUND**

### `tab_validation_mapping.tex`
- located: **NOT FOUND under rounds/**
- producer script(s): **NONE FOUND**

### `spec_validation.csv`
- located: **NOT FOUND under rounds/**
- producer script(s): **NONE FOUND**

### `fig_event_study_closures.png`
- located: **NOT FOUND under rounds/**
- producer script(s): **NONE FOUND**

### `spec_event_study.csv`
- located: **NOT FOUND under rounds/**
- producer script(s): **NONE FOUND**

### `fig_index_1990_2025.png`
- located: **NOT FOUND under rounds/**
- producer script(s): **NONE FOUND**

### `index_monthly.csv`
- located: **NOT FOUND under rounds/**
- producer script(s): **NONE FOUND**

### `fig_wind_placebo.png`
- located: **NOT FOUND under rounds/**
- producer script(s): **NONE FOUND**

### `spec_fleet_robustness.csv`
- located: **NOT FOUND under rounds/**
- producer script(s): **NONE FOUND**

### `fig_exit_margin.png`
- located: **NOT FOUND under rounds/**
- producer script(s): **NONE FOUND**

### `tab_coverage_audit.tex`
- located: `rounds/round-1-t100-panel/tables/tab_coverage_audit.tex`
- producer script(s): `code/03_audit/03_coverage_audit.py`
- upstream: `code/01_ingest/00_bootstrap_manifest.py`, `code/01_ingest/01_ingest_t100.py`, `code/02_build/02_carrier_nation.py`, `code/04_panel/04_build_panel.py`, `code/05_outcomes/05_build_excess.py`, `code/06_wedge/06_wedge_availability.py`

## UNRESOLVED (fix by reading scripts, then rerun)
- `fig_headline_index_timeline.png`
- `tab_data_coverage.tex`
- `fig_raw_wedge_useastasia.png`
- `fig_construction_schematic.png`
- `tab_validation_mapping.tex`
- `spec_validation.csv`
- `fig_event_study_closures.png`
- `spec_event_study.csv`
- `fig_index_1990_2025.png`
- `index_monthly.csv`
- `fig_wind_placebo.png`
- `spec_fleet_robustness.csv`
- `fig_exit_margin.png`

## AMBIGUOUS (multiple candidate producers — verify)
- none

