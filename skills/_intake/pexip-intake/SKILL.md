---
name: pexip-intake
description: Use at the START of any open-ended Pexip Infinity task — server-side (management/admin APIs, events, policy, room integration, dial plan) or client-side (webapp, embedded client, CVI, branding) — to scope the work before answering. Triggers when the user says "I want to use Pexip", "set up Pexip", "automate Pexip", "report on Pexip calls", "build a Pexip app", or any project-shaped request without specifics. Ask the questions in this skill BEFORE diving in. Do NOT use for narrow specific questions like "how does summarize_calls work" or "kick Alice from the standup" — only for project-shaped requests where the user hasn't yet decided what they're building.
license: MIT
---

# Pexip intake

A Pexip task can be many shapes. On the **server side**: a one-off operator action ("kick this person"), a recurring report ("daily call volume"), a configuration push ("add 50 VMRs"), an integration extension ("build a webhook receiver"), or a developer task wrapping the admin APIs ("add a tool that calls endpoint X"). On the **client side**: embedding the webapp, building a custom client with the Pexip client SDK, configuring CVI for Teams/Webex/Zoom, or skinning the meeting experience with branding manifests.

The right skill set, dependencies, and operational stance differ a lot across these.

**Don't guess.** Ask a small number of targeted questions, then route.

Keep it brief. Most management tasks resolve in 2-3 questions.

## When to use

- Any "I want to use Pexip to…" type request, server-side or client-side
- Any "automate" / "report" / "monitor" / "embed" / "skin" Pexip request without scope
- The user mentioned Pexip but not what they're trying to build or do

## When NOT to use

- Narrow API questions: "what's the schema for `conference`?" → answer with `pexip-config-api`
- Live operator verbs: "kick Alice", "lock the AllHands" → answer with `pexip-operations`
- Specific tool questions: "how do I call `summarize_calls`?" → answer with `pexip-operations`
- Specific endpoint questions: route to the matching `pexip-*-api` developer-reference skill
- Specific client-side questions ("how do I add a Pexip widget to my React app"): route to `pexip-client-intake` or the matching `skills/client/pexip-*` skill

## The minimum questions

Ask one at a time, with options where possible. Stop as soon as you have enough to route.

### Q0. Server side or client side? (always ask first)

```
A) Server side — managing or extending a Pexip Infinity deployment:
   admin/management APIs, events, dial plan, room integration (MJX),
   external policy, reporting, operator runbooks
B) Client side — building or customizing the *meeting experience*:
   embedding the webapp, building with the Pexip client SDK, CVI for
   Teams/Webex/Zoom, branding manifests, custom layouts
C) Both / not sure yet — usually a full-stack feature
```

Routing:

- **A** → continue with Q1 below (this skill handles server-side routing)
- **B** → load `pexip-client-intake` (under `skills/client/`). It asks the
  webapp / SDK / branding / CVI scoping questions and routes to the matching
  client skill (`pexip-call-lifecycle`, `pexip-media-pipeline`,
  `pexip-signals-pattern`, `pexip-preflight`, `pexip-chat`, etc.).
