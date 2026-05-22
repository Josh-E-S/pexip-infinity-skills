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

## Advanced Sharing Controls, Audio Mixing, and Recovery

For detailed explanations of presentation audio mixing, dynamic content hints (motion vs detail encoding preferences), ICE restart recovery logic, capability validation, and screen sharing edge-cases (gotchas), see [Presentation Sharing: Content Hints, Audio Mixing, and Recovery](presentation-sharing.md).

## Reference source

- `src/hooks/usePresentationSetup.ts` — the wiring (124 LOC)
- `src/services/Media.service.ts:213-316` — `getDisplayMedia` + `setCurrentDisplayMedia`
- `src/services/Media.service.ts:182-192` — `deriveDegradationPreference`
- `src/services/InfinityClient.service.ts:1198-1211` — `handlePresentationStream` (auto-unmute on shared audio)
- `pexip-sdks/media-components/src/hooks/usePresentation.ts` — the hook source
- `pexip-sdks/media/src/displayMedia.ts` — `createGetDisplayMedia` source
