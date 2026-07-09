---
name: pexip-reconnect
description: Use when handling Pexip reconnect UX, wiring `useNetworkState`, suppressing toast spam during a reconnect window, surfacing the `<NetworkAlert>` banner, or coordinating `onReconnecting` / `onReconnected` / `onFailedRequest` events. Triggers on `NetworkState`, `Reconnecting`, `Reconnected`, `useNetworkState`, `useOnFailedInfinityRequest`, `NetworkAlert`, `onFailedRequest`. Also use when the user reports "we get spammed with 'failed to send' toasts every time the network blips."
license: MIT
---

# Pexip reconnect coordination

When a Pexip call's signaling (event source) or media (peer connection) hiccups, you get a flood of events. Without coordination, the user sees:
- A "Failed to send" toast for every queued operation that bounced

## Barebones reconnect banner

Renders a banner during reconnect and suppresses error toasts for 8 seconds.

```tsx
import { useState, useEffect, useRef } from 'react';
import { NetworkState, useNetworkState } from '@pexip/infinity';
import type { InfinityClientSignals } from '@pexip/infinity';

export function ReconnectBanner({ infinityClientSignals }: { infinityClientSignals: InfinityClientSignals }) {
    const networkState   = useNetworkState({ infinityClientSignals });
    const suppressUntil  = useRef(0);
    const [reconnecting, setReconnecting] = useState(false);

    useEffect(() => {
        infinityClientSignals.onReconnecting.add(() => {
            suppressUntil.current = Date.now() + 8000; // suppress toasts for 8s
            setReconnecting(true);
        });
        infinityClientSignals.onReconnected.add(() => setReconnecting(false));
    }, [infinityClientSignals]);

    // Use suppressUntil.current in your toast handler:
    // if (Date.now() < suppressUntil.current) return; // skip toast

    if (!reconnecting) return null;
    return (
        <div style={{ background: '#f59e0b', color: '#000', padding: '0.5rem', textAlign: 'center', fontWeight: 600 }}>
            Reconnecting…
        </div>
    );
}
- A "Failed to send" toast again, three more times, as the SDK retries
- A "Reconnecting…" banner appearing and disappearing
- Occasionally, a real "Disconnected" error buried under the noise

Webapp3 has a tight, three-piece coordination that makes this usable: a **state hook** that aggregates SDK reconnect events, a **toast hook** that suppresses spam *while reconnecting*, and a **banner component** that surfaces the state to the user. This skill captures the wiring.

## The three pieces

### 1. `useNetworkState` — the state machine

From `@pexip/media-components`. Subscribes to `callSignals.onReconnecting` and `callSignals.onReconnected` and produces a `NetworkState` value.

```ts
import {useNetworkState} from '@pexip/media-components';
import {callSignals} from '../signals/Call.signals';

const networkState = useNetworkState(
    callSignals.onReconnecting,
    callSignals.onReconnected,
);
```

`NetworkState` is an enum with at minimum:
- `Connected` — happy path
- `Reconnecting` — peer connection / event stream is recovering
- (other states the SDK may add — treat unknown values as "connected" with logging)

This hook is the source of truth. Every reconnect-related UI element should derive from it.

### 2. `useOnFailedInfinityRequest` — the toast suppressor

A 20-line hook that **only subscribes to `onFailedRequest` when not reconnecting**. The full implementation (worth reading in full):

```ts
import {useEffect} from 'react';
import {notificationToastSignal} from '@pexip/components';
import {NetworkState} from '@pexip/media-components';
import {infinityClientSignals} from '../signals/InfinityClient.signals';

export const useOnFailedInfinityRequest = (networkState: NetworkState) => {
    useEffect(() => {
        if (networkState !== NetworkState.Reconnecting) {
            return infinityClientSignals.onFailedRequest.add(request => {
                notificationToastSignal.emit([
                    {
                        message: `Failed to send '${request}'. Please check your network.`,
                        timeout: 5000,
                        isDanger: true,
                        isInterrupt: true,
                    },
                ]);
            });
        }
    }, [networkState]);
};
```

The mechanism is subtle: the `useEffect` returns the detach function from `signal.add()`. When `networkState` flips to `Reconnecting`, the effect re-runs, the previous detach fires, and **no new subscription is set up**. The detach also returns from the empty branch, so cleanup works.

When `Reconnecting` flips back to `Connected`, the effect runs again, re-subscribes, and toasts resume firing for *new* failures only. The flood of mid-reconnect failures was already suppressed.

### 3. `<NetworkAlert>` — the banner

From `@pexip/media-components`. Pass it the `networkState`:

```tsx
import {NetworkAlert} from '@pexip/media-components';

