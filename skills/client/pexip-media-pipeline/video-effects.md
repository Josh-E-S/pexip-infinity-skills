# Video effects: blur, replace, segmentation

How webapp3 wires MediaPipe's selfie segmenter to produce live background blur and replacement.

## What's in the video chain

```
camera input
   ↓
[VideoStreamTrackProcessor]   ← stream API or canvas API
   ↓
[MediaPipe selfie segmenter]   ← runs on frames, produces a mask
   ↓
[Canvas transform]   ← composites: blur background, or overlay image
   ↓
[contentHint applied]   ← 'motion' or 'detail'
   ↓
output track for SDP
```

The segmenter runs every frame at the configured `frameRate` (default 30). On a low-end device it's the dominant CPU/GPU cost — webapp3 has tunables for processing dimensions and dynamic scaling.

## The three rendering modes

`videoSegmentation` controls what the canvas transform does with the segmentation mask:

| Mode | Behavior |
|---|---|
| `'none'` | Pass-through, no segmentation runs (segmenter still loaded but idle) |
| `'blur'` | Blur the background using `backgroundBlurAmount` |
| `'overlay'` | Replace the background with `backgroundImageUrl` or a custom image |

Switch at runtime via the config subscription:

```ts
config.subscribe('segmentationEffects', effects => {
    void mediaService.media?.applyConstraints({video: {videoSegmentation: effects}});
});
```

## Setting up the segmenter

Two assets are needed: the MediaPipe Tasks Vision WASM bundle and the model file (`.tflite`):

```ts
import {createSegmenter, createCanvasTransform} from '@pexip/media-processor';

const taskVisionURL = new URL(
    './assets/@mediapipe/tasks-vision/wasm/',
    document.baseURI,
);
const selfieSegmenterURL = new URL(
    './assets/@mediapipe/models/selfie_segmenter_landscape.tflite',
    document.baseURI,
);

const selfieSegmenter = createSegmenter(taskVisionURL.pathname, {
    modelAsset: {
        path: selfieSegmenterURL.pathname,
        modelName: 'selfie',
    },
    delegate: () => config.get('videoProcessingDelegate'), // 'GPU' | 'CPU'
    log: (message, meta) =>
        logger.debug({context: 'media segmenter', meta}, message),
});
```

The `delegate` function is called every time the segmenter is (re)initialized. Webapp3 lets users toggle GPU/CPU at runtime — handy for debugging GPU-driver bugs on Linux.

The webapp3 build ships these files into `assets/@mediapipe/tasks-vision/wasm/` and `assets/@mediapipe/models/`. Your bundler needs to copy them — Vite and Webpack both have plugins for this; check `@pexip/media-processor`'s docs for current setup.

## The canvas transformer (where blur/replace happens)

```ts
const renderParams = {
    backgroundBlurAmount: 16,        // 0-100, but >50 has diminishing returns
    foregroundThreshold: 0.5,        // 0-1, mask cutoff for foreground
    edgeBlurAmount: 4,               // softens edges between fg and bg
    videoSegmentation: 'blur',       // 'none' | 'blur' | 'overlay'
    maskCombineRatio: 0.5,           // alpha-blend with previous frame mask, reduces flicker
    backgroundImageUrl: '/images/office.jpg', // for 'overlay' mode
    selfManageSegmenter: true,
};

const transformer = createCanvasTransform(selfieSegmenter, renderParams);
```

`maskCombineRatio` is the temporal smoothing — without it, the segmentation jitters between frames, especially on low-light video.

`selfManageSegmenter: true` lets the transformer subscribe to processor lifecycle events (start/stop/restart) and manage the segmenter's load state. Set false only if you're driving the segmenter from outside.

## The video processor (the thing that actually pumps frames)

```ts
const videoProcessor = createVideoStreamProcess({
    // Processing dimensions — what the segmenter sees, NOT what's sent
    processingWidth: 1280,
    processingHeight: 720,
    lowestProcessingHeight: 360,           // for dynamic scaling
    dynamicProcessingDimensions: () => true, // scales down under CPU pressure
    frameRate: 30,
    gpuAPI: () => config.get('gpuAPI'),    // 'webgl2' | 'webgpu'
    segmenters: {selfie: selfieSegmenter}, // map for multiple model support
    shouldEnable: () => true,
    stopAsMute: () => config.get('stopCameraAsMute'),
    trackProcessorAPI: () => 'stream',     // 'stream' (newer) | 'canvas' (compat)
    transformer,
    signals: mediaSignals,
    ...renderParams,
});
```

### `trackProcessorAPI`: stream vs canvas

| Mode | When to use |
|---|---|
| `'stream'` | Modern browsers — uses `MediaStreamTrackProcessor`/`MediaStreamTrackGenerator`. Lower overhead, GPU-friendly. |
| `'canvas'` | Older browsers (Safari < 16.x, some Firefox builds). Renders to a `<canvas>` and captures via `captureStream()`. |

Webapp3's chooser:

```ts
const chooseVideoProcessorAPI = (): VideoStreamTrackProcessorAPIs => {
    const videoProcessingAPI = config.get('videoProcessingAPI');
    if (videoProcessingAPI === 'stream' || videoProcessingAPI === 'canvas') {
        return videoProcessingAPI;
    }
    return 'stream'; // Default to stream API
};
```

If you want auto-detection: feature-test `'MediaStreamTrackProcessor' in window` and fall back to canvas if missing.

## Custom backgrounds (user-uploaded images)

Webapp3 lets users upload their own background image. The flow:

1. User picks a file → it's converted to an `ImageBitmap`
2. Stored in an `ImageStore` (signal-driven)
3. Transformer subscribes to the store and updates `backgroundImage` directly

