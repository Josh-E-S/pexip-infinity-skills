---
name: pexip-pexrtc
description: Use for any browser-based Pexip video app — building, debugging, or planning. Covers the full PexRTC API: call setup and negotiation, PIN/IDP/extension auth, media (audio/video/screenshare), participant roster, host controls (mute all, lock, kick, dial-out, layout), chat, breakout rooms, FECC, live captions, STUN/TURN, and React integration. Triggers when someone wants to build a Pexip web app, telehealth/telemedicine app, video widget, or progressive web app; when debugging call connection, media, or video issues in a browser Pexip client; when planning features like chat, raised hands, layouts, or screenshare; or when asked how Pexip call negotiation works in the browser. Also triggers on `PexRTC`, `makeCall`, `onSetup`, `onConnect`, `pexrtc.js`, `connect(pin)`, `onParticipantCreate`, `disconnectParticipant`, `transformLayout`, `present`, `sendChatMessage`, `createBreakout`. Do NOT use for @pexip/infinity npm SDK (use pexip-call-lifecycle) or non-browser clients (use pexip-rest-client-api).
license: MIT
---

PexRTC is the right choice for **95% of Pexip web integrations**: no npm install, no bundler, no TypeScript required — load one script tag and you get a full-featured WebRTC client with every host control, roster event, and media feature Pexip supports.

## Barebones working app

This is the complete minimal scaffold — copy, fill in `NODE`, `ALIAS`, and `DISPLAY_NAME`, and it works. Expand from here for any feature.

