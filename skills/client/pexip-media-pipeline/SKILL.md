---
name: pexip-media-pipeline
description: Use when wiring `@pexip/media`'s `createMedia`, configuring audio + video processors, getUserMedia constraints, switching cameras/mics mid-call, applying content hints (`motion`/`detail`/`text`/`music`), changing bandwidth, or building the layer that produces the `MediaStream` you pass to `infinityClient.call()`. Triggers on `createMedia`, `mediaService`, `getUserMedia`, audio constraints, video constraints, `MediaTrack`, `applyConstraints`, denoise, VAD, ASD, MediaPipe, segmenter, content hint, facing mode, presentation audio mixing.
license: MIT
---

# Pexip media pipeline

`@pexip/media` is the layer between the browser's `getUserMedia` and `@pexip/infinity`. It wraps device selection, applies audio + video processors (denoise, blur, replace), tracks mute state, and emits signals when anything changes. **Build this once, hand the resulting `MediaStream` to the InfinityClient, and let signals coordinate the rest.**

This skill covers the architecture and the minimum setup. The deep details — how denoise wires the WASM worklet, how MediaPipe runs the segmenter, what `ProcessorRestarted` means — are in sibling files.

## The pipeline shape

```
config (mute state, device IDs, blur amount, etc.)
   ↓
getDefaultConstraints()  →  {audio: {...}, video: {...}}
   ↓
mediaService.getUserMedia(constraints)
   ↓
[audioProcessor]  →  denoise WASM, VAD, ASD, presentation mix
[videoProcessor]  →  MediaPipe segmenter, canvas transform, blur/replace
   ↓
mediaService.media.stream  →  MediaStream
   ↓
infinityClient.setStream(stream)   ← already-running call
infinityClient.call({mediaStream})  ← initial join
```

The processors are pluggable: pass them in at `createMedia` time, and they auto-attach to every track produced by `getUserMedia`.

## Quick start: the simplest viable pipeline

```ts
import {createMedia, createMediaSignals} from '@pexip/media';

// Signal hub — see signals-pattern skill
const mediaSignals = createMediaSignals(
    [
        'onAddTrack',
        'onDevicesChanged',
        'onMediaTrackMuted',
        'onMediaTrackResumed',
        'onMediaTrackStopped',
        'onMediaTrackSuspended',
        'onRemoveTrack',
        'onStatusChanged',
        'onUpdatingAudio',
        'onUpdatingVideo',
    ],
    'my-app-main',
);

const getDefaultConstraints = () => ({
    audio: {
        sampleRate: 48000,
        echoCancellation: true,
        autoGainControl: true,
        noiseSuppression: true,
    },
    video: {
        width: 1280,
        height: 720,
        frameRate: 30,
        facingMode: 'user',
    },
});

export const mediaService = createMedia({
    getMuteState: () => ({audio: false, video: false}),
    signals: mediaSignals,
    stopVideoTrackAsMute: () => true, // releases camera when video is muted
    audioProcessors: [],
    videoProcessors: [],
    getDefaultConstraints,
});

// Acquire the stream
await mediaService.getUserMedia(getDefaultConstraints());

// Hand to Infinity
infinityClient.setStream(mediaService.media!.stream);
```

That's a working pipeline. Without processors, you get raw `getUserMedia` with mute-as-track-stop semantics and the mediaSignals event bus. Add processors below.

## The full webapp3 setup (with processors)

For details on configuring the audio processor (RNNoise denoise, voice activity detection), video segmenter (MediaPipe landscape model), canvas transform, and integrating them into `createMedia`, see [Complete Media Pipeline Setup](pipeline-setup.md).

## Connecting media to InfinityClient

Two wires:

```ts
// 1. New device acquired (initial or device change) → push to call
mediaSignals.onMediaChanged.add(media => {
    if (media?.stream) {
        infinityClient.setStream(media.stream);
    }
});

// 2. Bandwidth change → applyConstraints to scale resolution/bitrate
config.subscribe('bandwidth', bandwidth => {
    infinityClient.setBandwidth(Number(bandwidth));
    void mediaService.media?.applyConstraints({
        video: {...qualityToMediaConstraints(getStreamQuality(bandwidth))},
    });
});
```

