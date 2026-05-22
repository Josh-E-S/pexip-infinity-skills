# Preflight Device Checks and Permissions

This document details browser-specific permission flow instructions, output device sink testing, and device unplug fallback notification logic in Webapp3's pre-call preflight screen.

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
