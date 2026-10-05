#!/bin/sh
set -eu
if [ -n "${GITHUB_WORKSPACE:-}" ]; then
  cd "$GITHUB_WORKSPACE"
fi
agentshield run --agent "$1" --suite "$2" --policy "$3" --fail-on "${4:-high}"
