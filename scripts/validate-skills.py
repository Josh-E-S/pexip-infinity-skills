#!/usr/bin/env python3
"""Lint every skills/**/SKILL.md against the pexip-infinity-skills conventions.

Rules (see spec/pexip-conventions.md):

  1. Frontmatter must have exactly: name, description, license.
  2. `name` must match the parent directory name.
  3. `name` must be kebab-case and prefixed `pexip-`.
  4. `description` ≤ 1,024 characters (open Agent Skills spec hard cap).
     We warn at 800 to keep a margin.
  5. License must be `MIT`.
  6. No host-specific frontmatter keys (allowed-tools, disable-model-invocation,
     context, paths, hooks, agent, model, effort, argument-hint, arguments,
     user-invocable, when_to_use, shell).
  7. Body must end with a "Reference source" or "Authoritative docs" section,
     and that section must cite at least one authoritative Pexip docs URL
     (docs.pexip.com / www.pexip.com / github.com/pexip). Per spec §7 the
     authoritative URL is mandatory — a header alone is not enough.
  8. Body should be under 500 lines (warn at 250).
  9. Relative-path markdown links in any skill or recipe markdown must resolve.

Exit code: 0 = no errors (warnings are informational), 2 = errors.
Pass `--strict` to treat warnings as exit-1 (useful for opt-in CI gates).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

HOST_SPECIFIC_KEYS = {
    "allowed-tools",
    "disable-model-invocation",
    "user-invocable",
    "context",
    "agent",
    "paths",
    "hooks",
    "argument-hint",
    "arguments",
    "model",
    "effort",
    "shell",
    "when_to_use",
}

DESCRIPTION_HARD_CAP = 1024  # open Agent Skills spec
DESCRIPTION_WARN_CAP = 800   # internal margin
BODY_LINES_HARD_CAP = 500
LINK_RE = re.compile(r"\[(?P<text>[^\]]+)\]\((?P<href>[^)]+)\)")
BODY_LINES_WARN = 250
NAME_RE = re.compile(r"^pexip-[a-z0-9]+(-[a-z0-9]+)*$")
FOOTER_HEADER_RE = re.compile(
    r"^##\s+(reference source|authoritative docs)\s*$", re.IGNORECASE | re.MULTILINE
)
PEXIP_DOCS_URL_RE = re.compile(
    r"https?://(?:[a-z0-9-]+\.)*pexip\.com/|https?://github\.com/pexip/", re.IGNORECASE
)


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Tiny YAML frontmatter parser — handles plain string and quoted values."""
    if not text.startswith("---\n"):
        raise ValueError("file does not start with '---'")
    body_start = text.find("\n---\n", 4)
    if body_start == -1:
        raise ValueError("no closing '---' for frontmatter")
    raw = text[4:body_start]
    body = text[body_start + 5 :]
    fm: dict[str, Any] = {}
    for raw_line in raw.splitlines():
        line = raw_line.rstrip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"malformed frontmatter line: {line!r}")
        k, _, v = line.partition(":")
        v = v.strip()
        # Strip wrapping quotes; treat everything as string.
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            v = v[1:-1]
        fm[k.strip()] = v
    return fm, body


