# Self-healing media

A subtle bug webapp3 fixed in production: after the video processor restarts (e.g. after the user toggles blur on/off, or the GPU context resets), the resulting track is sometimes stuck in a `muted: true` state and never recovers. The browser doesn't fire any error — the track just silently produces no frames.

Webapp3's fix: subscribe to the segmenter's `ProcessorRestarted` signal, wait briefly, and if the track is still muted, re-request `getUserMedia` from scratch.

## The pattern

```ts
import {TIME_WAIT_FOR_MUTED_TRACK_RECOVERY_MS} from '../constants';
// webapp3 uses 1000ms

selfieSegmenter.subscribe('ProcessorRestarted', () => {
    const startTime = performance.now();

    const handleTrackMuted = () => {
        mediaSignals.onMediaTrackResumed.remove(handleTrackUnmuted);
        const endTime = performance.now();
        const [track] = mediaService.media?.stream?.getVideoTracks() ?? [];
        if (track?.muted) {
            // Track is still stuck muted — recover by re-requesting media
            logger.debug(
                {track, muted: track.muted, startTime, endTime},
                'Track muted after ProcessorRestarted, re-requesting media',
            );
            mediaService.getUserMedia(getDefaultConstraints());
        }
    };

    const handleTrackUnmuted = () => {
        mediaSignals.onMediaTrackResumed.remove(handleTrackUnmuted);
        clearTimeout(mutedTrackTimer);
    };

    const mutedTrackTimer = setTimeout(
        handleTrackMuted,
        TIME_WAIT_FOR_MUTED_TRACK_RECOVERY_MS,
    );

    mediaSignals.onMediaTrackResumed.add(handleTrackUnmuted);
});
```

## Why the wait

The race: `ProcessorRestarted` fires, but the track may take up to ~1s to re-emit frames. If the track recovers in that window, `onMediaTrackResumed` fires and we cancel the timer. If not, we assume it's stuck and re-request.

Without the wait, you'd hammer `getUserMedia` on every legitimate processor restart, causing flicker.

Without the watchdog, the user sees a black video tile forever.

## When does `ProcessorRestarted` fire?

The video processor restarts the segmenter on:
- Effect mode change (`videoSegmentation` from `'none'` → `'blur'`)
- Background image change (URL or bitmap)
- Processing dimensions change
- Delegate change (GPU ↔ CPU)
- Track replacement (new device selected)

So this safety net runs on basically every effects-modal interaction. It must be cheap on the happy path — and it is: just a `setTimeout` that gets cancelled.

## Generalizing

The pattern is reusable for any processor that has its own restart event. The shape:

```
[restart event] → start watchdog timer
                ↓                          ↓
[track recovers] → cancel timer       [timer fires]
                                          ↓
                                     [re-request media]
```

If you add a custom processor (e.g. green-screen, custom segmentation model), wire its restart to the same pattern.

## Gotchas

- **Don't make the timeout too short.** 1s is webapp3's value. Below ~500ms, you get false positives.
- **Don't make it too long.** Above ~3s, the user notices the black tile.
- **The cleanup branch** (`handleTrackUnmuted`) is critical — without it, you leak observers and the watchdog re-fires on every subsequent resume event.
- **`getUserMedia` on recovery may itself fail.** If permissions changed mid-call, you'll get a `NotAllowedError`. Surface this through `mediaSignals.onStatusChanged` rather than swallowing.
- **Don't apply this to audio.** Audio tracks don't have the same `muted` behavior — they have `enabled` instead, and audio processors recover differently.

## Reference source

- `src/services/Media.service.ts:131-155` — the full self-healing block
- `src/constants.ts` — `TIME_WAIT_FOR_MUTED_TRACK_RECOVERY_MS`
