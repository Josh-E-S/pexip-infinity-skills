---
name: pexip-presentation
description: Use when implementing screen sharing in a Pexip app — wiring `getDisplayMedia`, `usePresentation` hook, content hints (motion vs detail), presentation audio mixing, ICE-restart preservation, monitor/window/tab restrictions, cursor capture. Triggers on `getDisplayMedia`, `displaySurface`, `present`, `endPresent`, `presentationStreamSignal`, `usePresentation`, `presoContentHint`, `MonitorSharingNotAllowed`, screen share, screencast.
license: MIT
---

# Pexip presentation (screen sharing)

Pexip's presentation flow is *two* media tracks (your camera + your screen) negotiated through the same peer connection, with separate content hints, separate quality settings, and a separate audio mix. It also has to survive ICE restart so a network blip doesn't terminate your screenshare.

This skill captures the working setup. Most of the heavy lifting is in `@pexip/media-components`'s `usePresentation` hook — webapp3 wraps it with the few app-specific pieces.

## The pieces

| Piece | What it does |
|---|---|
| `getDisplayMedia` (webapp3 wrapper) | Calls browser's `navigator.mediaDevices.getDisplayMedia()` with config-driven constraints |
| `setCurrentDisplayMedia(stream)` | Stores the active screen stream globally + emits signals + applies audio content hint |
| `usePresentation(...)` from `@pexip/media-components` | The state machine: start/stop, remote stream, capability checks, restart-aware |
| `meeting.present(stream)` / `meeting.endPresent()` | The actual SDK calls — wired internally by `usePresentation` |
| `presentationStreamSignal` / `endPresentationSignal` | Pub/sub for "presentation started" / "presentation ended" |

## Quick start: the full setup

```ts
import {usePresentation} from '@pexip/media-components';
import {stopMediaStream} from '@pexip/media-control';

import {callSignals} from '../signals/Call.signals';
import {
    startPresentationSignal,
    endPresentationSignal,
} from '../signals/Meeting.signals';
import {
    getDisplayMedia,
    setCurrentDisplayMedia,
} from '../services/Media.service';
import {CallStage} from '../services/InfinityClient.service';
import {useMeetingContext} from './meeting';

export const usePresentationSetup = () => {
    const meeting = useMeetingContext();

    // ICE restart awareness: the hook needs to know if a restart is in progress
    // so it can keep the local stream alive across the gap
    const isCallRestarting = useCallback(
        () => meeting.getCallStage() === CallStage.Restarting,
        [meeting],
    );

    const presentation = usePresentation({
        presentationReceiveStreamSignal: callSignals.onRemotePresentationStream,
        presentationConnectionStateChangeSignal: callSignals.onPresentationConnectionChange,
        present: meeting.present,
        getPresentationCapability: () => ({
            send: meeting.ableToPresent(),
            recv: meeting.ableToReceivePresentation(),
        }),
        stopPresentation: meeting.endPresent,
        handleGetDisplayMedia: getDisplayMedia,
        handlaGetDisplayMediaError: error => {
            // see error mapping below
        },
        isCallRestarting,
    });

    // External "start presentation" trigger (e.g. from a CallStage.Restarting recovery)
    useEffect(
        () => startPresentationSignal.add(({stream}) =>
            presentation.startPresentation(stream)),
        [presentation],
    );

    // Wire the local stream lifecycle to the audio mixer + cleanup
    useEffect(() => {
        if (meeting.getEndedReason() === 'DirectMediaTransfer') return;
        setCurrentDisplayMedia(presentation.localMediaStream);

        return () => {
            if (meeting.getEndedReason() === 'DirectMediaTransfer') return;
            endPresentationSignal.emit?.();
            stopMediaStream(presentation.localMediaStream);
        };
    }, [meeting, presentation.localMediaStream]);

    return presentation;
};
```

The `presentation` object the hook returns has:
- `localMediaStream` — your screen capture
- `remotePresentationStream` — what *another* participant is presenting
- `startPresentation(stream)`, `stopPresentation()` — manual triggers
- `presentationCapability` — derived from your callType

## `getDisplayMedia` — the constraints

Webapp3's wrapper feeds the browser API with user-config:

