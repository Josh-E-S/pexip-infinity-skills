---
name: pexip-stats-monitoring
description: Use when surfacing call quality, monitoring WebRTC stats, building "your connection is poor" UI, logging quality changes, or wiring `@pexip/peer-connection-stats`. Triggers on `onRtcStats`, `onCallQuality`, `qualityLimitationReason`, `fpsVolatility`, `Quality.GOOD/OK/BAD/TERRIBLE`, `NormalizedRTCStats`, `StatsCollector`, `framerateMean`, `roundTripTime`, packets lost.
license: MIT
---

# Pexip stats monitoring

`@pexip/peer-connection-stats` collects WebRTC stats periodically, normalizes the cross-browser mess (`framesPerSecond` vs `framerateMean`, etc.), and emits three signals: raw stats, derived call quality, and quality history. Webapp3 uses these to log only when something *meaningfully* changes — most apps don't need to render anything from this, but if you do, this skill captures the patterns.

## What stats look like

The SDK normalizes WebRTC stats into typed shapes:

```ts
type NormalizedRTCStats =
    | InboundAudioMetrics
    | InboundVideoMetrics
    | OutboundAudioMetrics
    | OutboundVideoMetrics;

interface VideoMetrics extends Metrics {
    framesPerSecond?: number;
    resolution?: string;
    resolutionHeight?: number;
    resolutionWidth?: number;
    fpsVolatility?: number;  // <4% good, <8% reasonable
}

interface OutboundVideoMetrics extends VideoMetrics {
    qualityLimitationReason?: 'cpu' | 'bandwidth' | 'other' | 'none';
    qualityLimitationDurations?: {[k]?: number};
    averagePacketSendDelay?: number;
    averageEncodeTime?: number;
}

enum Quality {
    GOOD = 0,
    OK = 1,
    BAD = 2,
    TERRIBLE = 3,
}
```

The fields you'll actually look at:
- **`qualityLimitationReason`** — why the encoder is throttling (the most actionable single signal)
- **`fpsVolatility`** — frame rate stability; high values mean stuttering
- **`framesPerSecond`** + **`resolution`** — what's being sent/received right now
- **`Quality`** — derived 0–3 score the SDK computes from packet loss + jitter + RTT

## Wiring

```ts
import {createCallSignals} from '@pexip/infinity';

const callSignals = createCallSignals([
    'onRtcStats',
    'onCallQuality',
    'onCallQualityStats',
]);

// Then pass callSignals to createInfinityClient — the SDK wires its internal
// stats collector to emit on these signals.
const infinityClient = createInfinityClient(infinityClientSignals, callSignals);

// Subscribe
callSignals.onRtcStats.add(stats => {
    // stats is a NormalizedRTCStats; dispatch by type/kind
});
callSignals.onCallQuality.add(quality => {
    // quality is Quality (0–3); use for "poor connection" indicator
});
callSignals.onCallQualityStats.add(history => {
    // packet-loss + jitter array; useful for graphs
});
```

## Webapp3's "log only on change" filter

Webapp3 doesn't render anything from these signals. It just **logs to Sentry on quality transitions**, so if a user reports "my call was choppy at 4:32", you can correlate. The interesting bit is the change-detection:

```ts
const hasQualityStatsChanged = (last: Stats | undefined, current: Stats) => {
    if (!last) return true;

    if (
        last?.outbound?.video?.qualityLimitationReason !==
        current?.outbound?.video?.qualityLimitationReason
    ) {
        return true;
    }

    const lastHighFpsVolatility = Number(last?.outbound?.video?.fpsVolatility) > 10;
    const highFpsVolatility = Number(current?.outbound?.video?.fpsVolatility) > 10;
    if (lastHighFpsVolatility !== highFpsVolatility) {
        return true;
    }

    return false;
};

const logStats = (stats: Stats) => {
    logger.info({stats}, 'Quality stats changed');
};

const handleRtcStats = (stats: Stats) => {
    const lastStats = window.pexDebug?.stats as Stats;
    if (hasQualityStatsChanged(lastStats, stats)) {
        logStats(stats);
    }
    window.pexDebug = {...window.pexDebug, stats};
};
```

Two transitions logged:
1. `qualityLimitationReason` flipped (e.g. CPU → none = bandwidth recovered)
2. `fpsVolatility` crossed the 10% threshold (stable ↔ stuttering)

Both are *transitions*, not states — webapp3 emits one log line per change, not per stats tick. With ~1Hz tick rate, this keeps the log lean while still capturing anything that mattered.

`window.pexDebug` is webapp3's debugging convention — every tick, it stashes the latest stats on the global. Open DevTools, type `pexDebug.stats`, see what the encoder is doing right now.

## Building a "poor connection" indicator

If you want UI rather than logs, subscribe to `onCallQuality` and gate UI on the level:

