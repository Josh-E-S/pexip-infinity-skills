---
name: pexip-event-sinks
description: Use when configuring or extending Pexip's event sink push API — register webhook URLs Pexip POSTs conference / participant / call lifecycle events to, build the receiver side of that contract, replay or backfill events, or move from polling the History API to a push-based pipeline. Triggers on `event_sink`, `/api/admin/configuration/v1/event_sink/`, `list_event_sinks`, `create_event_sink`, `update_event_sink`, `delete_event_sink`, `bulk_support`, `webhook`, "Pexip events", "push events", "real-time CDR", "event collector". Do NOT use for one-off live state reads (use `pexip-status-api` / `pexip-operations`) or post-call CDR pulls (use `pexip-history-api`).
license: MIT
---

# Pexip event sinks — webhook push events

Pexip Infinity can **push** real-time events for conferences, participants, and call milestones to an HTTP endpoint you control. The Pexip side is configured via the Configuration API's `event_sink` resource (CRUD wrapped by the `*_event_sink` MCP tools). The receiver side is your own HTTP listener — out of scope for the MCP server itself, in scope for this skill.

This is the **push-based alternative** to polling the History API. For high-volume platforms or anything approaching real-time, event sinks beat polling on latency, completeness (no 10,000-instance retention cap), and rate-limit headroom.

## When to use

- "Move from polling the History API to push events"
- "Set up a webhook so we get notified when calls start/end"
- "Build a CDR collector that survives the 10,000-instance retention limit"
- "Stream Pexip events into our data warehouse / SIEM / dashboard"
- Configuring `event_sink` records via the MCP server

## When NOT to use

- One-shot reads of live state → `pexip-status-api` / `pexip-operations/live-meeting-ops.md`
- Historical CDR queries / reports → `pexip-history-api` / `pexip-operations/reporting.md`
- Modifying the MCP server's `tools/event_sink.py` code → `pexip-config-api` (the CRUD is there)

## Configuration side (MCP tools)

```
list_event_sinks(name_contains="…")
get_event_sink(sink="<name or id>")
create_event_sink(name=…, url="https://…", version=2,
                  bulk_support=True, verify_tls=True,
                  username=…, password=…)
update_event_sink(sink=…, url=…, …)
delete_event_sink(sink=…)
```

`version=2` is the current event protocol version. `bulk_support=True` lets Pexip batch events in one POST body (recommended; receivers should support it).

If TLS verification fails on a self-signed lab node, you can set `verify_tls=False` per-sink, but **do not ship that to production** — events contain participant identifiers and call metadata.

## Event categories Pexip pushes

Pexip's event sink protocol covers roughly:

| Category | Examples |
|---|---|
| Conference lifecycle | `conference_started`, `conference_ended`, `conference_updated` |
| Participant lifecycle | `participant_connected`, `participant_disconnected`, `participant_updated` |
| Call lifecycle | `participant_call_quality_low`, `participant_call_disconnected` |
| Layout / role changes | `participant_role_changed`, `layout_changed` |

The exact event shape is documented at https://docs.pexip.com/admin/event_sink.htm — that's the authoritative reference for field names and payload schema. Don't memorize them here; they change between Pexip versions.

## Receiver side (out of scope for the MCP server)

You'll need a separate HTTP listener at the URL you registered. Minimum requirements:

1. **Accept POST** with `Content-Type: application/json`.
2. **Return 2xx quickly** (Pexip will retry on non-2xx and on timeout). Don't do heavy processing in the request handler — queue + ack.
3. **Validate HTTP Basic auth** if you set `username` / `password` on the sink.
4. **Tolerate batches.** If you set `bulk_support=True`, the body is an array of events, not a single event.
5. **Idempotency.** Pexip retries on failure — your handler must dedupe (typically by event `id` or `call_id`).

### Bootstrap pattern

The recipe `recipes/webhook-collector-bootstrap.md` walks through:
- Registering the sink with `create_event_sink`
- A minimal FastAPI/Flask/Cloud Function receiver
- An idempotent queue write (Redis Streams / Kafka / SQS)
- A reconciliation job that fills gaps from the History API

## Field gotchas

- **Event payloads are NOT exposed via the MCP server.** The MCP server only configures sinks; receiving and querying events is a separate system.
- **`bulk_support` is a contract.** If you set it true and your receiver only handles one event per request, you'll silently drop everything after the first event in a batch.
- **`url` must be reachable from every Conferencing Node**, not just the Management Node. Plan for the data-plane network when picking the host.
- **Pexip retries failed deliveries** but the retry budget is finite. Falling behind for hours can lose events. Pair with a reconcile job that fills gaps from the History API.

## Safety notes

- **Credentials in `username` / `password` are returned as null on GET.** Treat absence as "set but write-only".
- **The sink URL is plain text on GET.** Don't put secrets in the URL itself; use Basic auth or signed query params.
- **Disabling TLS verification is logged as a warning** but Pexip will happily POST to an HTTP URL too — be intentional.

## Reference source

- **Authoritative Pexip docs:**
  - Event sink overview: https://docs.pexip.com/admin/event_sink.htm
  - Configuration API (event_sink resource): https://docs.pexip.com/api_manage/api_configuration.htm
- **Reference implementation (MCP):** [`pexip-mgmt-mcp`](https://github.com/Josh-E-S/pexip-mgmt-mcp), `src/pexip_mcp/tools/event_sink.py` — one example of wrapping these endpoints.
- **Related skills:** `pexip-config-api` (the resource itself), `pexip-history-api` (the polling alternative), `pexip-operations/reporting.md` (reporting patterns)
- **Related recipe:** `recipes/webhook-collector-bootstrap.md`
- **Parent repo's roadmap:** see `TODO.md` in the `pexip-mgmt-mcp` repo for the "event-sink collector" sketch — a sibling project that would host the receiver side end-to-end.
