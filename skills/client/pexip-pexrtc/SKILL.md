---
name: pexip-pexrtc
description: Use for any browser-based Pexip video app — building, debugging, or planning. Covers the full PexRTC API: call setup and negotiation, PIN/IDP/extension auth, media (audio/video/screenshare), participant roster, host controls (mute all, lock, kick, dial-out, layout), chat, breakout rooms, FECC, live captions, STUN/TURN, and React integration. Triggers when someone wants to build a Pexip web app, telehealth/telemedicine app, video widget, or progressive web app; when debugging call connection, media, or video issues in a browser Pexip client; when planning features like chat, raised hands, layouts, or screenshare; or when asked how Pexip call negotiation works in the browser. Also triggers on `PexRTC`, `makeCall`, `onSetup`, `onConnect`, `pexrtc.js`, `connect(pin)`, `onParticipantCreate`, `disconnectParticipant`, `transformLayout`, `present`, `sendChatMessage`, `createBreakout`. Do NOT use for @pexip/infinity npm SDK (use pexip-call-lifecycle) or non-browser clients (use pexip-rest-client-api).
license: MIT
---

PexRTC is the right choice for **95% of Pexip web integrations**: no npm install, no bundler, no TypeScript required — load one script tag and you get a full-featured WebRTC client with every host control, roster event, and media feature Pexip supports.

## Loading and instantiating

```html
<script src="https://<node>/static/webrtc/js/pexrtc.js"></script>
<script>
  const rtc = new PexRTC();
</script>
```

Assign all callbacks **before** calling `makeCall`. The API is callback-based — no promises, no signals.

## The join flow

```
makeCall() → onSetup → connect(pin) → onConnect(stream) → [in meeting]
                ↑ may re-fire (wrong PIN, extension required, IDP selection)
```

```javascript
rtc.onSetup = function(stream, pin_status, conference_extension, idp_selection) {
    // pin_status: 'none' | 'required' | 'optional'
    // conference_extension: non-null if this is a Virtual Reception
    if (conference_extension) {
        // Show extension picker, then: rtc.connect(null, chosenExtension);
        return;
    }
    if (pin_status === 'required') {
        // Show PIN form, then: rtc.connect(enteredPin);
        return;
    }
    rtc.connect(null); // no PIN needed
};

rtc.onConnect = function(stream) {
    // stream is null for roster-only (call_type: 'none') sessions
    if (stream) videoEl.srcObject = stream;
};

rtc.onError = function(err) {
    console.error('Fatal call error:', err);
};

rtc.onDisconnect = function(reason) {
    console.log('Disconnected:', reason);
};

// Pre-call config (set before makeCall)
rtc.bandwidth_in  = 1264;
rtc.bandwidth_out = 1264;
// rtc.audio_source = deviceId;  // specific mic
// rtc.video_source = deviceId;  // specific camera
// rtc.user_media_stream = stream; // pre-acquired MediaStream

rtc.makeCall('<node_fqdn>', 'meet.alice', 'Alice', 1264, 'audiovisual');
```

### Call types for `makeCall`

| Value | Media |
|---|---|
| `'audiovisual'` (default) | Audio + video |
| `'audioonly'` | Audio only |
| `'recvonly'` | Receive-only (no mic/cam) |
| `'screen'` | Screenshare as primary |
| `'none'` | Roster + control, no media |

## Participant roster

```javascript
const participants = new Map();

rtc.onParticipantCreate = p => participants.set(p.uuid, p);
rtc.onParticipantUpdate = p => participants.set(p.uuid, p);
rtc.onParticipantDelete = p => participants.delete(p.uuid);
```

Key participant fields: `uuid`, `display_name`, `role` (`"chair"` / `"guest"`), `is_muted`, `is_video_muted`, `is_presenting`, `service_type`, `protocol`, `buzz_time`, `fecc_supported`.

Your own UUID and role are available as `rtc.uuid` and `rtc.role` after `onConnect`.

## Host controls

```javascript
// Conference-level
rtc.setConferenceLock(true);
rtc.setMuteAllGuests(true);
rtc.setGuestsCanUnmute(false);
rtc.startConference();            // release waiting room
rtc.transformLayout({ layout: '1:7', streaming_indicator: true });

// Per-participant
rtc.setParticipantMute(uuid, true);
rtc.videoMuted(uuid);             // mute video
rtc.setRole(uuid, 'chair');       // promote to host
rtc.setParticipantSpotlight(uuid, true);
rtc.setBuzz();                    // raise own hand
rtc.clearBuzz(uuid);              // lower specific hand
rtc.clearAllBuzz();
rtc.disconnectParticipant(uuid);
rtc.transferParticipant(uuid, 'meet.bob', 'guest', null);
rtc.dialOut('sip:bob@example.com', 'sip', 'guest', cb, {});
rtc.sendDTMF('1234', uuid);
```

## Screenshare and presentation

