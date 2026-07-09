---
name: pexip-call-lifecycle
description: Use when setting up `@pexip/infinity`, calling `createInfinityClient`, joining or leaving a Pexip meeting, building the join flow (PIN/IDP/extension/host-vs-guest), handling `onPeerDisconnect` ICE restart, wiring `onTransfer` for breakouts/direct-media, or implementing meeting splash screens. Also use when building the `MeetingFlow` state machine (Loading → Idp → EnterPin → AreYouHost → ReadyToJoin → InMeeting). Triggers on `InfinityClient`, `infinityClientSignals`, `onPinRequired`, `onTransfer`, `onPeerDisconnect`, `MeetingFlow`, `CallStage`, ICE restart, conference alias, presentation in mix.
license: MIT
---

# Pexip call lifecycle

Joining a Pexip meeting is **not** "call this function and you're in." There are 6 call stages, ~30 event handlers, a join-flow state machine with 7+ steps, and several invariants that webapp3 has fought through in production. This skill captures the shape that actually works.

## Barebones working app

Complete minimal scaffold using `@pexip/infinity`. Fill in `NODE`, `ALIAS`, `DISPLAY_NAME` and it works. Expand per-feature using the sections below and sibling skills.

```tsx
// signals.ts — create once, import everywhere
import { createSignal } from '@pexip/signal';

export const remoteStreamSignal = createSignal<MediaStream | undefined>({ name: 'call:remoteStream', variant: 'behavior' });
export const stepSignal         = createSignal<string>({ name: 'call:step', variant: 'behavior' });
export const pinRequiredSignal  = createSignal<boolean>({ name: 'call:pinRequired' });
```

```tsx
// PexipCall.tsx
import { useEffect, useRef, useState } from 'react';
import {
    createInfinityClient,
    createInfinityClientSignals,
    createCallSignals,
    ClientCallType,
} from '@pexip/infinity';
import { remoteStreamSignal, stepSignal, pinRequiredSignal } from './signals';

const infinityClientSignals = createInfinityClientSignals([]);
const callSignals           = createCallSignals([]);

export function PexipCall({ node, alias, displayName }: { node: string; alias: string; displayName: string }) {
    const videoRef    = useRef<HTMLVideoElement>(null);
    const clientRef   = useRef<ReturnType<typeof createInfinityClient> | null>(null);
    const callArgsRef = useRef<object>({});
    const [pin, setPin]               = useState('');
    const [pinVisible, setPinVisible] = useState(false);

    useEffect(() => {
        const client = createInfinityClient({ infinityClientSignals, callSignals });
        clientRef.current = client;

        infinityClientSignals.onPinRequired.add(() => setPinVisible(true));

        infinityClientSignals.onCallConnected.add(() => {
            stepSignal.emit('InMeeting');
            setPinVisible(false);
        });

        infinityClientSignals.onPeerDisconnect.add(async () => {
            await client.call(callArgsRef.current as any); // ICE restart
        });

        infinityClientSignals.onDisconnected.add(() => {
            stepSignal.emit('Idle');
            if (videoRef.current) videoRef.current.srcObject = null;
        });

        callSignals.onRemoteStream.add(stream => {
            remoteStreamSignal.emit(stream);
            if (videoRef.current) videoRef.current.srcObject = stream ?? null;
        });

        const args = {
            conferenceAlias: alias,
            callType: ClientCallType.AudioSendRecvVideoSendRecvPresentationSendRecv,
            bandwidth: 1264,
            displayName,
            node,
            host: `https://${node}`,
        };
        callArgsRef.current = args;
        stepSignal.emit('Loading');
        void client.call(args);

        return () => { void client.disconnect(); };
    }, [node, alias, displayName]);

    const submitPin = () => {
        setPinVisible(false);
        void clientRef.current?.call({ ...callArgsRef.current as any, pin });
    };

    return (
        <div>
            <video ref={videoRef} autoPlay playsInline style={{ width: '100%', background: '#000' }} />
            {pinVisible && (
                <div>
                    <input type="password" value={pin} onChange={e => setPin(e.target.value)} placeholder="Enter PIN" />
                    <button onClick={submitPin}>Join</button>
                </div>
            )}
        </div>
    );
}
```

## Which SDK is this?

These skills cover **`@pexip/infinity`** — the modular TypeScript SDK that Pexip's own webapp3 is built on. It uses typed signals, `createInfinityClient`, and `infinityClientSignals`.

Pexip also publishes **PexRTC** — an older, simpler SDK with a callback-based API (`makeCall` + `connect(pin)` pattern). PexRTC is loaded from the Conferencing Node at `/static/webrtc/js/pexrtc.js` and is what Pexip's official developer documentation primarily covers.

**The two SDKs are not interchangeable.** If you find examples using `pexRTC.makeCall()`, `onSetup`, or `connect(pin)`, those are PexRTC — not the API documented here.

| | PexRTC | `@pexip/infinity` |
|---|---|---|
| Load method | `<script>` tag from node | `npm install @pexip/infinity` |
| API style | Callbacks (`onSetup`, `onConnect`) | Typed signals (`createSignal`) |
| Join flow | `makeCall()` → `onSetup` → `connect(pin)` | `infinityClient.call({pin})` → `onPinRequired` |
| Docs | docs.pexip.com/api_client/api_pexrtc.htm | These skills + webapp3 source |

For PexRTC patterns and examples, see the `pexip-pexrtc` skill. For the raw REST API, see `pexip-rest-client-api`.

## The two state machines

Every Pexip call has **two state machines that run in parallel**:

```
CallStage              MeetingFlow (UI step)
─────────              ────────────────────
New                    Loading
  ↓                      ↓
