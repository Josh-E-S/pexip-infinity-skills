# Pexip Infinity Skills

[![CI](https://github.com/Josh-E-S/pexip-infinity-skills/actions/workflows/ci.yml/badge.svg)](https://github.com/Josh-E-S/pexip-infinity-skills/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-green)](https://github.com/Josh-E-S/pexip-infinity-skills/blob/main/LICENSE)
[![Agent Skills Compatible](https://img.shields.io/badge/Agent_Skills-compatible-blue)](https://agentskills.io)

> **Status: actively maturing.** All 27 skills are usable today, but two
> quality passes are still in progress:
>
> - **Trigger evals** — automated tests that confirm each skill fires on
>   real user phrasing. Currently authored for 4 of 27 skills; the rest
>   are being added incrementally.
> - **Manual skill-tree review** — walking each skill's `SKILL.md` and its
>   sibling docs against the authoritative Pexip sources for accuracy and
>   completeness.
>
> Expect content to keep improving. Pin a commit if you need stability.

`pexip-infinity-skills` is the **umbrella [Agent Skills](https://agentskills.io)
package for [Pexip Infinity](https://www.pexip.com/products/infinity-platform)**.
Drop it into any compliant skills host to give that host concrete,
current knowledge about Pexip — both **server-side** (admin APIs,
events, dial plan, external policy, room integration, operator
runbooks) and **web client-side** (TypeScript / React with
`@pexip/infinity` + `@pexip/media` and the rest of the `@pexip/*` SDK
family, webapp embedding, plugins, branding, CVI). Useful for building
applications, answering questions, debugging a deployment, or running
live operator workflows.

Native mobile and desktop clients (iOS / Android / Electron / …) use
separate Pexip SDKs and are not yet covered here — see Roadmap.

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
│   └── client/                   Client SDK / webapp / branding / plugins (17 skills)
├── recipes/                      Multi-skill workflows ready to run
└── scripts/                      Install / validate / scaffold / hygiene
```

There is **no `.mcp.json`** at the repo root. Users wire MCP via their own
host's config — see Prerequisites below.

## Skill index

**27 skills across server-side and client-side domains.**

### Server-side (`skills/_intake`, `operations`, `management-api`, `events`, `policy`, `room-integration`)

| Skill                      | Domain           | Audience                                                                                                  |
| -------------------------- | ---------------- | --------------------------------------------------------------------------------------------------------- |
| **pexip-intake**           | router           | both — start here for open-ended "I want to use Pexip" requests; routes server- or client-side            |
| **pexip-operations**       | operations       | operator — kick / lock / report / configure / health-check                                                |
| **pexip-config-api**       | management-api   | developer — Configuration admin API (CRUD on VMRs, dial plan, locations, end-users, …)                    |
| **pexip-status-api**       | management-api   | developer — Status admin API (live conferences, participants, node load, alarms)                          |
| **pexip-history-api**      | management-api   | developer — History admin API (post-call CDRs, quality forensics)                                         |
| **pexip-command-api**      | management-api   | developer — Command admin API (live actions: kick / mute / lock / transfer / layout)                      |
| **pexip-event-sinks**      | events           | both — webhook push events from Pexip                                                                     |
| **pexip-external-policy**  | policy           | developer — external policy server hooks for per-call decisions                                           |
| **pexip-mjx**              | room-integration | both — MJX / One-Touch Join for in-room video systems                                                     |
| **pexip-room-integration** | room-integration | developer — hardware room systems (Cisco RoomOS, Poly, Crestron, Q-SYS, Logitech) via macros / local APIs |

### Client-side (`skills/client/`) — web (TypeScript + React)

For building or customizing the **web meeting experience** — embedding
or extending webapp3, building custom web clients with Pexip's
JavaScript SDK (`@pexip/infinity`, `@pexip/media`, `@pexip/signal`,
`@pexip/components`, `@pexip/plugin-api`, …), branding manifests,
plugins, and CVI.

> **Scope note:** these skills cover Pexip's **web client surface only
> (TypeScript / React, browser runtime)**. Native iOS / Android /
> desktop / Electron clients use different SDKs and are not yet
> covered in this package — see the Roadmap.

| Skill                                | Audience                                                                                                |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------- |
| **pexip-client-intake**              | both — start here for open-ended client-side requests                                                   |
| **pexip-signals-pattern**            | developer —`@pexip/signal` pub/sub architecture, when to add a signal hub vs use React state            |
| **pexip-call-lifecycle**             | developer —`createInfinityClient`, join flows (PIN/IDP/extension/host-vs-guest), ICE restart, transfers |
| **pexip-media-pipeline**             | developer —`createMedia` + audio/video processors, denoise, blur, audio mixing, self-healing tracks     |
| **pexip-preflight**                  | developer — device enumeration, permission UX, mic/camera test, blocked-permission screens              |
| **pexip-reconnect**                  | developer —`NetworkState` coordination, toast-spam suppression, `onFailedRequest`                       |
| **pexip-chat**                       | developer — group + direct messages, optimistic UI, retry-queue reconciliation, character limit         |
| **pexip-participants**               | developer —`GroupKey` filters, mute/kick/admit, host/guest sorting, batched activity                    |
| **pexip-presentation**               | developer — screen sharing, content hints, audio mixing, ICE-restart preservation                       |
| **pexip-breakouts**                  | developer — open/edit/close rooms, auto vs manual assignment, ask-for-help, guest tokens                |
| **pexip-layouts**                    | developer — host vs personal layouts, lecture-mode guest layout, presentation-in-mix detection          |
| **pexip-branding-manifest**          | developer —`manifest.json` loading, color palette, hidden functionality, custom step iframe             |
| **pexip-plugin-host**                | developer —`@pexip/plugin-api`, sandboxed iframes, panel widgets, toolbar buttons                       |
| **pexip-stats-monitoring**           | developer —`onRtcStats`, `qualityLimitationReason`, `fpsVolatility`, call-quality UI                    |
| **pexip-browser-close-confirmation** | developer —`beforeunload` wiring, "Are you sure you want to leave?" prompt                              |
| **pexip-live-captions**              | developer — real-time transcription overlay, interim vs final, auto-clear timer, breakout reset         |
| **pexip-fecc**                       | developer — far-end camera control (PTZ), capability detection, currently-controlling tracking          |

See `ARCHITECTURE.md` for the design rules. See `CONTRIBUTING.md` for how
to add a skill and the public-repo hygiene policy enforced by pre-commit
hooks.

---

## Install

The package is host-agnostic; each host has its own way to load skills.
Pick whichever matches your tool.

> **Just want to act on a live deployment?** Loading the skills (below) is
> instant and needs nothing but the files. To actually _run_ commands
> against a Pexip Management Node, you'll also need an MCP host or direct
> REST access — see [Prerequisites](#prerequisites).

### Step 1 — Get the package

Clone the repo (or download it as a ZIP from GitHub and unzip it). Every
command below is run from inside the resulting folder.

```bash
git clone https://github.com/Josh-E-S/pexip-infinity-skills.git
cd pexip-infinity-skills
```

### Step 2 — Load the skills into your host

### Claude Code

The repo ships a Claude Code plugin manifest at `.claude-plugin/plugin.json`,
so the most ergonomic install is the plugin path:

```bash
# Local dev: load directly from this directory (run from the repo root)
claude --plugin-dir .

# Or, once published to a marketplace:
/plugin install pexip-infinity-skills@<marketplace-name>
```

You can also point Claude Code at individual skills by copying any
`skills/<domain>/<skill-name>/` directory into your skills tree:

```bash
mkdir -p ~/.claude/skills
cp -r skills/operations/pexip-operations ~/.claude/skills/
```

### Gemini CLI

Skills are picked up from Gemini CLI's configured skill directories. Copy
the ones you want:

```bash
mkdir -p ~/.gemini/skills
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
mkdir -p <host-skills-dir>
cp -r skills/operations/pexip-operations <host-skills-dir>/
```

### Bulk install (all skills at once)

```bash
# Default target — Claude Code's skills directory (~/.claude/skills)
./scripts/install.sh

# Or pass your own target directory
./scripts/install.sh ~/.gemini/skills/

# Prefer symlinks (so `git pull` updates the installed skills in place)
./scripts/install.sh --symlink ~/.claude/skills/
```

Run with no argument, it installs to `~/.claude/skills`. It copies every
skill in `skills/**/` into the target directory, flattening the domain
grouping (most hosts expect `<target>/<skill-name>/SKILL.md`), and skips
any skill that's already there. Add `--help` to see all options.

---

## Prerequisites

Two ways to actually _use_ the skills, both supported:

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

The package covers both server-side and client-side surface today, with
plenty of room to grow:

**Server-side**

- [x] Configuration API — high-level + 4 dev-reference skills
- [x] Status API
- [x] History API
- [x] Command API
- [x] Operator runbook
- [x] Event sinks (fleshed out webhook receiver patterns)
- [ ] External Policy API (stub)
- [ ] MJX / One-Touch Join (stub)
- [ ] Per-resource granular skills (`pexip-vmrs`, `pexip-end-users`, `pexip-gateway-rules`, `pexip-ldap-sync`, `pexip-licensing`, `pexip-alarms`, `pexip-conferencing-nodes`)
- [ ] New server-side domains: `pexip-cvi-teams`, `pexip-infrastructure-commands`

**Client-side — web (TypeScript / React)**

- [x] SDK foundation (signals, call lifecycle, media pipeline, preflight, reconnect)
- [x] Meeting features (chat, participants, presentation, breakouts, layouts, live captions, FECC)
- [x] Integration & polish (branding manifest, plugin host, stats monitoring, browser close)
- [ ] More CVI-specific skills for Teams / Webex / Zoom interop

**Client-side — native (not yet covered)**

- [ ] iOS SDK (Swift / Objective-C)
- [ ] Android SDK (Kotlin / Java)
- [ ] Desktop / Electron embed

Contributions welcome. See `CONTRIBUTING.md`.

---

## Companion packages

- [**pexip-mgmt-mcp**](https://github.com/Josh-E-S/pexip-mgmt-mcp) —
  reference MCP server implementation that pairs with the skills here.
  Wraps Pexip's four admin APIs as MCP tools. If you want ready-made
  tools instead of writing your own REST client, install this alongside
  the skills.

---

## License

MIT. See `LICENSE`.