```ts
import {createGetDisplayMedia} from '@pexip/media';

export const getDisplayMedia = createGetDisplayMedia(() => ({
    video: {
        displaySurface: config.get('displaySurface'),  // 'monitor' | 'window' | 'browser'
        cursor: config.get('cursorCapture'),           // 'never' | 'always' | 'motion'
        // Cap at screen resolution — higher values force resampling and waste CPU
        width: {max: window.screen.width},
        height: {max: window.screen.height},
    },
    audio: config.get('captureAudio'),
    surfaceSwitching: config.get('surfaceSwitching'),  // 'include' | 'exclude'
    monitorTypeSurfaces: applicationConfig.monitorTypeSurfaces, // 'exclude' to block whole-screen
    selfBrowserSurface: applicationConfig.selfBrowserSurface,
    systemAudio: applicationConfig.systemAudio,
}));
```

The `monitorTypeSurfaces: 'exclude'` is the manifest.json setting that prevents users from sharing their entire screen — only windows/tabs allowed. Useful for compliance use cases.

## Error handling — translating the browser zoo

`getDisplayMedia` throws different error types/names depending on browser, user action, and policy. Webapp3's mapping:

```ts
handlaGetDisplayMediaError: error => {
    let message = t('media.presentation.error', 'Unable to share screen.');

    if (error instanceof TypeError) {
        if (error.message === 'MonitorSharingNotAllowed') {
            // Pexip-specific: user picked monitor when monitorTypeSurfaces:'exclude'
            message = t('media.presentation.no-sharing-monitor', 'Sharing the entire screen is not allowed!');
        } else {
            message = t('media.presentation.not-fulfilled', 'Sharing screen is not allowed!');
        }
    } else {
        const errorName = error.name === 'Error' ? error.message : error.name;
        switch (errorName) {
            case 'NotAllowedError':
                // User clicked "Cancel" in the picker
                message = t('media.presentation.not-allowed', 'Screen sharing was cancelled');
                break;
            case 'NotFoundError':
                // No capturable surfaces (rare — e.g. a totally empty browser)
                message = t('media.presentation.not-found', 'No sources of screen are available for capture!');
                break;
            case 'NotReadableError':
                // OS-level capture failed (e.g. macOS screen recording permission)
                message = t('media.presentation.not-readable', 'The source of sharing is not available!');
                break;
        }
    }

    notificationToastSignal.emit([{message}]);
}
```

The `error.name === 'Error' ? error.message : error.name` dance handles a Pexip-internal throw style: `new Error('MonitorSharingNotAllowed')` instead of a custom error class.

**Don't write this from scratch.** Copy the above. The error names are non-obvious and browser-version-dependent.

## Content hints — motion vs detail

Two user-tunable hints affect both the video encoder *and* the audio mix:

```ts
config.subscribe('presoContentHint', hint => {
    // Apply to video tracks immediately
    currentDisplayMedia?.getVideoTracks().forEach(applyContentHint(hint));

    // Re-derive audio settings (motion + audio = music; detail = speech)
    const audioContentHint = deriveAudioContentHintFromPreso(currentDisplayMedia);
    void mediaService.media?.applyConstraints({
        audio: {
            ...deriveAudioFeaturesFromAudioContentHint(audioContentHint),
            contentHint: audioContentHint,
        },
    });
});
```

Webapp3 also feeds the hint into the RTC degradation preference:

```ts
const deriveDegradationPreference = (): RTCDegradationPreference => {
    const hint = config.get('presoContentHint');
    switch (hint) {
        case 'motion':
            return 'maintain-framerate';   // smooth video, drop resolution
        case 'detail':
        case 'text':
            return 'maintain-resolution';  // sharp text, drop framerate
        default:
            return 'balanced';
    }
};

// Pushed to the SDK on hint change:
config.subscribe('presoContentHint', () => {
    infinity.setDegradationPreference({
        presentation: deriveDegradationPreference(),
    });
});
```

This is how a "Prioritize sharing motion" toggle in the settings actually changes encoding behavior.

## Audio mixing during presentation

If the user shares a tab/window with audio, that audio gets mixed into the outgoing stream. See `media-pipeline/audio-processing.md` for the mixer setup. When `setCurrentDisplayMedia(stream)` runs, it also flips the audio constraints:

```ts
export const setCurrentDisplayMedia = (newDisplayMedia?: MediaStream) => {
    currentDisplayMedia = newDisplayMedia;
    const [audioTrack] = newDisplayMedia?.getAudioTracks() ?? [];
    presentationStreamSignal.emit(newDisplayMedia);

    if (audioTrack) {
        // Apply video content hint to video tracks
        newDisplayMedia?.getVideoTracks().forEach(applyContentHint(config.get('presoContentHint')));

        // Switch audio processor to "music" mode if appropriate
        const contentHint = deriveAudioContentHintFromPreso(newDisplayMedia);
        void mediaService.media?.applyConstraints({
            audio: {
                mixWithAdditionalMedia: true,
                ...deriveAudioFeaturesFromAudioContentHint(contentHint),
                contentHint,
            },
        });
    }
};
```

