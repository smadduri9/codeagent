#!/usr/bin/env bash
# Unattended build driver for codeagent. Owner-supplied: the agent must not edit this file.
# Runs one Cursor CLI session per phase, checks results between sessions, halts on trouble.
# Compatible with macOS bash 3.2 (no associative arrays, no GNU-only flags, no `timeout`).
#
# Usage:   scripts/autobuild.sh
# Options (environment variables):
#   CURSOR_MODEL=composer-2.5   model id as shown by `agent --list-models`
#   MAX_PHASE=8                 last phase to build
#   MAX_SESSIONS_PER_PHASE=6    sessions allowed per phase
#   SESSION_MINUTES=120         hard limit per Cursor session
#   MAX_HOURS=10                hard limit for the whole run
#   REVIEW_GATED_PHASES="3 4 5 6"   phases where a FAILED review blocks the next phase
set -uo pipefail

CURSOR_MODEL="${CURSOR_MODEL:-composer-2.5}"
MAX_PHASE="${MAX_PHASE:-8}"
MAX_SESSIONS_PER_PHASE="${MAX_SESSIONS_PER_PHASE:-6}"
SESSION_MINUTES="${SESSION_MINUTES:-120}"
MAX_HOURS="${MAX_HOURS:-10}"
REVIEW_GATED_PHASES="${REVIEW_GATED_PHASES:-3 4 5 6}"

cd "$(dirname "$0")/.." || exit 1
ROOT="$(pwd)"

# Keep the Mac awake for the whole run (display, idle, system, user activity).
if [ -z "${AUTOBUILD_CAFFEINATED:-}" ] && command -v caffeinate >/dev/null 2>&1; then
  export AUTOBUILD_CAFFEINATED=1
  exec caffeinate -dimsu "$0" "$@"
fi

mkdir -p .autobuild/logs .autobuild/reviews
LOG=".autobuild/logs/driver.log"
START_EPOCH="$(date +%s)"

log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG"; }
halt() { log "HALT: $*"; rmdir .autobuild/lock 2>/dev/null; exit 1; }

# Single instance.
if ! mkdir .autobuild/lock 2>/dev/null; then
  echo "Another autobuild appears to be running (.autobuild/lock exists). Remove it if that is wrong." >&2
  exit 1
fi
trap 'rmdir .autobuild/lock 2>/dev/null' EXIT

# Pick the Cursor CLI binary.
if command -v agent >/dev/null 2>&1; then AGENT=agent
elif command -v cursor-agent >/dev/null 2>&1; then AGENT=cursor-agent
else halt "Cursor CLI not found. Install: curl https://cursor.com/install -fsS | bash"; fi

# ---- Pre-flight -------------------------------------------------------------
preflight() {
  command -v git >/dev/null 2>&1 || halt "git not found"
  command -v gh  >/dev/null 2>&1 || halt "gh not found"
  gh auth status >/dev/null 2>&1 || halt "gh is not logged in. Run: gh auth login"
  git remote get-url origin >/dev/null 2>&1 || halt "no git remote named origin"
  [ -f AGENTS.md ] && [ -f DESIGN.md ] && [ -f BUILD_PLAN.md ] || halt "AGENTS.md, DESIGN.md or BUILD_PLAN.md missing"
  [ -f .cursor/cli.json ] || halt ".cursor/cli.json missing (permission rules for the agent)"
  # Check the key exists without ever printing it.
  if [ ! -f .env ] || ! grep -Eq '^GROQ_API_KEY=.{8,}' .env || grep -Eq '^GROQ_API_KEY=your_groq_key_here' .env; then
    halt ".env has no real GROQ_API_KEY (see .env.example). Needed from phase 6 onward; add it before starting."
  fi
  if git ls-files --error-unmatch .env >/dev/null 2>&1; then halt ".env is tracked by git"; fi
  # Create the phase labels and the blocked label (owner login; idempotent).
  for n in 0 1 2 3 4 5 6 7 8 9 10; do gh label create "phase-$n" --color 0E8A16 --force >/dev/null 2>&1; done
  gh label create blocked --color B60205 --force >/dev/null 2>&1
  if ! "$AGENT" --list-models 2>/dev/null | grep -Fq "$CURSOR_MODEL"; then
    log "Model '$CURSOR_MODEL' not found in '$AGENT --list-models'. Composer entries:"
    "$AGENT" --list-models 2>&1 | grep -i composer | tee -a "$LOG"
    halt "set CURSOR_MODEL to a listed Composer id"
  fi
  if [ -z "${CURSOR_API_KEY:-}" ]; then
    "$AGENT" status >/dev/null 2>&1 || log "WARNING: not sure the Cursor CLI is signed in (run: agent login, or export CURSOR_API_KEY)."
  fi
}

