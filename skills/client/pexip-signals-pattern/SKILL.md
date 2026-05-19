---
name: pexip-signals-pattern
description: Use when designing how SDK events flow through a Pexip app, when deciding between `useState` and a signal hub, when the user mentions `@pexip/signal`, `createSignal`, signal hubs, behavior signals, batched signals, replay signals, or pub/sub for video-call events. Also use before adding new event-driven state to an Infinity-based app — get the architecture right first.
license: MIT
---

# Pexip signals pattern

Pexip's webapp3 doesn't store SDK state in React. It uses **`@pexip/signal`** — a typed pub/sub primitive — as the spine connecting `@pexip/infinity`, `@pexip/media`, and the UI. Service modules emit signals, components subscribe. This is why webapp3 stays responsive during reconnect, transfer, and noisy event streams.

If you're building on `@pexip/infinity` and reaching for `useState` to mirror SDK state, **stop and read this first**.

## Why signals, not React state

| Problem with React state for SDK data | Signal solution |
|---|---|
| SDK fires events faster than React renders → dropped updates | Signals dispatch synchronously; observers see every event |
| Many components need the same SDK data → prop drilling or context churn | Any component subscribes directly to the same signal |
| State diffs cause cascading re-renders during transfer/reconnect | Signals fire only on emit; subscribers decide what to re-render |
| Batched events (participant joins) flood React | `batched` signal variant collects in a buffer, fires once per scheduler tick |

Webapp3 has **10 signal hubs** organized by domain. The UI is a thin layer of `useEffect(() => signal.add(handler), [])` subscriptions.

## The four signal variants

```ts
import {createSignal} from '@pexip/signal';

// 1. Generic — fire-and-forget. Subscribe AFTER an emit and you miss it.
const onChatMessage = createSignal<ChatMessage>({name: 'meeting:chatMessage'});

// 2. Behavior — replays the latest value to every new subscriber. Use for "current state".
const networkStateSignal = createSignal<NetworkState>({
    name: 'meeting:networkState',
    variant: 'behavior',
});

// 3. Replay — buffer last N values, replay them to new subscribers.
const recentTranscripts = createSignal<Transcript>({
    name: 'meeting:transcripts',
    variant: 'replay',
    bufferSize: 10,
});

// 4. Batched — collect events in a buffer, fire as an array on a scheduler tick.
//    Webapp3 uses this for participant activity (joins/leaves can flood).
const participantActivitySignal = createSignal<ParticipantActivity>({
    name: 'meeting:participantActivity',
    variant: 'batched',
    schedule: task => setTimeout(task, 100),
    bufferSize: 50,
    emitImmediatelyWhenFull: true,
});
```

## Quick start: a signal hub for your app

Group signals by domain into a single file. Webapp3 has 10 hubs (`InfinityClient.signals`, `Call.signals`, `Media.signals`, `Meeting.signals`, `MeetingFlow.signals`, `InMeeting.signals`, `Participant.signals`, `BreakoutRooms.signals`, `ImageStore.signals`, `StepByStep.signals`).

```ts
// src/signals/Meeting.signals.ts
import {createSignal} from '@pexip/signal';
import type {TransferDetails} from '@pexip/infinity';
import type {ChatMessage} from '@pexip/media-components';

export const stepSignal = createSignal<MeetingFlow>({name: 'meeting:step'});
export const remoteStreamSignal = createSignal<MediaStream | undefined>({
    name: 'meeting:remoteStream',
});
export const pinRequiredSignal = createSignal<boolean>({
    name: 'meeting:pinRequired',
});
export const transferSignal = createSignal<TransferDetails>({
    name: 'meeting:transfer',
});
export const chatMessageSignal = createSignal<ChatMessage>({
    name: 'meeting:chatMessage',
});
```

The infinity SDK gives you two pre-built hubs:

```ts
// src/signals/InfinityClient.signals.ts
import {createInfinityClientSignals} from '@pexip/infinity';

export const infinityClientSignals = createInfinityClientSignals([], {
    batchScheduleTimeoutMS: 100,
    batchBufferSize: 50,
});

// src/signals/Call.signals.ts
import {createCallSignals} from '@pexip/infinity';

export const callSignals = createCallSignals([]);
```

