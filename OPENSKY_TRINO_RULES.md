# OPENSKY TRINO RULES (Part 0b — binding for every agent, every session)

Incorporated by reference into STANDING_RULES.md. Never weakened by a round
file. Source: https://opensky-network.org/data/trino (read 2026-09-01).
OpenSky states plainly that repeated failure to follow the performance
guidelines results in the user's IP being blocked and access revoked. A ban
ends the project's Phase-2 data access. These rules therefore outrank
task completion: a task that cannot be done within them is BLOCKED, never
worked around.

## What OpenSky requires (verbatim-in-spirit from their guidelines)

- ALWAYS filter on the partition column in the WHERE clause: `hour` for
  most tables (state_vectors_data4 etc.), `day` for flights_data4/5.
  Filtering on `time` alone is insufficient and causes a full-table scan.
  Their page addresses LLMs directly on exactly this point.
- Prefer many small queries over one large one: target a limited
  partition range per query.
- Concurrency: max 2 concurrent + 2 queued queries per user; global
  limits also apply.
- A query running > 5 minutes must be reduced (smaller time frame /
  batching). Hard maximum query length is 30 minutes INCLUDING queue time.
- Bulk multi-full-day downloads: contact OpenSky for an alternative, do
  not hammer Trino.
- Stuck/unintended queries must be killed in the Trino web UI (filter by
  username → KILL).
- Known lost-data periods (UTC) must be excluded from research:
  2023-01-02 23:00→2023-01-03 10:00; 2023-01-18 11:00→2023-01-23 07:00;
  2023-06-21 13:00→2023-06-21 22:00; 2023-11-15 06:00→2023-11-16 08:00;
  2023-11-20 01:00→2023-11-20 03:00; 2023-12-02 08:00→2023-12-05 03:00;
  2024-05-20 10:00→2024-05-21 05:00.

## Binding rules for agents (T1–T9)

- **T1 — One door.** All Trino access goes through `code/opensky_query.py`
  (`OpenSkyClient`). No script imports `pyopensky`, `trino`, or `traffic`
  directly, and no agent invokes the `trino` CLI (denied in settings).
  `code/98_check_trino_usage.py` FAILs the round if either happens.
- **T2 — Partition filter is enforced by code.** The wrapper refuses to
  send SQL that lacks an equality/BETWEEN/IN predicate on the partition
  column for EVERY table referenced (`hour` for hour-partitioned tables,
  `day` for flights_data4/5). No agent may edit, bypass, or monkey-patch
  the guard. If the guard rejects a query, the query is wrong.
- **T3 — Small partitions.** Default caps: ≤ 6 hours of `hour` partitions
  per query on state-vector-type tables; ≤ 7 days of `day` partitions on
  flights tables. Longer windows go through `run_chunked()`, which issues
  one query per chunk sequentially with a pause between chunks. Raising a
  cap needs a DECISION-PENDING memo and human approval — never a silent
  edit.
- **T4 — Bounded queries.** State-vector queries must also carry a row
  bound beyond the partition: an `icao24`/`callsign` list or a lat/lon
  box. Unbounded pulls of a full partition are refused unless the caller
  passes `allow_unbounded=True`, which itself requires a round-file
  instruction quoting this rule.
- **T5 — Serial, polite, and one at a time.** The wrapper runs at most ONE
  query at a time per process, and there is at most one process querying
  Trino at any time in this project. Never parallelize with threads,
  subprocesses, or multiple sessions. No retry storms: on error, back off
  (60 s, then 5 min), retry at most twice, then BLOCKED.
- **T6 — Time budget.** Soft limit 5 minutes per query (logged WARNING and
  the chunk size must be halved before the next chunk). Hard limit 25
  minutes wall clock: the wrapper stops waiting, the agent STOPS issuing
  queries, records BLOCKED, and tells the human to kill the query in the
  Trino UI. Never leave a running process behind (T5).
- **T7 — Cache first, never re-pull.** Every result is written to
  `data/raw/opensky/<query-hash>.parquet` with a sidecar `.sql` file; the
  wrapper returns the cached result if it exists. Re-running a script must
  never re-hit Trino for data already on disk.
- **T8 — Attended only.** Unattended runs (/overnight, /run-analysis)
  never query Trino: they read `data/raw/opensky/` and mark tasks BLOCKED
  if extracts are missing. Live pulls happen only in an attended session
  where the human has explicitly asked for a pull in this conversation.
- **T9 — Lost periods excluded; audit trail kept.** The chunker skips the
  lost-data periods above and logs the skips; every SQL sent, with
  timestamp, duration, row count, and cache path, is appended to
  `logs/opensky_queries.log`. The overseer reads this log at round close.

## What "efficient" looks like (canonical patterns)

- Flight list for a corridor: `flights_data4 WHERE day = <unix-midnight>`
  plus `estdepartureairport IN (...)` / `estarrivalairport IN (...)`, one
  query per day, chunked.
- Trajectory for a known flight: `state_vectors_data4 WHERE hour BETWEEN
  <dep-hour> AND <arr-hour> AND icao24 = '<hex>' AND time BETWEEN
  <firstseen> AND <lastseen>`; the `hour` bound is mandatory even though
  `time` is present.
- FIR-transit flags: pull the trajectory once (cached), compute FIR
  crossings locally from the parquet — never re-query to recompute.
