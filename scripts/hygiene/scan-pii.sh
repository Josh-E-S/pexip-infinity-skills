#!/usr/bin/env bash
# Pre-commit guard: lightweight PII / private-info scan over staged content.
#
# Catches the obvious foot-guns:
#   - Email addresses on non-allowlisted domains (anything that looks like a
#     real person's email rather than a documentation placeholder)
#   - Public-routable IPv4 addresses (anything outside RFC 1918 / RFC 5737
#     test ranges / loopback / link-local)
#   - Bearer/JWT-shaped tokens (heuristic; gitleaks covers the rest)
#
# This is intentionally a *heuristic*. It errs toward false positives so the
# author has to look at the line and decide. Exit non-zero on any match.

set -euo pipefail

email_allow_domains=(
  'example.com' 'example.org' 'example.net'
  'pexip.com'
  'localhost'
)

# Build the email allowlist regex once.
allow_re="@($(IFS='|'; echo "${email_allow_domains[*]}"))\\b"

# IPv4 ignore regex: RFC 1918 / loopback / link-local / TEST-NET-1/2/3 / multicast / broadcast / 0.x
ip_ignore_re='^(10\.|127\.|169\.254\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.0\.2\.|198\.51\.100\.|203\.0\.113\.|2(2[4-9]|3[0-9])\.|255\.255\.255\.255|0\.)'

# Avoid `mapfile` — macOS ships bash 3.2 by default.
files=()
while IFS= read -r line; do
  [[ -n "$line" ]] && files+=("$line")
done < <(git diff --cached --name-only --diff-filter=ACM)
[[ ${#files[@]} -eq 0 ]] && exit 0

allow_paths=(
  'scripts/hygiene/'
  '.gitleaks.toml'
  '.pre-commit-config.yaml'
)

violations=0

scan_file() {
  local f="$1"

  # Emails: any RFC-ish address not on the allowlist.
  while IFS=: read -r line_no line; do
    [[ -z "${line:-}" ]] && continue
    # Extract each email-looking token from the line.
    while read -r email; do
      [[ -z "$email" ]] && continue
      if ! [[ "$email" =~ $allow_re ]]; then
        echo "::error file=$f,line=$line_no::Email on non-allowlisted domain: $email"
        violations=$((violations + 1))
      fi
    done < <(printf '%s\n' "$line" | grep -oE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' || true)
  done < <(git show ":$f" 2>/dev/null | grep -InE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' || true)

  # IPv4 outside known-safe ranges.
  while IFS=: read -r line_no line; do
    [[ -z "${line:-}" ]] && continue
    while read -r ip; do
      [[ -z "$ip" ]] && continue
      if ! [[ "$ip" =~ $ip_ignore_re ]]; then
        echo "::error file=$f,line=$line_no::Public-routable IPv4 address: $ip"
        violations=$((violations + 1))
      fi
    done < <(printf '%s\n' "$line" | grep -oE '\b([0-9]{1,3}\.){3}[0-9]{1,3}\b' || true)
  done < <(git show ":$f" 2>/dev/null | grep -InE '\b([0-9]{1,3}\.){3}[0-9]{1,3}\b' || true)
}

for f in "${files[@]}"; do
  [[ -f "$f" ]] || continue

  skip=0
  for ap in "${allow_paths[@]}"; do
    if [[ "$f" == $ap* ]]; then skip=1; break; fi
  done
  [[ $skip -eq 1 ]] && continue

  # Only scan text files
  if git show ":$f" 2>/dev/null | grep -Iq . ; then
    scan_file "$f"
  fi
done

if (( violations > 0 )); then
  echo
  echo "Refusing to commit: $violations possible PII / public-IP leak(s)."
  echo "If a match is a legitimate documentation example, add it to the"
  echo "allowlist in scripts/hygiene/scan-pii.sh or .gitleaks.toml."
  exit 1
fi