- **C** → ask which half they want to start with; usually server side first
  (the client doesn't have anything to talk to until the deployment exists)

### Q1. What are you trying to do? (always ask for server-side)

```
A) One-off operator action against a live or recent meeting
   (kick, lock, transfer, change layout, check who's in)
B) Recurring reporting or monitoring
   (daily / weekly call volume, quality forensics, alarm dashboard)
C) Bulk configuration change
   (create N VMRs, update dial-plan rules, manage end users)
D) Write or extend code that wraps the Pexip admin APIs
   (add a new MCP tool, build a CLI / script / app that calls the REST
    endpoints directly, wrap an endpoint not currently covered)
E) Build a webhook receiver for Pexip events
   (event sinks pushing to a custom HTTP listener)
F) Integrate Pexip with a room system (MJX / One-Touch Join)
G) Other — please describe
```

Routing:

- **A** → `pexip-operations` (operator runbook, all live-meeting playbooks)
- **B** → `pexip-operations` → `reporting.md` (or `platform-health.md` for alarm-style monitoring)
- **C** → `pexip-operations` → `vmr-administration.md` and / or `dial-plan.md`
- **D** → the matching developer-reference skill:
  - Configuration CRUD → `pexip-config-api`
  - Live state reads → `pexip-status-api`
  - CDR / history reads → `pexip-history-api`
  - Live commands (kick/lock/transfer) → `pexip-command-api`
- **E** → `pexip-event-sinks`
- **F** → `pexip-mjx`
- **G** → ask follow-up

### Q2. How will you reach the Pexip Management API? (always ask)

```
A) Via the pexip-mgmnt MCP server (ready-made tools, no code to write
   for common operations)
B) Calling the REST endpoints directly from your own code (script, CLI,
   custom service)
C) Not sure / I just want to read the skills as documentation
```

If **A**:
- Confirm `pexip-mgmnt` shows up in the host's MCP server list.
- If not, point them at the install instructions in this package's `README.md`,
  and at the upstream server: https://github.com/Josh-E-S/pexip-mgmt-mcp
- Suggest they run `mcp-healthcheck.sh` (bundled with the `pexip-operations`
  skill, MCP-host-specific) to confirm the server is talking to the
  Management Node.

If **B**:
- All skills cite the underlying REST endpoint paths
  (`/api/admin/configuration/v1/…` etc.) and auth (HTTP Basic over HTTPS).
- The reference implementation in `pexip-mgmt-mcp:src/pexip_mcp/tools/`
  is a worked example of wrapping each endpoint, useful even if you're
  not running MCP.

If **C**:
- That's fine — every skill is readable as standalone documentation.
  Tool-name triggers in skill descriptions still apply if you later
  decide to add MCP.

### Q3. (Conditional) For routes A/B/C: confirm scope

Recurring reports? Ask:
```
- Time window the user cares about (today, this week, last 30 days, on a schedule?)
- Grouping (by direction? by quality? by VMR? by location?)
- Output format (Markdown? JSON? email?)
```

Bulk configuration? Ask:
```
- Are you adding, updating, or removing?
- Will you run this once, or repeatedly?
- Do you have the source data (CSV, spreadsheet, LDAP)?
```

Live operator action? Ask:
```
- Which conference / participant (be specific about name or alias)
- Is the action reversible (mute) or destructive (disconnect)?
```

For destructive actions specifically, also reference `pexip-operations/safety.md` before acting.

## Don't ask these (defaults are fine)

These have sensible defaults; don't make the user justify them:

- Output format → Markdown unless they ask otherwise
- Time format → UTC ISO 8601 on input, user's local TZ on display
- Pagination size → default 20, bump to `fetch_all=True` for reports
- Confirmation on destructive ops → on by default unless the user named the target unambiguously

## After the questions: the recommendation format

Respond with this shape:

```
Based on your answers, here's how I'd proceed:

  Skill(s) to load:
  - <skill name>          — for <one-line reason>
  - <skill name>          — for <one-line reason>

  First concrete step:
  <action, named tool call, or "I need X first">

  Open questions before I act:
  - <max 2-3 if anything's still unclear>
```

Then **wait for confirmation** before running any destructive tool. For read-only actions (list_*, get_*, summarize_calls) it's fine to proceed immediately.

## Example session

> User: "I want to start pulling daily call reports out of Pexip."

```
A few quick questions:

1. Which of these matches what you want?

   A) A one-shot report for a specific day, run on demand
   B) A scheduled daily report (emailed / posted somewhere)
   C) A live dashboard

   (For B/C we'll need somewhere to run a scheduler — out of scope
    for this skill package, but the skill content tells you how.)
```

> User: "B — emailed to me each morning."

```
2. What should it group calls by? Common options:

   - call_direction (in vs out)
   - call_quality   (good / ok / bad / terrible)
   - protocol       (sip / h323 / mssip / webrtc / rtmp / teams)
   - service_tag    (your tags on VMRs)
   - conference_name (per-VMR breakdown)
   - system_location (per-datacenter breakdown)
   - disconnect_reason

   You can also combine — start with one.
```

> User: "Direction and quality."

```
Plan:

  Skill(s) to load:
  - pexip-operations → reporting.md      (CDR / summarize_calls patterns)
  - recipes/daily-call-report.md         (end-to-end recipe for this exact use case)

  First step:
  Test the report by calling summarize_calls(start_time, end_time,
  group_by='call_direction') for yesterday. I'll then run the same
  with group_by='call_quality' and show both.

  Open questions:
  - Email transport: Gmail / Postmark / Mailgun / something else?
    (Out of scope for this skill package — you'll need a separate
     mail tool or a small cron job.)
```

## Reference source

- Authoritative Pexip docs: https://docs.pexip.com/api_manage/management_intro.htm
- Client-side counterpart router: `pexip-client-intake`
- Related skills (server-side): `pexip-operations`, `pexip-config-api`, `pexip-status-api`, `pexip-history-api`, `pexip-command-api`, `pexip-event-sinks`, `pexip-external-policy`, `pexip-mjx`
