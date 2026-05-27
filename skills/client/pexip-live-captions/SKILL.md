---
name: pexip-live-captions
description: Use when implementing Pexip live captions (real-time transcription overlay) — enabling/disabling captions, rendering interim vs final transcripts, auto-clear timer, breakout-aware reset. Triggers on `onLiveCaptions`, `enableLiveCaptions`, `liveCaptionsEnabled`, `liveCaptionsAvailability`, `useLiveCaptions`, `useLiveCaptionsAvailable`, transcripts, isFinal, speakers, captioning, transcription.
license: MIT
---

# Pexip live captions

Pexip's MCU produces real-time transcripts via the conferencing node's speech engine. The signaling channel emits `onLiveCaptions` events with `{data, isFinal, speakers}`. Webapp3's `useLiveCaptions` hook turns this into a flickerless caption overlay with auto-clear.

The trick is that captions arrive as a **stream of refinements**: the engine sends interim text ("hello there"), then a longer interim ("hello there how are"), then finally `isFinal: true` ("hello there, how are you"). Render naïvely and the caption flashes between revisions. Webapp3's hook handles this.

## Quick start

```tsx
import {useLiveCaptions, useLiveCaptionsAvailable} from '../hooks/useLiveCaptions';

export const CaptionsOverlay: React.FC = () => {
    const isAvailable = useLiveCaptionsAvailable();
    const {data, isEnabled, toggleCaptions} = useLiveCaptions();

    if (!isAvailable) return null;

    return (
        <>
            <button onClick={toggleCaptions}>
                {isEnabled ? 'Hide captions' : 'Show captions'}
            </button>
            {isEnabled && data && <div className="captions-overlay">{data}</div>}
        </>
    );
};
```

`useLiveCaptionsAvailable()` checks both the conference's capability *and* the brand's `showLiveCaptionsFeature` flag. Use it to gate the toggle button.

## The hook implementation

```ts
const CLEAR_CAPTIONS_AFTER = 5000;  // ms — clear if no new caption within window

export const useLiveCaptions = () => {
    const meeting = useMeetingContext();
    const liveCaptionsEnabled = useLiveCaptionsEnabled(meeting.getLiveCaptionsEnabled);
    const [captions, setCaptions] = useState('');
    const previousCaptions = useRef('');
    const timerRef = useRef<number>(undefined);

    const toggleCaptions = useCallback(() => {
        const enable = !liveCaptionsEnabled;
        meeting.setLiveCaptionsEnabled(enable);  // optimistic UI
        meeting.enableLiveCaptions({enable}, undefined, () => {
            // SDK call failed — roll back UI
            meeting.setLiveCaptionsEnabled(false);
        });
        if (!enable) setCaptions('');
    }, [liveCaptionsEnabled, meeting]);

    useEffect(() => {
        if (!liveCaptionsEnabled) return;

        const renderCaptions = (next: {data: string; isFinal: boolean}) => {
            if (next.isFinal) {
                setCaptions(next.data);
                previousCaptions.current = '';
            } else if (next.data.length > previousCaptions.current.length) {
                // Interim refinement — only update if it grew (avoid flicker on revisions)
                setCaptions(next.data);
                previousCaptions.current = next.data;
            }

            // Reset auto-clear timer on every new caption
            clearTimeout(timerRef.current);
            timerRef.current = window.setTimeout(() => {
                setCaptions('');
            }, CLEAR_CAPTIONS_AFTER);
        };

        const detach = infinityClientSignals.onLiveCaptions.add(renderCaptions);
        return () => {
            clearTimeout(timerRef.current);
            detach();
        };
    }, [liveCaptionsEnabled]);

    // Breakout-room reset
    useEffect(() => {
        if (!meeting.getConferenceFeatureFlags()?.isDirectMedia &&
            meeting.getLiveCaptionsAvailability()) {
            return infinityClientSignals.onCallDisconnected.add(() => {
                meeting.setLiveCaptionsEnabled(false);
                setCaptions('');
                previousCaptions.current = '';
                clearTimeout(timerRef.current);
                meeting.enableLiveCaptions({enable: false}, undefined, e => {
                    logger.error(e, 'Failed to turn off live captions');
                });
            });
        }
    }, [meeting]);

    return {data: captions, isEnabled: liveCaptionsEnabled, toggleCaptions};
};
```

Three effects:
1. **Toggle action** — optimistic UI update + SDK call + rollback on failure
2. **Caption stream** — only subscribed when enabled; handles interim/final + auto-clear
3. **Breakout reset** — when host moves between rooms, reset captions explicitly

## The flicker-free rendering rule

```ts
if (next.isFinal) {
    setCaptions(next.data);
    previousCaptions.current = '';  // reset for next utterance
} else if (next.data.length > previousCaptions.current.length) {
    setCaptions(next.data);
    previousCaptions.current = next.data;
}
// else: ignore — interim got *shorter*, which means engine revised
```

Three cases:
- **Final** → render and reset (next utterance starts fresh)
- **Interim, longer than previous** → render (engine extended the partial)
- **Interim, shorter or same** → **drop** (engine revised; don't show the shorter version, it'll flicker)

Without the length check, you see "hello there how are" → "hello there" → "hello there, how are you" flashing in the overlay.

## The 5-second auto-clear

After `CLEAR_CAPTIONS_AFTER` (5000ms) of silence, the caption clears. Without this, the last spoken phrase sits on screen forever during long pauses.

The timer resets on every new caption, so during continuous speech the caption never disappears. It only fires after the speaker actually pauses.

