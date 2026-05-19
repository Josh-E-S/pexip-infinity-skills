#!/usr/bin/env bash
# commit-msg hook: forbid AI-attribution boilerplate in commit messages.
#
# This repo will never carry "Co-Authored-By: Claude" or similar markers in
# its git history. They leak the authoring tool into public history with no
# upside.

set -euo pipefail

msg_file="${1:-}"
if [[ -z "$msg_file" || ! -f "$msg_file" ]]; then
  exit 0
fi

forbidden=(
  'Co-Authored-By:[[:space:]]*Claude'
  'Co-Authored-By:[[:space:]]*claude'
  '🤖 Generated with \[Claude Code\]'
  'Generated with \[?Claude Code'
  'Assisted-By:[[:space:]]*Claude'
)

for pat in "${forbidden[@]}"; do
  if grep -qE "$pat" "$msg_file"; then
    echo "Refusing commit: forbidden attribution in message."
    echo "  Pattern: /$pat/"
    echo
    echo "Edit the message and remove AI-attribution lines."
    exit 1
  fi
done