Then `createInfinityClient(infinityClientSignals, callSignals)` wires them into the SDK.

## Subscribing in components

```tsx
import {useEffect, useState} from 'react';
import {stepSignal} from '../signals/Meeting.signals';
import {MeetingFlow} from '../types';

export function useMeetingStep() {
    const [step, setStep] = useState<MeetingFlow>(MeetingFlow.Loading);

    useEffect(() => {
        // .add() returns a detach function — return it from useEffect for cleanup
        return stepSignal.add(setStep);
    }, []);

    return step;
}
```

For "current state" data (network state, mute state, current participants), use `variant: 'behavior'` — new subscribers get the latest value immediately, no race condition on mount.

## The `createSignalHandler` pattern (logging + error containment)

Webapp3 wraps every signal subscription with a logger and error trap so a buggy handler can't crash the call. From `services/InfinityClient.service.ts`:

```ts
const createSignalHandler = <T extends Signal<unknown>>(
    signal: T,
    handle: (arg: ExtractSignalType<T>) => void | Promise<void>,
    name = 'event',
) => {
    return async (arg: ExtractSignalType<T>) => {
        try {
            await handle(arg);
            logger.info(
                {context: 'Meeting Signals', signal: signal.name},
                `Handled ${signal.name ?? name}`,
            );
        } catch (error) {
            logger.error({error}, `Failed to handle ${signal.name ?? name}`);
        }
    };
};

// Usage
const handleOnPinRequired = createSignalHandler(
    infinityClientSignals.onPinRequired,
    ({hasHostPin, hasGuestPin}) => {
        if (hasHostPin && hasGuestPin) {
            updateStep(MeetingFlow.EnterPin);
        } else {
            updateStep(MeetingFlow.AreYouHost);
        }
    },
);
detachSignals.push(infinityClientSignals.onPinRequired.add(handleOnPinRequired));
```

This pattern is **mandatory** if your handler does any async work — an unhandled rejection in a signal handler will silently fail and you'll spend hours debugging.

## When to add a new signal hub vs reuse an existing one

| Situation | Decision |
|---|---|
| New event type fits an existing domain (e.g. another chat-related event) | Add to existing hub (`Meeting.signals.ts`) |
| New event spans domains (e.g. "user closed effects modal" — affects media + UI) | New hub |
| Event needs different batching/replay than rest of hub | New hub |
| One-off internal coordination between two modules | Local `createSignal` inside the module, not exported |

## Gotchas

- **`add()` returns the detach function.** Always return it from `useEffect` or call it in cleanup, or you'll leak observers and `DuplicatedObserver` errors will throw on remount.
- **Signal handlers run synchronously.** A slow handler blocks all other subscribers. Defer with `queueMicrotask` or `setTimeout` if you do heavy work.
- **`addOnce` throws if you add the same observer twice.** Don't share observer functions between multiple `addOnce` calls.
- **Don't `emit()` inside an observer of the same signal** — you'll hit `RangeError: Possible recursive call`. Signals catch this and rethrow.
- **Behavior signals replay on subscribe.** If you don't want the replay (e.g. you only care about *new* events), use `generic`.
- **Batched signals require a scheduler.** No default — `setTimeout(task, 100)` is webapp3's choice for participant events.

## See also

- `pexip-call-lifecycle` — how the InfinityClient signal hubs are wired into the meeting state machine
- `pexip-media-pipeline` — how Media signals coordinate track lifecycle with the SDK
- `pexip-reconnect` — how `NetworkState` (a behavior signal in `@pexip/media-components`) gates other subscribers
- `pexip-participants` — uses the **batched** signal variant for `onParticipantJoined`/`Updated`/`Left`
- `ARCHITECTURE.md` (top-level) — table of all 10 signal hubs and which skills subscribe to each

## Reference source

webapp3 v40-12.0:
- `src/signals/*.ts` — the 10 hub files
- `src/services/InfinityClient.service.ts:306-324` — `createSignalHandler`
- `@pexip/signal` — the `createSignal` implementation
