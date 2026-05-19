---
name: pexip-event-sinks
description: Use when configuring or extending Pexip's event sink push API — register webhook URLs Pexip POSTs conference / participant / call lifecycle events to, build the receiver side of that contract, correlate events into call records, move from polling the History API to a push-based pipeline. Triggers on `event_sink`, `/api/admin/configuration/v1/event_sink/`, `list_event_sinks`, `create_event_sink`, `update_event_sink`, `delete_event_sink`, `eventsink_started`, `eventsink_bulk`, `participant_connected`, `participant_disconnected`, `participant_media_stream_window`, `participant_media_streams_destroyed`, `conference_started`, `conference_ended`, `bulk_support`, `webhook`, "Pexip events", "push events", "real-time CDR", "event collector". Do NOT use for one-off live state reads (use `pexip-status-api` / `pexip-operations`) or post-call CDR pulls (use `pexip-history-api`).
license: MIT
---

# Pexip event sinks — webhook push events

## Quick reference

| Need | Where |
|---|---|
| Configure a sink (CRUD) | `/api/admin/configuration/v1/event_sink/` |
| Common message envelope | `node`, `seq`, `version`, `time`, `event`, `data` |
| Lifecycle events | `eventsink_started` / `_updated` / `_stopped`, `conference_started` / `_updated` / `_ended`, `participant_connected` / `_updated` / `_disconnected` |
| Quality / media (v2) | `participant_media_stream_window`, `participant_media_streams_destroyed` |
| Bulk delivery wrapper | `event: "eventsink_bulk"`, `node: "127.0.0.1"`, `seq: 0`, `data: [<events>]` |
| Per-event field schemas | [`events-reference.md`](events-reference.md) |
| Disconnect reasons enum | `pexip-operations/disconnect-reasons.json` |
| Receiver scaffolding recipe | `recipes/webhook-collector-bootstrap.md` |
| Authoritative docs | https://docs.pexip.com/admin/event_sink.htm |

Pexip Infinity **pushes** real-time events for conferences, participants,
and call milestones to an HTTP endpoint you control. The Pexip side is
configured via the Configuration API's `event_sink` resource. The
receiver side is your own HTTP listener — out of scope for the
reference MCP server itself, in scope for this skill.

Push beats polling on latency, completeness (no 10,000-instance
retention cap), and rate-limit headroom. Use it for real-time CDR,
quality forensics, dashboards, SIEM feeds, anything that needs to
react sooner than a periodic History API pull would allow.

## When to use

- "Move from polling the History API to push events"
- "Set up a webhook so we get notified when calls start/end"
- "Build a CDR collector that survives the 10,000-instance retention limit"
- "Stream Pexip events into our data warehouse / SIEM / dashboard"
- "Correlate audio + video + presentation streams for one logical participant"
- Configuring `event_sink` records via the MCP server

## When NOT to use

- One-shot reads of live state → `pexip-status-api` / `pexip-operations/live-meeting-ops.md`
- Historical CDR queries / reports → `pexip-history-api` / `pexip-operations/reporting.md`
- Modifying the MCP server's wrapper code itself → `pexip-config-api` (the CRUD lives there)

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

- `version=2` is the current event protocol version. v1 is supported but
  missing the media-stream events (`participant_media_stream_window`,
  `participant_media_streams_destroyed`) — see "Protocol versions" below.
- `bulk_support=True` lets Pexip batch events into one POST body
  (recommended; the receiver MUST handle both single and bulk shapes).
- Multiple sinks can be configured. Each sink gets its **own per-node
  `seq` counter** — see "The `seq` field" below.
- `url` must be reachable from **every Conferencing Node**, not just the
  Management Node. Plan the data-plane network when picking the host.

If TLS verification fails on a self-signed lab node you can set
`verify_tls=False` per-sink, but events contain participant identifiers
and call metadata — never ship that to production.

## The message envelope

Every event Pexip POSTs has the same outer shape:

```json
{
  "node": "10.44.99.2",
  "seq": 1,
  "version": 2,
  "time": 1559897774.520606,
  "event": "eventsink_started",
  "data": { … }
}
```

