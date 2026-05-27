---
name: pexip-browser-close-confirmation
description: Use when wiring the "Are you sure you want to leave?" browser-close prompt for an in-call user. Triggers on `beforeunload`, `useBrowserCloseConfirmation`, `enableBrowserCloseConfirmationByDefault`, `BrowserCloseConfirmation`, accidental tab close, leave confirmation, prevent navigation away from meeting.
license: MIT
---

# Pexip browser-close confirmation

The browser's `beforeunload` hook gives you the standard "Reload site? Changes you made may not be saved" prompt. For a video call, that's exactly what you want when the user accidentally closes the tab — interrupting an active call should require confirmation.

But the implementation has nuance: browsers handle `beforeunload` differently across versions, the user can toggle the preference mid-call, and `disconnectDestination` redirects can fight with the prompt. This skill captures the right wiring.

## The handler — both modern and legacy patterns

```ts
const preventBrowserCloseHandler = (event: BeforeUnloadEvent) => {
    // Modern (recommended) — calling preventDefault triggers the prompt
    event.preventDefault();
    // Legacy support for Chrome/Edge < 119
    event.returnValue = true;
};
```

Both lines are needed. The W3C spec says `preventDefault()` is enough; older Chrome/Edge required `returnValue` to be truthy. Including both is the no-regret default.

You **can't customize the message** — modern browsers ignore any string you set. The prompt is browser-controlled and locale-aware.

## The hook

```ts
import {useEffect} from 'react';
import {config} from '../config';
import {BrowserCloseConfirmation} from '../types';
import {useBrowserCloseConfirmationConfig} from './useBrowserCloseConfirmationConfig';

export const useBrowserCloseConfirmation = () => {
    const {shouldShowBrowserCloseConfirmation} = useBrowserCloseConfirmationConfig();

    // Initial wiring: register based on the current config
    useEffect(() => {
        if (shouldShowBrowserCloseConfirmation) {
            window.addEventListener('beforeunload', preventBrowserCloseHandler);
        }
        return () => {
            window.removeEventListener('beforeunload', preventBrowserCloseHandler);
        };
    }, [shouldShowBrowserCloseConfirmation]);

    // React to user toggling the preference mid-call
    useEffect(() =>
        config.subscribe('browserCloseConfirmation', browserClosePrevention => {
            if (browserClosePrevention === BrowserCloseConfirmation.Enabled) {
                window.addEventListener('beforeunload', preventBrowserCloseHandler);
            } else {
                window.removeEventListener('beforeunload', preventBrowserCloseHandler);
            }
        }),
    []);
};
```

Two effects:
1. **Mount-time wiring** — register the handler if config says so, clean up on unmount
2. **Live config subscription** — add/remove the handler when the user toggles "Confirm before leaving" in settings

The two-listener pattern is intentional. The mount effect is gated by the *derived* `shouldShowBrowserCloseConfirmation` value (which folds in the default + user override). The subscribe effect reacts to the *raw* config key. Together they handle:
- Page load with default-on → register
- Page load with default-off → don't register
- User toggles on → register
- User toggles off → unregister
- Unmount → always cleanup

## The config logic — `useBrowserCloseConfirmationConfig`

The decision tree:

```
"enforceBrowserCloseConfirmation" branding flag is on?
    └── Yes: always show, ignore user
    └── No:
        "browserCloseConfirmation" user setting is set?
            └── Enabled: show
            └── Disabled: don't show
            └── Unset (initial state):
                "enableBrowserCloseConfirmationByDefault" branding default?
                    └── true: show
                    └── false: don't show
```

The three-state user setting (`Enabled` / `Disabled` / `Unset`) lets the brand default carry forward until the user explicitly chooses. Once they toggle it, their preference sticks across sessions.

The `BrowserCloseConfirmation` enum:

```ts
export enum BrowserCloseConfirmation {
    Unset,    // 0 — user hasn't chosen
    Enabled,  // 1 — user wants confirmation
    Disabled, // 2 — user wants no confirmation
}
```

## When to call the hook

Webapp3 calls `useBrowserCloseConfirmation()` at the meeting page level — only inside an active call. Calling it on the home page would prompt users when they navigate to a meeting (annoying). Calling it on the post-meeting page would prompt them when they leave (also annoying).

```tsx
export const MeetingPage: React.FC = () => {
    useBrowserCloseConfirmation();  // active only while this page is mounted
    // ...
};
```

## Interaction with `disconnectDestination`

If the manifest sets `disconnectDestination: 'https://example.com/post-call'`, webapp3 navigates there programmatically when the call ends. Pexip's docs note:

> If users have browser close confirmation enabled (via either their user settings, or as a default setting), they may be shown a confirmation pop-up when redirected to the disconnect destination.

This is unavoidable — the browser doesn't distinguish between "user clicked X" and "JS called window.location.assign". To prevent the prompt during the redirect, **remove the listener immediately before navigating**:

```ts
// Before navigating away programmatically
window.removeEventListener('beforeunload', preventBrowserCloseHandler);
window.location.href = applicationConfig.disconnectDestination;
```

Webapp3's `navigateToPostMeeting` doesn't do this currently — it relies on the user clicking "Leave the site" in the prompt. If you want a smoother UX, add the unregister.

## See also

- `pexip-branding-manifest` — `enableBrowserCloseConfirmationByDefault` is a brand-level default
- `pexip-call-lifecycle` — `pagehide` (different from `beforeunload`) is what tells the server to free the slot

## Gotchas

- **`beforeunload` and `pagehide` are different.** `beforeunload` is "user is *about* to leave, can be cancelled." `pagehide` is "user *did* leave, can't be cancelled." Webapp3 uses `pagehide` to send the disconnect to the server — use `beforeunload` only for the prompt.
- **Don't try to customize the prompt message.** Returning a string from the handler used to set the message; modern browsers ignore it. The locale-translated default is what users see.
- **The `addEventListener` with no options** is what triggers the prompt. Adding `{passive: true}` would *prevent* it. Don't add options thinking it's safer.
- **Some browsers ignore `beforeunload` on tabs that haven't received user interaction.** A user who tabs away without ever clicking won't get the prompt. There's no workaround.
- **Mobile Safari ignores `beforeunload` entirely.** It will not prompt. This is by design — mobile UX. Don't fight it.
- **The two-effect pattern is critical.** If you collapse them into one effect that handles both initial wiring and config changes, you'll double-register on mount.
- **`config.subscribe` returns an unsubscribe function.** The `useEffect(() => config.subscribe(...), [])` pattern relies on this — the returned function is the cleanup.
- **Don't unregister on `onDisconnected`.** The user might rejoin the same call. Webapp3 only unregisters on full unmount or explicit user toggle.

## Reference source

- **Authoritative Pexip docs:**
  - Pexip client SDK overview: https://docs.pexip.com/developer/clientapi.htm
  - `@pexip/infinity` JS client API reference: https://docs.pexip.com/api_client/api_pexrtc.htm
- **Reference implementation (webapp3):**

- `src/hooks/useBrowserCloseConfirmation.tsx` — the hook (60 LOC)
- `src/hooks/useBrowserCloseConfirmationConfig.tsx` — the decision-tree resolver
- `src/types.ts` — `BrowserCloseConfirmation` enum
- `src/config.ts:127` — `defaultUserConfig.enableBrowserCloseConfirmationByDefault` default
