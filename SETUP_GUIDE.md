# Setup guide (for a new user or RA)

This walks you from a blank laptop to a running autonomous research pipeline. No prior Docker or Claude Code experience assumed. Budget ~45 minutes the first time (most of it is downloads); every project after that takes ~5 minutes.

## What this pack is, in one paragraph

You describe a research project once (in `PROJECT.md`). Four AI agents then work in a loop inside an isolated container: a **director** decides what to analyze next and writes work orders; an **econometrician** implements them; an **overse er** adversarially audits every result against the raw output files; an **author** turns verified results into a LaTeX paper, beamer slides, and literature notes. A watchdog script restarts the loop if it stalls, and a set of hard-coded integrity rules (sanity gates, "numbers only from code", no re-specification chasing significance) keeps an unattended overnight run honest. Your job is: fill in the brief, launch, and review what came back.

## Part 1 — Install the tools (once per machine)

1. **A Docker engine** — either Docker Desktop (docker.com) or OrbStack (orbstack.dev; the lighter, faster option on macOS — fully compatible, nothing else in this guide changes). Install and open it once so the engine is running. (The agents run inside a container: they cannot touch anything on your laptop outside the project folder.) Note the two shared volumes in Part 2 live inside whichever engine you pick, so do the one-time secrets setup after settling on one.
2. **VS Code** — download from code.visualstudio.com.
3. **VS Code "Dev Containers" extension** — in VS Code: Extensions sidebar → search "Dev Containers" (publisher: Microsoft) → Install.
4. **A Claude subscription** (Pro or Max) or an Anthropic API key — Max is strongly recommended; unattended runs burn a lot of tokens.
5. **An OpenSky Network account** with historical/Trino access approval, if the project pulls OpenSky data (this one does).
6. Optional but recommended: the **ntfy** app on your phone (ntfy.sh). Pick any hard-to-guess topic name, e.g. `sasha-research-8k2q`. The pipeline pings this topic when a run finishes or gets stuck.

## Part 2 — First project setup

7. Make an empty folder for the project and unzip the pack into it. **Check the hidden files arrived**: the folder must contain `.claude/`, `.devcontainer/`, and `.gitignore` (on Mac press Cmd+Shift+. in Finder to show hidden files; or run `ls -a` in a terminal).
8. In a terminal, inside the folder:
   ```bash
   git init && git add -A && git commit -m "pack"
   ```
9. Open the folder in VS Code. A popup appears: **"Reopen in Container"** — click it. (If no popup: Cmd/Ctrl+Shift+P → "Dev Containers: Reopen in Container".) The first build downloads Python, LaTeX, and the Claude CLI — 5–15 minutes. Later builds are fast.
10. When the container is ready, open a terminal inside VS Code (Terminal → New Terminal) and store your secrets. **This step is once per machine, ever** — the secrets live in a Docker volume shared by all future projects:
    ```bash
    cat > ~/.secrets/pyopensky_settings.conf <<'CONF'
    [default]
    username = YOUR_OPENSKY_USERNAME
    password = YOUR_OPENSKY_PASSWORD
    CONF
    echo 'your-ntfy-topic' > ~/.secrets/ntfy_topic
    ```
    Then rebuild once so the credentials install: Cmd/Ctrl+Shift+P → "Dev Containers: Rebuild Container". OpenSky is only queried in attended sessions; overnight runs read the extracts you place in `data/raw/`.
11. Log in to Claude, also once per machine:
    ```bash
    claude
    ```
    and follow the browser login. Type `/exit` when done. Credentials persist across projects and rebuilds.

## Part 3 — Brief the agents

12. Put any vendor data files (PitchBook exports, etc.) into `data/raw/`. The agents treat this folder as read-only.
13. Fill in **`PROJECT.md`**. This is the most important 30 minutes of the whole setup: the research question, the sample, the outcomes, the identification strategies you'd allow, known data pitfalls, and the exploration stance (this pack has no kill criteria: weak results get characterized and parked, not used to shut down lines of inquiry). Everything the director is allowed to decide is bounded by this file; anything not covered becomes a "DECISION-PENDING" note for you rather than a guess.

## Part 4 — Launch a run

14. Launch. The one-liner arms the run (creates the gate flag), starts the watchdog, and kicks off the overnight campaign headless:
    ```bash
    chmod +x launch.sh && ./launch.sh overnight 3
    ```
    Prefer watching it in the panel? `./launch.sh arm` does the flag + watchdog only, then type the command yourself.
