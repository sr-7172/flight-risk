#!/usr/bin/env python3
"""Stop-gate hook for unattended remediation runs.

Behavior on every Stop event:
  - No .remediation_active flag        -> allow stop (normal interactive use).
  - Flag + STATUS.md has ALL COMPLETE  -> lift the gate (delete flag), ping
    ntfy, allow stop. This is the completion notification the /run-analysis
    contract mentions.
  - Flag + not complete                -> block the stop up to MAX_BLOCKS
    times per flag lifetime, feeding Claude a resume instruction. Beyond the
    cap, allow the stop and leave the flag for watchdog.sh (the outer retry
    loop) so a confused session can't spin forever.

Fail-open by design: any unexpected error allows the stop, so a hook bug can
never brick the session.
"""
import json
import os
import subprocess
import sys

MAX_BLOCKS = 2

RESUME = (
    "STATUS.md does not contain ALL COMPLETE and .remediation_active exists, "
    "so the run is not finished. If STATUS.md is missing or names no active "
    "round, you are in the preflight/planning phase of the command in "
    ".run_command — continue that contract. Otherwise read STATUS.md and "
    "REVIEW_REPORT.md, then resume from the first task not marked DONE or "
    "BLOCKED, following the "
    "/run-analysis contract. If every task truly is DONE or BLOCKED, finish "
    "the closing sequence instead: python code/build_run_log.py, "
    "python code/99_validate_outputs.py, director close-out "
    "(ROUND_NN_FINDINGS.md in the round folder, PROJECT_STATE.md refresh, "
    "code/sync_min_scripts.py), overseer OVERALL verdict with the "
    "findings-audit, then append ALL COMPLETE to STATUS.md."
)


def ntfy(msg: str, root: str) -> None:
    candidates = [
        os.path.join(root, ".ntfy_topic"),
        os.path.expanduser("~/.secrets/ntfy_topic"),
    ]
    for path in candidates:
        try:
            if os.path.isfile(path):
                topic = open(path, encoding="utf-8").read().strip()
                if topic:
                    subprocess.run(
                        ["curl", "-s", "-m", "10", "-d", msg,
                         f"https://ntfy.sh/{topic}"],
                        capture_output=True, timeout=15,
                    )
                return
        except Exception:
            return


def main() -> None:
    try:
        json.load(sys.stdin)  # payload unused; consume to be a good citizen
    except Exception:
        pass

    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    flag = os.path.join(root, ".remediation_active")
    counter = os.path.join(root, ".stop_gate_count")

    if not os.path.isfile(flag):
        sys.exit(0)

    status = ""
    status_path = os.path.join(root, "STATUS.md")
    if os.path.isfile(status_path):
        status = open(status_path, encoding="utf-8", errors="replace").read()

    if "ALL COMPLETE" in status:
        for p in (flag, counter):
            try:
                os.remove(p)
            except OSError:
                pass
        ntfy("Run complete: STATUS.md says ALL COMPLETE. Gate lifted.", root)
        sys.exit(0)

    n = 0
    try:
        n = int(open(counter, encoding="utf-8").read().strip() or 0)
    except Exception:
        n = 0

    if n >= MAX_BLOCKS:
        try:
            os.remove(counter)
        except OSError:
            pass
        ntfy("Stop gate: session ended without ALL COMPLETE after "
             f"{n} in-session nudges; flag left for watchdog.", root)
        sys.exit(0)

    try:
        with open(counter, "w", encoding="utf-8") as fh:
            fh.write(str(n + 1))
    except OSError:
        pass

    print(json.dumps({"decision": "block", "reason": RESUME}))
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)
