# Changelog

All notable changes to this package. Follows [Keep a Changelog](https://keepachangelog.com/).

## [0.2.0] — 2026-05-19

Adds client-side coverage under `skills/client/` — the package now spans
both server-side (admin APIs, events, dial plan, policy, room
integration) and client-side (webapp embedding, custom clients with
`@pexip/infinity` + `@pexip/media`, branding, plugins, CVI).

### Added (skills)

17 new client-side skills under `skills/client/`:

- `pexip-client-intake` — client-side scoping router; routed to from
  `pexip-intake`'s server-vs-client question.
- SDK foundation: `pexip-signals-pattern`, `pexip-call-lifecycle`,
  `pexip-media-pipeline`, `pexip-preflight`, `pexip-reconnect`.
- Meeting features: `pexip-chat`, `pexip-participants`,
  `pexip-presentation`, `pexip-breakouts`, `pexip-layouts`,
  `pexip-live-captions`, `pexip-fecc`.
- Integration & polish: `pexip-branding-manifest`, `pexip-plugin-host`,
  `pexip-stats-monitoring`, `pexip-browser-close-confirmation`.

### Changed

- `pexip-intake`'s Q0 (server side vs. client side) now routes
  client-side requests inward to `pexip-client-intake` instead of
  pointing at an external package.
- `README.md` skill index split into server-side and client-side
  tables; tree diagram and Roadmap updated to reflect the 26-skill
  state.
- `ARCHITECTURE.md` describes both halves and how the two intake
  routers cooperate.
- `scripts/validate-skills.py` gains link checking — every relative-path
  markdown link across SKILL.md sibling docs, recipes, and root docs is
  verified to resolve. Existing rules (frontmatter shape, name match,
  description hard-cap of 1,024 chars per the open spec, body-length
  ceiling, mandatory Reference source footer) carry over.

### Package size

- v0.1.0: 9 skills, 5 recipes.
- v0.2.0: **26 skills**, 5 recipes.

## [0.1.0] — 2026-05-19

Initial public release of `pexip-infinity-skills` as the umbrella
[Agent Skills](https://agentskills.io) package for the Pexip Infinity
platform.

### Host-agnostic, umbrella scope

- **Host-agnostic.** Skills no longer depend on any particular Agent
  Skills host. Works in Claude Code, Gemini CLI, Codex CLI, Cursor, Kiro,
  or anything else that follows the open Agent Skills spec.
- **MCP demoted from runtime to one recommended invocation path.** The
  bundled `.mcp.json` server config is gone from the repo root. Users
  wire MCP via their host's own config. Skills cite REST endpoints
  throughout; the [`pexip-mgmt-mcp`](https://github.com/Josh-E-S/pexip-mgmt-mcp)
  server is referenced as a worked example, not a dependency.
- **Reference-source footer convention softened.** The authoritative
  Pexip docs URL is mandatory; the MCP reference-implementation line
  is optional and cited only where a reference implementation exists.
- **Intake router widened.** Renamed `pexip-mgmt-intake` →
  `pexip-intake`. The router now asks a server-vs-client question
  first; client-side requests are pointed at the companion
  [`awesome-pexip-skills`](https://github.com/Josh-E-S/awesome-pexip-skills)
  package until that content is absorbed.
- **`skills/client/` reserved.** Empty placeholder for a future
  absorption of `awesome-pexip-skills` into this umbrella.

### Added (skills shipped in v0.1.0)

Nine skills, organized by domain:

- `_intake/pexip-intake` — router; asks 2-3 scoping questions and points
  the agent at the right tier-2 skill.
- `operations/pexip-operations` — operator runbook for using the Pexip
  admin APIs to do real work (control live meetings, run reports,
  administer VMRs / aliases / dial plan, check platform health).
- `management-api/pexip-config-api` — developer reference for the
  Configuration admin API (CRUD on VMRs, end-users, locations, dial-plan
  rules, conferencing nodes, IVR themes, …).
- `management-api/pexip-status-api` — developer reference for the Status
  admin API (live conferences, participants, node load, alarms,
  licensing, media stats).
- `management-api/pexip-history-api` — developer reference for the
  History admin API (post-call CDRs, call-quality forensics).
- `management-api/pexip-command-api` — developer reference for the
  Command admin API (live actions: kick / mute / lock / transfer /
  layout transforms).
- `events/pexip-event-sinks` — webhook push events from Pexip; stub.
- `policy/pexip-external-policy` — External Policy API for per-call
  routing / auth / admission decisions; stub.
- `room-integration/pexip-mjx` — MJX / One-Touch Join for in-room
  video systems; stub.

### Added (recipes)

Five multi-skill workflows under `recipes/`:

- `daily-call-report.md`
- `kick-and-lock-meeting.md`
- `audit-bad-quality-calls.md`
- `provision-team-vmr.md`
- `webhook-collector-bootstrap.md`

### Added (tooling)

- Pre-commit hygiene framework on `main` enforcing public-repo policy:
  secret scanning, custom hooks for author-tool attribution and
  internal-notes markers, PII / public-IP allowlisting, commit-message
  attribution guard. All hooks are bash-3.2 portable.
- GitHub Actions CI workflow (`.github/workflows/ci.yml`) running the
  hygiene hooks and `validate-skills.py` on every PR and push.
- `scripts/install.sh`, `scripts/new-skill.sh`, `scripts/validate-skills.py`
  for installing, scaffolding, and linting skills.

### Companion packages

- [`pexip-mgmt-mcp`](https://github.com/Josh-E-S/pexip-mgmt-mcp) —
  reference MCP server implementation.
- [`awesome-pexip-skills`](https://github.com/Josh-E-S/awesome-pexip-skills)
  — client-side Pexip skills package, to be absorbed into
  `skills/client/` in a future release.