## Optimistic toggle with rollback

```ts
const toggleCaptions = useCallback(() => {
    const enable = !liveCaptionsEnabled;
    meeting.setLiveCaptionsEnabled(enable);  // optimistic — UI updates immediately
    meeting.enableLiveCaptions({enable}, undefined, () => {
        meeting.setLiveCaptionsEnabled(false);  // SDK failed — roll back
    });
    if (!enable) setCaptions('');
}, [liveCaptionsEnabled, meeting]);
```

Two-step pattern: flip the local state immediately (so the button reflects the click), then call the SDK with a failure handler that resets local state if the server refused. The webapp3 source comment notes:

> FIXME: Instead of update the state immediately, there should be a intermediate state when calling the api

— so this isn't perfect. A "loading" state would be better UX, but for v1 the optimistic approach is fine.

## Breakout reset

When the host is moved between breakout rooms, captions need to reset because the new conference may not have captions enabled or may have a different language model. The third effect:

```ts
return infinityClientSignals.onCallDisconnected.add(() => {
    meeting.setLiveCaptionsEnabled(false);
    setCaptions('');
    previousCaptions.current = '';
    clearTimeout(timerRef.current);
    meeting.enableLiveCaptions({enable: false}, undefined, e => {
        logger.error(e, 'Failed to turn off live captions');
    });
});
```

The guard `!isDirectMedia && getLiveCaptionsAvailability()` skips this if either:
- Conference is direct-media (no MCU = no captions to reset)
- Captions weren't available anyway

This effect doesn't fire on the *initial* disconnect — it's specific to the transitions between rooms during breakout transfers.

## `useLiveCaptionsAvailable`

A reactive boolean: are captions both *technically* available (conference status) and *enabled in branding* (manifest flag)?

```ts
export const useLiveCaptionsAvailable = () => {
    const meeting = useMeetingContext();
    const isLiveCaptionsAvailable = useSyncExternalStore(
        infinityClientSignals.onConferenceStatus.add,
        meeting.getLiveCaptionsAvailability,
    );
    return isLiveCaptionsAvailable && applicationConfig.showLiveCaptionsFeature;
};
```

`useSyncExternalStore` is the React 18+ way to subscribe an external value into the render. The hook returns the current snapshot, re-renders when the signal fires.

## What about the transcripts list (history view)?

`useLiveCaptions` shows the *current* caption only. For a scrolling transcript history, look at `Meeting.signals.transcriptsSignal` and the `handleOnLiveCaptions` handler in `InfinityClient.service.ts:1221-1251` — that one builds a chronological list with the same interim/final logic but appends instead of replacing.

```ts
// From InfinityClient.service.ts
const handleOnLiveCaptions = createSignalHandler(
    infinityClientSignals.onLiveCaptions,
    ({data: text, isFinal, speakers}) => {
        const transcript = {text, isFinal, timestamp: Date.now(), speakers};
        const last = transcripts[transcripts.length - 1];
        if (last && !last.isFinal) {
            // Replace the in-progress transcript at the tail
            if (transcript.isFinal || transcript.text.length >= last.text.length) {
                transcripts[transcripts.length - 1] = transcript;
                transcripts = [...transcripts];
            }
        } else {
            transcripts = [...transcripts, transcript];
        }
        transcriptsSignal.emit();
    },
);
```

Use this for a transcript panel; use `useLiveCaptions` for the live overlay.

## See also

- `call-lifecycle/reference.md` — `handleOnLiveCaptions` builds the transcripts list
- `pexip-signals-pattern` — `infinityClientSignals.onLiveCaptions` is the source signal
- `pexip-branding-manifest` — `applicationConfig.showLiveCaptionsFeature` toggles the whole feature off

## Gotchas

- **`isFinal: false` events fire faster than React renders.** The length-comparison filter catches *most* flicker, but for very chatty engines you may still want a 100ms throttle.
- **The `previousCaptions` ref must reset on `isFinal`.** Otherwise the next utterance's interim text gets compared against the previous final length and ignored.
- **`speakers` array is in the SDK payload but not used by webapp3's overlay.** If you want speaker attribution, pull from `next.speakers` and look up display names via the participants util.
- **Languages are server-configured.** You can't change the caption language client-side — the conferencing node decides based on the conference's profile.
- **Direct-media conferences don't have captions.** The MCU isn't in the path. Hide the toggle entirely for direct-media calls.
- **`onConferenceStatus` is the right signal for availability changes.** Don't poll `getLiveCaptionsAvailability()` in an interval — it's reactive.
- **The `useSyncExternalStore` subscribe function** must have a stable identity. Webapp3 passes `infinityClientSignals.onConferenceStatus.add` directly, which works because the signal hub is a stable singleton.
- **Hide the overlay if `data === ''`.** The hook leaves it as the empty string after the auto-clear; rendering an empty `<div>` may cause unwanted layout space.

## Reference source

- **Authoritative Pexip docs:**
  - Pexip client SDK overview: https://docs.pexip.com/developer/clientapi.htm
  - `@pexip/infinity` JS client API reference: https://docs.pexip.com/api_client/api_pexrtc.htm
- **Reference implementation (webapp3):**

- `src/hooks/useLiveCaptions.ts` — hook implementation (125 LOC)
- `src/services/InfinityClient.service.ts:1221-1251` — server-side transcript builder
- `src/services/InfinityClient.service.ts:890-901` — `enableLiveCaptions` SDK wrapper
- `src/applicationConfig.ts:55` — `showLiveCaptionsFeature` default
