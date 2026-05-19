# Event sink — per-event field reference

Full per-event field schemas, sourced from the authoritative Pexip docs at
https://docs.pexip.com/admin/event_sink.htm. Load this from `SKILL.md`
when you need exact field names, types, and per-event payload shape.

The common message envelope (`node`, `seq`, `version`, `time`, `event`,
`data`) is described in `SKILL.md`; this file documents the contents of
the `data` field for each event type.

---

## Event sink lifecycle events

`eventsink_started`, `eventsink_updated`, `eventsink_stopped` all have
empty payloads: `"data": {}`. They mark the timestamp at which a sink
was configured, had its configuration changed, or was removed.

Use them to:

- Detect a `seq` reset (a fresh `eventsink_started` followed by `seq=1`).
- Audit configuration changes from the receiver side.
- Detect node shutdown (the corresponding `eventsink_stopped` may or
  may not arrive, depending on shutdown order — don't rely on it as
  the sole shutdown signal).

```json
{
  "node": "10.44.99.2",
  "seq": 1,
  "version": 2,
  "time": 1559897774.520606,
  "data": {},
  "event": "eventsink_started"
}
```

---

## Conference events

`conference_started`, `conference_updated`, `conference_ended`.

### Common fields (all three)

| Field | Type | Description |
|---|---|---|
| `guests_muted` | bool | Whether all Guests are muted |
| `is_locked` | bool | Whether the conference is locked |
| `is_started` | bool | Whether a Host with audio/video has joined (or a presentation-only Host clicked Start Conference) |
| `name` | string | Conference name — correlate across nodes by this field |
| `service_type` | string | `conference` (VMR), `lecture` (Virtual Auditorium), `two_stage_dialing` (Virtual Reception), `media_playback`, `test_call`, `gateway` |
| `start_time` | float | Unix time the conference started on this node |
| `tag` | string | Optional tag for tracking service usage |

### Only in `conference_ended`

| Field | Type | Description |
|---|---|---|
| `end_time` | float | Unix time the conference ended on this node |

### Example

```json
{
  "node": "10.47.2.21",
  "seq": 2,
  "version": 2,
  "time": 1559897886.582799,
  "event": "conference_started",
  "data": {
    "guests_muted": false,
    "is_locked": false,
    "is_started": false,
    "name": "meet.webapp",
    "service_type": "conference",
    "start_time": 1559897886.582629,
    "tag": ""
  }
}
```

**Multi-node duplication:** the same logical conference produces a
`conference_started` from **every** node that hosts a participant. The
`name` field is your correlation key. To count "real" conferences, dedupe
by `name` within a time window, not by raw event count.

---

## Participant events — common fields

These fields appear in `participant_connected`, `participant_updated`,
and `participant_disconnected`. The two media-stream events
(`participant_media_stream_window`, `participant_media_streams_destroyed`)
use a smaller subset — see those sections below.

| Field | Type | Description |
|---|---|---|
| `uuid` | string | Pexip's unique identifier for this participant *event leg* |
| `call_direction` | string | `in` (inbound to Pexip) or `out` (dialed from Pexip) |
| `call_id` | string | Correlates all messages from the same call leg |
| `call_tag` | string | Optional tag assigned to this participant |
| `conference` | string | Conference name |
| `connect_time` | float | Unix time the participant connected |
| `conversation_id` | string | Correlates separate "calls" (A/V, RDP, chat) for one logical participant |
| `destination_alias` | string | Alias dialed to connect |
| `display_name` | string | Display name |
| `encryption` | string | `"On"` or `"Off"` |
| `has_media` | bool | Whether this participant is using media |
| `is_idp_authenticated` | bool | IdP-authenticated at join |
| `is_client_muted` | bool | Participant muted themselves |
| `is_muted` | bool | Administratively muted |
| `is_presenting` | bool | Sending a presentation |
| `is_streaming` | bool | Streaming flag set |
| `media_node` | string | IP of the Conferencing Node handling media |
| `protocol` | string | `WebRTC` / `SIP` / `H323` / `TEAMS` / `MSSIP` / `GHM` / `RTMP` / `API` |
| `proxy_node` | string | Address of the Proxying Edge Node, if applicable |
| `related_uuids` | array | UUIDs of sibling participant events (e.g. presentation for the same logical user) |
| `remote_address` | string | Source IP of signaling |
| `role` | string | `chair` (Host), `guest`, `unknown` (in IVR / waiting) |
| `rx_bandwidth` | int | Receive bandwidth in kbps |
| `service_tag` | string | Service-level tag |
| `service_type` | string | `connecting`, `conference`, `lecture`, `two_stage_dialing`, `media_playback`, `test_call`, `ivr`, `waiting_room` |
| `signalling_node` | string | IP of node handling signaling |
| `source_alias` | string | Source alias of the call |
| `system_location` | string | Pexip location name |
| `tx_bandwidth` | int | Transmit bandwidth in kbps |
| `vendor` | string | Endpoint vendor / version string |