15. Or stage it manually in the Claude Code panel. The all-in-one overnight campaign is:
    ```
    /overnight 3
    ```
    This plans a round if none is pending, runs up to 3 rounds unattended, then (if a round closed cleanly) scans the literature, drafts the paper and slides, and leaves you a `MORNING_BRIEF.md`. If you'd rather stage it manually:
    ```
    /plan-round
    ```
    drafts `rounds/ROUND_01.md` for you to skim (at kickoff it will be data plumbing and diagnostics, deliberately: no headline regressions before the data passes its checks), then
    ```
    /run-analysis rounds/ROUND_01.md auto 3
    ```
    runs the analysis loop only, with no writing closeout. `auto 3` means: run this round, and let the director plan and run up to two more without you.
17. You'll get an ntfy ping when everything completes (or when the run is blocked and needs you). You can also just glance at `STATUS.md` any time.

## Part 5 — When you come back

If you launched with `/overnight`, start with **`MORNING_BRIEF.md`** — a one-page status: verdicts, pending decisions, blocked items, and what compiled. Then read, in this order:
- **the latest `rounds/round-NN-<slug>/ROUND_NN_FINDINGS.md`** — the round's story told for a coauthor with zero context, the scripts it touched, and its Suggested next steps (edit these bullets to steer the next round before you run /plan-round).
- **`human-readable/PROJECT_STATE.md`** — where the whole project stands, in plain words.
- **`RESEARCH_LOG.md`** — the director's terse for-the-record narrative: what was established, what died, what's uncertain.
- **`REVIEW_REPORT.md`** — the overseer's verdicts, including the "three results a referee will attack first".
- **`DECISIONS.md`** — anything marked DECISION-PENDING is a judgment call waiting for *you*.
- **`FINAL_RUN_LOG.md`** — the machine-generated results tables.

Then either edit PROJECT.md / answer the pending decisions and launch the next round, or move to writing:

- **`/lit-review hormuz war-risk premia`** (attended) — the author searches published and working papers, writes `docs/LIT_NOTES.md` with a NOVELTY-RISK flag on anything that's already been done, notes where each method comes from, and leaves you a 5-paper reading queue. One manual step first: web access is switched off for safety during unattended runs, so open `.claude/settings.json` and delete the two lines `"WebFetch",` and `"WebSearch"` from the `deny` list; put them back afterwards.
- **`/write-up both`** — the author drafts `paper/main.tex` and `slides/seminar.tex` from verified results only. Every table is generated by code from the output CSVs; nothing is typed by hand.

## Troubleshooting

- **"Reopen in Container" never appears** → the Dev Containers extension isn't installed, or Docker Desktop isn't running.
- **`uv sync` or the build fails** → rebuild the container (Cmd/Ctrl+Shift+P → Rebuild); the setup steps are fail-soft and print what they skipped.
- **Data tasks marked BLOCKED** → the expected file is missing from `data/raw/` (agents never fetch data themselves), or your `~/.secrets/pyopensky_settings.conf` has a typo. Test credentials with: `uv run python -c "from pyopensky.trino import Trino; Trino()"`.
- **Run seems stalled** → check `watchdog.log` in the project root; the watchdog nudges a stale session every 45 minutes, up to 16 times, then pings ntfy and gives up.
- **A task says BLOCKED-NEEDS-HUMAN** → the implementer and reviewer disagreed for 3 cycles, or a sanity gate failed. That's the system working: read the relevant REVIEW_REPORT.md section and decide.

## Command cheat sheet

| Command | Who | What |
|---|---|---|
| `/overnight [N]` | everyone | The full campaign: plan if needed → up to N analysis rounds → lit scan → paper/slides draft → MORNING_BRIEF.md. `/overnight 0` reruns just the closeout. |
| `/plan-round` | director | Reads the evidence, writes the next round file. Plans only — nothing runs. |
| `/run-analysis rounds/ROUND_NN.md [auto N]` | all three analysis agents | Executes a round unattended: implement → audit → fix loop per task, then round close and director handoff. |
| `/tech-debt` | econometrician + overseer | Repo cleanup with a proof that results are byte-identical after. Only when the validator is green. |
| `/lit-review [topic]` | author | Literature search: novelty risks, method provenance, reading queue. Attended; needs web temporarily enabled. |
| `/write-up paper\|slides\|both` | author | Drafts/updates the LaTeX paper and beamer deck from verified results. |
