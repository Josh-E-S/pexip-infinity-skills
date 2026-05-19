#!/usr/bin/env bash
# Pre-commit guard: refuse to commit files that contain markers we never want
# in a public repo. Looks at the *staged* content only.
#
# Triggers a hard fail if any staged file contains:
#   - Claude/agent attribution lines
#   - Brainstorming / internal-notes section headers
#   - Explicit "INTERNAL ONLY" / "DO NOT COMMIT" tags
#
# This complements .gitignore (which only blocks whole paths). This catches
# the case where someone copies a snippet from an internal doc into a public
# file inline.

set -euo pipefail

# Patterns that should never appear in committed content. Each entry is an
# ERE regex passed to grep -E.
patterns=(
  'Co-Authored-By:[[:space:]]*Claude'
  '🤖 Generated with \[Claude Code\]'
  'Generated with \[?Claude Code'
  '<<+ *CLAUDE_NOTES'
  '\bCLAUDE_NOTES\b'
  '^# *Brainstorming'
  '^## *Brainstorming'
  '\bINTERNAL[ _-]ONLY\b'
  '\bDO[ _-]NOT[ _-]COMMIT\b'
  '\bCONFIDENTIAL[ _-]-?[ _-]?PEXIP[ _-]?INTERNAL\b'
)

# Files to scan: every staged Added/Copied/Modified path, excluding deletions.
# We use git diff --cached so we only see what the commit will contain.
# Avoid `mapfile` — macOS ships bash 3.2 by default.
files=()
while IFS= read -r line; do
  [[ -n "$line" ]] && files+=("$line")
done < <(git diff --cached --name-only --diff-filter=ACM)

# Allow only the hook scripts and their direct configs to reference the
# literal patterns. Public-facing documentation must describe the rules in
# generic terms so the patterns themselves don't end up in git history.
allow_paths=(
  'scripts/hygiene/'
  '.pre-commit-config.yaml'
  '.gitleaks.toml'
  '.gitignore'
)

violations=0
# Guard against empty array under bash 3.2 + set -u.
[[ ${#files[@]} -eq 0 ]] && exit 0

for f in "${files[@]}"; do
  [[ -f "$f" ]] || continue

  skip=0
  for ap in "${allow_paths[@]}"; do
    if [[ "$f" == $ap* ]]; then skip=1; break; fi
  done
  [[ $skip -eq 1 ]] && continue

  for pat in "${patterns[@]}"; do
    # -I = skip binary, -n = line numbers, -E = extended regex
    if matches=$(git show ":$f" 2>/dev/null | grep -InE "$pat" || true); [[ -n "$matches" ]]; then
      echo "::error file=$f::Forbidden marker matched pattern /$pat/"
      echo "$matches" | sed "s|^|  $f:|"
      violations=$((violations + 1))
    fi
  done
done

if (( violations > 0 )); then
  echo
  echo "Refusing to commit: $violations forbidden marker(s) found."
  echo "This repo is public. Remove agent attribution, internal-notes blocks,"
  echo "and DO-NOT-COMMIT markers before re-staging."
  exit 1
fi