```ts
import {imageStore} from './Image.service';

const transformer = createCanvasTransform(selfieSegmenter, renderParams);

userCustomImageSignal.add(record => {
    if (!record) return;
    transformer.backgroundImage = imageStore.getBitmapRecord();
});
```

For URL-based backgrounds (default `bgImageUrl`), use `applyConstraints`:

```ts
config.subscribe('bgImageUrl', backgroundImageUrl => {
    void mediaService.media?.applyConstraints({video: {backgroundImageUrl}});
});
```

The constraint route loads from URL; the direct `transformer.backgroundImage` route uses the already-decoded bitmap. Pick one path per source.

## Default video constraints

```ts
const video: InputConstraintSet | false = requestVideo
    ? {
          ...qualityToMediaConstraints(getStreamQuality()), // resolution from bandwidth tier
          foregroundThreshold: config.get('foregroundThreshold'),
          backgroundBlurAmount: config.get('backgroundBlurAmount'),
          edgeBlurAmount: config.get('edgeBlurAmount'),
          maskCombineRatio: config.get('maskCombineRatio'),
          frameRate: applicationConfig.frameRate,
          videoSegmentation: config.get('segmentationEffects'),
          videoSegmentationModel: applicationConfig.segmentationModel,
          backgroundImageUrl: config.get('bgImageUrl'),
          facingMode: getFacingMode(config.get('isUserFacing')),
          resizeMode: 'none',
          contentHint: config.get('videoContentHint'),
          ...(hasValidDevice(videoDevice) ? {device: videoDevice} : {}),
          // PTZ if browser supports it
          ...(!browserSupportsPtzConstraints()
              ? {}
              : {pan: fecc, tilt: fecc, zoom: fecc}),
      }
    : false;
```

## Facing-mode toggle (mobile front/back camera)

```ts
const getFacingMode = (isUserFacing: boolean) =>
    isUserFacing ? 'user' : 'environment';

export const toggleFacingMode = (track: MediaStreamTrack | undefined) => {
    config.set({key: 'videoInput', value: undefined}); // clear any device pin
    const currentFacingMode =
        interpretCurrentFacingMode(track) ??
        (config.get('isUserFacing') ? 'user' : 'environment');
    const isUserFacing = !isUserFacingMode(currentFacingMode);
    config.set({key: 'isUserFacing', value: isUserFacing, persist: true});

    mediaService.getUserMedia({
        audio: true,
        video: {facingMode: {ideal: getFacingMode(isUserFacing)}},
    });
};
```

Two non-obvious bits:
1. **Clear `videoInput` first** — a pinned `deviceId` overrides `facingMode`.
2. **Check the current track's actual facing mode** — `interpretCurrentFacingMode(track)` reads from `getSettings()`, which beats config drift.

The `canShowFacingModeToggle` check uses `areMultipleFacingModeSupported(devices)` plus an iOS Safari label-translation workaround:

```ts
let cacheFacingModeToggleDetected = false;
export const canShowFacingModeToggle = (devices: MediaDeviceInfoLike[]): boolean => {
    if (cacheFacingModeToggleDetected) return cacheFacingModeToggleDetected;
    cacheFacingModeToggleDetected =
        areMultipleFacingModeSupported(devices) ||
        currentBrowserName === 'Safari iPad' ||
        currentBrowserName === 'Safari iPhone';
    return cacheFacingModeToggleDetected;
};
```

(The cache is intentional — Safari translates device labels in the user's locale, making label-based detection unreliable.)

## Preview vs main pipeline

Webapp3 runs **two segmenters**: one for the preflight preview (smaller dimensions, lower CPU) and one for the main call. They share a model file but have independent processor instances:

```ts
const previewSegmenter = createSegmenter(taskVisionBasePath, {modelAsset, delegate});

export const usePreviewController = createPreviewControllerHook(() => {
    // Preview-specific renderParams with smaller dimensions
    const renderParams = {
        width: SETTINGS_PROCESSING_WIDTH,   // smaller
        height: SETTINGS_PROCESSING_HEIGHT, // smaller
        // ...
    };
    return {
        videoProcessors: [
            createVideoStreamProcess({
                segmenters: {selfie: previewSegmenter},
                // ...
            }),
        ],
        // ...
    };
});
```

The preview uses smaller processing dimensions because it doesn't need to feed an SDP encoder — just a `<video>` element. Saves significant CPU during the join flow.

## Gotchas

- **`processingWidth/Height` is segmenter input dimensions, not output resolution.** The output frame matches the source camera resolution. Lower processing dims = faster but blockier mask edges.
- **GPU delegate fails silently on some Intel iGPUs.** Provide a UI escape hatch (config `videoProcessingDelegate: 'CPU'`).
- **Don't change `processingWidth/Height` mid-call.** They require recreating the processor. Set them once based on device capability.
- **MediaPipe model files are 5–10MB.** Lazy-load behind the user's effects-modal click, not on app startup.
- **`backgroundImageUrl` must be CORS-accessible.** Cross-origin images fail with a tainted-canvas error. Host backgrounds on the same origin or with `Access-Control-Allow-Origin: *`.
- **Safari throttles processing in background tabs.** When the tab loses focus, segmentation FPS drops to ~5. This is by design — don't fight it.

## Reference source

- `src/services/Media.service.ts:104-211` — main video processor setup
- `src/services/Media.service.ts:499-572` — preview controller with separate segmenter
- `src/services/Media.service.ts:680-719` — facing mode toggle
- `pexip-sdks/media-processor/src/segmenter.ts` — MediaPipe wrapping
- `pexip-sdks/media-processor/src/canvasTransform.ts` — blur/overlay implementation
