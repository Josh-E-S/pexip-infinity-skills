---
name: pexip-preflight
description: Use when building the pre-call screen — device pickers, mic/camera test, permission prompts, blocked-permission help UX. Triggers when wiring `useDevices`, `useAudioInput`, `useVideoInput`, `usePreviewController`, `DevicesSelection`, `JoinMeetingButton`, or any "before-they-join-the-call" flow on Pexip. Also use when designing fallback messaging for users with denied camera/mic permissions, including per-browser instructional videos for Chrome / Firefox / Safari / Edge on desktop and mobile.
license: MIT
---

# Pexip preflight

The preflight screen is the gauntlet between "user clicked a meeting link" and "user is in the call." Webapp3 handles a surprising amount here: device enumeration with hot-swap detection, permission prompts that can fail in 5+ different ways, mic/camera test, fallback notifications when devices vanish, blocked-permission help screens with browser-specific instructional videos, and a separate preview pipeline so effects like blur work *before* the main media pipeline starts.

This skill captures the right structure. The deep details live in the parent `pexip-media-pipeline` skill (`createMedia` setup) — preflight is mostly about the **UI hooks** that `@pexip/media-components` provides, plus the browser-detection pattern.

## The two flows: Express vs Standard

Webapp3 has two preflight UX patterns:

| Flow | When it fires | Layout |
|---|---|---|
| **Express** (desktop) | User clicks a meeting URL with full path | Single-screen: device pickers + "Join" button + "Other join options" |
| **Standard** (mobile/tablet, or no alias) | User lands on the home page first | Multi-step cards: pick name → pick devices → confirm |

```tsx
// From src/viewModels/ExpressFlow.viewModel.tsx
export const ExpressFlow: React.FC<{conferenceAlias: string}> = ({conferenceAlias}) => {
    const call = useJoinMeetingCallback(conferenceAlias);
    const [callType] = useConfig('callType');

    return userAgentDetails.isMobile || userAgentDetails.isTablet ? (
        <ReadyToJoinStep call={call} />
    ) : (
        <ExpressFlowView showSpinner={false}>
            <PreflightJoin flowType={FlowType.Express}>
                <PreflightDeviceSelection />
                <JoinMeetingButton onClick={call} callType={callType} />
                {applicationConfig.availableCallTypes.length > 0 && (
                    <OtherJoiningOptions />
                )}
            </PreflightJoin>
        </ExpressFlowView>
    );
};
```

The mobile branch uses `ReadyToJoinStep` (a card-based flow), desktop uses `ExpressFlowView` (a sidebar layout).

## Device enumeration & selection

`@pexip/media-components` provides ready-made hooks. The pattern:

```tsx
import {
    DevicesSelection,
    useDeviceErrorMessage,
    useDeviceErrorMessageState,
    onDeviceSelectChange,
} from '@pexip/media-components';

import {
    useAudioInput,
    useAudioInputChangeHandler,
    useAudioOutput,
    useAudioOutputChangeHandler,
    useDevices,
    useHaveRequestedAudio,
    useHaveRequestedVideo,
    useMediaRequest,
    useMediaStatus,
    useVideoInput,
    useVideoInputChangeHandler,
} from '../hooks/userMedia';

export const PreflightDeviceSelection: React.FC = () => {
    const devices = useDevices();
    const selectedAudioInput = useAudioInput();
    const selectedVideoInput = useVideoInput();
    const selectedAudioOutput = useAudioOutput();

    const requestedVideo = useHaveRequestedVideo();
    const requestedAudio = useHaveRequestedAudio();
    const status = useMediaStatus();

    const handleVideoInputChange = useVideoInputChangeHandler();
    const handleAudioInputChange = useAudioInputChangeHandler();
    const onAudioOutputChange = useAudioOutputChangeHandler(true);

    const {
        videoInputError, setVideoInputError,
        audioInputError, setAudioInputError,
    } = useDeviceErrorMessageState();

    // The device-error message hook ties media status → user-friendly errors
    useDeviceErrorMessage({
        setAudioInputError,
        setVideoInputError,
        streamStatus: status,
        requested: {audio: requestedAudio, video: requestedVideo},
    });

    return (
        <DevicesSelection
            devices={devices}
            audioInput={selectedAudioInput}
            videoInput={selectedVideoInput}
            audioOutput={selectedAudioOutput}
            onAudioInputChange={onDeviceSelectChange(setAudioInputError, handleAudioInputChange)}
            onVideoInputChange={onDeviceSelectChange(setVideoInputError, handleVideoInputChange)}
            onAudioOutputChange={onAudioOutputChange}
            requestedAudio={requestedAudio}
            requestedVideo={requestedVideo}
            audioInputError={(requestedAudio && audioInputError) || undefined}
            videoInputError={(requestedVideo && videoInputError) || undefined}
            // ... more props
        />
    );
};
```