```html
<!DOCTYPE html>
<html>
<head><title>Pexip Call</title></head>
<body>
  <video id="remote" autoplay playsinline style="width:100%;background:#000"></video>
  <video id="local"  autoplay playsinline muted style="width:200px;position:fixed;bottom:1rem;right:1rem"></video>

  <div id="pin-screen" style="display:none">
    <input id="pin-input" type="password" placeholder="Enter PIN" />
    <button onclick="submitPin()">Join</button>
  </div>

  <div id="controls" style="display:none">
    <button onclick="toggleMic()">Mute mic</button>
    <button onclick="toggleCam()">Mute cam</button>
    <button onclick="shareScreen()">Share screen</button>
    <button onclick="hangup()">Leave</button>
  </div>

  <div id="chat">
    <div id="messages"></div>
    <input id="chat-input" placeholder="Message..." />
    <button onclick="sendChat()">Send</button>
  </div>

  <ul id="roster"></ul>

  <script src="https://NODE/static/webrtc/js/pexrtc.js"></script>
  <script>
    const rtc = new PexRTC();
    const participants = new Map();
    let micMuted = false, camMuted = false;

    // ── Callbacks ─────────────────────────────────────────────────────────────

    rtc.onSetup = function(stream, pin_status, conference_extension) {
      // Wire local preview (stream may be null for audio-only)
      if (stream) document.getElementById('local').srcObject = stream;

      if (pin_status === 'required' || pin_status === 'optional') {
        document.getElementById('pin-screen').style.display = 'block';
        // If optional, user can also click "Join without PIN" → rtc.connect(null)
      } else {
        rtc.connect(null);
      }
    };

    rtc.onConnect = function(stream) {
      document.getElementById('pin-screen').style.display = 'none';
      document.getElementById('controls').style.display = 'flex';
      if (stream) document.getElementById('remote').srcObject = stream;
    };

    rtc.onDisconnect = function(reason) {
      console.log('Disconnected:', reason);
      document.getElementById('controls').style.display = 'none';
    };

    rtc.onError = function(err) {
      console.error('Call error:', err);
    };

    // ── Roster ────────────────────────────────────────────────────────────────

    rtc.onParticipantCreate = p => { participants.set(p.uuid, p); renderRoster(); };
    rtc.onParticipantUpdate = p => { participants.set(p.uuid, p); renderRoster(); };
    rtc.onParticipantDelete = p => { participants.delete(p.uuid); renderRoster(); };

    function renderRoster() {
      const el = document.getElementById('roster');
      el.innerHTML = '';
      for (const p of participants.values()) {
        const li = document.createElement('li');
        li.textContent = `${p.display_name} (${p.role})${p.is_muted === 'YES' ? ' 🔇' : ''}`;
        el.appendChild(li);
      }
    }

    // ── Chat ──────────────────────────────────────────────────────────────────

    rtc.onChatMessage = msg => {
      const div = document.getElementById('messages');
      div.innerHTML += `<p><b>${msg.origin}:</b> ${msg.payload}</p>`;
    };

    function sendChat() {
      const input = document.getElementById('chat-input');
      if (input.value) { rtc.sendChatMessage(input.value); input.value = ''; }
    }

    // ── Controls ──────────────────────────────────────────────────────────────

    function submitPin() {
      const pin = document.getElementById('pin-input').value;
      rtc.connect(pin);
    }

    function toggleMic() {
      micMuted = rtc.muteAudio(!micMuted);
    }

    function toggleCam() {
      camMuted = rtc.muteVideo(!camMuted);
    }

    function shareScreen() {
      rtc.present('screen');
    }

    function hangup() {
      rtc.disconnect();
    }

    // ── Start ─────────────────────────────────────────────────────────────────

    rtc.makeCall('NODE', 'ALIAS', 'DISPLAY_NAME', 1264, 'audiovisual');
  </script>
</body>
</html>
```

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
    if (conference_extension) {
        // Virtual Reception — show extension picker
        // rtc.connect(null, chosenExtension);
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

rtc.onError      = err    => console.error('Fatal:', err);
rtc.onDisconnect = reason => console.log('Disconnected:', reason);

rtc.makeCall('<node_fqdn>', 'meet.alice', 'Alice', 1264, 'audiovisual');
```

### Call types

| Value | Media |
|---|---|
| `'audiovisual'` | Audio + video (default) |
| `'audioonly'` | Audio only |
| `'recvonly'` | Receive-only |
| `'screen'` | Screenshare as primary |
| `'none'` | Roster + control, no media |

## Participant roster

```javascript
const participants = new Map();
rtc.onParticipantCreate = p => participants.set(p.uuid, p);
rtc.onParticipantUpdate = p => participants.set(p.uuid, p);
rtc.onParticipantDelete = p => participants.delete(p.uuid);
```

Key fields: `uuid`, `display_name`, `role` (`"chair"` / `"guest"`), `is_muted`, `is_video_muted`, `is_presenting`, `buzz_time`, `fecc_supported`.
Own UUID/role available as `rtc.uuid` / `rtc.role` after `onConnect`.

## Host controls

```javascript
rtc.setConferenceLock(true);
rtc.setMuteAllGuests(true);
rtc.setGuestsCanUnmute(false);
rtc.startConference();                           // release waiting room
rtc.transformLayout({ layout: '1:7' });

rtc.setParticipantMute(uuid, true);
rtc.videoMuted(uuid);
rtc.setRole(uuid, 'chair');
rtc.setParticipantSpotlight(uuid, true);
rtc.setBuzz();                                   // raise own hand
rtc.clearBuzz(uuid);
rtc.clearAllBuzz();
rtc.disconnectParticipant(uuid);
rtc.transferParticipant(uuid, 'meet.bob', 'guest', null);
rtc.dialOut('sip:bob@example.com', 'sip', 'guest', cb, {});
```

## Screenshare and presentation

```javascript
rtc.present('screen');                           // start sharing
rtc.onScreenshareConnected = stream => { previewEl.srcObject = stream; };
rtc.onScreenshareStopped   = reason => {};
rtc.present(null);                               // stop sharing

rtc.getPresentation();                           // receive incoming
rtc.onPresentationConnected    = stream => { presEl.srcObject = stream; };
rtc.onPresentationDisconnected = reason => { presEl.srcObject = null; };
rtc.onPresentation = (active, name, uuid) => {}; // active=true may fire twice (presenter change)
```

## Chat

```javascript
rtc.onChatMessage   = msg => console.log(msg.origin, msg.payload);
rtc.onDirectMessage = msg => console.log('DM:', msg.origin, msg.payload);

rtc.sendChatMessage('Hello everyone');
rtc.sendChatMessage('Hello Alice', uuid);        // direct message
rtc.sendApplicationMessage({ type: 'ping' });    // arbitrary JSON
```

## Breakout rooms

```javascript
rtc.createBreakout('Room A', 0, 'transfer', [uuid1, uuid2], true, cb);
rtc.moveToBreakout(breakout_uuid);
rtc.moveParticipantsFromBreakout(fromUuid, toUuid, [participantUuid]);
rtc.closeBreakout(breakout_uuid);
rtc.setBreakoutHelp(true);                       // guest requests help
rtc.onBreakoutHelp = (breakout_uuid, setting) => {};
```

## Live captions and FECC

```javascript
rtc.showLiveCaptions(uuid);
rtc.onLiveCaptions = msg => renderCaption(msg.data, msg.is_final);

rtc.fecc_supported = true;                       // set before makeCall
rtc.sendFECC('start', 'pan', 'left', uuid, 500);
```

## Mid-call device / bandwidth changes

```javascript
rtc.video_source = newDeviceId;
rtc.renegotiate(false);     // device switch
rtc.bandwidth_in = rtc.bandwidth_out = 2048;
rtc.renegotiate(true);      // SDP renegotiation
```

## STUN / TURN

```javascript
rtc.default_stun = 'stun:stun.example.com';
rtc.turn_server  = { urls: ['turn:turn.example.com'], username: 'u', credential: 'p' };
```

## React pattern

```jsx
function PexipCall({ node, alias, displayName }) {
    const videoRef = useRef(null);
    const rtcRef   = useRef(null);
    const [pinRequired, setPinRequired] = useState(false);

    useEffect(() => {
        const rtc = new window.PexRTC();
        rtcRef.current = rtc;

        rtc.onSetup = (stream, pin_status) => {
            if (pin_status === 'required') { setPinRequired(true); return; }
            rtc.connect(null);
        };
        rtc.onConnect = stream => {
            if (videoRef.current && stream) videoRef.current.srcObject = stream;
        };
        rtc.onError      = err => console.error(err);
        rtc.onDisconnect = ()  => {};

        rtc.makeCall(node, alias, displayName, 1264, 'audiovisual');
        return () => rtc.disconnect();
    }, [node, alias, displayName]);

    const submitPin = pin => { setPinRequired(false); rtcRef.current.connect(pin); };

    return (
        <>
            <video ref={videoRef} autoPlay playsInline />
            {pinRequired && <PinModal onSubmit={submitPin} />}
        </>
    );
}
```

## Gotchas

- **`onSetup` and `onConnect` each fire more than once.** `onSetup` re-fires on wrong PIN or extension step; `onConnect` re-fires when video is ready. Guard state transitions with a flag.
- **`onConnect` stream is null for `call_type: 'none'` (roster-only).** Always null-check before assigning `srcObject`.
- **`audio_source`/`video_source` and `user_media_stream` are mutually exclusive** — pick one before `makeCall`.
- **`onRosterList` is deprecated** — use `onParticipantCreate`/`Update`/`Delete`.
- **`onPresentation(true)` can follow `onPresentation(true)`** without an intervening false — presenter changed, not a bug.
- **`transformLayout({})` resets all layout params** — pass only what you want to change.
- **`disconnect()` blocks briefly** — use `disconnectcall()` in `beforeunload` handlers instead.
- **`getMediaStatistics()` is Chrome-only.**

## Reference source

- Authoritative Pexip docs: https://docs.pexip.com/api_client/api_pexrtc.htm
- Related skills: `pexip-client-intake` (project scoping), `pexip-rest-client-api` (non-browser REST), `pexip-call-lifecycle` (@pexip/infinity npm SDK)