def check(skill_md: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    text = skill_md.read_text(encoding="utf-8")
    try:
        fm, body = parse_frontmatter(text)
    except ValueError as e:
        return [f"frontmatter: {e}"], []

    # 1. Required keys.
    for key in ("name", "description", "license"):
        if key not in fm:
            errors.append(f"frontmatter: missing required key `{key}`")

    # 6. No host-specific keys.
    for key in fm:
        if key in HOST_SPECIFIC_KEYS:
            errors.append(
                f"frontmatter: `{key}` is host-specific — see spec/pexip-conventions.md"
            )

    # 2. Name matches directory.
    dir_name = skill_md.parent.name
    if fm.get("name") and fm["name"] != dir_name:
        errors.append(
            f"frontmatter: name={fm['name']!r} does not match directory name {dir_name!r}"
        )

    # 3. Name shape.
    if fm.get("name") and not NAME_RE.match(fm["name"]):
        errors.append(
            f"frontmatter: name={fm['name']!r} must be kebab-case and prefixed `pexip-`"
        )

    # 4. Description length.
    if "description" in fm:
        n = len(fm["description"])
        if n > DESCRIPTION_HARD_CAP:
            errors.append(
                f"frontmatter: description is {n} chars "
                f"(open-spec hard cap {DESCRIPTION_HARD_CAP})"
            )
        elif n > DESCRIPTION_WARN_CAP:
            warnings.append(
                f"frontmatter: description is {n} chars "
                f"(soft target {DESCRIPTION_WARN_CAP}, hard cap {DESCRIPTION_HARD_CAP})"
            )

    # 5. License.
    if fm.get("license") and fm["license"] != "MIT":
        errors.append(f"frontmatter: license={fm['license']!r} must be 'MIT'")

    # 7. Reference source footer + mandatory authoritative Pexip docs URL.
    footer = FOOTER_HEADER_RE.search(body)
    if not footer:
        errors.append(
            "body: missing '## Reference source' (or '## Authoritative docs') section"
        )
    else:
        # Look for a Pexip docs URL anywhere from the footer header onward.
        # Spec §7: the authoritative URL is mandatory, not just the header.
        if not PEXIP_DOCS_URL_RE.search(body[footer.start() :]):
            errors.append(
                "body: footer has no authoritative Pexip docs URL "
                "(docs.pexip.com / www.pexip.com / github.com/pexip) — see spec/pexip-conventions.md §7"
            )

    # 8. Body line counts.
    lines = body.count("\n")
    if lines > BODY_LINES_HARD_CAP:
        errors.append(f"body: {lines} lines exceeds cap {BODY_LINES_HARD_CAP}")
    elif lines > BODY_LINES_WARN:
        warnings.append(
            f"body: {lines} lines exceeds target {BODY_LINES_WARN} — consider splitting"
        )

    return errors, warnings


def check_links(md_path: Path, root: Path) -> list[str]:
    """Rule 9: verify every relative-path markdown link resolves."""
    errors: list[str] = []
    text = md_path.read_text(encoding="utf-8")
    for m in LINK_RE.finditer(text):
        href = m.group("href").strip()
        # Skip external URLs, anchor-only refs, mailto, and inline-code-with-paren noise.
        if href.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target_path = href.split("#", 1)[0].split("?", 1)[0]
        if not target_path:
            continue
        target = (md_path.parent / target_path).resolve()
        if not target.exists():
            errors.append(
                f"{md_path.relative_to(root)}: broken link → {href}"
            )
    return errors


def main() -> int:
    strict = "--strict" in sys.argv[1:]
    root = Path(__file__).resolve().parent.parent
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        print(f"error: {skills_dir} does not exist", file=sys.stderr)
        return 2

    skill_files = sorted(skills_dir.glob("**/SKILL.md"))
    if not skill_files:
        print(f"error: no SKILL.md files under {skills_dir}", file=sys.stderr)
        return 2

    total_errors = 0
    total_warnings = 0
    for skill_md in skill_files:
        rel = skill_md.relative_to(root)
        errors, warnings = check(skill_md)
        if not errors and not warnings:
            print(f"OK   {rel}")
            continue
        for e in errors:
            print(f"ERR  {rel}: {e}")
            total_errors += 1
        for w in warnings:
            print(f"WARN {rel}: {w}")
            total_warnings += 1

    # Rule 9: link check across every markdown file in the repo.
    # Covers SKILL.md sibling docs, recipes, README, ARCHITECTURE, etc.
    link_targets = sorted(
        set(skills_dir.rglob("*.md"))
        | set((root / "recipes").glob("*.md") if (root / "recipes").is_dir() else [])
        | {p for p in root.glob("*.md")}
    )
    link_errors_total = 0
    for md in link_targets:
        for e in check_links(md, root):
            print(f"ERR  {e}")
            link_errors_total += 1
            total_errors += 1

    print()
    print(
        f"{len(skill_files)} skill(s) checked, "
        f"{len(link_targets)} markdown file(s) link-checked. "
        f"{total_errors} error(s), {total_warnings} warning(s)."
    )
    if total_errors:
        return 2
    if total_warnings and strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
