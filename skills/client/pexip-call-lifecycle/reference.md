# Call lifecycle: full event handler reference

This reference catalogs every signal handler webapp3 wires up during a call. Each entry: what fires it, what to do, why webapp3 does it that way.

Read `SKILL.md` first for the overview. Use this when you need the exact behavior for a specific event.

## Setup invariants

Before reading the handlers, these things are always true in webapp3:

1. The `InfinityClient` is created **once** at app startup, not per-call.
2. The `Meeting` object (state container) is recreated for each `.call()`.
3. All event subscriptions are stored in `props.detachSignals[]` and torn down in `release()`.
4. Every handler is wrapped in `createSignalHandler` (try/catch + logger).

## Event-stream lifecycle

### `infinityClientSignals.onConnected`
Fired when the server-sent-events stream is established. **Not** when media is flowing.

```ts
const handleOnConnected = createSignalHandler(
    infinityClientSignals.onConnected,
    async () => {
        callStage = CallStage.EventStreamConnected;
        if (isControlOnly(config.get('callType'))) {
            showMeetingWithControlInfo(); // No media → show meeting controls splash
        } else {
            await presInMix({state: config.get('preferPresInMix')});
        }
        // The MCU treats this API call as the source of truth for initial mute
        await clientMute({mute: media?.audioMuted ?? true});
    },
);
```

**Don't skip the `clientMute` call** — without it, the server assumes unmuted regardless of local state.

### `infinityClientSignals.onAuthenticatedWithConference`
Fired only on **fresh** connect (not on ICE restart). Webapp3 uses this to push initial `muteVideo` state.

```ts
const handleOnAuthenticatedWithConference = createSignalHandler(
    infinityClientSignals.onAuthenticatedWithConference,
    async () => {
        await muteVideo({muteVideo: media?.videoMuted ?? true});
    },
);
```

The comment in webapp3 references `pexip/mcu#40796` — there's a server-side reason this needs to be a separate API call from `clientMute`. Don't try to combine them.

### `callSignals.onCallConnected`
Fired when media starts flowing (after SDP exchange). This is the "you are now in the call" event.

```ts
const handleOnCallConnected = createSignalHandler(
    infinityClientSignals.onCallConnected,
    () => {
        // Initial sync — but only if NOT recovering from ICE restart
        if (callStage !== CallStage.EventStreamConnected) {
            void muteVideo({muteVideo: media?.videoMuted ?? true});
        }
        // Resume presentation if we were presenting before the restart
        if (callStage === CallStage.Restarting && presentationStream) {
            present(presentationStream);
        }
        callStage = CallStage.Connected;
        if (!isReceivingAnyMedia(config.get('callType'))) {
            showMeetingWithControlInfo();
        }
    },
);
```

### `callSignals.onRemoteStream`
The remote media stream is ready. Wire to your video element.

```ts
const handleOnRemoteStream = createSignalHandler(
    callSignals.onRemoteStream,
    stream => {
        updateStep(MeetingFlow.InMeeting);
        setRemoteStream(stream);
    },
);
```

## Join-flow gates (server demands user input)

### `infinityClientSignals.onPinRequired`
Server requires a PIN. Decide between "are you a host?" prompt and direct PIN entry based on which PINs exist:

```ts
const handleOnPinRequired = createSignalHandler(
    infinityClientSignals.onPinRequired,
    ({hasHostPin, hasGuestPin}) => {
        if (hasHostPin && hasGuestPin) {
            updateStep(MeetingFlow.EnterPin);
        } else {
            updateStep(MeetingFlow.AreYouHost);
        }
        setPinRequired(hasHostPin && hasGuestPin);
    },
);
```

### `infinityClientSignals.onIdp`
Single sign-on identity providers configured. Show provider chooser:

```ts
infinityClientSignals.onIdp.add(idps => {
    setIdps(idps);
    updateStep(MeetingFlow.Idp);
});
```

### `infinityClientSignals.onExtension`
Conference is a gateway requiring an extension number:

```ts
infinityClientSignals.onExtension.add(() => {
    updateStep(MeetingFlow.EnterExtension);
});
```

### `infinityClientSignals.onError` with `'Invalid PIN'`
User entered the wrong PIN. Re-show the PIN entry step:

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

## Resilience

### `infinityClientSignals.onPeerDisconnect`
ICE failure or peer connection died. Recover via `restartCall` — don't rejoin.

```ts
const handleOnPeerDisconnect = createSignalHandler(
    infinityClientSignals.onPeerDisconnect,
    async () => {
        callStage = CallStage.Restarting;
        await infinityClient.restartCall(callArgs);
    },
);
```

