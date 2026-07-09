---
name: pexip-rest-client-api
description: Use when building a Pexip client outside the browser — native iOS or Android app, Python/Node.js/Go server-side bot, CLI tool, desktop app, or Electron app — that needs to join conferences, receive real-time events, and control meetings via HTTP. Covers token auth, PIN auth, SDP/ICE call setup, the SSE event stream (participants, presentation, chat, captions, stage), and all REST control endpoints (mute, kick, lock, dial-out, layout, screenshare). Triggers when someone is building a native mobile Pexip app, a server-side script or bot that joins or monitors Pexip calls, a CLI tool for conference control, or any Pexip integration where PexRTC is not available. Also triggers on `/api/client/v2/`, `request_token`, `refresh_token`, `take_floor`, `release_floor`, SSE event stream, native Pexip client, server-side Pexip bot. Do NOT use for browser web apps (use pexip-pexrtc) or @pexip/infinity npm SDK (use pexip-call-lifecycle).
license: MIT
---

The REST Client API is the right choice when you **cannot load pexrtc.js** — native mobile, desktop, CLI — or when you need raw HTTP control over the WebRTC stack. For browser apps, PexRTC (`pexip-pexrtc`) is almost always the better choice: it abstracts SDP/ICE and works with a single script tag.

## When to use the REST API instead of PexRTC

| Situation | Choose |
|---|---|
| Browser web app | PexRTC |
| React Native / Flutter / Swift / Kotlin | REST API |
| Server-side bot (Node.js, Python, Go…) | REST API |
| CLI tool or automation script | REST API |
| Need to manage the WebRTC peer connection yourself | REST API |
| No JavaScript / no browser context | REST API |

## Auth flow: `request_token`

Every session starts with a token. The token is refreshed periodically and released on disconnect.

```
POST https://<node>/api/client/v2/conferences/<alias>/request_token
```

Headers for PIN-protected conferences:
```
Pin: <host-or-guest-pin>
```

Request body (JSON):
```json
{
    "display_name": "Alice",
    "call_tag": "my-client"
}
```

Response fields you need:
```json
{
    "token": "<bearer-token>",
    "expires": 120,
    "participant_uuid": "<uuid>",
    "role": "HOST",
    "service_type": "conference",
    "stun": [{"url": "stun:..."}],
    "turn": [{"url": "turn:...", "username": "...", "credential": "..."}],
    "chat_enabled": true,
    "version": {"version_id": "35"}
}
```

Use the returned `stun`/`turn` servers when building your `RTCPeerConnection`.

Refresh every `expires / 2` seconds:
```
POST /api/client/v2/conferences/<alias>/refresh_token
Authorization: Bearer <token>
```

Release on disconnect:
```
POST /api/client/v2/conferences/<alias>/release_token
Authorization: Bearer <token>
```

## SSE event stream

After obtaining a token, open the event stream:
```
GET /api/client/v2/conferences/<alias>/events
Authorization: Bearer <token>
```

This is a long-lived `text/event-stream` (Server-Sent Events) connection. Parse each `data:` line as JSON. Key events:

| Event name | Fired when |
|---|---|
| `participant_sync_begin` | Start of initial roster sync |
| `participant_create` | Participant joins (or initial sync entry) |
| `participant_update` | Participant state changes |
| `participant_delete` | Participant leaves |
| `participant_sync_end` | Initial sync complete |
| `conference_update` | Conference properties change (locked, recording, etc.) |
| `presentation_start` | Someone begins presenting |
| `presentation_stop` | Presentation ends |
| `message_received` | Chat message arrives |
| `stage` | Active speaker order update |
| `live_captions` | Caption text (with `is_final`, `src_lang`, `tgt_lang`) |
| `call_disconnected` | Your call was ended server-side |
| `layout_update` | Layout or participant positions changed |
| `breakout_begin/end/refer/update` | Breakout room lifecycle |

