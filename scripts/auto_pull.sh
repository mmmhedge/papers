#!/bin/bash
set -e

cd /Users/marypavlenko/papers

export PATH="/Library/Frameworks/Python.framework/Versions/3.8/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

if [ -n "${GITHUB_TOKEN:-}" ]; then
  repo_url="https://${GITHUB_TOKEN}@github.com/mmmhedge/papers.git"
else
  repo_url="origin"
fi

echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Starting paper vault sync"

# Retry for transient wake/network issues while Wi-Fi and DNS settle.
for attempt in 1 2 3 4 5 6 7 8 9 10; do
  if git pull --rebase --autostash "$repo_url" main; then
    echo "Pull succeeded on attempt $attempt"
    python3 scripts/build_web.py
    echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Paper vault sync complete"
    exit 0
  fi
  echo "Attempt $attempt failed, waiting 60 seconds..."
  sleep 60
done

echo "All attempts failed"
exit 1
