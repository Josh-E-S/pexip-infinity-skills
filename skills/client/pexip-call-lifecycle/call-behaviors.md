# Non-Obvious Call Behaviors

This document captures production-tested heuristics and edge-case handling for the Pexip call lifecycle.

## 1. Sync mute state on `onConnected`, not before

The MCU (Pexip's media server) uses the mute API as the *source of truth* for the initial state. If you set `audioMuted = true` locally before `onConnected` fires, the server doesn't know. Webapp3 always calls `clientMute` and `muteVideo` immediately on `onConnected`, even if the user hasn't touched the mute button:

```ts
// From InfinityClient.service.ts
const handleOnConnected = createSignalHandler(
    infinityClientSignals.onConnected,
    async () => {
        callStage = CallStage.EventStreamConnected;
        // The MCU only knows what we tell it via this API
        await clientMute({mute: media?.audioMuted ?? true});
    },
);
```

There's a parallel handler for `onAuthenticatedWithConference` that sends `muteVideo` — needed because of MCU implementation details (see `pexip/mcu#40796` referenced in the source).

## 2. ICE restart, not rejoin, on `onPeerDisconnect`

When the peer connection dies (network blip, NAT change), don't tear down and rejoin. Use `restartCall`:

```ts
const handleOnPeerDisconnect = createSignalHandler(
    infinityClientSignals.onPeerDisconnect,
    async () => {
        callStage = CallStage.Restarting;
        await infinityClient.restartCall(callArgs);
    },
);
```

If `callStage === CallStage.Restarting` when `onCallConnected` fires again, **don't re-sync mute state** (the local UI is already authoritative) and **resume presentation** if one was active:

```ts
const handleOnCallConnected = createSignalHandler(
    infinityClientSignals.onCallConnected,
    () => {
        if (callStage !== CallStage.EventStreamConnected) {
            // ICE restart finished, NOT initial connect — skip mute sync
        } else {
            void muteVideo({muteVideo: media?.videoMuted ?? true});
        }
        if (callStage === CallStage.Restarting && presentationStream) {
            present(presentationStream);
        }
        callStage = CallStage.Connected;
    },
);
```

## 3. The browser-close handler

Hook `pagehide` and call `disconnect({reason: 'Browser closed'})`. If you skip this, the server sees the participant as still connected for ~30s while it times out, blocking room capacity.

```ts
window.addEventListener('pagehide', () => {
    void infinityClient.disconnect({reason: 'Browser closed'});
});
```

## 4. PIN/IDP/extension are all server-driven

You don't decide whether to show a PIN screen — `onPinRequired`, `onIdp`, and `onExtension` tell you. The server may also re-prompt mid-flow if the user types a wrong PIN (`onError` with `'Invalid PIN'`):

```ts
const handleOnError = createSignalHandler(
    infinityClientSignals.onError,
    ({error, errorCode}) => {
        if (error === 'Invalid PIN') {
            invalidPinSignal.emit();
            updateStep(joinAsHost ? MeetingFlow.EnterHostPin : MeetingFlow.EnterPin);
        } else {
            updateInfinityError(error, errorCode);
        }
    },
);
```

## 5. Splash screens during direct-media transitions

Pexip can transition a call from "transcoded" (server in the middle) to "direct" (peer-to-peer) at runtime. The server sends `onSplashScreen` events with keys like `direct_media_escalate` and `direct_media_deescalate`. These are *not* errors — they're informational. Webapp3 surfaces them as toasts, not splash screens, because they're transient:

```ts
const handleOnSplashScreen = createSignalHandler(
    infinityClientSignals.onSplashScreen,
    splashScreen => {
        if (
            splashScreen?.text &&
            ['direct_media_escalate', 'direct_media_deescalate'].includes(
                splashScreen?.screenKey
            )
        ) {
            return; // Show as toast elsewhere, not as splash
        }
        updateSplashScreen(splashScreen);
    },
);
```
