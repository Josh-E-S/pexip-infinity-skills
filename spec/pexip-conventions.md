# pexip-infinity-skills conventions

Local rules on top of the [Agent Skills open standard](./agent-skills.md). The validator (`./scripts/validate-skills.py`) enforces these.

## 1. Frontmatter

Three keys, in this order:

```yaml
---
name: pexip-<short-name>
description: Use when … Triggers on <symbol-list>. Do NOT use for <anti-trigger>.
license: MIT
---
```

- `name` is kebab-case, prefixed `pexip-`, matches the directory name. The open spec caps `name` at 64 chars total.
- `description` ≤ **1,024 characters** — the open spec's hard cap. (Claude Code extends this to 1,536 chars via an optional `when_to_use` field, but we don't use that extension because it isn't part of the host-agnostic spec. Staying under 1,024 means every host can show the full description without truncation.)
- `license` is `MIT` for everything in this package.

The open spec also permits two additional optional fields we don't currently use:

- `compatibility` (max 500 chars) — environment requirements (intended product, system packages, network access).
- `metadata` — arbitrary key-value map.

If a skill in this package ever needs them, they're fine to add. **Don't add host-specific keys** (`allowed-tools`, `disable-model-invocation`, `context: fork`, `paths:`, `hooks:`, `model:`, `effort:`, `argument-hint`, `arguments`, `agent:`, `shell:`, `user-invocable`, `when_to_use`). Those are runtime-specific extensions; layer them via host settings if needed.

## 2. Directory layout per skill

Flat. No subdirectories inside a skill directory:

```
skills/<domain>/<skill-name>/
├── SKILL.md              # required
├── <topic>.md            # optional sibling detail docs
├── <name>.json           # optional reference data
└── <name>.sh / .py       # optional helper scripts
```

Why flat: matches `awesome-pexip-skills` convention; one less click to read; easier for the agent to know what's there.

## 3. SKILL.md body shape

Predictable section order so a reader can scan:

```markdown
# <Skill Name>

<One-paragraph what-and-why.>

## When to use
<3-5 bullets, concrete.>

## Recipes
### <Recipe 1 verb-y title>
### <Recipe 2 verb-y title>

## Field gotchas / safety notes
<one or both, depending on the skill>

## Reference source
- Authoritative Pexip docs: <URL>                                  # required
- Reference implementation (MCP): `pexip-mgmt-mcp`, `src/pexip_mcp/tools/<file>.py`   # optional
- Related skills: <names>
```

Not every skill needs every section, but the order should be the same.

## 4. Description style

Lead with **when**, then **triggers**, then **anti-triggers**:

> Use when adding, modifying, or debugging code that wraps the Pexip Configuration API — CRUD on VMRs, aliases, end users, gateway rules, system locations, conferencing nodes, automatic participants, LDAP sync sources, IVR themes, global settings. Whether you're writing MCP tools or calling the REST endpoints directly, this is the surface. Triggers on `/api/admin/configuration/v1/`, `conference`, `conference_alias`, `end_user`, `system_location`, `gateway_routing_rule`, `worker_vm`, `automatic_participant`, `ldap_sync_source`, `ivr_theme`, `tools/conference.py`, `tools/alias.py`. Do NOT use for live in-progress meetings (use `pexip-command-api` / `pexip-status-api`) or post-call data (use `pexip-history-api`).

Concrete API symbols and source-file paths help hosts match precisely. Anti-triggers prevent two skills both firing on overlapping requests.

## 5. Sizing

| Component | Target | Hard ceiling |
|---|---|---|
| `description` | < 800 chars (target) | 1,024 chars (open-spec hard cap) |
| `SKILL.md` body | < 250 lines | 500 lines |
| Sibling `.md` per file | < 300 lines | none |
| Scripts | as small as the task allows | none |
| Asset JSON | < 200 lines | none |

Over the ceiling? Split. Two focused skills beat one bloated one.

## 6. Naming

- Domain folders: lowercase, kebab if multi-word (`management-api`, `room-integration`).
- Skill folders: lowercase kebab-case, prefixed `pexip-`.
- Sibling docs: lowercase kebab-case, no `pexip-` prefix (they're scoped to the skill).
- Scripts: lowercase, snake_case or kebab-case. Match the existing style in the skill.

## 7. "Reference source" footer

Every SKILL.md and every sibling doc ends with a Reference source (or
"Authoritative docs") section. Two parts, different bars:

- **Authoritative Pexip docs URL — mandatory.** This is non-negotiable —
  it's how a reader verifies the skill against ground truth and how the
  next maintainer knows where the content came from. A skill without one
  is not finished.
- **Reference implementation (MCP) — optional, cited only where one
  exists.** Today the reference implementation is
  [`pexip-mgmt-mcp`](https://github.com/Josh-E-S/pexip-mgmt-mcp); a skill
  that maps to a tool in `src/pexip_mcp/tools/` can cite that file as a
  worked example. Skills covering surfaces the MCP server hasn't wrapped
  yet either omit this line or note it as `_not yet implemented_`.

The package is host-agnostic — direct REST callers should be just as
well-served by a skill as MCP users.

## 8. Cross-skill references

Inline, by name, not by path:

> For confirmation rules before destructive operations, see `pexip-operations/safety.md`.

The reader (human or agent) resolves the path from the skill name. Paths break when files move; names don't.

## 9. What we don't do

- **No host-specific frontmatter.** No `allowed-tools`, no `disable-model-invocation`, no `context: fork`, no `paths:`, no `hooks:`. These are host concerns; users layer them via host settings.
- **No subdirectories inside a skill.** Flat is faster to read and scan.
- **No skills without an authoritative Pexip docs URL in the Reference source.** A skill that can't cite its source is not finished. (The MCP reference implementation line is optional — see §7.)
- **No "future-proofing" sections.** If a feature isn't implemented yet, don't document it as if it were.