The recovery path: `onPeerDisconnect → restartCall → onCallConnected (with callStage===Restarting)`.

### `infinityClientSignals.onDisconnected`
Server-side disconnect (host kicked, conference ended, error). Honor `disconnectDestination` if branded:

```ts
const handleOnDisconnect = createSignalHandler(
    infinityClientSignals.onDisconnected,
    ({error, errorCode}) => {
        if (applicationConfig.disconnectDestination) {
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

### `pagehide` (DOM event, not a signal)
User closed the tab. Tell the server explicitly so the participant slot frees immediately.

```ts
window.addEventListener('pagehide', () => {
    void infinityClient.disconnect({reason: 'Browser closed'});
});
```

## Splash screens

### `infinityClientSignals.onSplashScreen`
Server-rendered messages ("Waiting for host", "Meeting will start soon", direct-media transition notices). Filter direct-media keys — those are toasts, not splashes:

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
            return;
        }
        if (
            isReceivingAnyMedia(config.get('callType')) ||
            ['direct_media_welcome', 'direct_media_waiting_for_host'].includes(
                splashScreen?.screenKey
            )
        ) {
            updateSplashScreen(splashScreen);
        }
        updateStep(MeetingFlow.InMeeting);
    },
);
```

## Layout

### `infinityClientSignals.onLayoutOverlayTextEnabled`
Whether participant name overlays are on. Just sync the flag:

```ts
infinityClientSignals.onLayoutOverlayTextEnabled.add(setLayoutOverlayTextEnabled);
```

### `infinityClientSignals.onRequestedLayout` and `onLayoutUpdate`
Track current layout and whether presentation is in mix:

```ts
infinityClientSignals.onRequestedLayout.add(layout => {
    currentHostLayout = layout.primaryScreen.hostLayout;
});

infinityClientSignals.onLayoutUpdate.add(layout => {
    isPresentationInMixActive = !!layout.pres_slot_coords;
});
```

## Chat

### `infinityClientSignals.onMessage`
Incoming chat (group or direct). Filter overly long messages, dedup by id, dispatch to direct vs group buckets:

```ts
const CHARACTER_LIMIT = 5000; // webapp3's value

const handleOnChatMessage = createSignalHandler(
    infinityClientSignals.onMessage,
    message => {
        if (message.message.length > CHARACTER_LIMIT) {
            logger.warn(`Message too big. Length: ${message.message.length}`);
            return;
        }
        const chatMessage = {
            ...message,
            displayName: message.displayName || 'User',
            timestamp: toTime(message.at),
            type: 'user-message' as const,
        };
        if (message.direct) {
            addDirectChatMessage(message.userId, chatMessage);
            addUnreadDirectChatMessage(message.userId, chatMessage);
        } else {
            updateChatMessages([...chatMessages, chatMessage]);
            updateUnreadChatMessages([...unreadChatMessages, chatMessage]);
        }
    },
);
```

### Sending chat with optimistic UI + retry-queue reconciliation

Webapp3's `sendMessage` adds the message as `pending: true` immediately, then waits for confirmation. If the SDK queues it (returns falsy), it subscribes once to `onRetryQueueFlushed` to mark it sent later:

```ts
const sendMessage = async (message: string, toParticipantUuid?: ParticipantID) => {
    const me = infinity.getMe();
    if (!me) return;

    const chatMessage = {
        displayName: me.displayName || 'User',
        id: uuid(),
        message,
        timestamp: toTime(new Date()),
        type: 'user-message',
        userId: me.uuid,
    } as const;

    // Optimistic add
    if (toParticipantUuid) {
        addDirectChatMessage(toParticipantUuid, {...chatMessage, pending: true});
    } else {
        updateChatMessages([...chatMessages, {...chatMessage, pending: true}]);
    }

    const result = await infinity.sendMessage({
        payload: message,
        participantUuid: toParticipantUuid,
    });

    const setMsgSuccess = () => {
        // Replace pending with confirmed
        if (toParticipantUuid) {
            deleteDirectChatMessage(toParticipantUuid, chatMessage.id);
            addDirectChatMessage(toParticipantUuid, chatMessage);
        } else {
            const filtered = chatMessages.filter(({id}) => id !== chatMessage.id);
            updateChatMessages([...filtered, chatMessage]);
        }
    };

    if (result) {
        setMsgSuccess();
    } else {
        // Queued — wait for the SDK to flush
        infinityClientSignals.onRetryQueueFlushed.addOnce(() => setMsgSuccess());
    }
};
```

## Hands & captions

### `infinityClientSignals.onRaiseHand`
Replace displayName with overlayText if set (server can override the display name during raise-hand):

```ts
infinityClientSignals.onRaiseHand.add(({participant}) => {
    participant.displayName = participant.overlayText || participant.displayName;
});
```