Key insight: **`useDeviceErrorMessage` does the translation** from raw `MediaStatus` to user-facing strings. You don't need to write that mapping — pass the hooks in, get formatted error messages out.

## The "have I requested" hooks

`useHaveRequestedAudio()` and `useHaveRequestedVideo()` return `true` once the user has *attempted* to grant permission (regardless of success). This drives the difference between:

- "We haven't asked yet" → show a "Click to enable camera" CTA
- "We asked and got something" → show device pickers
- "We asked and got an error" → show the error + help video

Without this gating, the device pickers render in a useless state on first render (no devices listed because no permission yet).

## Browser-specific permission help

When permissions are blocked, webapp3 shows a **per-browser instructional video** demonstrating exactly which menu to click to grant access. The webapp3 build ships these as MP4 + WebM in `assets/blocked-permissions-gifs/`:

```
blocked-chrome.{mp4,webm}            ← Chrome desktop, also Edge desktop
blocked-chrome-mobile.{mp4,webm}     ← Chrome/Edge Android
blocked-firefox.{mp4,webm}           ← Firefox desktop
blocked-safari-macosx.{mp4,webm}     ← Safari macOS
blocked-safari-ios.{mp4,webm}        ← Safari iOS / Chrome iOS
blocked-safari-ipados.{mp4,webm}     ← Safari iPadOS
```

The browser-detection pattern uses a typed dispatch table:

```ts
import {BROWSER_NAME, getUserAgentDetails} from '@pexip/media-components';

export interface BrowserDetection<T> {
    onChromeOnAndroid: () => T;
    onChromeOnDesktop: () => T;
    onChromeOnIPhone: () => T;
    onChromeOnIPad: () => T;
    onFirefoxOnDesktop: () => T;
    onEdgeOnAndroid: () => T;
    onEdgeOnDesktop: () => T;
    onEdgeOnOtherOs: () => T;
    onSafariOnIPhone: () => T;
    onSafariOnIPad: () => T;
    onSafariOnMacOs: () => T;
    onOtherBrowser: () => T;
}

export const identifyBrowserContext = <T>(
    userAgentDetails: UserAgentsDetails,
    browserDetection: BrowserDetection<T>,
): T => {
    switch (userAgentDetails.browserName) {
        case BROWSER_NAME.Chrome:
            if (userAgentDetails.isAndroid) return browserDetection.onChromeOnAndroid();
            if (userAgentDetails.isIOS) return browserDetection.onChromeOnIPhone();
            if (userAgentDetails.isIPad) return browserDetection.onChromeOnIPad();
            if (userAgentDetails.isDesktop) return browserDetection.onChromeOnDesktop();
            break;
        case BROWSER_NAME.Safari:
        case BROWSER_NAME.MobileSafari:
            if (userAgentDetails.isIOS && userAgentDetails.isMobile)
                return browserDetection.onSafariOnIPhone();
            if (userAgentDetails.isIPad) return browserDetection.onSafariOnIPad();
            if (userAgentDetails.isMacOS) return browserDetection.onSafariOnMacOs();
            break;
        // ... Firefox, Edge, etc.
    }
    return browserDetection.onOtherBrowser();
};
```

This pattern beats `if/else` chains: every browser/OS combo gets a typed handler, so you can't forget a case. Use it for any per-browser branching, not just permission help videos.

The dispatch is reused for **multiple things**: video file URLs, "permission info type" (which UI variant to show), help-link URLs. One detection, multiple outputs.

## Mic test (audio meter)

Webapp3 has a `TestYourMicrophone` component that drives an audio meter from the local stream. The meter reads peak amplitude from the `audioProcessor` and renders bars. The pattern:

1. Get the current audio track via `mediaService.media?.audioInput`
2. Subscribe to amplitude events on `mediaSignals` (the `audioProcessor` emits these via `onVoiceActivityDetected` / similar)
3. Render bars

The audio meter is a `@pexip/media-components` component (`AudioMeter`); webapp3 wires it via `viewModels/AudioMeter.viewModel.tsx`. You don't normally need to reimplement it — pass the stream in.

## Output device test (speaker test)

