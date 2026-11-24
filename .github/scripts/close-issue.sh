#!/usr/bin/env bash
# Close the open issue with this exact title, if there is one.
# usage: close-issue.sh "<title>" "<comment>"
set -euo pipefail
title="$1"
comment="$2"
for num in $(gh issue list --state open --limit 100 --json number,title \
  --jq "map(select(.title == \"${title}\")) | .[].number"); do
  gh issue close "$num" --comment "$comment"
  echo "closed issue #$num"
done