### `infinityClientSignals.onLiveCaptions`
Streaming captions. The pattern: replace the last transcript if non-final, append if final:

```ts
const handleOnLiveCaptions = createSignalHandler(
    infinityClientSignals.onLiveCaptions,
    ({data: text, isFinal, speakers}) => {
        const transcript = {text, isFinal, timestamp: Date.now(), speakers};
        const last = transcripts[transcripts.length - 1];
        if (last && !last.isFinal) {
            // Replace the in-progress transcript
            if (transcript.isFinal || transcript.text.length >= last.text.length) {
                transcripts[transcripts.length - 1] = transcript;
                transcripts = [...transcripts];
            }
        } else {
            transcripts = [...transcripts, transcript];
        }
        transcriptsSignal.emit();
    },
);
```

## Stats & quality

### `callSignals.onRtcStats`
Fired periodically with WebRTC stats. **Don't log every tick** — only when quality actually changes:

```ts
const hasQualityStatsChanged = (last: Stats | undefined, current: Stats) => {
    if (!last) return true;
    if (last?.outbound?.video?.qualityLimitationReason !==
        current?.outbound?.video?.qualityLimitationReason) {
        return true;
    }
    const lastHighFpsVolatility = Number(last?.outbound?.video?.fpsVolatility) > 10;
    const highFpsVolatility = Number(current?.outbound?.video?.fpsVolatility) > 10;
    return lastHighFpsVolatility !== highFpsVolatility;
};

const handleRtcStats = (stats: Stats) => {
    const lastStats = window.pexDebug?.stats as Stats;
    if (hasQualityStatsChanged(lastStats, stats)) {
        logger.info({stats}, 'Quality stats changed');
    }
    window.pexDebug = {...window.pexDebug, stats};
};
```

## Breakouts

### `infinityClientSignals.onBreakoutRefer`
You're being moved to a breakout. Clear the chat (breakouts have their own chat scope):

```ts
infinityClientSignals.onBreakoutRefer.add(_roomUuid => {
    updateChatMessages([]);
});
```

### `infinityClientSignals.onTransfer`
See `transfer-flow.md` — this is the most complex handler.

## Track muted (mediaSignals, not infinity signals)

When the local track changes mute state, sync to the server with debouncing to avoid mute-flap:

```ts
const handleAudioMute = createDebounceMute(
    {timerId: 0, muted: undefined},
    muted => {
        void clientMute({mute: muted});
        const me = infinity.getMe();
        // If host or guests-can-unmute, also unmute server-side
        if (!muted && me?.isMuted &&
            (me?.isHost || infinity.conferenceStatus.get(infinity.roomId)?.guestsCanUnmute)) {
            void mute({mute: false});
        }
    },
);

const handleTrackMuted = createSignalHandler(
    mediaSignals.onMediaTrackMuted,
    track => {
        if (!media?.isCurrentTrack(track)) return;
        switch (track.kind) {
            case 'audioinput': handleAudioMute(track); break;
            case 'videoinput': handleVideoMute(track); break;
        }
    },
);
```

The `createDebounceMute` factory (default 800ms) collapses rapid mute/unmute toggles during track changes:

```ts
const createDebounceMute =
    (stack: MuteStack, handle: (muted: boolean) => void, throttleMS = 800) =>
    (track: MediaTrack) => {
        if (stack.timerId) {
            window.clearTimeout(stack.timerId);
            stack.timerId = 0;
        }
        if (stack.muted === undefined) {
            stack.muted = track.muted ?? true;
        } else if (stack.muted !== (track.muted ?? true)) {
            // Toggled within the throttle window — net-zero, cancel the emit
            stack.muted = undefined;
        }
        stack.timerId = window.setTimeout(() => {
            if (stack.muted === undefined) return;
            handle(stack.muted);
            stack.muted = undefined;
        }, throttleMS);
    };
```

## Subscription teardown

Webapp3 collects every subscription's detach function in a single array, then iterates on `release()`:

```ts
const detachSignals: Detach[] = [
    infinityClientSignals.onConnected.add(handleOnConnected),
    infinityClientSignals.onPinRequired.add(handleOnPinRequired),
    infinityClientSignals.onPeerDisconnect.add(handleOnPeerDisconnect),
    infinityClientSignals.onDisconnected.add(handleOnDisconnect),
    // ... ~25 more
];

const release = () => {
    for (const d of detachSignals) d();
    detachSignals.length = 0;
};
```

This is the right shape — call `release()` before recreating the meeting on transfer.

## Source

`src/services/InfinityClient.service.ts` (lines 947–1357 contain the full `subscribeEvents` block).
