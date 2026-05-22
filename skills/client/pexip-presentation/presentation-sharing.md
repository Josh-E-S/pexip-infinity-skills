# Presentation Sharing: Content Hints, Audio Mixing, and Recovery

This document details advanced implementation aspects of Pexip presentation (screen sharing), including content encoding hints, audio mixing lifecycle, call recovery, and capability checks in Webapp3.

## Content hints — motion vs detail

Two user-tunable hints affect both the video encoder and the audio mix:

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

This is how a "Prioritize sharing motion" toggle in the settings changes encoding behavior.

## Audio mixing during presentation

If the user shares a tab/window with audio, that audio gets mixed into the outgoing stream. See [pexip-media-pipeline](../pexip-media-pipeline/SKILL.md) for the mixer setup. When `setCurrentDisplayMedia(stream)` runs, it also flips the audio constraints:

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

Forgetting the cleanup is a common bug where a user stops sharing but their voice still sounds robotic because echo cancellation/AGC stayed off.

## ICE restart preservation

When `onPeerDisconnect` triggers `restartCall`, the local presentation stream stays alive without a `getDisplayMedia` re-prompt. Webapp3's call-lifecycle handler resumes presentation when the new connection comes up:

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

The `usePresentation` hook participates via `isCallRestarting` — when `true`, the hook does not tear down the local stream during the connection gap.

## Capability checks: `ableToPresent`, `ableToReceivePresentation`

The capability is a function of:
- `callType` — `AudioSendRecvVideoSendRecvPresentationSendRecv` allows both directions; `AudioSendRecv` allows neither.
- Browser support for `getDisplayMedia` (mobile Safari < 17 does not support it).
- Conference type — Pexip's gateway calls have `callType !== 'video'` and disable presentation.

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

Use these to gate the "Share screen" button. Do not render it unconditionally.

## Gotchas

- **Do not call `getDisplayMedia` twice in one click.** Some users double-click the share button. Use the `usePresentation` hook's state to ignore the second call while a stream is active.
- **`stopMediaStream(stream)` is from `@pexip/media-control`.** It handles additional cleanup events the SDK listens to, beyond stopping tracks.
- **`MonitorSharingNotAllowed` is webapp3-internal.** Pexip does not get this from the browser; it is thrown by validation when `monitorTypeSurfaces: 'exclude'` and the user picked a monitor anyway.
- **Direct-media transfers preserve presentation differently.** The `endedReason === 'DirectMediaTransfer'` check in the cleanup effect prevents `endPresentationSignal` from firing during transfer so the new connection can pick up the same stream.
- **System audio (macOS speakers) requires Chrome + a permission.** On other browsers, the `systemAudio` constraint is silently ignored.
- **`surfaceSwitching: 'include'`** lets the user change what they are sharing without restarting. Without it, switching from a window to a tab requires a re-prompt.
- **`pres_slot_coords` in layout updates** indicates whether presentation is in mix (server is composing it into the layout) vs side-by-side. Use it to determine if you need to render a separate presentation tile.