```python
import sseclient, requests

resp = requests.get(
    f'https://{node}/api/client/v2/conferences/{alias}/events',
    headers={'Authorization': f'Bearer {token}'},
    stream=True,
)
client = sseclient.SSEClient(resp)
for event in client.events():
    data = json.loads(event.data)
    handle_event(data['type'], data.get('data', {}))
```

## WebRTC call setup (SDP/ICE)

The REST API requires you to manage the `RTCPeerConnection` yourself.

```
POST /api/client/v2/conferences/<alias>/participants/<uuid>/calls
Authorization: Bearer <token>

Body: {
    "call_type": "WEBRTC",
    "sdp": "<your SDP offer>"
}
```

Response: `{"call_uuid": "<call_uuid>", "sdp": "<SDP answer>"}` — apply the answer to your peer connection.

Trickle ICE candidates:
```
POST /api/client/v2/conferences/<alias>/participants/<uuid>/calls/<call_uuid>/new_candidate
Body: {"candidate": "<ICE candidate string>", "mid": "<mid>"}
```

Acknowledge (required to start media):
```
POST /api/client/v2/conferences/<alias>/participants/<uuid>/calls/<call_uuid>/ack
```

ICE restart / SDP update:
```
POST /api/client/v2/conferences/<alias>/participants/<uuid>/calls/<call_uuid>/update
Body: {"sdp": "<new SDP offer>"}
```

## Conference and participant control

All endpoints require `Authorization: Bearer <token>`.

```
# Mute/unmute self
POST /participants/<uuid>/mute
POST /participants/<uuid>/unmute

# Video mute/unmute
POST /participants/<uuid>/video_muted
POST /participants/<uuid>/video_unmuted

# Raise/lower hand
POST /participants/<uuid>/buzz
POST /participants/<uuid>/clearbuzz

# Host controls
POST /conference/lock          Body: {"setting": true}
POST /conference/muteGuests    Body: {"setting": true}
POST /conference/startConference
POST /participants/<uuid>/disconnect
POST /participants/<uuid>/role  Body: {"role": "chair"}
POST /participants/<uuid>/transfer  Body: {"destination": "meet.bob", "role": "guest"}
POST /conference/disconnect

# Layout
POST /conference/transformLayout  Body: {"layout": "1:7"}

# Screenshare / presentation
POST /participants/<uuid>/take_floor
POST /participants/<uuid>/release_floor

# Chat
POST /conference/message   Body: {"payload": "Hello", "type": "text/plain"}
POST /participants/<uuid>/message  # direct

# Dial out
POST /conference/dial   Body: {"destination": "sip:bob@example.com", "protocol": "sip", "role": "guest"}

# DTMF
POST /participants/<uuid>/dtmf   Body: {"digits": "1234"}

# Live captions
POST /participants/<uuid>/showLiveCaptions
POST /participants/<uuid>/hideLiveCaptions
```

Base URL for all conference endpoints:
```
https://<node>/api/client/v2/conferences/<conference_alias>/
```

## Gotchas

- **Always release the token on disconnect.** Unreleased tokens hold a participant slot until they expire (~2 min). Use `finally` blocks.
- **Refresh before expiry.** Tokens expire; refresh at `expires/2` seconds. A 401 mid-call means the token expired.
- **`/ack` is required.** Media will not flow until you POST to `/ack` after applying the SDP answer.
- **ICE candidates must be sent before `/ack`.** Send all gathered candidates, then ack.
- **TURN credentials come from `request_token`** — don't hardcode them; they are session-scoped.
- **The SSE stream closes if the token expires** — keep your refresh loop alive for the duration.
- **PIN errors return HTTP 403**, not a JSON error body — check status code, not response content.

## Reference source

- Authoritative Pexip docs: https://docs.pexip.com/api_client/api_rest.htm
- Related skills: `pexip-pexrtc` (browser / PexRTC alternative), `pexip-client-intake` (project scoping), `pexip-event-sinks` (server-side webhook events, separate from client SSE)
