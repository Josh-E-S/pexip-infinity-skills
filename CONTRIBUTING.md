# Contributing

Adding a skill to `pexip-infinity-skills`. Read `ARCHITECTURE.md` first for
the design rules.

## Hygiene policy (public repo)

This is a public repo. Several categories of content are blocked by
pre-commit hooks and CI:

- **No author-tool attribution.** Commit messages and file content must not
  identify the editor, IDE, or any assistive tool used to author the change.
- **No local agent scratch files.** Editor- and agent-local state files,
  notes, and scratch directories are gitignored and must not be force-added.
- **No internal-only notes.** Brainstorming, design rationale, and any
  content tagged as internal or non-public stays out of this repo.
- **No secrets.** Credentials, tokens, private keys, and live config files
  are gitignored and additionally screened by a secret scanner on every
  commit and in CI.
- **No customer-identifiable data.** Email addresses are restricted to a
  short allowlist of documentation domains. IPv4 addresses are restricted
  to RFC 1918 private space, RFC 5737 documentation ranges, and loopback.

Exact patterns and allowlists live in `scripts/hygiene/` and
`.gitleaks.toml`. If a documented placeholder you need to use trips a hook,
extend the allowlist there rather than disabling the hook.

### Local setup

```bash
pip install pre-commit
pre-commit install --hook-type pre-commit --hook-type commit-msg
```

Hooks are intentionally fast; heavier checks (skill validation) run in CI.

## Scaffold a new skill

```bash
./scripts/new-skill.sh <domain> <skill-name>
# e.g.
./scripts/new-skill.sh events pexip-event-replay
```

Creates `skills/<domain>/<skill-name>/SKILL.md` from `template/new-skill/`.
The template's frontmatter, "Reference source" footer, and sectioning all
match the conventions.

## Workflow

1. **Pick the right domain folder.** See the table in `README.md`. If your
   skill doesn't fit, propose a new domain in your PR — don't drop it at
   the top level.
2. **Write `SKILL.md` first.** Keep it under 250 lines. State *when to use*
   and *when not to use* prominently. List trigger symbols (API endpoint
   names, MCP tool names) in the description so the host can match user
   requests.
3. **Push detail into sibling files.** If the skill grows past 250 lines,
   split per-workflow detail into `<skill>/<workflow>.md` files and
   reference them from `SKILL.md`.
4. **Add a "Reference source" footer** linking to the authoritative Pexip
   doc URL. Optionally include a reference implementation (e.g. the
   matching file in `pexip-mgmt-mcp`) when one exists.
5. **Validate.**
   ```bash
   ./scripts/validate-skills.py
   ```
6. **Bump `CHANGELOG.md`.**
7. **Open a PR.**

## Frontmatter checklist

Every `SKILL.md` must start with:

```yaml
---
name: pexip-<short-name>
description: Use when … Triggers on <symbol-list>. Do NOT use for <anti-trigger>.
license: MIT
---
```

- `name` matches the directory name exactly.
- Description leads with "Use when…", then trigger symbols, then anti-triggers.
- Combined `description` + `when_to_use` ≤ 1,536 characters (run the validator).
- No host-specific keys (`allowed-tools`, `disable-model-invocation`, etc.). See `spec/pexip-conventions.md`.

## Body structure

A consistent shape readers can predict:

```markdown
# <Skill Name>

<One-paragraph what-and-why.>

## When to use

<3-5 bullets, concrete.>

## Recipes
### <verb-y title>
<step-by-step or code block>
### <another>
<…>

## Field gotchas / safety notes
<…>

## Reference source
- Authoritative Pexip docs: <URL>
- Reference implementation (MCP, optional): `pexip-mgmt-mcp`, `src/pexip_mcp/tools/<file>.py`
- Related skills: <sibling skill names>
```

Not every skill needs every section, but the order should be predictable.

## Coverage queue

The Phase-2 list from `README.md`'s roadmap is the priority queue for new skills:

- Per-resource splits: `pexip-vmrs`, `pexip-end-users`, `pexip-gateway-rules`, `pexip-ldap-sync`, `pexip-licensing`, `pexip-alarms`, `pexip-conferencing-nodes`
- New domains: `pexip-cvi-teams`, `pexip-branding-manifest`, `pexip-infrastructure-commands`
- Flesh out the stubs: `pexip-event-sinks`, `pexip-external-policy`, `pexip-mjx`

Pick from the queue or propose a new one in an issue first.

## Recipe contributions

Recipes (multi-skill workflows) live in `recipes/<name>.md`. They're shorter
than skills — typically one page — and reference skills inline. See
existing recipes for the shape.

## Code style for scripts

- Bash scripts: `#!/usr/bin/env bash`, `set -euo pipefail`, prefer POSIX-ish constructs that work on macOS bash 3.2.
- Python scripts: target Python 3.10+, no external deps unless absolutely necessary. Self-contained `#!/usr/bin/env python3` scripts the user can run without setting up an environment.

## License

By contributing you agree your work is released under MIT (matching the package).