# ---- Helpers ----------------------------------------------------------------
elapsed_hours_exceeded() {
  now="$(date +%s)"
  [ $(( (now - START_EPOCH) / 3600 )) -ge "$MAX_HOURS" ]
}

phase_done() {   # tag phase-N exists on origin
  git ls-remote --tags origin "refs/tags/phase-$1" 2>/dev/null | grep -q "phase-$1"
}

check_blocked() {
  n="$(gh pr list --label blocked --state open --json number --jq 'length' 2>/dev/null || echo 0)"
  if [ "${n:-0}" -gt 0 ]; then halt "a pull request labeled 'blocked' is open ($n). Read it, decide, then restart."; fi
}

check_secrets() {
  git fetch --quiet origin main 2>/dev/null
  for f in .env .autobuild; do
    if git ls-tree -r --name-only origin/main 2>/dev/null | grep -Eq "^${f}(/|$)"; then halt "$f is tracked on origin/main"; fi
  done
  if git grep -Eq 'gsk_[A-Za-z0-9]{20,}' origin/main -- 2>/dev/null; then halt "a Groq-style key appears in origin/main"; fi
}

snapshot() {   # progress fingerprint: main head + all pushed branch heads
  git fetch --quiet --prune origin 2>/dev/null
  git for-each-ref --format='%(objectname)' refs/remotes/origin | sort | shasum | cut -d' ' -f1
}

run_with_deadline() {   # run_with_deadline <minutes> <logfile> <command...>
  mins="$1"; logfile="$2"; shift 2
  "$@" >>"$logfile" 2>&1 &
  pid=$!
  waited=0
  limit=$(( mins * 60 ))
  while kill -0 "$pid" 2>/dev/null; do
    sleep 5
    waited=$(( waited + 5 ))
    if [ "$waited" -ge "$limit" ]; then
      log "session exceeded ${mins} minutes; stopping it"
      kill "$pid" 2>/dev/null; sleep 5; kill -9 "$pid" 2>/dev/null
      wait "$pid" 2>/dev/null
      return 124
    fi
  done
  wait "$pid"
  return $?
}

phase_prompt() {
cat <<PROMPT
Read AGENTS.md, DESIGN.md, BUILD_PLAN.md and docs/PROGRESS.md if it exists. Follow the session start checklist in BUILD_PLAN.md section 6.2. We are working on Phase $1. Work feature by feature using the per-feature loop in section 6.3, committing, pushing, opening pull requests, and merging as BUILD_PLAN.md section 3 specifies and AGENTS.md allows. Do not wait for or ask the owner anything. When the last feature of the phase has merged, update docs/PROGRESS.md, create and push the tag phase-$1, print the phase report, and end the session. If a feature is stuck after three distinct attempts, follow BUILD_PLAN.md section 3.11 and end the session.
PROMPT
}

fix_prompt() {
cat <<PROMPT
Read AGENTS.md and the review in .autobuild/reviews/phase-$1.md (use the shell to read it; it is git-ignored). For each finding marked high or medium, make a fix/ branch, add a test that fails without the fix, fix it, and merge through a pull request per BUILD_PLAN.md section 3. Record any finding you reject, with a reason, in docs/decisions/. End the session when done.
PROMPT
}

review_prompt() {
cat <<PROMPT
Review the code merged in Phase $1 against DESIGN.md. Report (1) deviations from the design, (2) edge cases from DESIGN.md section 10 not handled, (3) any place a tool call or permission rule could be bypassed, (4) any test that would pass even if the feature were broken, (5) any place the system prompt plus tool definitions or a request could exceed the free-tier limits of DESIGN.md 8.20. Mark each finding high, medium, or low. Do not change code. End with exactly one line: VERDICT: PASS or VERDICT: FAIL. Use FAIL if there is any high finding.
PROMPT
}

