#!/bin/sh
set -u
if [ -n "${GITHUB_WORKSPACE:-}" ]; then
  cd "$GITHUB_WORKSPACE"
fi
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
rc=0
agentshield run --agent "$1" --suite "$2" --policy "$3" --fail-on "${4:-high}" || rc=$?
if [ -n "${GITHUB_OUTPUT:-}" ]; then
  echo "exit_code=$rc" >> "$GITHUB_OUTPUT"
fi
exit "$rc"