`mediaSignals.onMediaChanged` (a behavior signal in webapp3) replays the current media to new subscribers, so the InfinityContext provider just adds the listener and the stream attaches automatically.

## Mute as device-release (the `stopCameraAsMute` flag)

By default, webapp3 sets `stopCameraAsMute: true` — muting video releases the camera so other apps (Zoom, OS-level capture) can use it. To keep the camera held but the track muted, set `false`. This is a UX call:

```ts
config.subscribe('stopCameraAsMute', /* ... */);
```

When `stopCameraAsMute` flips to `false` mid-call, webapp3 re-requests media (`mediaService.getUserMedia(getDefaultConstraints())`) to apply the new behavior.

## Reactive constraints — config-driven `applyConstraints`

Webapp3 wires every user-tunable config key to a constraint update. This is how the effects modal works without restarting media:

```ts
config.subscribe('backgroundBlurAmount', amount => {
    void mediaService.media?.applyConstraints({video: {backgroundBlurAmount: amount}});
});
config.subscribe('denoise', denoise => {
    void mediaService.media?.applyConstraints({
        audio: {denoise, noiseSuppression: !denoise},
    });
});
config.subscribe('vad', vad => {
    void mediaService.media?.applyConstraints({audio: {vad}});
});
config.subscribe('bgImageUrl', backgroundImageUrl => {
    void mediaService.media?.applyConstraints({video: {backgroundImageUrl}});
});
```

These run *without* re-requesting `getUserMedia` — the processors swap parameters in place.

## Sibling references

- `audio-processing.md` — denoise WASM details, VAD, ASD, presentation audio mixing, content hints
- `video-effects.md` — MediaPipe wiring, blur vs replace, GPU vs CPU delegate, processing dimensions, custom backgrounds
- `self-healing.md` — the `ProcessorRestarted` listener that recovers stuck-muted tracks

## See also

- `pexip-signals-pattern` — `mediaSignals` is a `createMediaSignals` hub; understand the variants
- `pexip-preflight` — uses preview hooks (`createPreviewHook`, etc.) before the main pipeline starts
- `pexip-call-lifecycle` — `clientMute` / `muteVideo` API calls coordinate with `mediaSignals.onMediaTrackMuted`
- `pexip-reconnect` — `applyConstraints` + bandwidth changes during reconnect
- `pexip-branding-manifest` — `applicationConfig.audioProcessing` / `videoProcessing` flags toggle whole subsystems
- `pexip-fecc` — PTZ constraints (`pan`/`tilt`/`zoom`) flow through `getDefaultConstraints`

## Gotchas

- **Don't call `getUserMedia` directly.** Always go through `mediaService.getUserMedia(constraints)` — it routes through the processors.
- **`audio` and `video` constraints can be `false`** to disable that track. Webapp3 derives this from `callType` (e.g. audio-only call → `video: false`).
- **`applyConstraints` is async but doesn't reject on processor errors.** Watch `mediaSignals.onMediaTrackMuted` for actual failures.
- **`getDefaultConstraints` runs every time** the SDK needs to acquire media. Make it cheap and side-effect-free.
- **Browser quirks:** Safari Mac 18.4–18.5 has H264 issues. Webapp3 sets `allowH264: false` for those versions in the call config (not a media config — but check user-agent there).
- **The `device` field accepts a `MediaDeviceInfoLike`**, not a `deviceId` string. Use `toMediaDeviceInfo()` from `@pexip/media-control` to convert.

## Reference source

- `src/services/Media.service.ts` — the full pipeline (720 LOC)
- `src/signals/Media.signals.ts` — the signal hub
- `src/contexts/UserMediaContextProvider.tsx` — how the service is exposed to React
- `src/contexts/InfinityContextProvider.tsx` — how media wires into the call
- `pexip-sdks/media/src/media.ts` — SDK source
