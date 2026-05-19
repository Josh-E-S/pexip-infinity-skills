# Architecture

How `pexip-infinity-skills` is laid out and why. Read this if you're contributing a skill or reorganizing existing ones.

This package is the **umbrella** Agent Skills SDK for the Pexip Infinity
platform. It covers both the **server-side** surface (management/admin
APIs, events, dial plan, room integration, external policy, operator
runbooks) under domain folders such as `skills/operations/`,
`skills/management-api/`, etc., and the **web client-side** surface
under `skills/client/` — Pexip's JavaScript SDK family
(`@pexip/infinity`, `@pexip/media`, `@pexip/signal`,
`@pexip/components`, `@pexip/plugin-api`, …) used in TypeScript / React
to embed webapp3, build custom web clients, plugins, branding
manifests, CVI, layouts, breakouts, etc.

Native mobile and desktop client SDKs (iOS, Android, Electron) are
**not yet covered** in this package — they use separate Pexip SDKs.
They're on the roadmap; see `README.md`.

The package is host-agnostic — Claude Code, Gemini CLI, Codex CLI,
Cursor, Kiro, or any compliant host can load it.

## Design principles

1. **One skill per coherent concept.** A skill should answer one kind of question well. Not "all of Pexip" and not "one HTTP endpoint".
2. **Progressive disclosure.** `SKILL.md` stays small (target < 250 lines). Detail lives in sibling `.md` files that load only when the agent needs them.
3. **Self-contained directories.** Every skill folder ships everything it needs (instructions, sub-docs, scripts, assets). Copy-paste portable to any Agent Skills host.
4. **Open-standard frontmatter.** Use only fields from the [Agent Skills spec](https://agentskills.io): `name`, `description`, `license`. No host-specific extensions in the canonical SKILL.md.
5. **Two audiences, two skill flavors.**
   - **Operator runbooks** (`skills/operations/`) — tell the agent how to *use* the Pexip admin APIs (via the `pexip-mgmnt` MCP server or by calling REST directly) to do real work. Phrased as playbooks.
   - **Developer reference** (`skills/management-api/`) — tell the agent how to work with a given API surface: writing or modifying MCP tools that wrap it, or building a CLI / script / app that calls the endpoints directly. Phrased as API docs.

## Directory layout

```
pexip-infinity-skills/
├── .claude-plugin/plugin.json    # Plugin manifest (installable as /plugin install pexip-infinity-skills)
├── README.md                     # Index + install + roadmap
├── ARCHITECTURE.md               # This file
├── CONTRIBUTING.md               # How to add a skill + hygiene policy
├── CHANGELOG.md                  # Versioned changes
├── LICENSE                       # MIT
├── spec/                         # Standards reference
│   ├── agent-skills.md           # Pinned link to the open standard
│   └── pexip-conventions.md      # Our local rules on top of the spec
├── template/                     # Scaffold for new skills
│   └── new-skill/                # `./scripts/new-skill.sh foo` copies this
├── skills/                       # Skills, grouped by domain
│   ├── _intake/                  # Router skills, always loaded first
│   ├── operations/               # Operator playbooks
│   ├── management-api/           # Developer reference per admin API
│   ├── events/                   # Event sinks / webhooks
│   ├── policy/                   # External Policy API
│   ├── room-integration/         # MJX / room systems
│   └── client/                   # Client SDK / webapp / branding / plugins (17 skills)
├── recipes/                      # Multi-skill workflows
└── scripts/                      # Repo-wide tooling (install, scaffolder, validator, hygiene)
```

There is **no `.mcp.json`** at the repo root. This package is host-agnostic;
users wire MCP via their own host's config (see `README.md`). MCP is one
recommended invocation path for the skills, not a dependency.

### Why domain folders under `skills/`

Matches [anthropics/skills](https://github.com/anthropics/skills) (Creative & Design, Document Skills, Enterprise & Communication, etc.). Helps human navigation as the SDK grows past ~20 skills. **Domain folders are organizational only** — Claude Code and other hosts still discover skills by walking to the `SKILL.md` file; the domain folder name doesn't appear in the skill identifier.

### Why a leading underscore on `_intake/`

The `_` keeps router skills sorted to the top of file listings. Convention only; not load-bearing.

## Skill anatomy

Every skill is a directory with at minimum:

```
my-skill/
└── SKILL.md          # Frontmatter + body. REQUIRED.
```

Larger skills add sibling files (no subdirectories — flat is easier to navigate):

```
my-skill/
├── SKILL.md          # Entry point — short, links to siblings.
├── recipe-a.md       # Detail doc, loaded on demand.
├── recipe-b.md
├── cheatsheet.json   # Reference data.
└── helper.sh         # Optional script.
```

The agent loads `SKILL.md` first, then loads sibling `.md` files only when the work matches. Reference siblings from `SKILL.md` with brief explanations of when to read each.

See `template/new-skill/` for a working scaffold.

## Frontmatter conventions

The three required fields:

```yaml
---
name: pexip-foo
description: Use when …. Triggers on <symbol1>, <symbol2>, …. Do NOT use for ….
license: MIT
---
```

### `name`

- kebab-case
- Prefixed `pexip-` for discoverability
- Matches the directory name
- Max 64 chars (Claude Code limit, lower in practice)

### `description`

- Lead with **when to use it** ("Use when…")
- Then list **trigger symbols** — API method names, tool names, error messages the user might paste
- End with **anti-triggers** ("Do NOT use for…") to keep loading precision high

Why the symbol-stuffing: hosts use the description to decide whether to surface a skill. Listing concrete identifiers (`onPeerDisconnect`, `summarize_calls`, `list_active_participants`) matches the user's actual phrasing better than abstract verbs ("control meetings").

Hard cap: **1,024 characters** on `description` alone — the open Agent Skills spec's limit. (Claude Code extends this to 1,536 chars via an optional `when_to_use` field; we don't use that extension because it isn't part of the host-agnostic spec.) Keep descriptions tight enough that every host can show them in full.

### `license`

Always `MIT` for this package. Lets downstream re-distribute without checking each skill.

### What we DON'T put in frontmatter

To stay open-standard-portable, we avoid Claude-Code-specific keys:
- `allowed-tools` — host-specific
- `disable-model-invocation` / `user-invocable` — host-specific
- `context: fork`, `agent:` — host-specific
- `paths:` — host-specific
- `hooks:` — host-specific
- `argument-hint`, `arguments` — host-specific
- `model`, `effort` — host-specific

A host that supports these can layer them via its own settings (`skillOverrides`, project `settings.json`).

## Sizing rules

| Component | Target | Hard ceiling |
|---|---|---|
| `description` | < 800 chars (target) | 1,024 chars (open-spec hard cap) |
| `SKILL.md` body | < 250 lines | 500 lines |
| Sibling `.md` per file | < 300 lines | none (loaded on demand) |
| Scripts | as small as the task allows | none |
| Asset JSON | < 200 lines | none |

Over the ceiling? Split into more skills. Splitting is cheap; one giant skill is hard to discover and expensive in context.

## Routing between skills

Skills can refer to other skills by name. `pexip-intake` is the canonical router — it asks 2-3 scoping questions (including a server-vs-client question that may route the user to the companion client-side package) and points the agent at the right tier-2 skill. Inline cross-links inside a SKILL.md body are fine too:

> For the post-call equivalent of this analysis, see `pexip-operations/reporting.md`.

Avoid hard dependencies between skills (no "you must read X first"). Each skill should be self-sufficient.

## "Reference source" footer

Every SKILL.md ends with a section pointing at:

1. The **authoritative Pexip doc URL** for the API surface this skill covers (required).
2. A **reference implementation** (optional): typically the matching file in the [`pexip-mgmt-mcp`](https://github.com/Josh-E-S/pexip-mgmt-mcp) server (e.g., `src/pexip_mcp/tools/conference.py`). Cite this only where a reference implementation exists. Direct REST callers can read the same source as a worked example.

This footer lets a human (or another agent) verify the skill against ground truth quickly.

## Recipes vs. skills

A **skill** teaches knowledge. A **recipe** is a runnable, end-to-end workflow that composes several skills.

- Recipes live in `recipes/<name>.md`, not under `skills/`.
- A recipe is invoked the same way a skill is in Claude Code (slash command), but its content is explicitly step-by-step ("first run X, then if Y, run Z").
- Recipes can reference skills inline: "See `pexip-operations/safety.md` for the confirmation rules before the disconnect step."

Pattern borrowed from Google Workspace's [50 curated recipes](https://github.com/googleworkspace/cli).

## Validation

`./scripts/validate-skills.py` lints every `skills/**/SKILL.md`:

- Frontmatter has the three required fields
- `name` matches the directory name
- `description` ≤ 1,024 chars (open-spec hard cap)
- Body has a final "Reference source" or "Authoritative docs" section
- No host-specific frontmatter keys

Run it before pushing changes.

## Client-side vs. server-side organization

Skills under `skills/client/` describe how to build or customize the
**web meeting experience** in TypeScript / React using Pexip's JS SDK
family — `@pexip/infinity`, `@pexip/media`, `@pexip/signal`,
`@pexip/components`, `@pexip/plugin-api`, `@pexip/media-components`,
`@pexip/media-processor`, etc. — for webapp embedding, custom web
clients, branding manifests, plugins, CVI, layouts, breakouts, chat,
and so on. These live as a flat set inside `skills/client/` rather
than being further split by sub-domain, because the client SDK is one
coherent surface (signals + services + view components) and authors
are usually moving between them.

**Runtime in scope:** browser (the SDK family is JavaScript / TypeScript
with React for UI integration). **Out of scope today:** native iOS
(Swift), native Android (Kotlin / Java), desktop (Electron and others).
Native mobile / desktop are different Pexip SDKs and would warrant their
own `skills/client/<native>/` set if added later.

Skills under `skills/operations/`, `skills/management-api/`,
`skills/events/`, `skills/policy/`, and `skills/room-integration/`
describe the **deployment side** — operating, configuring, monitoring,
and extending a Pexip Infinity platform via its admin APIs. These are
grouped by domain because the API surface is large and the audiences
(operator vs. developer-wrapping-the-API) are distinct.

Both halves share the same conventions: sibling-file disclosure,
three-field frontmatter, "Reference source" footer with mandatory
Pexip docs URL, intake-style routers (one server-side, one client-side).

The two intake routers cooperate:

- `pexip-intake` is the top-level router. Its first question is
  "server side or client side?".
- If client → it loads `pexip-client-intake`, which scopes the
  client-side work (webapp vs. custom SDK vs. branding vs. CVI vs. …)
  and routes to the right `skills/client/pexip-*` skill.
- If server → it asks the existing server-side scoping questions
  and routes to the right tier-2 skill.
