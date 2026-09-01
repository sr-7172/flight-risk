#!/usr/bin/env bash
# launch.sh — deterministic run launcher. The gate flag is created HERE, by
# the shell, so the watchdog never depends on the model remembering to
# touch it, and never has to wait for it.
#
#   ./launch.sh overnight [N] [flags]          arm + watchdog + headless /overnight
#   ./launch.sh run <round file> [auto N]      arm + watchdog + headless /run-analysis
#   ./launch.sh arm                            arm + watchdog only (then type the
#                                              command in the VS Code panel yourself)
#   ./launch.sh status                         flag / watchdog / STATUS.md summary
#   ./launch.sh disarm                         remove the flag; watchdog exits next tick
#
# Headless mode runs `claude -p "<slash command>"` in the background and logs
# to run.log; the watchdog's resume uses `claude -c` (continue most recent
# conversation in this directory) and falls back to re-issuing .run_command
# if no conversation exists yet. If you prefer the interactive panel, use
# `arm` and paste the command — the flag already exists, so the watchdog is
# live from second zero.
set -u
cd "$(dirname "$0")"
FLAG=".remediation_active"
CMDFILE=".run_command"

arm() {
  touch "$FLAG"
  rm -f .stop_gate_count
  if pgrep -f "bash watchdog.sh" > /dev/null 2>&1; then
    echo "watchdog already running"
  else
    chmod +x watchdog.sh
    nohup bash watchdog.sh > /dev/null 2>&1 &
    echo "watchdog started (pid $!)"
  fi
  echo "armed: $FLAG present"
}

case "${1:-}" in
  overnight)
    shift; CMD="/overnight ${*:-3}"
    echo "$CMD" > "$CMDFILE"; arm
    nohup claude -p "$CMD" >> run.log 2>&1 &
    echo "launched headless: $CMD (log: run.log)";;
  run)
    shift; [ -n "${1:-}" ] || { echo "usage: ./launch.sh run <round file> [auto N]"; exit 1; }
    CMD="/run-analysis $*"
    echo "$CMD" > "$CMDFILE"; arm
    nohup claude -p "$CMD" >> run.log 2>&1 &
    echo "launched headless: $CMD (log: run.log)";;
  arm)
    arm; echo "now run your slash command in the Claude panel";;
  status)
    [ -f "$FLAG" ] && echo "flag: ARMED" || echo "flag: not armed"
    pgrep -f "bash watchdog.sh" > /dev/null 2>&1 && echo "watchdog: running" || echo "watchdog: not running"
    [ -f "$CMDFILE" ] && echo "run command: $(cat "$CMDFILE")"
    [ -f STATUS.md ] && { echo "STATUS.md head:"; head -3 STATUS.md; } || echo "STATUS.md: none yet"
    [ -f watchdog.log ] && { echo "watchdog.log tail:"; tail -3 watchdog.log; };;
  disarm)
    rm -f "$FLAG" .stop_gate_count; echo "disarmed; watchdog exits on its next check";;
  *)
    sed -n '2,20p' "$0"; exit 1;;
esac
