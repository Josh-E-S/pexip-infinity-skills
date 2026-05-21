#!/usr/bin/env bash
# Run trigger evals for one skill using the upstream anthropics/skills
# harness (skill-creator/scripts/run_eval.py), pinned to the SHA in
# scripts/SKILL_CREATOR_VERSION.
#
# Layout:
#   <skill>/evals/evals.json                       authored input
#   <skill>-workspace/iteration-<N>/results.json   harness output (gitignored)
#
# Usage:
#   scripts/run-evals.sh <path-to-skill-dir> [extra args passed to run_eval.py]
# Example:
#   scripts/run-evals.sh skills/events/pexip-event-sinks --verbose
#
# Requires: bash 3.2+, git, python3, the `claude` CLI on PATH, PyYAML.

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <path-to-skill-dir> [extra run_eval.py args]" >&2
  exit 2
fi

skill_dir="$1"
shift

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
version_file="$repo_root/scripts/SKILL_CREATOR_VERSION"
cache_dir="$repo_root/.cache/skill-creator"
upstream_repo="https://github.com/anthropics/skills.git"

if [[ ! -d "$skill_dir" ]]; then
  echo "error: skill dir not found: $skill_dir" >&2
  exit 1
fi
if [[ ! -f "$skill_dir/SKILL.md" ]]; then
  echo "error: no SKILL.md at $skill_dir" >&2
  exit 1
fi

eval_set="$skill_dir/evals/evals.json"
if [[ ! -f "$eval_set" ]]; then
  echo "error: no eval set at $eval_set" >&2
  echo "       author one per agentskills.io/skill-creation/evaluating-skills" >&2
  exit 1
fi

pinned_sha="$(grep -v '^#' "$version_file" | grep -v '^$' | head -1 | tr -d '[:space:]')"
if [[ -z "$pinned_sha" ]]; then
  echo "error: no SHA in $version_file" >&2
  exit 1
fi

# Clone-or-update the pinned harness into the local cache.
if [[ ! -d "$cache_dir/.git" ]]; then
  echo "scripts/run-evals.sh: cloning anthropics/skills @ $pinned_sha" >&2
  rm -rf "$cache_dir"
  mkdir -p "$(dirname "$cache_dir")"
  git clone --quiet "$upstream_repo" "$cache_dir"
fi

cached_sha="$(git -C "$cache_dir" rev-parse HEAD)"
if [[ "$cached_sha" != "$pinned_sha" ]]; then
  echo "scripts/run-evals.sh: cache at $cached_sha, want $pinned_sha — fetching" >&2
  git -C "$cache_dir" fetch --quiet origin "$pinned_sha"
  git -C "$cache_dir" checkout --quiet "$pinned_sha"
fi

run_eval_py="$cache_dir/skills/skill-creator/scripts/run_eval.py"
if [[ ! -f "$run_eval_py" ]]; then
  echo "error: harness not found at $run_eval_py (upstream layout changed?)" >&2
  exit 1
fi

# Place the iteration workspace next to the skill, gitignored via *-workspace/.
skill_basename="$(basename "$skill_dir")"
workspace="$(dirname "$skill_dir")/${skill_basename}-workspace"
mkdir -p "$workspace"

# Next iteration number = max existing + 1.
last_iter=0
for d in "$workspace"/iteration-*; do
  [[ -d "$d" ]] || continue
  n="${d##*/iteration-}"
  case "$n" in
    ''|*[!0-9]*) continue ;;
  esac
  if [[ "$n" -gt "$last_iter" ]]; then
    last_iter="$n"
  fi
done
iter=$((last_iter + 1))
iter_dir="$workspace/iteration-$iter"
mkdir -p "$iter_dir"

abs_skill="$(cd "$skill_dir" && pwd)"
abs_eval_set="$(cd "$(dirname "$eval_set")" && pwd)/$(basename "$eval_set")"
abs_out_file="$(cd "$iter_dir" && pwd)/results.json"
out_file="$abs_out_file"

echo "scripts/run-evals.sh: skill=$abs_skill" >&2
echo "scripts/run-evals.sh: eval-set=$abs_eval_set" >&2
echo "scripts/run-evals.sh: out=$out_file" >&2

# Run our wrapper, which imports the upstream run_eval module and patches
# its detection to also match the real skill name in Read/Skill tool calls.
# See scripts/run_eval_patched.py for why.
SKILL_CREATOR_CACHE="$cache_dir" python3 "$repo_root/scripts/run_eval_patched.py" \
  --skill-path "$abs_skill" \
  --eval-set "$abs_eval_set" \
  "$@" \
  > "$abs_out_file"

echo "scripts/run-evals.sh: wrote $out_file" >&2
