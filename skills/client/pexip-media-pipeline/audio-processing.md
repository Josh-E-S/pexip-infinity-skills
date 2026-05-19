# Audio processing

How webapp3 wires denoise, VAD (voice activity detection), ASD (audio signal detection while muted), and presentation-audio mixing.

## What's in the audio chain

```
mic input
   ↓
[browser AGC + EC + NS]   ← echoCancellation, autoGainControl, noiseSuppression constraints
   ↓
[Pexip denoise (RNNoise WASM)]   ← optional, replaces browser NS
   ↓
[VAD analyzer]   ← emits onVAD events
   ↓
[ASD analyzer]   ← emits onSilentDetected when track is muted but mic picks up speech
   ↓
[presentation audio mixer]   ← mixes in screenshare audio if active
   ↓
output track for SDP
```

## Denoise

Pexip ships RNNoise as WebAssembly + AudioWorklet. The two URL exports plug straight in:

```ts
import {denoiseWasm} from '@pexip/denoise/urls';
import {urls as mpUrls} from '@pexip/media-processor';

const audioProcessor = createAudioStreamProcess({
    shouldEnable: () => applicationConfig.audioProcessing,
    denoiseParams: {
        wasmURL: denoiseWasm.href,
        workletModule: mpUrls.denoise().href,
    },
    // ...
});
```

You **don't** load these manually. The audio processor handles instantiation. They must be served from the same origin (or with proper CORS) — check your bundler's asset handling.

The webapp3 build ships `denoise.worklet.<hash>.js` and `denoise_bg.wasm` as separate assets. Vite/Webpack should emit them automatically when you import from `@pexip/denoise/urls`.

### Denoise vs browser noise suppression

Don't enable both. Webapp3's logic:

```ts
const audio = {
    noiseSuppression:
        shouldEnableAudioTuneables() &&
        (config.get('noiseSuppression') || !config.get('denoise')),
    denoise: config.get('denoise'),
};
```

If `denoise` is on → browser `noiseSuppression` off. Otherwise → browser `noiseSuppression` on. Never both.

## Voice activity detection (VAD)

VAD fires `mediaSignals.onVAD` when the user is actually speaking. Use it for:
- "Currently speaking" UI indicators
- Auto-unmute prompts (push-to-talk, whisper, etc.)
- Speaker gating in spotlight mode

Configuration:

```ts
const audioProcessor = createAudioStreamProcess({
    fftSize: 2048,                       // FFT analyzer resolution
    analyzerUpdateFrequency: 30,         // Hz — how often VAD samples
    throttleMs: 200,                     // Min ms between onVAD emissions
    onVoiceActivityDetected: mediaSignals.onVAD.emit,
    // ...
});
```

VAD is gated by the `vad` config flag — you can turn it off if you don't use it (saves CPU):

```ts
config.subscribe('vad', vad => {
    void mediaService.media?.applyConstraints({audio: {vad}});
});
```

## Audio signal detection (ASD) — "you're speaking but muted"

ASD watches the mic *even when the track is muted* and fires when the user's been talking continuously into a muted mic. This is what powers the "Trying to speak? Your mic is muted" notification.

```ts
const audioProcessor = createAudioStreamProcess({
    audioSignalDetectionDuration: 3,    // seconds of continuous speech before firing
    onAudioSignalDetected: mediaSignals.onSilentDetected.emit,
    // ...
});
```

The signal name (`onSilentDetected`) is webapp3's choice — the underlying SDK callback is `onAudioSignalDetected`. Wire whichever is clearer in your codebase.

Like VAD, it's config-gated:

```ts
config.subscribe('asd', asd => {
    void mediaService.media?.applyConstraints({audio: {asd}});
});

export const enableAudioSignalDetection = () =>
    config.set({key: 'asd', value: true});
export const disableAudioSignalDetection = () =>
    config.set({key: 'asd', value: false});
```

## Presentation audio mixing

When the user shares a screen with audio (e.g. playing a video in a tab with "Share tab audio"), webapp3 mixes that audio into the outgoing stream. This is `createAudioMixingProcess`:

```ts
import {createAudioMixingProcess, isScreenShareSupported} from '@pexip/media';

const presentationMixer = createAudioMixingProcess(
    getCurrentDisplayMedia,    // function returning the active getDisplayMedia stream
    mediaSignals,
);

export const mediaService = createMedia({
    audioProcessors: [
        audioProcessor,
        isScreenShareSupported && presentationMixer,
    ].flatMap(p => (p ? [p] : [])),
    // ...
});
```