Plays a test sound through the chosen output device. The `OutputAudioTester` component takes a `sinkId` (the chosen output's `deviceId`) and routes audio there via `HTMLMediaElement.setSinkId()`. Browser support for `setSinkId` varies — Chromium has it, Firefox has it behind a flag, Safari does not.

Webapp3 uses pre-encoded test tones from `assets/test.<hash>.flac`.

## Fallback device notifier

Devices can vanish mid-preflight (user unplugs USB cam). `useFallbackDeviceNotifier` from `@pexip/media-components` watches for this and shows a toast:

```ts
import {useFallbackDeviceNotifier} from '@pexip/media-components';

const handleMessageFallback = useCallback((message: string) => {
    if (config.get('lastFallBackMsg') !== message) {
        notificationToastSignal.emit([{message}]);
        config.set({key: 'lastFallBackMsg', value: message, persist: true});
    }
}, []);

useFallbackDeviceNotifier(
    mediaSignals.onMediaChanged.add,
    handleMessageFallback,
);
```

The dedup against `lastFallBackMsg` matters — without it, repeated unplug/replug cycles spam the user with toasts.

## Preview pipeline (effects-aware preflight)

The preview uses a *separate* `MediaService` instance with its own segmenter. This is so:
- Effects (blur, replace) work in preflight without committing to the main pipeline
- Smaller processing dimensions = lower CPU cost during the join flow
- The user can change cameras without disrupting an already-running call (relevant when re-joining)

```ts
// From src/services/Media.service.ts
export const usePreviewController = createPreviewControllerHook(() => {
    const previewSignals = createMediaSignals([/* ... */], 'PreviewStreamController');
    const renderParams = {
        width: SETTINGS_PROCESSING_WIDTH,    // smaller than main
        height: SETTINGS_PROCESSING_HEIGHT,  // smaller than main
        // ...
    };
    return {
        getCurrentDevices: () => mediaService.devices,
        getCurrentMedia: () => mediaService.media,
        getDefaultConstraints,
        updateMainStream: constraints => {
            applyCallTypeSendDirectionChange(constraints);
            return mediaService.getUserMediaAsync(constraints);
        },
        mainMediaSignal: mediaSignals.onMediaChanged,
        signals: previewSignals,
        // ... preview-specific processors
    };
});
```

The preview hooks (`usePreviewAudioInput`, `usePreviewVideoInput`, `usePreviewSegmentationEffects`, etc.) write through to the same `config` object that the main pipeline reads, so effects "stick" when the user joins the call.

## Mobile vs desktop UX differences

| Concern | Desktop | Mobile |
|---|---|---|
| Layout | Sidebar (`ExpressFlowView`) | Full-screen card (`ReadyToJoinStep`) |
| Camera toggle | Device dropdown | Front/back facing-mode swap button |
| Mic test | Live audio meter visible | Tap-to-test (saves battery) |
| Effects | Inline | In a separate modal |
| Permissions video | Native `<video>` tag | Native `<video>` tag (autoplay sometimes blocked) |

The mobile facing-mode toggle uses `toggleFacingMode` from the media service (see `media-pipeline/video-effects.md`).

## See also

- `pexip-media-pipeline` — the full `createMedia` setup; preflight is a UI layer over it
- `pexip-signals-pattern` — `mediaSignals.onMediaChanged` is what drives device-list reactivity
- `pexip-call-lifecycle` — what happens when the user clicks "Join"
- `pexip-branding-manifest` — `customStepConfig` adds an extra card to this flow

## Gotchas

- **Don't call `enumerateDevices` directly.** Use `useDevices()`. The hook respects permission state and re-emits when devices hot-plug.
- **Audio output (`sinkId`) selection only works in some browsers.** Hide the dropdown in Safari and Firefox-without-flag, or you'll get an `setSinkId is not a function` error on click.
- **Device labels are empty until permission is granted.** Show "Default microphone" placeholders before permission, real labels after.
- **iOS Safari requires a user gesture** to start the audio context. The mic test must trigger from a click, not on mount.
- **Preview pipeline must stop before main pipeline starts.** Otherwise both segmenters run simultaneously and CPU explodes. Webapp3 wires `onEnded` to clean up the preview when the user joins.
- **The `lastFallBackMsg` config key is persisted.** Clear it when the user resolves the device situation, or stale toasts haunt the next session.
- **`useDeviceErrorMessage` translates errors to copy.** If you wrap your own UI, route through this hook — don't roll your own error-message logic, the cases are too numerous (NotAllowed, NotFound, NotReadable, OverconstrainedError, AbortError, SecurityError, TypeError).

## Reference source

- `src/pages/Preflight.page.tsx` — top-level preflight page
- `src/viewModels/ExpressFlow.viewModel.tsx` — desktop branch
- `src/viewModels/PreflightDeviceSelection.viewModel.tsx` — device-picker wiring
- `src/utils/getBrowserSpecificVideoFiles.ts` — browser-detection dispatch
- `src/utils/getBlockedBrowserPermissionsInfo.ts` — permission-help logic
- `src/services/Media.service.ts:499-572` — preview controller
- `pexip-sdks/media-components/src/hooks/` — the `useDevices`, `usePreview*` hooks
