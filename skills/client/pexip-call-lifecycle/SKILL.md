---
name: pexip-call-lifecycle
description: Use when setting up `@pexip/infinity`, calling `createInfinityClient`, joining or leaving a Pexip meeting, building the join flow (PIN/IDP/extension/host-vs-guest), handling `onPeerDisconnect` ICE restart, wiring `onTransfer` for breakouts/direct-media, or implementing meeting splash screens. Also use when building the `MeetingFlow` state machine (Loading → Idp → EnterPin → AreYouHost → ReadyToJoin → InMeeting). Triggers on `InfinityClient`, `infinityClientSignals`, `onPinRequired`, `onTransfer`, `onPeerDisconnect`, `MeetingFlow`, `CallStage`, ICE restart, conference alias, presentation in mix.
license: MIT
---

# Pexip call lifecycle

Joining a Pexip meeting is **not** "call this function and you're in." There are 6 call stages, ~30 event handlers, a join-flow state machine with 7+ steps, and several invariants that webapp3 has fought through in production. This skill captures the shape that actually works.

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

callSignals.onRemoteStream.add(stream => {
    // Wire to <video srcObject={stream} />
    setRemoteStream(stream);
    setMeetingStep(MeetingFlow.InMeeting);
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
    callType: 'AudioSendRecvVideoSendRecvPresentationSendRecv',
    bandwidth: 1264,
    clientId: 'my-client-id',
    displayName: 'Alice',
    node: 'pexip.example.com',
    mediaStream: media.stream,
});
```

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

## Gotchas

- **Don't `await` inside `infinityClientSignals.onMessage.add` for chat.** Server may fire the same message twice during reconnect. Use `id` for dedup.
- **`callType` strings matter.** Use the v39+ format: `AudioSendRecvVideoSendRecvPresentationSendRecv`. Don't pass legacy numeric IDs.
- **`directMedia: true`** disables `presInMix` — skip the call if so (the SDK throws otherwise).
- **`infinityClient.call()` is async, but doesn't resolve when the call connects.** It resolves when the SDK has accepted the request. Use `callSignals.onCallConnected` for "actually connected".
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