### Only in `participant_disconnected`

| Field | Type | Description |
|---|---|---|
| `disconnect_reason` | string | Free-text reason from a known enum — see `../../operations/pexip-operations/disconnect-reasons.json` |
| `duration` | float | Call duration in seconds |
| `end_time` | float | Unix time of disconnect |
| `media_streams` | array | **v1 only** — end-of-call media stats (in v2 these move to `participant_media_streams_destroyed`) |

### Example: `participant_disconnected` (v2)

```json
{
  "node": "10.44.34.11",
  "seq": 688,
  "version": 2,
  "time": 1606392917.976155,
  "event": "participant_disconnected",
  "data": {
    "protocol": "WebRTC",
    "disconnect_reason": "Timer expired awaiting token refresh",
    "is_presenting": false,
    "connect_time": 1606392757.777584,
    "duration": 160.19991468900116,
    "media_node": "10.44.34.11",
    "conference": "Alice's VMR",
    "display_name": "Alice",
    "uuid": "a0ed2c58-f45b-4d96-a1cb-89812ec938ea",
    "signalling_node": "10.44.34.15",
    "call_id": "a0ed2c58-f45b-4d96-a1cb-89812ec938ea",
    "role": "chair",
    "conversation_id": "a0ed2c58-f45b-4d96-a1cb-89812ec938ea",
    "rx_bandwidth": 1722,
    "tx_bandwidth": 868,
    "destination_alias": "meet.alice",
    "related_uuids": ["0b8eb723-cf9d-4540-b12d-0f28149a7560"],
    "remote_address": "10.44.250.22",
    "service_type": "conference",
    "system_location": "Ruscombe",
    "call_direction": "in",
    "end_time": 1606392917.976151
  }
}
```

---

## `participant_media_stream_window` (v2 only)

Fired when a participant's perceived call quality transitions between
buckets (e.g. good → bad). Contains the recent window's quality
samples and per-stream packet-loss history.

### `data` top-level fields

| Field | Type | Description |
|---|---|---|
| `uuid` | string | Participant UUID this window belongs to |
| `call_quality_was` | string | Previous bucket: `"0_unknown"`, `"1_good"`, `"2_ok"`, `"3_bad"`, `"4_terrible"` |
| `call_quality_now` | string | Current bucket (same enum) |
| `packet_loss_history` | array | Per-stream loss samples since the previous window |
| `recent_quality` | array | Quality samples for the current window |

### `packet_loss_history[]` entries

| Field | Type | Description |
|---|---|---|
| `stream_id` | string | Opaque per-stream id |
| `stream_type` | string | `audio`, `video`, `presentation` |
| `time` | float | Unix time of these stats |
| `time_delta` | float | Time delta from previous sample |
| `tx_packets_sent` | int | Count of packets sent |
| `tx_packets_lost` | int | Sent packets reported lost by far end |
| `rx_packets_received` | int | Count of packets received |
| `rx_packets_lost` | int | Packets lost on receive |

### `recent_quality[]` entries

| Field | Type | Description |
|---|---|---|
| `time` | float | Unix time of the sample |
| `time_delta` | float | Time delta from previous sample |
| `quality` | int / null | Aggregate audio + video quality (see enum below) |
| `audio` | int / null | Latest audio quality |
| `video` | int / null | Latest video quality |
| `presentation` | int / null | Latest presentation-stream quality |
| `applicationsharing` | int / null | Latest Skype-for-Business RDP / app-sharing quality |

### Quality enum

For the integer fields above (`quality`, `audio`, `video`,
`presentation`, `applicationsharing`):

| Value | Meaning |
|---|---|
| `null` | Stream not in use |
| `0` | Unknown |
| `1` | Good |
| `2` | OK |
| `3` | Bad |
| `4` | Terrible |

The string form used in `call_quality_was` / `call_quality_now` is
`"0_unknown"`, `"1_good"`, `"2_ok"`, `"3_bad"`, `"4_terrible"`.

### Example

```json
{
  "node": "10.0.1.52",
  "seq": 29,
  "version": 2,
  "time": 1603188859.437286,
  "event": "participant_media_stream_window",
  "data": {
    "uuid": "c0548ea2-6ba5-4726-a022-019c0cad75b6",
    "call_quality_was": "1_good",
    "call_quality_now": "3_bad",
    "packet_loss_history": [
      { "stream_id": "0",   "stream_type": "audio", "time": 1603188839.639175, "time_delta": -19.79547, "tx_packets_sent": 1227, "tx_packets_lost": 0, "rx_packets_received": 1120, "rx_packets_lost": 58 },
      { "stream_id": "1.0", "stream_type": "video", "time": 1603188841.533143, "time_delta": -17.90153, "tx_packets_sent": 2552, "tx_packets_lost": 0, "rx_packets_received": 1901, "rx_packets_lost": 104 }
    ],
    "recent_quality": [
      { "time": 1603188817.38981,  "time_delta": -42.044601, "quality": 1, "audio": 1, "video": 0, "presentation": null, "applicationsharing": null },
      { "time": 1603188859.435012, "time_delta": 0,          "quality": 3, "audio": 3, "video": 3, "presentation": null, "applicationsharing": null }
    ]
  }
}
```

