# Tool index — all 69 pexip-mgmnt MCP tools

Grouped by intent. Each entry has the tool name and a one-line description. Use this as a lookup when you know WHAT you want to do but not which tool name to call.

## Live meeting state (Status API — read)

| Tool | Description |
|---|---|
| `list_active_conferences` | Currently-running conference instances. Filter by `name`, `service_type`, `tag`. |
| `list_active_participants` | Currently-connected participants. Filter by `conference_name`, `role`, `protocol`, `is_muted`. |
| `get_active_participant` | One active participant by UUID. |
| `list_node_status` | Live load + sync state for each Conferencing Node. |
| `get_node_status` | One Conferencing Node's live status. |
| `list_alarms` | Active platform alarms. Filter by `level`, `node_name`. |
| `get_licensing_status` | Concurrent port usage vs entitlement, per location. |
| `get_participant_quality` | Live call quality + per-stream stats for one participant. |

## Live meeting control (Command API — write)

| Tool | Idempotent? | Description |
|---|---|---|
| `dial_participant` | NO | Place an outbound call to add a participant to a running conference. |
| `disconnect_participant` | yes | Kick one participant (404 → already gone). |
| `mute_participant` / `unmute_participant` | yes | Audio mute one participant. |
| `video_mute_participant` / `video_unmute_participant` | yes | Video mute one participant. |
| `set_participant_role` | yes | Change role to `chair` or `guest`. |
| `spotlight_participant` / `unspotlight_participant` | yes | Pin a participant in the layout. |
| `transfer_participant` | NO | Move a participant to another conference. |
| `disconnect_conference` | yes | End a meeting (disconnect everyone). DESTRUCTIVE. |
| `lock_conference` / `unlock_conference` | yes | Lock new joiners out. |
| `mute_guests` / `unmute_guests` | yes | Audio mute every participant with role=guest. |
| `set_conference_layout` | yes | Change active layout. See `layouts.json` (sibling of `SKILL.md`). |

## Post-call (History API — read)

| Tool | Description |
|---|---|
| `list_history_conferences` | Completed conference instances in a time window. |
| `get_history_conference` | One past conference instance. |
| `list_history_participants` | Completed participant legs (CDRs). |
| `get_history_participant` | One past participant — includes `bucketed_call_quality` + `historic_call_quality`. |
| `summarize_calls` | Aggregate counts + duration in a time window, grouped by direction/quality/protocol/etc. **Prefer this for reporting.** |

## VMR / conference configuration

| Tool | Description |
|---|---|
| `list_vmrs` / `get_vmr` / `create_vmr` / `update_vmr` / `delete_vmr` | CRUD on Virtual Meeting Rooms. Name-or-id everywhere. |
| `list_aliases` / `add_vmr_alias` / `delete_alias` | Manage dial strings on a VMR. |
| `list_automatic_participants` / `add_automatic_participant` / `delete_automatic_participant` | Auto-dial entries (recorder, streamer) per VMR. |

## Directory

| Tool | Description |
|---|---|
| `list_end_users` / `get_end_user` / `create_end_user` / `update_end_user` / `delete_end_user` | Directory CRUD. Handle is `primary_email_address`. |
| `list_ldap_sources` / `get_ldap_source` / `create_ldap_source` / `update_ldap_source` / `delete_ldap_source` | LDAP / AD sync sources. `get_ldap_source` returns last sync status. |

## Dial plan

| Tool | Description |
|---|---|
| `list_gateway_rules` / `get_gateway_rule` / `create_gateway_rule` / `update_gateway_rule` / `delete_gateway_rule` | Outbound dial-plan rules, evaluated in ascending `priority`. |

## Infrastructure (read-only)

| Tool | Description |
|---|---|
| `list_locations` / `get_location` | System locations (datacenter / region groupings of nodes). |
| `list_conferencing_nodes` / `get_conferencing_node` | Conferencing Node configuration (the `worker_vm` resource). |
| `list_ivr_themes` / `get_ivr_theme` | Branding bundles assignable to VMRs. |

## Webhook / event sinks

| Tool | Description |
|---|---|
| `list_event_sinks` / `get_event_sink` / `create_event_sink` / `update_event_sink` / `delete_event_sink` | Configure URLs Pexip pushes events to. Does NOT receive events — run a separate HTTP listener at that URL. |

## Platform-wide

| Tool | Description |
|---|---|
| `get_global_settings` / `update_global_settings` | Singleton at `/configuration/v1/global/1/`. Affects the whole platform. |
| `get_resource_schema(resource=…)` | Fetch the live JSON schema for any resource. Use before guessing field names or enum values. |

## Intentionally NOT wrapped by the reference MCP server

The reference [`pexip-mgmt-mcp`](https://github.com/Josh-E-S/pexip-mgmt-mcp)
deliberately does **not** wrap these endpoints — they're either
deployment-tooling territory, security-sensitive, or too niche for an
admin-agent surface. They still exist in Pexip's REST API; you can call
them directly from your own code if you have a justified reason.

- TLS certificate / trusted CA management.
- Platform commands (`update_software`, `restart_conferencing_node`, `cloud_node_create` / `_delete`).
- DTMF injection (`participant/dtmf`) and text overlay (`participant/set_text_overlay`) — these inject content into live calls.
- Recurring conferences, MJX (One-Touch Join), SIP / H.323 / MSSIP signaling proxies.
- Backplane media stats (`/status/backplane/`), DNS lookup, node-to-node connectivity matrix.

If a user asks for one of these, surface that the reference MCP server
doesn't expose it. Options: extend the server, call the REST endpoint
directly, or use the Pexip admin UI.