EventStreamConnected   Idp / EnterPin / AreYouHost / EnterExtension
  ↓                      ↓
Connected              ReadyToJoin
  ↓                      ↓
Restarting (on ICE)    InMeeting
  ↓                      ↓
Ending                 PostMeeting
  ↓
Ended
```

`CallStage` is internal — driven by SDK events. `MeetingFlow` is what the user sees. They're decoupled: `Loading` may persist across `New → EventStreamConnected` while the server decides whether to ask for a PIN.

```ts
export enum CallStage {
    New = 0,
    EventStreamConnected = 1,
    Connected = 2,
    Restarting = 3,
    Ending = 4,
    Ended = 5,
}

export enum MeetingFlow {
    Loading,
    Idp,
    EnterPin,
    EnterHostPin,
    AreYouHost,
    EnterExtension,
    ReadyToJoin,
    InMeeting,
    Ended,
}
```

## Quick start: minimal call setup

```ts
import {
    createInfinityClient,
    createInfinityClientSignals,
    createCallSignals,
    ClientCallType,
} from '@pexip/infinity';

// 1. Create the signal hubs (see signals-pattern skill)
const infinityClientSignals = createInfinityClientSignals([], {
    batchScheduleTimeoutMS: 100,
    batchBufferSize: 50,
});
const callSignals = createCallSignals([]);

// 2. Create the client
const infinityClient = createInfinityClient(
    infinityClientSignals,
    callSignals,
);

// 3. Wire the events you care about (BEFORE calling .call())
infinityClientSignals.onPinRequired.add(({hasHostPin, hasGuestPin}) => {
    // Server demands a PIN — show the appropriate UI step
    setMeetingStep(
        hasHostPin && hasGuestPin ? MeetingFlow.EnterPin : MeetingFlow.AreYouHost
    );
});

infinityClientSignals.onConnected.add(() => {
    // Event stream is up. Sync initial mute state to the server NOW.
    void infinityClient.clientMute({mute: media.audioMuted ?? true});
    void infinityClient.muteVideo({muteVideo: media.videoMuted ?? true});
});

infinityClientSignals.onCallConnected.add(() => {
    setMeetingStep(MeetingFlow.InMeeting);
});

callSignals.onRemoteStream.add(stream => {
    // Wire to <video srcObject={stream} />
    setRemoteStream(stream);
});

infinityClientSignals.onPeerDisconnect.add(async () => {
    // ICE failed — call restartCall to recover without rejoining
    await infinityClient.restartCall({
        ...callConfigs,
        conferenceAlias,
        mediaStream: media.stream,
    });
});

