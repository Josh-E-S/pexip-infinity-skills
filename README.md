# pexip-infinity-skills

`pexip-infinity-skills` is the **umbrella [Agent Skills](https://agentskills.io)
package for [Pexip Infinity](https://www.pexip.com/products/infinity-platform)**.
Drop it into any compliant skills host to give that host concrete, current
knowledge about Pexip's admin APIs, events, dial plan, external policy,
and room integration — useful for building applications, answering
questions, debugging a deployment, or running live operator workflows.

It's **host-agnostic**: works in Claude Code, Gemini CLI, Codex CLI,
Cursor, Kiro, or anything else that reads the open Agent Skills
spec. MCP is a recommended invocation path, not a dependency.

It's also **modular**: every `skills/<domain>/<skill-name>/` directory is
self-contained and can be copied individually if you don't want the whole
package.

---

## What's inside

```
pexip-infinity-skills/
├── .claude-plugin/plugin.json    Plugin manifest
├── spec/                         Agent Skills standard + Pexip conventions
├── template/                     Scaffold for new skills
├── skills/                       The skills, grouped by domain
│   ├── _intake/                  Router — start here for open-ended requests
│   ├── operations/               OPERATOR runbooks (use the platform)
│   ├── management-api/           DEVELOPER reference per admin API
│   ├── events/                   Event sinks + webhook patterns
│   ├── policy/                   External Policy API
│   ├── room-integration/         MJX / One-Touch Join
│   └── client/                   Reserved — see Roadmap below
├── recipes/                      Multi-skill workflows ready to run
└── scripts/                      Install / validate / scaffold / hygiene
```

There is **no `.mcp.json`** at the repo root. Users wire MCP via their own
host's config — see Prerequisites below.

## Skill index (v0.1.0)

| Skill | Domain | Audience |
|---|---|---|
| **pexip-intake** | router | both — start here for open-ended "I want to use Pexip" requests, server-side or client-side |
| **pexip-operations** | operations | operator — kick / lock / report / configure / health-check |
| **pexip-config-api** | management-api | developer — Configuration admin API (CRUD on VMRs, dial plan, locations, end-users, …) |
| **pexip-status-api** | management-api | developer — Status admin API (live conferences, participants, node load, alarms) |
| **pexip-history-api** | management-api | developer — History admin API (post-call CDRs, quality forensics) |
| **pexip-command-api** | management-api | developer — Command admin API (live actions: kick / mute / lock / transfer / layout) |
| **pexip-event-sinks** | events | both — webhook push events from Pexip |
| **pexip-external-policy** | policy | developer — external policy server hooks for per-call decisions |
| **pexip-mjx** | room-integration | both — MJX / One-Touch Join for in-room video systems |

`skills/client/` is **reserved** (see Roadmap).

See `ARCHITECTURE.md` for the design rules. See `CONTRIBUTING.md` for how
to add a skill and the public-repo hygiene policy enforced by pre-commit
hooks.

---

## Install

The package is host-agnostic; each host has its own way to load skills.
Pick whichever matches your tool.

### Claude Code

The repo ships a Claude Code plugin manifest at `.claude-plugin/plugin.json`,
so the most ergonomic install is the plugin path:

```bash
# Local dev: load directly from this directory
claude --plugin-dir /path/to/pexip-infinity-skills

# Or, once published to a marketplace:
/plugin install pexip-infinity-skills@<marketplace-name>
```

You can also point Claude Code at individual skills by copying any
`skills/<domain>/<skill-name>/` directory into your skills tree:

```bash
cp -r skills/operations/pexip-operations ~/.claude/skills/
```

### Gemini CLI

Skills are picked up from Gemini CLI's configured skill directories. Copy
the ones you want:

```bash
cp -r skills/operations/pexip-operations ~/.gemini/skills/
```

See Gemini CLI's skills documentation for the exact location it scans on
your platform.

### Codex CLI / Cursor / Kiro / others

Any host that follows the open
[Agent Skills](https://agentskills.io) standard reads
`SKILL.md` frontmatter directly. Drop a skill directory into the host's
skills location:

```bash
cp -r skills/operations/pexip-operations <host-skills-dir>/
```

### Bulk install (all skills at once)

```bash
./scripts/install.sh ~/.claude/skills/
```

Copies every skill in `skills/**/` into the target directory, flattening
the domain grouping (most hosts expect `<target>/<skill-name>/SKILL.md`).

---

## Prerequisites

Two ways to actually *use* the skills, both supported:

### 1. Using an MCP host

Install the [pexip-mgmnt MCP
server](https://github.com/Josh-E-S/pexip-mgmt-mcp) separately and wire it
into your host the way that host expects (Claude Code's `mcpServers`
config, Gemini CLI's MCP settings, etc.). The server exposes ready-made
tools — `list_active_participants`, `summarize_calls`, `disconnect_participant`,
and so on — that the skills cite as concrete trigger examples.

Set these environment variables before the host launches the server:

```bash
export PEXIP_HOST=manager.example.com
export PEXIP_USERNAME=admin
export PEXIP_PASSWORD=...
# Optional:
# export PEXIP_VERIFY_TLS=true
# export PEXIP_TIMEOUT=30
# export PEXIP_MAX_RETRIES=3
```

Run `skills/operations/pexip-operations/mcp-healthcheck.sh` (bundled with
the `pexip-operations` skill) to confirm the server is talking to your
Management Node before the host needs it.

### 2. Calling Pexip APIs directly

Every skill cites the underlying REST endpoints
(`/api/admin/configuration/v1/…`, `/api/admin/status/v1/…`,
`/api/admin/history/v1/…`, `/api/admin/command/v1/…`). Auth is HTTP Basic
over HTTPS to the Management Node. You can use the skills as a
specification and call the endpoints from any language; no server code is
bundled in this repo.

The
[`pexip-mgmt-mcp:src/pexip_mcp/tools/`](https://github.com/Josh-E-S/pexip-mgmt-mcp/tree/main/src/pexip_mcp/tools)
tree is a worked example of wrapping each endpoint — useful reading even
if you're not running MCP.

---

## Recipes

Multi-step workflows that compose several skills. Each lives at
`recipes/<name>.md`:

- `daily-call-report` — pull a daily usage report and format as Markdown
- `kick-and-lock-meeting` — live ops playbook with safety prompts
- `audit-bad-quality-calls` — quality forensics over a time window
- `provision-team-vmr` — new VMR + aliases + automatic participant in one flow
- `webhook-collector-bootstrap` — event sink registration + receiver skeleton

Invoke them through your host's recipe / workflow mechanism, or read them
as runbooks.

---

## Roadmap

This package aims to cover **every Pexip Infinity admin and platform API**
plus events, and then absorb the client-side surface today. Current state:

- [x] Configuration API — high-level + 4 dev-reference skills
- [x] Status API
- [x] History API
- [x] Command API
- [x] Operator runbook
- [ ] Event sinks (stub — flesh out webhook receiver patterns)
- [ ] External Policy API (stub)
- [ ] MJX / One-Touch Join (stub)
- [ ] Per-resource granular skills (`pexip-vmrs`, `pexip-end-users`, `pexip-gateway-rules`, `pexip-ldap-sync`, `pexip-licensing`, `pexip-alarms`, `pexip-conferencing-nodes`)
- [ ] New server-side domains: `pexip-cvi-teams`, `pexip-branding-manifest`, `pexip-infrastructure-commands`
- [ ] **Absorb [awesome-pexip-skills](https://github.com/Josh-E-S/awesome-pexip-skills)** into `skills/client/` (client SDK, webapp embed, CVI, branding)

Contributions welcome. See `CONTRIBUTING.md`.

---

## Companion packages

- [**pexip-mgmt-mcp**](https://github.com/Josh-E-S/pexip-mgmt-mcp) —
  reference MCP server implementation that pairs with the skills here.
  Wraps Pexip's four admin APIs as MCP tools. If you want ready-made
  tools instead of writing your own REST client, install this alongside
  the skills.
- [**awesome-pexip-skills**](https://github.com/Josh-E-S/awesome-pexip-skills)
  — client-side Pexip skills (`@pexip/infinity`, `@pexip/media`, webapp
  embedding, CVI, branding). Will eventually be absorbed into
  `skills/client/` here; until then, the two packages are companions.

---

## License

MIT. See `LICENSE`.
