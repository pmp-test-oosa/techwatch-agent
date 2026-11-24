#!/usr/bin/env bash
# Open an issue with this exact title, or comment on the open one (never creates duplicates).
# usage: upsert-issue.sh "<title>" <body-file>
set -euo pipefail
title="$1"
body="$2"
num=$(gh issue list --state open --limit 100 --json number,title \
  --jq "map(select(.title == \"${title}\")) | .[0].number // empty")
if [ -n "$num" ]; then
  gh issue comment "$num" --body-file "$body"
  echo "commented on issue #$num"
else
  gh issue create --title "$title" --body-file "$body"
fi