<NetworkAlert networkState={networkState} />
```

This renders nothing when `Connected`, a "Reconnecting…" banner when `Reconnecting`, and resolves itself when `Reconnected` fires.

## Wiring it all together

Webapp3 wires these in two places: `pages/MeetingManager.page.tsx` (control-only meetings) and `pages/InMeeting.page.tsx` (full media meetings). The pattern is identical:

```tsx
export const InMeeting: React.FC<{...}> = () => {
    const networkState = useNetworkState(
        callSignals.onReconnecting,
        callSignals.onReconnected,
    );

    // Suppresses toast spam during reconnects
    useOnFailedInfinityRequest(networkState);

    return (
        <>
            <NetworkAlert networkState={networkState} />
            <MeetingRoom networkState={networkState} /* ... */ />
        </>
    );
};
```

The `networkState` is **also passed down to media components** (`MeetingRoom`, `InMeetingLocalStream`) so they can render their own UI hints (e.g. dimmed video tile during reconnect).

## How this interacts with `onPeerDisconnect`

This skill is about the *UI layer*. The actual recovery — calling `restartCall` to revive the peer connection — is handled at the service layer (see `pexip-call-lifecycle` skill). The two layers cooperate:

```
PEER CONNECTION DEAD
        ↓
infinityClientSignals.onPeerDisconnect.emit
        ↓
service: callStage = Restarting; await restartCall(...)
        ↓                                         ↓
        ↓                      callSignals.onReconnecting.emit
        ↓                                         ↓
        ↓                      hook: networkState = Reconnecting
        ↓                                         ↓
        ↓                      hook: <NetworkAlert> shown
        ↓                      hook: toast subscriber detached
        ↓
restartCall succeeds → callSignals.onCallConnected.emit
                       callSignals.onReconnected.emit
                                ↓
                  hook: networkState = Connected
                                ↓
                  hook: <NetworkAlert> dismissed
                  hook: toast subscriber re-attached
```

The service handles the *what* (restart the call); the UI handles the *how it looks while it's happening* (suppress noise, show banner).

## What about WebSocket / EventSource reconnects?

The `@pexip/infinity` SDK emits `onReconnecting` / `onReconnected` on **both** event-stream reconnects *and* peer-connection ICE restarts. The UI doesn't care which — `NetworkState.Reconnecting` covers both. If you want to differentiate, you'd subscribe to `infinityClientSignals.onPeerDisconnect` and `infinityClientSignals.onConnected` separately, but webapp3 doesn't bother.

## Customizing the toast

The toast shape is `{message, timeout, isDanger, isInterrupt}`:
- `timeout: 5000` — disappears after 5s
- `isDanger: true` — red styling
- `isInterrupt: true` — bumps any currently-shown toast

If you want a quieter UX, drop `isInterrupt` so the toast queues instead of replacing. If you want to surface only the *first* failure per outage, add a debounce around the subscription.

## The `request` argument

`onFailedRequest` fires with the request name (e.g. `'mute'`, `'sendMessage'`, `'kick'`). Webapp3 includes it verbatim in the message. For non-English locales, you may want a lookup table — but most users just see "Failed to send 'mute'" and understand: try again.

## See also

- `pexip-call-lifecycle` — `onPeerDisconnect` → `restartCall` is the recovery mechanism this skill renders UI for
- `pexip-signals-pattern` — `callSignals` is a `createCallSignals` hub from `@pexip/infinity`
- `pexip-media-pipeline` — bandwidth changes during reconnect can be triggered by quality monitoring (out of scope here, but related)

## Gotchas

- **Don't subscribe to `onFailedRequest` outside this hook.** If you have other subscribers, they won't be auto-suppressed during reconnects, and you'll get partial spam.
- **Don't show your own "Reconnecting" UI alongside `<NetworkAlert>`.** Pick one. Webapp3 uses `<NetworkAlert>` exclusively at the page level and only adds smaller hints (dimmed video) at the component level.
- **`useNetworkState` returns a fresh value on every reconnect cycle.** Don't memoize it improperly. Subscribers running in `useEffect([networkState])` re-run every transition by design.
- **Initial state is `Connected`.** If you mount before the call connects, the hook reports `Connected` even though there's no call yet. That's fine — `onReconnecting` only fires after a successful connect, so you won't get a false "Reconnecting" banner.
- **Server-side disconnects are not reconnects.** If `onDisconnected` fires (host kicked, conference ended), you should *not* show a reconnect banner. Disconnect handling is in `call-lifecycle`.
- **The hook must run inside a Provider** that gives it access to `callSignals` (typically the InfinityContext provider). Calling it at the route level is fine; calling it in a top-level App component before the provider mounts is not.

## Reference source

- **Authoritative Pexip docs:**
  - Pexip client SDK overview: https://docs.pexip.com/developer/clientapi.htm
  - `@pexip/infinity` JS client API reference: https://docs.pexip.com/api_client/api_pexrtc.htm
- **Reference implementation (webapp3):**

- `src/hooks/useOnFailedInfinityRequest.ts` — the toast suppressor (20 LOC)
- `src/pages/MeetingManager.page.tsx:41-87` — the wiring for control-only meetings
- `src/pages/InMeeting.page.tsx:64-109` — the wiring for full meetings
- `pexip-sdks/media-components/src/hooks/useNetworkState.ts` — the state machine source
- `pexip-sdks/media-components/src/components/NetworkAlert/` — the banner component
