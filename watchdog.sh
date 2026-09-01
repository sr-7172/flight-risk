#!/usr/bin/env bash
# watchdog.sh — auto-resume the analysis run after usage-limit pauses,
# crashes, or stalls. Run it in a SECOND terminal inside the dev container
# BEFORE you leave:
#
#     chmod +x watchdog.sh && nohup bash watchdog.sh > /dev/null 2>&1 &
#
# Preferred launch: ./launch.sh (creates the flag itself and starts this).
#
# Logic:
#   - If started BEFORE the flag exists (e.g. you launched the watchdog and
#     then typed the command in the panel), it waits up to WAIT_FOR_FLAG
#     minutes for .remediation_active to appear instead of exiting. Run
#     `bash watchdog.sh arm` to have it create the flag itself.
#   - Then only acts while .remediation_active exists (the run's gate flag).
#   - Every CHECK_INTERVAL, looks at the newest mtime anywhere in the repo
#     (code/output/log files). If nothing has changed for STALE_MINUTES,
#     the run is presumed paused (usage limit, crash, or dead panel) and
#     it fires a headless resume:  claude -c -p "<resume prompt>"
#   - If you're still rate-limited, that invocation fails fast; the loop
#     sleeps and retries — so the run resumes within ~CHECK_INTERVAL of
#     your limit refreshing. No reset-time parsing needed.
#   - Caps total nudges, logs to watchdog.log, pings ntfy on each nudge
#     if a topic is configured (repo .ntfy_topic, else ~/.secrets/ntfy_topic).
#
# Notes:
#   - The headless resume continues the SAME conversation as your VS Code
#     session (most recent in this directory) in a new process. Progress
#     lands in files/commits/STATUS.md, not in the VS Code panel transcript.
#   - STALE_MINUTES=45 is deliberately conservative so it never nudges a
#     session that is merely thinking through a long computation. A long
#     single WRDS query that writes nothing for >45 min could trigger a
#     spurious nudge; the resume prompt tells Claude to check STATUS.md
#     first, so a spurious nudge is wasteful but not harmful.

set -u
cd "$(dirname "$0")"

CHECK_INTERVAL=900        # seconds between checks (15 min)
STALE_MINUTES=45          # repo silence before declaring the run stalled
MAX_NUDGES=16
WAIT_FOR_FLAG=60          # minutes to wait for the flag to appear at startup
LOG="watchdog.log"
FLAG=".remediation_active"
CMDFILE=".run_command"

RESUME_PROMPT='You were paused (usage limit or interruption) during an unattended run. Determine the phase first: (a) if STATUS.md names an active round that is not COMPLETE, read STATUS.md and REVIEW_REPORT.md and resume from the first task not marked DONE or BLOCKED, following the /run-analysis contract exactly (econometrician implements, overseer reviews, max 3 cycles per task, commit per completed task, close the round with build_run_log.py, 99_validate_outputs.py, 98_check_trino_usage.py, the director close-out — ROUND_NN_FINDINGS.md in the round folder, PROJECT_STATE.md refresh, sync_min_scripts.py — the overseer OVERALL verdict with findings-audit, and ALL COMPLETE in STATUS.md); (b) if there is no STATUS.md or no active round, you are in the planning/preflight phase of the command recorded in .run_command — continue that contract from where the repo state shows it stopped. Do not redo tasks already marked DONE.'

log() { echo "[$(date '+%F %T')] $*" >> "$LOG"; }

notify() {
  topic=""
  if [ -f .ntfy_topic ]; then
    topic="$(tr -d '[:space:]' < .ntfy_topic)"
  fi
  if [ -z "$topic" ] && [ -f "$HOME/.secrets/ntfy_topic" ]; then
    topic="$(tr -d '[:space:]' < "$HOME/.secrets/ntfy_topic")"
  fi
  [ -n "$topic" ] && curl -s -m 10 -d "$1" "https://ntfy.sh/$topic" > /dev/null 2>&1
}

newest_mtime_minutes_ago() {
  # Minutes since the most recent modification anywhere in the repo,
  # excluding the watchdog's own log and git internals.
  newest=$(find . -type f \
      -not -path './.git/*' \
      -not -name 'watchdog.log' \
      -printf '%T@\n' 2>/dev/null | sort -rn | head -1)
  if [ -z "${newest:-}" ]; then
    # macOS/BSD fallback (no -printf)
    newest=$(find . -type f -not -path './.git/*' -not -name 'watchdog.log' \
      -exec stat -f '%m' {} + 2>/dev/null | sort -rn | head -1)
  fi
  [ -z "${newest:-}" ] && { echo 99999; return; }
  now=$(date +%s)
  echo $(( (now - ${newest%.*}) / 60 ))
}

if [ "${1:-}" = "arm" ]; then
  touch "$FLAG"; rm -f .stop_gate_count
  log "Armed: created $FLAG myself."
fi

log "Watchdog started (interval=${CHECK_INTERVAL}s, stale=${STALE_MINUTES}m, max_nudges=${MAX_NUDGES})."

# Wait for the flag instead of exiting if the run hasn't been armed yet.
waited=0
while [ ! -f "$FLAG" ]; do
  if [ "$waited" -ge "$WAIT_FOR_FLAG" ]; then
    log "No $FLAG after ${WAIT_FOR_FLAG}m; exiting. Use ./launch.sh or 'bash watchdog.sh arm'."
    exit 0
  fi
  [ "$waited" -eq 0 ] && log "No $FLAG yet; waiting up to ${WAIT_FOR_FLAG}m for the run to be armed."
  sleep 60; waited=$((waited + 1))
done
log "Flag present; monitoring."
nudges=0

while [ -f "$FLAG" ]; do
  sleep "$CHECK_INTERVAL"
  [ -f "$FLAG" ] || break   # run completed while we slept

  idle=$(newest_mtime_minutes_ago)
  if [ "$idle" -lt "$STALE_MINUTES" ]; then
    log "Healthy: last repo change ${idle}m ago."
    continue
  fi

  if [ "$nudges" -ge "$MAX_NUDGES" ]; then
    log "Nudge cap reached (${MAX_NUDGES}); standing down."
    notify "Watchdog: nudge cap reached; run still incomplete. Manual restart needed."
    break
  fi

  nudges=$((nudges + 1))
  log "Stalled ${idle}m. Nudge ${nudges}/${MAX_NUDGES}: invoking headless resume..."
  notify "Watchdog nudge ${nudges}: attempting to resume run."

  # Headless continue of the most recent conversation in this directory.
  # If still rate-limited, this fails fast and we just retry next cycle.
  if claude -c -p "$RESUME_PROMPT" >> "$LOG" 2>&1; then
    log "Resume invocation exited 0 (turn completed or gate-blocked-and-continued)."
  elif [ -f "$CMDFILE" ] && [ ! -f STATUS.md ]; then
    # No conversation to continue and the run never started: (re)issue the
    # recorded launch command fresh.
    log "No resumable conversation; issuing recorded command: $(cat "$CMDFILE")"
    claude -p "$(cat "$CMDFILE")" >> "$LOG" 2>&1 \
      && log "Fresh launch exited 0." || log "Fresh launch failed (rate-limited?); will retry."
  else
    log "Resume invocation failed (likely still rate-limited); will retry."
  fi
done

if [ ! -f "$FLAG" ]; then
  log "Gate flag gone — run concluded. Watchdog exiting."
else
  log "Watchdog exiting."
fi