When presentation ends, the cleanup signal flips it back:

```ts
endPresentationSignal.add(async () => {
    const contentHint = deriveAudioContentHintFromPreso(undefined);
    await mediaService.media?.applyConstraints({
        audio: {
            mixWithAdditionalMedia: false,
            contentHint,
            ...deriveAudioFeaturesFromAudioContentHint(contentHint),
        },
    });
});
```

Forgetting the cleanup is a common bug — user stops sharing but their voice still sounds robotic because echo cancellation/AGC stayed off.

## ICE restart preservation

When `onPeerDisconnect` triggers `restartCall`, the local presentation stream stays alive (no `getDisplayMedia` re-prompt). Webapp3's call-lifecycle handler resumes presentation when the new connection comes up:

```ts
const handleOnCallConnected = createSignalHandler(
    infinityClientSignals.onCallConnected,
    () => {
        if (callStage === CallStage.Restarting && presentationStream) {
            present(presentationStream);
        }
        callStage = CallStage.Connected;
    },
);
```

The `usePresentation` hook participates via `isCallRestarting` — when `true`, the hook doesn't tear down the local stream during the connection gap.

## Capability checks: `ableToPresent`, `ableToReceivePresentation`

The capability isn't just "does the browser support it." It's a function of:
- `callType` — `AudioSendRecvVideoSendRecvPresentationSendRecv` allows both directions; `AudioSendRecv` allows neither
- Browser support for `getDisplayMedia` (mobile Safari < 17 doesn't)
- Conference type — Pexip's gateway calls have `callType !== 'video'` and disable presentation

Webapp3's check:

```ts
ableToPresent: () => {
    return (
        isSendingPresentation(config.get('callType')) &&
        Boolean(
            navigator?.mediaDevices &&
                'getDisplayMedia' in navigator.mediaDevices &&
                infinityService.conferenceFeatureFlags?.callType === 'video',
        )
    );
},

ableToReceivePresentation: () => {
    return isReceivingPresentation(config.get('callType'));
},
```

Use these to gate the "Share screen" button. Don't render it unconditionally — users will hit confusing errors.

## See also

- `media-pipeline/audio-processing.md` — presentation audio mixing details
- `call-lifecycle/reference.md` — `onCallConnected` resumption logic
- `pexip-signals-pattern` — `presentationStreamSignal`, `endPresentationSignal`, `startPresentationSignal`
- `pexip-stats-monitoring` — `qualityLimitationReason` often correlates with degraded presentation video

## Gotchas

- **Don't call `getDisplayMedia` twice in one click.** Some users double-click the share button. Use the `usePresentation` hook's state — it ignores the second call while a stream is active.
- **`stopMediaStream(stream)` is from `@pexip/media-control`.** It's not just `stream.getTracks().forEach(t => t.stop())` — it also handles cleanup events the SDK listens to.
- **`MonitorSharingNotAllowed` is webapp3-internal.** Pexip doesn't get this from the browser; it's thrown by their own validation when `monitorTypeSurfaces: 'exclude'` and the user picked a monitor anyway.
- **Direct-media transfers preserve presentation differently.** The `endedReason === 'DirectMediaTransfer'` check in the cleanup effect prevents `endPresentationSignal` from firing during transfer — the new connection picks up the same stream.
- **System audio (macOS speakers) requires Chrome + a permission.** On other browsers, `systemAudio` constraint is silently ignored.
- **`surfaceSwitching: 'include'`** lets the user change *what* they're sharing without restarting. Most apps want this on. Without it, switching from a window to a tab requires a re-prompt.
- **`pres_slot_coords` in layout updates** indicates whether presentation is *in mix* (server is composing it into the layout) vs side-by-side. Use it to know whether you should still render a separate presentation tile.

## Reference source

- `src/hooks/usePresentationSetup.ts` — the wiring (124 LOC)
- `src/services/Media.service.ts:213-316` — `getDisplayMedia` + `setCurrentDisplayMedia`
- `src/services/Media.service.ts:182-192` — `deriveDegradationPreference`
- `src/services/InfinityClient.service.ts:1198-1211` — `handlePresentationStream` (auto-unmute on shared audio)
- `pexip-sdks/media-components/src/hooks/usePresentation.ts` — the hook source
- `pexip-sdks/media/src/displayMedia.ts` — `createGetDisplayMedia` source
