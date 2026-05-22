# Complete Media Pipeline Setup

This document detailing the full webapp3 media pipeline configuration, including audio stream processes (denoise/VAD/ASD), selfie segmenters, and Canvas transformers.

## The full webapp3 setup (with processors)

```ts
import {
    AUDIO_CONTENT_HINTS,
    VIDEO_CONTENT_HINTS,
    createAudioStreamProcess,
    createMedia,
    createVideoStreamProcess,
} from '@pexip/media';
import {denoiseWasm} from '@pexip/denoise/urls';
import {
    urls as mpUrls,
    createSegmenter,
    createCanvasTransform,
} from '@pexip/media-processor';

// 1. Audio processor (denoise + VAD + ASD)
const audioProcessor = createAudioStreamProcess({
    shouldEnable: () => true,
    denoiseParams: {
        wasmURL: denoiseWasm.href,             // RNNoise WASM blob
        workletModule: mpUrls.denoise().href,  // AudioWorklet glue
    },
    fftSize: 2048,
    analyzerUpdateFrequency: 30,                // Hz
    audioSignalDetectionDuration: 3,            // seconds
    throttleMs: 200,
    onAudioSignalDetected: mediaSignals.onSilentDetected.emit,
    onVoiceActivityDetected: mediaSignals.onVAD.emit,
    signals: mediaSignals,
});

// 2. Video segmenter (MediaPipe selfie)
const taskVisionBasePath = new URL(
    './assets/@mediapipe/tasks-vision/wasm/',
    document.baseURI,
).pathname;

const selfieSegmenter = createSegmenter(taskVisionBasePath, {
    modelAsset: {
        path: '/assets/@mediapipe/models/selfie_segmenter_landscape.tflite',
        modelName: 'selfie',
    },
    delegate: () => 'GPU', // or 'CPU' — see video-effects.md
});

const transformer = createCanvasTransform(selfieSegmenter, {
    backgroundBlurAmount: 16,
    foregroundThreshold: 0.5,
    edgeBlurAmount: 4,
    videoSegmentation: 'blur', // 'none' | 'blur' | 'overlay'
    maskCombineRatio: 0.5,
});

// 3. Video processor
const videoProcessor = createVideoStreamProcess({
    frameRate: 30,
    processingWidth: 1280,
    processingHeight: 720,
    segmenters: {selfie: selfieSegmenter},
    shouldEnable: () => true,
    stopAsMute: () => true,
    trackProcessorAPI: () => 'stream', // or 'canvas' — see video-effects.md
    transformer,
    signals: mediaSignals,
    backgroundBlurAmount: 16,
    foregroundThreshold: 0.5,
    edgeBlurAmount: 4,
    videoSegmentation: 'blur',
    maskCombineRatio: 0.5,
});

// 4. Wire it all
export const mediaService = createMedia({
    getMuteState: () => ({audio: false, video: false}),
    signals: mediaSignals,
    stopVideoTrackAsMute: () => true,
    audioProcessors: [audioProcessor],
    videoProcessors: [videoProcessor],
    getDefaultConstraints,
});
```