// 4. Make the call
await infinityClient.call({
    conferenceAlias: 'meet.alice',
    callType: ClientCallType.AudioSendRecvVideoSendRecvPresentationSendRecv,
    bandwidth: 1264,
    clientId: 'my-client-id',
    displayName: 'Alice',
    node: 'pexip.example.com',
    host: 'https://pexip.example.com',
    mediaStream: media.stream,
});
```

### Submitting the PIN

After the user enters their PIN, call `infinityClient.call()` again with the `pin` parameter:

```ts
await infinityClient.call({
    ...originalCallArgs,
    pin: userEnteredPin,
});
```

You can also pass `pin` on the initial `.call()` if the user already knows it (e.g., from a join form). If the PIN is correct, the server skips `onPinRequired`. If wrong, `onError` fires with `'Invalid PIN'`.

## Non-obvious behaviors and edge cases

Webapp3 implements several production-hardened heuristics, such as syncing mute state on event stream connection, recovery via ICE restart on peer disconnect, browser-close session cleanup, server-driven authentication prompts, and direct-media transition handling. For details, see [Non-Obvious Call Behaviors](call-behaviors.md).

## Disconnect & post-meeting routing

```ts
const handleOnDisconnect = createSignalHandler(
    infinityClientSignals.onDisconnected,
    ({error, errorCode}) => {
        if (applicationConfig.disconnectDestination) {
            // manifest.json said "send users to this URL after the call"
            return navigateToPostMeeting(conferenceAlias, applicationConfig.disconnectDestination);
        }
        if (error) {
            updateInfinityError(error, errorCode);
        } else {
            navigateToPostMeeting(conferenceAlias);
        }
    },
);
```

Honor the `disconnectDestination` from your branding manifest — it's how organizations redirect users to a custom landing page after meetings.

## Deeper references

- `reference.md` — full catalog of all 30+ event handlers, with what each does and why
- `transfer-flow.md` — the direct-media/breakout transfer flow (preserves chat + participants)

## See also

- `pexip-signals-pattern` — the pub/sub spine; read this first if it's your first Pexip app
- `pexip-media-pipeline` — `mediaStream` you pass to `.call()` comes from `@pexip/media`'s `mediaService`
- `pexip-reconnect` — how `useOnFailedInfinityRequest` and `NetworkState` cooperate with this flow
- `pexip-preflight` — what runs before this skill kicks in
- `pexip-browser-close-confirmation` — the `beforeunload` companion to the `pagehide` handler
- `pexip-stats-monitoring` — the `onRtcStats` handler shape used in this skill is documented in detail there
- `pexip-live-captions` — `onLiveCaptions` events flow through this skill's event handlers
- `pexip-pexrtc` — the PexRTC JavaScript client API (callback-based, loaded from node)
- `pexip-rest-client-api` — raw HTTP + SSE client API (non-browser clients)

## Gotchas

- **Don't `await` inside `infinityClientSignals.onMessage.add` for chat.** Server may fire the same message twice during reconnect. Use `id` for dedup.
- **`callType` must be the `ClientCallType` enum, not a string.** Import `ClientCallType` from `@pexip/infinity` and pass the enum value (e.g., `ClientCallType.AudioSendRecvVideoSendRecvPresentationSendRecv` = `126`). Passing the string name silently produces `callType: None` (signaling-only, no media) because the SDK uses bitwise AND internally.
- **`directMedia: true`** disables `presInMix` — skip the call if so (the SDK throws otherwise).
- **`infinityClient.call()` is async, but doesn't resolve when the call connects.** It resolves when the SDK has accepted the request. Use `callSignals.onCallConnected` for "actually connected".
- **Don't gate the `InMeeting` transition on `onRemoteStream`.** It won't fire if you're the only participant in the VMR. Use `onCallConnected` (which fires when the WebRTC call is established, regardless of other participants) for the UI state transition. Use `onRemoteStream` only for wiring the video element.
- **Always pass `host` explicitly when developing on `http://localhost`.** The SDK builds API URLs as `${window.location.protocol}//${node}`. On localhost, this produces `http://your-pexip-node.com/...` which gets CORS-blocked when the node redirects to HTTPS. Pass `host: 'https://your-node.com'` to override.
- **Don't unsubscribe `onTransfer` until the transfer completes.** If you tear down on `onDisconnected`, you'll miss the redirect details.

## Reference source

- **Authoritative Pexip docs:**
  - Pexip client SDK overview: https://docs.pexip.com/developer/clientapi.htm
  - `@pexip/infinity` JS client API reference: https://docs.pexip.com/api_client/api_pexrtc.htm
- **Reference implementation (webapp3):**

- `src/services/InfinityClient.service.ts` — full implementation (1759 LOC)
- `src/signals/InfinityClient.signals.ts`, `Call.signals.ts`, `Meeting.signals.ts`
- `src/types.ts` — `MeetingFlow` enum
- `pexip-sdks/infinity/src/infinityClient.ts` — SDK source