```javascript
// Start outgoing screenshare
rtc.present('screen');
rtc.onScreenshareConnected = stream => { previewEl.srcObject = stream; };
rtc.onScreenshareStopped   = reason => console.log('Screenshare ended:', reason);

// Stop outgoing screenshare
rtc.present(null);

// Receive incoming presentation (full framerate)
rtc.getPresentation();
rtc.onPresentationConnected    = stream => { presEl.srcObject = stream; };
rtc.onPresentationDisconnected = reason => { presEl.srcObject = null; };

// Track who is presenting
rtc.onPresentation = (active, presenterName, presenterUuid) => {
    // active=true may fire twice without intervening false (presenter change)
};
```

## Chat

```javascript
rtc.onChatMessage    = msg => console.log(msg.origin, msg.payload);
rtc.onDirectMessage  = msg => console.log('DM from', msg.origin, msg.payload);

rtc.sendChatMessage('Hello everyone');       // broadcast
rtc.sendChatMessage('Hello Alice', uuid);    // direct
rtc.sendApplicationMessage({ type: 'ping' }); // arbitrary JSON
```

## Breakout rooms

```javascript
// Create a breakout (host only)
rtc.createBreakout('Room A', 0, 'transfer', [uuid1, uuid2], true, cb);

// Move participants between breakouts
rtc.moveToBreakout(breakout_uuid);
rtc.moveParticipantsFromBreakout(fromUuid, toUuid, [participantUuid]);
rtc.closeBreakout(breakout_uuid);

// Guest requesting help
rtc.setBreakoutHelp(true);
rtc.onBreakoutHelp = (breakout_uuid, setting) => { /* notify host */ };
```

## Live captions and FECC

```javascript
// Live captions
rtc.showLiveCaptions(uuid);
rtc.onLiveCaptions = msg => {
    // msg.data, msg.is_final, msg.src_lang, msg.tgt_lang
    renderCaption(msg.data, msg.is_final);
};

// Far-end camera control
rtc.fecc_supported = true;   // declare before makeCall
rtc.sendFECC('start', 'pan', 'left', uuid, 500);
rtc.onFECC = signal => { /* received FECC from another participant */ };
```

## Mid-call device/bandwidth changes

```javascript
// Switch camera or mic mid-call
rtc.video_source = newDeviceId;
rtc.renegotiate(false);   // false = device switch (no SDP resend)

// Change bandwidth mid-call
rtc.bandwidth_in  = 2048;
rtc.bandwidth_out = 2048;
rtc.renegotiate(false);

// Force SDP renegotiation (e.g., after network change)
rtc.renegotiate(true);
```

## STUN / TURN configuration

```javascript
rtc.default_stun = 'stun:stun.example.com';
rtc.turn_server  = {
    urls: ['turn:turn.example.com'],
    username: 'user',
    credential: 'secret',
};
```

## React integration pattern

```jsx
import { useEffect, useRef } from 'react';

function PexipCall({ node, alias, displayName }) {
    const videoRef = useRef(null);
    const rtcRef   = useRef(null);

    useEffect(() => {
        const rtc = new window.PexRTC();
        rtcRef.current = rtc;

        rtc.onSetup = (stream, pin_status) => {
            // Show PIN modal if pin_status === 'required', else:
            rtc.connect(null);
        };
        rtc.onConnect = stream => {
            if (videoRef.current) videoRef.current.srcObject = stream;
        };
        rtc.onDisconnect = () => { /* update UI */ };
        rtc.onError      = err => console.error(err);

        rtc.makeCall(node, alias, displayName, 1264, 'audiovisual');
        return () => rtc.disconnect();
    }, [node, alias, displayName]);

    return <video ref={videoRef} autoPlay playsInline />;
}
```

## Gotchas

- **`onSetup` and `onConnect` each fire more than once.** `onSetup` re-fires on wrong PIN or extension step; `onConnect` re-fires when video is ready after an initial roster-only fire. Guard state transitions with a flag.
- **`audio_source`/`video_source` and `user_media_stream` are mutually exclusive** — pick one before `makeCall` and don't switch approaches.
- **`onRosterList` is deprecated** — use `onParticipantCreate`/`Update`/`Delete`.
- **`onPresentation(true)` can follow `onPresentation(true)`** without an intervening `false` — this signals a presenter change, not a double-fire bug.
- **`getMediaStatistics()` is Chrome-only.**
- **`transformLayout({})` resets all layout parameters** — pass only the fields you want to change; an empty object clears everything.
- **`disconnect()` is synchronous and blocks briefly** — don't call it in a `beforeunload` handler; use `disconnectcall()` there.

## Reference source

- Authoritative Pexip docs: https://docs.pexip.com/api_client/api_pexrtc.htm
- Related skills: `pexip-client-intake` (project scoping), `pexip-rest-client-api` (non-browser / raw REST alternative), `pexip-call-lifecycle` (@pexip/infinity npm SDK)