- **`node`** — primary IP of the Conferencing Node that originated the
  event, **except for bulk messages** where it is hard-coded to
  `127.0.0.1` (that's how you detect a bulk envelope, not the event name).
- **`seq`** — sequence number on this Conferencing Node since the sink
  was started. Resets to `1` when the sink is stopped and restarted.
  Per-sink, per-node: if you have two sinks, each gets its own counter.
- **`version`** — Pexip event protocol version (currently `2`).
- **`time`** — Unix timestamp of the message.
- **`event`** — event name (see catalog below).
- **`data`** — event-specific payload; see `events-reference.md` for full schemas.

## Event catalog

Three groups plus a bulk wrapper.

### Event sink lifecycle

| Event | When |
|---|---|
| `eventsink_started` | A sink starts on this node |
| `eventsink_updated` | A sink's configuration changes |
| `eventsink_stopped` | A sink stops (deleted, or node shutdown) |

`data` is empty `{}` — these are just timestamps so you can detect
gaps and resets.

### Conference lifecycle

| Event | When |
|---|---|
| `conference_started` | A conference instance starts on this node |
| `conference_updated` | A conference property changes (lock, mute-all, etc.) |
| `conference_ended` | A conference instance ends on this node |

**Multi-node duplication — important.** A single logical conference can produce
**multiple `conference_started` / `conference_ended` events from
different nodes** as participants join and leave each node. Correlate
by the `name` field across nodes. Anyone counting conferences by raw
`conference_started` count will overcount.

### Participant lifecycle

| Event | When | Version |
|---|---|---|
| `participant_connected` | Participant joins | v1 + v2 |
| `participant_updated` | Participant property changes (role, mute, presentation, …) | v1 + v2 |
| `participant_media_stream_window` | Call quality changes between windows (e.g. good→bad) | **v2 only** |
| `participant_disconnected` | Participant disconnects (call signaling) | v1 + v2 |
| `participant_media_streams_destroyed` | Participant's media streams end (separate from signaling) | **v2 only** |

In **v1**, end-of-call media stats are folded into
`participant_disconnected` as a `media_streams` array. In **v2**, media
stats are emitted as a separate `participant_media_streams_destroyed`
event so disconnect signaling and media tear-down can be timed
independently. **v2 is preferred** for any analytics that depends on
media-stream timing.

### Bulk wrapper

When `bulk_support=True`, Pexip groups events at an interval and POSTs
them as one message:

```json
{
  "event": "eventsink_bulk",
  "node": "127.0.0.1",
  "seq": 0,
  "version": 2,
  "time": 1741679796.951206,
  "data": [
    { "event": "participant_updated", "node": "10.44.34.14", "seq": 2183, …  },
    { "event": "participant_updated", "node": "10.44.34.14", "seq": 2184, …  }
  ]
}
```

Detection: `node == "127.0.0.1"` and `event == "eventsink_bulk"`. Each
inner entry has its own real `node` and `seq`. **Always handle both
shapes** in the receiver — even with `bulk_support=True` Pexip may send
single events under load.

## Correlation: how to assemble a call record

Three identifiers, each for a different correlation level:

| Field | Correlates… | Stable across… |
|---|---|---|
| `uuid` | One participant event back to its participant | All events for that participant |
| `call_id` | Messages from the same call leg | All events for that call leg |
| `conversation_id` | Audio + video + presentation + chat for one logical participant | The whole logical participant's media graph |
| `related_uuids` | Sibling participant events (e.g. main A/V vs presentation stream) | At a point in time |

A "logical participant" — Alice in a meeting — can produce **multiple
`uuid`s** at the protocol level: one for her A/V leg, another for the
presentation she shares, possibly another for chat. To rebuild Alice's
full record, walk `related_uuids` from one of her events to find the
others, then group by `conversation_id`.

Practical rule of thumb:
- Need "events for this call leg"? → `call_id`
- Need "everything Alice did in this meeting"? → `conversation_id`
- Need "which events are siblings of this one right now"? → `related_uuids`

## Quality scoring enum (referenced from many events)

In `participant_media_stream_window.recent_quality[].*`:

| Field | Values |
|---|---|
| `quality` / `audio` / `video` / `presentation` / `applicationsharing` | `null` (not in use), `0` (Unknown), `1` (Good), `2` (OK), `3` (Bad), `4` (Terrible) |
| `call_quality_was` / `call_quality_now` | String: `"0_unknown"`, `"1_good"`, `"2_ok"`, `"3_bad"`, `"4_terrible"` |

The number-vs-string split is intentional — the per-window samples use
integers (compact), the transition markers use strings (self-describing
for log lines).

`participant_disconnected.disconnect_reason` is a free-text string but
the values come from a known enum. See
`pexip-operations/disconnect-reasons.json` for the catalog.

## Receiver side

You'll need a separate HTTP listener at the URL you registered.
Requirements:

1. **Accept POST** with `Content-Type: application/json`.
2. **Return 2xx quickly.** Pexip retries on non-2xx and timeout, and
   queues build up fast under load. Don't do heavy processing in the
   request handler — receive, queue, ack. See "Performance" below.
3. **Validate HTTP Basic auth** if you set `username` / `password` on
   the sink.
4. **Tolerate batches.** With `bulk_support=True`, the body is an
   `eventsink_bulk` envelope with `data` as an array. With it off, a
   single event. Handle both — Pexip may send singles even with bulk on.
5. **Idempotency.** Pexip retries on failure; dedupe on
   `(node, seq)` or on `(uuid, event_name)`.
6. **Detect resets.** `seq` restarts at `1` when a sink is restarted on
   a node. Pair an `eventsink_started` with the immediately following
   `seq=1` to detect a reset cleanly.

### Performance

Per the spec, deliveries are **in-order, one-by-one** by default, so a
slow receiver builds a queue on the Conferencing Node. With bulk
enabled, the queue is shorter but bursts still hit the receiver.
Either way:

- **Offload immediately** from the request handler to a local queue
  (Redis Streams / Kafka / SQS / channel + worker pool). The handler's
  only job is "validate auth, accept JSON, push to queue, return 200."
- **Diagnose back-pressure.** Track and alarm on receiver
  response-time percentiles and on the gap between Pexip's `time`
  field and your processing time.
- **Don't block on downstream sinks.** If a downstream system
  (warehouse, SIEM) is slow, the queue absorbs it. If you write
  synchronously to a slow downstream, you'll spread the slowness to
  Pexip itself.

### Bootstrap recipe

`recipes/webhook-collector-bootstrap.md` walks through:
- Registering the sink with `create_event_sink`
- A minimal FastAPI / Flask / Cloud Function receiver
- An idempotent queue write
- A reconciliation job that fills gaps from the History API

## Field gotchas

- **Event payloads are NOT exposed via the management API.** The
  management side configures sinks; receiving and querying events is a
  separate system you build.
- **`bulk_support` is a contract.** If you set it true and your
  receiver only handles a single event per request, you'll silently
  drop everything after the first event in a batch.
- **`seq` is per-sink-per-node.** Multiple sinks → each sees its own
  consecutive numbering. Don't try to merge `seq` across sinks; merge
  on `(node, time)` or correlate by `call_id`.
- **Multi-node duplicates** (see "Conference lifecycle" above) — every
  consumer that counts events must dedupe by `name` or `call_id`.

## Safety notes

- **Credentials in `username` / `password` are returned as `null` on GET.**
  Treat absence as "set but write-only."
- **The sink URL is plain text on GET.** Don't embed secrets in the URL
  path or query; use Basic auth instead.
- **Disabling TLS verification is logged as a warning** but Pexip will
  happily POST to an HTTP URL too — be intentional.
- **Events contain participant identifiers, IP addresses, vendor
  strings, and call metadata.** Treat the sink endpoint as PII-bearing
  and apply the same retention and access controls as a CDR pipeline.

## Protocol versions

- **v2** — current. Adds `participant_media_stream_window` and
  `participant_media_streams_destroyed`, splits media stats out of
  `participant_disconnected`.
- **v1** — older. `media_streams` is bundled into
  `participant_disconnected` instead of a separate event. No
  per-window quality samples.

Set `version=2` on new sinks. If you're on v1 and migrating, your
receiver must (a) start handling the two new event types and (b) stop
expecting `media_streams` inside `participant_disconnected`.

## Reference source

- **Authoritative Pexip docs:**
  - Event sink overview / payload reference: https://docs.pexip.com/admin/event_sink.htm
  - Configuration API (`event_sink` resource): https://docs.pexip.com/api_manage/api_configuration.htm
- **Per-event field schemas (this skill):** [`events-reference.md`](events-reference.md)
- **Reference implementation (MCP):** [`pexip-mgmt-mcp`](https://github.com/Josh-E-S/pexip-mgmt-mcp), `src/pexip_mcp/tools/event_sink.py` — one example of wrapping these endpoints.
- **Related skills:** `pexip-config-api` (the resource itself), `pexip-history-api` (the polling alternative), `pexip-operations/reporting.md` (reporting patterns), `pexip-operations/disconnect-reasons.json` (disconnect-reason enum)
- **Related recipe:** `recipes/webhook-collector-bootstrap.md`