Note the `flatMap` filter — `presentationMixer` may be falsy if screen share isn't supported, so we only include truthy processors.

## Content hints — `speech` vs `music`

When audio is presentation audio (a video playing), webapp3 changes the audio constraints to disable echo cancellation, AGC, and noise suppression — those would mangle music. The W3C spec says:

> For an audio track with the value "music", and for constraints `echoCancellation`, `autoGainControl` and `noiseSuppression` apply a default of "false".

Webapp3's helper:

```ts
export const deriveAudioFeaturesFromAudioContentHint = (hint: AudioContentHint) => {
    switch (hint) {
        case 'speech':
            return {
                echoCancellation: config.get('echoCancellation'),
                autoGainControl: config.get('autoGainControl'),
                noiseSuppression: shouldEnableAudioTuneables() &&
                    (config.get('noiseSuppression') || !config.get('denoise')),
                denoise: config.get('denoise'),
            };
        case 'music':
            return {
                echoCancellation: false,
                autoGainControl: false,
                noiseSuppression: false,
                denoise: false,
            };
    }
};
```

Trigger this when presentation audio starts:

```ts
export const setCurrentDisplayMedia = (newDisplayMedia?: MediaStream) => {
    currentDisplayMedia = newDisplayMedia;
    const [audioTrack] = newDisplayMedia?.getAudioTracks() ?? [];
    presentationStreamSignal.emit(newDisplayMedia);

    if (audioTrack) {
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

When the user stops presenting, **flip everything back**:

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

Forgetting this flip is a common bug — the user stops sharing but their voice still sounds robotic because EC/NS are still off.

## `presoContentHint` (for video, but affects audio derivation)

Users can choose `motion` (smoothness) or `detail` (sharpness) for presentation video. `motion` implies the user is showing video-like content, which webapp3 treats as a hint that audio is probably music:

```ts
export const deriveAudioContentHintFromPreso = (stream: MediaStream | undefined) => {
    return stream &&
        stream.getAudioTracks().length > 0 &&
        config.get('presoContentHint') === VIDEO_CONTENT_HINTS.Motion
        ? AUDIO_CONTENT_HINTS.Music
        : defaultUserConfig.audioContentHint;
};
```

So `motion + presentation audio = music content hint`. This is a webapp3 heuristic; not part of the SDK contract.

## Default constraints — the audio shape

```ts
const audio: InputConstraintSet | false = requestAudio
    ? {
          sampleRate: 48000,
          echoCancellation: config.get('echoCancellation'),
          autoGainControl: config.get('autoGainControl'),
          noiseSuppression: !config.get('denoise') && config.get('noiseSuppression'),
          denoise: config.get('denoise'),
          vad: config.get('vad'),
          asd: config.get('asd'),
          contentHint: config.get('audioContentHint'),
          mixWithAdditionalMedia: false,
          ...(hasValidDevice(audioDevice) ? {device: audioDevice} : {}),
      }
    : false;
```

`requestAudio` comes from `isSendingAudio(callType)`. If the call type doesn't send audio, the audio constraint is `false`.

## Gotchas

- **`sampleRate: 48000` is non-negotiable for the denoise worklet.** RNNoise expects this rate. Don't change it.
- **`mixWithAdditionalMedia: true`** must be set during presentation audio. If you skip it, the mixer doesn't engage and presentation audio doesn't reach the call.
- **Browser AGC fights with denoise.** If users complain about pumping/breathing artifacts, disable browser `autoGainControl` first.
- **Mobile Safari will silently drop denoise.** It doesn't support AudioWorklet in some contexts. Check `mediaSignals.onUpdatingAudio` for failure events.

## Reference source

- `src/services/Media.service.ts:85-102` — audio processor setup
- `src/services/Media.service.ts:316-319` — presentation mixer
- `src/services/Media.service.ts:240-294` — content hint derivation
- `src/services/Media.service.ts:328-371` — `getDefaultConstraints` for audio
- `pexip-sdks/media/src/audioProcessor.ts` — SDK audio processor source
- `pexip-sdks/media/src/audioMixingProcessor.ts` — presentation mixer source