---

## `participant_media_streams_destroyed` (v2 only)

End-of-call media statistics, emitted separately from
`participant_disconnected` so signaling and media tear-down can be
timed independently.

### `data` top-level fields

| Field | Type | Description |
|---|---|---|
| `uuid` | string | Participant UUID |
| `media_streams` | array | End-of-call stats per stream |

### `media_streams[]` entries

| Field | Type | Description |
|---|---|---|
| `stream_id` | string | Opaque per-stream id |
| `stream_type` | string | `audio`, `video`, `presentation` |
| `node` | string | Media node that handled the stream |
| `start_time` | float | Unix time the stream started |
| `end_time` | float | Unix time the stream ended |
| `rx_bitrate` | int | Receive bitrate (kbps) |
| `rx_codec` | string | Codec received |
| `rx_fps` | float | Received frames per second |
| `rx_resolution` | string | Resolution received (e.g. `"1280x720"`) |
| `rx_packets_received` | int | Total packets received |
| `rx_packets_lost` | int | Total packets lost on receive |
| `rx_packet_loss` | float | Receive loss percentage |
| `tx_bitrate` | int | Transmit bitrate (kbps) |
| `tx_codec` | string | Codec sent |
| `tx_fps` | float | Sent frames per second |
| `tx_resolution` | string | Resolution sent |
| `tx_packets_sent` | int | Total packets sent |
| `tx_packets_lost` | int | Sent packets reported lost by far end |
| `tx_packet_loss` | float | Send loss percentage |

### Example

```json
{
  "node": "10.44.34.11",
  "seq": 687,
  "version": 2,
  "time": 1606392917.869103,
  "event": "participant_media_streams_destroyed",
  "data": {
    "uuid": "0b8eb723-cf9d-4540-b12d-0f28149a7560",
    "media_streams": [
      { "stream_id": "0",   "stream_type": "audio", "node": "10.47.2.21", "start_time": 1559902904.1698,  "end_time": 1559902945.767812, "rx_bitrate": 32,   "rx_codec": "opus", "rx_fps": 0,  "rx_resolution": "",          "rx_packets_received": 1977, "rx_packets_lost": 0, "rx_packet_loss": 0, "tx_bitrate": 1,    "tx_codec": "opus", "tx_fps": 0,  "tx_resolution": "",          "tx_packets_sent": 2020, "tx_packets_lost": 0, "tx_packet_loss": 0 },
      { "stream_id": "1.2", "stream_type": "video", "node": "10.47.2.21", "start_time": 1559902904.318265, "end_time": 1559902945.768668, "rx_bitrate": 1405, "rx_codec": "VP8",  "rx_fps": 30, "rx_resolution": "1280x720", "rx_packets_received": 4493, "rx_packets_lost": 0, "rx_packet_loss": 0, "tx_bitrate": 1545, "tx_codec": "VP8",  "tx_fps": 30, "tx_resolution": "1280x720", "tx_packets_sent": 6883, "tx_packets_lost": 0, "tx_packet_loss": 0 }
    ]
  }
}
```

---

## Bulk envelope

When `bulk_support=True`, Pexip groups events at an interval and sends
them in one POST:

```json
{
  "event": "eventsink_bulk",
  "node": "127.0.0.1",
  "seq": 0,
  "version": 2,
  "time": 1741679796.951206,
  "data": [
    { "event": "participant_updated", "node": "10.44.34.14", "seq": 2183, "time": 1741679792.93,  "version": 2, "data": { /* full participant_updated data */ } },
    { "event": "participant_updated", "node": "10.44.34.14", "seq": 2184, "time": 1741679794.45,  "version": 2, "data": { /* full participant_updated data */ } }
  ]
}
```

Detection rule: `node == "127.0.0.1"` **and** `event == "eventsink_bulk"`.
Each inner entry has its own real `node`, `seq`, `time`, `version`, and
`data`. The outer `seq=0` is a sentinel — never treat the outer message
as part of the per-node sequence.

Even with `bulk_support=True`, Pexip may still send single events under
low load. The receiver MUST handle both shapes; the safe pattern is:

```python
if msg.get("event") == "eventsink_bulk":
    for inner in msg["data"]:
        handle_event(inner)
else:
    handle_event(msg)
```

---

## Reference

- Authoritative Pexip docs: https://docs.pexip.com/admin/event_sink.htm
- Disconnect-reason enum: `../../operations/pexip-operations/disconnect-reasons.json`
- Configuration API for the `event_sink` resource: https://docs.pexip.com/api_manage/api_configuration.htm