```tsx
import {Quality} from '@pexip/peer-connection-stats';

export function useCallQuality() {
    const [quality, setQuality] = useState(Quality.GOOD);
    useEffect(() => callSignals.onCallQuality.add(setQuality), []);
    return quality;
}

// In a component
const quality = useCallQuality();
if (quality >= Quality.BAD) {
    return <Banner severity="warning">Your connection is unstable</Banner>;
}
```

The SDK debounces `onCallQuality` internally — it doesn't fire on every stats tick, only on level changes. Don't add your own debouncing.

## Sub-stat filtering by track

`onRtcStats` fires for *every* stat type. If you only want outbound video:

```ts
callSignals.onRtcStats.add(stats => {
    if (stats.type === 'outbound-rtp' && stats.kind === 'video') {
        // OutboundVideoMetrics — has qualityLimitationReason, fpsVolatility, etc.
    }
});
```

Type narrowing works because `NormalizedRTCStats` is a discriminated union over `type` + `kind`.

## When to render a stats panel

Most apps don't. Reasons to skip:
- Most users can't act on the info
- It's CPU-noise during the call
- Pexip's "poor connection" banner via `onCallQuality` is enough

Reasons to add one:
- You're building a debug/admin tool
- You're a developer testing your own integration
- You're surfacing for IT support ("show this to your help desk")

If you do build one, render from `onRtcStats` — `onCallQuality` is too coarse.

## Resolution tracking

`outbound.video.frameWidth/frameHeight` tells you what the encoder is *currently* sending — usually lower than the camera capture resolution under bandwidth/CPU pressure. Watching this is how you know the encoder is downscaling:

```ts
callSignals.onRtcStats.add(stats => {
    if (stats.type === 'outbound-rtp' && stats.kind === 'video') {
        const captured = mediaService.media?.stream?.getVideoTracks()[0]?.getSettings();
        if (captured && stats.resolutionWidth) {
            const downscaleRatio = stats.resolutionWidth / (captured.width ?? 1);
            if (downscaleRatio < 0.5) {
                // Encoder dropped to <50% of camera resolution — heavy throttling
            }
        }
    }
});
```

## Packet loss & jitter via `onCallQualityStats`

The signal payload is a tuple stream: `[packetLoss, jitter][]` for audio, `[packetLoss][]` for video. Useful for sparkline graphs:

```ts
callSignals.onCallQualityStats.add(history => {
    // history is a sliding window — render last N samples
    setSparklineData(history.slice(-30));
});
```

## See also

- `call-lifecycle/reference.md` — the `handleRtcStats` event handler in context
- `pexip-signals-pattern` — `callSignals` is a `createCallSignals` hub
- `pexip-media-pipeline` — bandwidth changes interact with these stats (`config.subscribe('bandwidth', …)`)
- `pexip-reconnect` — quality-driven adaptive bandwidth is *not* part of webapp3; the SDK handles ICE/quality internally

## Gotchas

- **Don't poll `peerConnection.getStats()` yourself.** The SDK already does, with the right cadence and filtering. Subscribe to `onRtcStats`.
- **`Quality` is a derived score, not a direct stat.** Don't try to recompute it locally — the SDK knows the thresholds Pexip's tested.
- **Firefox vs Chrome stat names differ.** The SDK normalizes (`framerateMean` vs `framesPerSecond` → both reported as `framesPerSecond` in `NormalizedRTCStats`). Don't read raw `RTCStats` — use the normalized type.
- **`pexDebug.stats` is a debugging convention, not API.** Don't ship code that reads from `window.pexDebug` — that's only for human inspection.
- **`fpsVolatility > 10%` is a heuristic.** Webapp3's threshold is empirical. If your video is mostly text or slides, a lower threshold (e.g. 5%) may be more appropriate.
- **`qualityLimitationReason: 'cpu'` is the most actionable.** Tell the user to close other apps. `'bandwidth'` is the user's network — they can't really fix it. `'other'` is rare and usually means the SDK failed to capture the reason.
- **The stats collector resets on call restart.** After ICE restart, the first few ticks will be incomplete (no historical baseline). Don't trip a "poor connection" warning on the first tick.

## Reference source

- **Authoritative Pexip docs:**
  - Pexip client SDK overview: https://docs.pexip.com/developer/clientapi.htm
  - `@pexip/infinity` JS client API reference: https://docs.pexip.com/api_client/api_pexrtc.htm
- **Reference implementation (webapp3):**

- `src/services/InfinityClient.service.ts:1266-1309` — `hasQualityStatsChanged`, `handleRtcStats`, `handleCallQualityChanged`
- `pexip-sdks/peer-connection-stats/src/statsCollector.types.ts` — full type catalog
- `pexip-sdks/peer-connection-stats/src/statsCollector.ts` — collection loop
- `pexip-sdks/peer-connection-stats/src/utils.ts` — normalization
