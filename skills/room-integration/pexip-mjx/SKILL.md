---
name: pexip-mjx
description: Use when configuring or extending Pexip's MJX (Microsoft Join eXchange, aka One-Touch Join) integration — the feature that lets in-room video systems show a single "Join" button on their console for scheduled meetings by pulling calendar data from Exchange / Office 365 / Google Workspace and overlaying it onto the room-system UI. Triggers on `mjx_endpoint`, `mjx_integration`, `mjx_meeting_processing_rule`, `one-touch join`, "OTJ", "in-room join", "Cisco / Poly / Logitech room system", "Exchange room mailbox", "calendar-driven join", `/api/admin/configuration/v1/mjx_endpoint/`. Do NOT use for general client-side join flows (that's the webapp3 / Pexip client SDK domain — see `awesome-pexip-skills`) or for managing the VMRs MJX joins (use `pexip-operations/vmr-administration.md`).
license: MIT
---

# Pexip MJX — One-Touch Join for room systems

**MJX (Microsoft Join eXchange)** is Pexip's room-system integration. It connects to your calendar system (Exchange Online / on-prem, or Google Workspace), reads the upcoming meetings on each room mailbox, detects video-meeting URLs/aliases inside the invite body (Pexip, Teams, Zoom, Webex, Google Meet), and pushes a normalized "Join" button to the in-room codec's UI so users tap one button instead of typing a long URI.

Three Pexip resources govern it:

- `mjx_endpoint` — a room video system (Cisco CE, Poly OBTP, Logitech Tap, etc.) Pexip pushes the Join button to
- `mjx_integration` — the calendar source (Exchange / Google) Pexip reads from
- `mjx_meeting_processing_rule` — regex/transform rules that detect each meeting platform in the invite body and produce the dial string

> **Status: stub.** This skill is a placeholder for the next round of coverage. The Pexip MJX API is real and supported, but the `pexip-mgmt-mcp` server does **not** currently wrap the `mjx_*` resources. Adding them is on the roadmap.

## When to use

- "Set up One-Touch Join for our conference rooms"
- "Why isn't the Join button showing up on the Webex panels?"
- "Add a rule to detect Zoom meetings in the calendar invite"
- "Migrate room systems from vendor's OTJ to Pexip MJX"
- Adding `mjx_*` resource tools to the MCP server

## When NOT to use

- Client-side / WebRTC / webapp3 join flows → that's the [awesome-pexip-skills](https://github.com/Josh-E-S/awesome-pexip-skills) repo (`call-lifecycle` skill)
- VMR creation / management → `pexip-operations/vmr-administration.md`
- General gateway dial-plan rules (for non-room calls) → `pexip-operations/dial-plan.md`

## Architecture in one diagram

```
                       Exchange/O365/Google Workspace
                                  │  calendar read
                                  ▼
                    ┌─────────────────────────┐
                    │   mjx_integration       │
                    │   (calendar source)     │
                    └────────────┬────────────┘
                                 │
                  detect meeting │ apply rules
                                 ▼
                    ┌─────────────────────────┐
                    │ mjx_meeting_processing  │
                    │ _rule (regex/transform) │
                    └────────────┬────────────┘
                                 │ produces join URI
                                 ▼
                    ┌─────────────────────────┐
                    │   mjx_endpoint          │
                    │   (Cisco / Poly / …)    │
                    │   gets "Join" button    │
                    └─────────────────────────┘
```

## Configuration (when MCP coverage lands)

Anticipated tool surface (not yet implemented):

```
# Calendar integrations
list_mjx_integrations(…)
create_mjx_integration(name=…, calendar_type="exchange"|"o365"|"google",
                       service_account=…, …)

# Room endpoints
list_mjx_endpoints(integration=…, …)
create_mjx_endpoint(name=…, room_email=…, endpoint_type="cisco_ce"|"poly_obtp"|"logitech_tap"|…,
                    api_address=…, api_username=…, api_password=…, …)

# Processing rules (detect meeting URLs inside invite body)
list_mjx_meeting_processing_rules(…)
create_mjx_meeting_processing_rule(name=…, match_string="...", dial_string_template="...",
                                   protocol="sip"|"h323"|..., …)
```

Until then: configure via Pexip's admin UI under **Call Control → MJX**.

## Common processing rules

The detect-meeting-URL-in-invite-body step is where most of the value lives. Useful patterns:

| Meeting platform | Match string (regex) | Dial string template |
|---|---|---|
| Pexip Infinity | `meet\.example\.com/([a-z0-9._-]+)` | `\1@meet.example.com` |
| MS Teams (via CVI) | `teams\.microsoft\.com/l/meetup-join/[^\s]+` | `<tenantid>.<meeting>@<cvi-tenant>` |
| Zoom (via Zoom CVI) | `zoom\.us/j/([0-9]+)` | `\1.<zoom-cvi-suffix>` |
| Google Meet | `meet\.google\.com/([a-z-]+)` | `\1@<google-meet-cvi-suffix>` |
| Webex (via CVI) | `\b([a-z0-9]+)@webex\.com\b` | `\1@<webex-cvi-suffix>` |

CVI = Cloud Video Interop. Each platform has its own CVI dial-string convention — check the platform docs (Teams CVI, Zoom CVI, Webex CMR).

## Field gotchas (anticipated, verify when implementing)

- **Room mailbox vs user mailbox.** MJX reads from **resource** (room) mailboxes, not user mailboxes. Common config mistake.
- **Service account permissions.** The Exchange/Google service account needs `Calendars.Read` on the room mailboxes — failure here is silent until you try a real meeting.
- **Endpoint capacity.** Cisco CE, Poly OBTP, Logitech Tap all have slightly different "Join" button limits per day; processing rules that fire on every invite line can exhaust them.
- **Polling vs push.** Exchange supports push subscriptions; Google Workspace polls. Latency for "calendar change reflected in room" can differ.

## Reference source

- **Authoritative Pexip docs:**
  - MJX overview: https://docs.pexip.com/admin/mjx_intro.htm
  - MJX configuration: https://docs.pexip.com/admin/configuring_mjx.htm
  - API reference: https://docs.pexip.com/api_manage/api_configuration.htm (search `mjx_endpoint`, `mjx_integration`, `mjx_meeting_processing_rule`)
- **Reference implementation (MCP):** _not yet implemented_ — could be added to [`pexip-mgmt-mcp`](https://github.com/Josh-E-S/pexip-mgmt-mcp) as `src/pexip_mcp/tools/mjx.py` per the existing pattern. Until then, call the REST endpoints directly.
- **Related skills:** `pexip-config-api` (resource model), `pexip-operations/dial-plan.md` (the static-rule sibling), `pexip-external-policy` (more dynamic alternative)
- **Sister repo:** Client-side equivalents (in-meeting plugins, room UX) live in [awesome-pexip-skills](https://github.com/Josh-E-S/awesome-pexip-skills).