cursor_session() {   # cursor_session <logfile> <prompt>
  run_with_deadline "$SESSION_MINUTES" "$1" "$AGENT" -p --force --trust --model "$CURSOR_MODEL" --output-format text "$2"
}

sync_main() {
  git fetch --quiet origin || return 1
  git switch main >/dev/null 2>&1 || return 1
  git pull --ff-only --quiet origin main || return 1
}

review_phase() {   # returns 0 for PASS, 1 for FAIL
  n="$1"; out=".autobuild/reviews/phase-$n.md"
  log "phase $n: read-only review"
  sync_main || halt "cannot sync main for review"
  "$AGENT" -p --mode ask --model "$CURSOR_MODEL" --output-format text "$(review_prompt "$n")" >"$out" 2>>"$LOG"
  tail -n 5 "$out" | grep -q 'VERDICT: PASS'
}

is_gated() { for g in $REVIEW_GATED_PHASES; do [ "$g" = "$1" ] && return 0; done; return 1; }

# ---- Main -------------------------------------------------------------------
preflight
log "starting. model=$CURSOR_MODEL max_phase=$MAX_PHASE"

phase=0
while [ "$phase" -le "$MAX_PHASE" ]; do
  if phase_done "$phase"; then
    log "phase $phase already tagged; skipping"
    phase=$(( phase + 1 )); continue
  fi

  sessions=0; stalled=0; failures=0
  while ! phase_done "$phase"; do
    if elapsed_hours_exceeded; then halt "time limit of ${MAX_HOURS}h reached"; fi
    if [ "$sessions" -ge "$MAX_SESSIONS_PER_PHASE" ]; then halt "phase $phase not finished after $sessions sessions"; fi
    check_blocked
    check_secrets
    sync_main || halt "cannot sync main (local changes or diverged history?)"

    sessions=$(( sessions + 1 ))
    before="$(snapshot)"
    logfile=".autobuild/logs/phase-$phase-session-$sessions.log"
    log "phase $phase: session $sessions"
    cursor_session "$logfile" "$(phase_prompt "$phase")"
    rc=$?
    log "phase $phase: session $sessions exited with code $rc"

    if [ "$rc" -ne 0 ] && [ "$rc" -ne 124 ]; then
      failures=$(( failures + 1 ))
      if [ "$failures" -ge 3 ]; then halt "Cursor CLI failed 3 times in a row (usage limit or error). See $logfile"; fi
      log "waiting 15 minutes before retrying"; sleep 900
    else
      failures=0
    fi

    after="$(snapshot)"
    if [ "$before" = "$after" ]; then
      stalled=$(( stalled + 1 ))
      if [ "$stalled" -ge 2 ]; then halt "no progress in 2 consecutive sessions in phase $phase"; fi
    else
      stalled=0
    fi
  done

  check_blocked
  check_secrets
  log "phase $phase: complete (tag found)"

  if review_phase "$phase"; then
    log "phase $phase: review PASS"
  else
    log "phase $phase: review FAIL or unreadable (see .autobuild/reviews/phase-$phase.md)"
    if is_gated "$phase"; then
      round=0
      while [ "$round" -lt 2 ]; do
        round=$(( round + 1 ))
        log "phase $phase: fix round $round"
        cursor_session ".autobuild/logs/phase-$phase-fix-$round.log" "$(fix_prompt "$phase")"
        check_blocked; check_secrets
        if review_phase "$phase"; then log "phase $phase: review PASS after fix round $round"; break; fi
      done
      tail -n 5 ".autobuild/reviews/phase-$phase.md" | grep -q 'VERDICT: PASS' || halt "phase $phase review still failing after 2 fix rounds"
    fi
  fi

  phase=$(( phase + 1 ))
done

log "DONE: phases up to $MAX_PHASE are tagged. Read .autobuild/reviews/ and docs/PROGRESS.md."
