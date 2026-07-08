#!/usr/bin/env bash
# sync.sh — one-command sync for the Boorstein World Cup tracker.
#
# Use this after you've edited files locally (scripts, data, etc.).
# It integrates the hourly bot's latest commits, rebuilds index.html from
# the freshest data using the Title Race engine, and pushes.
#
#   ./sync.sh                 # normal: pull --rebase, rebuild, push
#   ./sync.sh "my message"    # same, but commit staged local edits first
#
# If a real merge conflict appears, the script stops and tells you what to do
# instead of guessing — resolve it, then run ./sync.sh again.

set -euo pipefail
cd "$(dirname "$0")"

say() { printf '\n\033[1m» %s\033[0m\n' "$1"; }
die() { printf '\n\033[31m✗ %s\033[0m\n' "$1" >&2; exit 1; }

# 0. Clean up any stray lock from a crashed git run.
rm -f .git/index.lock 2>/dev/null || true

# 1. Commit local edits if a message was given (otherwise assume tree is clean/committed).
if [ "${1:-}" != "" ]; then
  say "Committing local edits: $1"
  git add -A
  git commit -m "$1" || echo "  (nothing to commit)"
fi

# Refuse to proceed with a dirty tree and no message — avoids surprise stashes.
if [ "${1:-}" = "" ] && ! git diff --quiet HEAD 2>/dev/null; then
  die "You have uncommitted changes. Re-run as:  ./sync.sh \"describe your change\""
fi

# 2. Integrate the bot's work.
say "Pulling remote changes (rebase)…"
if ! git pull --rebase origin main; then
  # Data/build artifacts conflict predictably — auto-resolve by taking the bot's
  # fresh data and rebuilding. Anything else, stop for the human.
  conflicts="$(git diff --name-only --diff-filter=U)"
  others="$(echo "$conflicts" | grep -vE '^(data/results\.json|data/worldcup\.json|index\.html)$' || true)"
  if [ -n "$others" ]; then
    git rebase --abort 2>/dev/null || true
    die "Conflict in files that need a human: $others
    Resolve manually, then run ./sync.sh again."
  fi
  say "Auto-resolving data/artifact conflicts (taking bot's fresh data, rebuilding)…"
  git checkout --ours data/results.json data/worldcup.json 2>/dev/null || true
  python3 scripts/build.py
  git add data/results.json data/worldcup.json index.html
  GIT_EDITOR=true git rebase --continue
fi

# 3. Rebuild from the merged data so index.html reflects the latest results.
say "Rebuilding index.html…"
python3 scripts/build.py
if ! git diff --quiet -- index.html data/worldcup.json data/portfolio.json 2>/dev/null; then
  git add index.html data/worldcup.json data/portfolio.json
  git commit -m "rebuild: refresh index.html $(date -u +%FT%TZ)"
fi

# 4. Push.
say "Pushing to origin/main…"
git push origin main

say "Done. The push triggers the GitHub Action, which redeploys Pages."
