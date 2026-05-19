---
name: pexip-fecc
description: Use when implementing far-end camera control — letting one participant pan/tilt/zoom another participant's PTZ-capable camera. Triggers on `fecc`, `FeccButton`, `pan`, `tilt`, `zoom`, far-end camera, PTZ, `canFecc`, `isFeccEnabled`, `currentFeccPids`, FECC capability, `browserSupportsPtzConstraints`.
license: MIT
---

# Pexip far-end camera control (FECC)

FECC lets a participant remote-control another participant's pan/tilt/zoom (PTZ) camera. Niche feature — used in dedicated meeting-room setups (Cisco/Polycom hardware in conference rooms with PTZ cameras). Most calls won't use it. But when it's needed, it's needed.

The capability has three gates:
1. **Conference allows it** (`isFeccEnabled` from server)
2. **The remote user opts in** (`fecc: true` in their user config; off by default)
3. **The browser supports PTZ constraints** (`navigator.mediaDevices.getSupportedConstraints()` includes `pan`, `tilt`, `zoom`)

This skill covers wiring all three plus the "who can I currently control" tracking webapp3 maintains.

## Browser PTZ support check

```ts
export const browserSupportsPtzConstraints = () => {
    const browserSupports = navigator.mediaDevices.getSupportedConstraints();
    return (
        'pan' in browserSupports &&
        'tilt' in browserSupports &&
        'zoom' in browserSupports
    );
};
```

Chrome/Edge desktop yes. Firefox sometimes. Safari no. Mobile no.

When PTZ is supported and `config.get('fecc') === true`, webapp3 adds `pan`, `tilt`, `zoom` to the video constraints so the local browser knows to expose those API surfaces:

```ts
const fecc = config.get('fecc');
const video = {
    // ...other constraints...
    ...(!browserSupportsPtzConstraints()
        ? {}
        : {pan: fecc, tilt: fecc, zoom: fecc}),
};
```

The `fecc` boolean here is whether *this user* allows their camera to be controlled. Without it on the constraint, the browser doesn't grant the page permission to manipulate PTZ.

## Sending FECC commands (controller side)

The infinity SDK exposes `infinity.fecc({...})`:

```ts
const fecc = infinity.fecc;  // typed: Parameters<InfinityClient['fecc']>

// Move a participant's camera
await fecc({
    participantUuid: 'remote-user-uuid',
    action: 'pan',         // or 'tilt' | 'zoom'
    direction: 'left',     // or 'right' | 'up' | 'down' | 'in' | 'out'
});
```

The exact API shape varies by SDK version — verify against your `@pexip/infinity` types.

Webapp3 wraps it with the standard `toFn` shim (drops the await/return for fire-and-forget):

```ts
fecc: toFn(fecc),
```

So you call `meeting.fecc({...})` and don't bother with the promise.

## Receiving FECC (controlled side)

If your camera is being controlled, the browser's PTZ constraints kick in automatically — the controller-side API call results in your local track moving. There's no per-frame event you handle; the camera just moves.

Webapp3 doesn't expose any "your camera is being controlled" signal — the user can see it in the video tile.

## Tracking who I'm currently controlling

Multiple participants in a room can have FECC-capable cameras. Webapp3 tracks "who am I actively in the FECC menu for" via a `SignalState`:

```ts
currentFeccPids: createSignalState<Set<ParticipantID>>(new Set()),

// Adding/removing
addCurrentRoomFeccParticipantID: (pid) => {
    const set = props.currentFeccPids.get();
    set.add(pid);
    props.currentFeccPids.set(set);
},
removeCurrentRoomFeccParticipantID: (pid) => {
    const set = props.currentFeccPids.get();
    set.delete(pid);
    props.currentFeccPids.set(set);
},
```

`SignalState` is webapp3's wrapper around `createSignal({variant: 'behavior'})` plus a getter — it's reactive state that re-renders subscribers when the value changes (see `pexip-signals-pattern`).

## Filtering "who *can* be FECCed"

Use `GroupKey.FECC` from the participants util to find FECC-capable participants in the current room:

```ts
const feccEnabledPids = participants.get({
    filterBy: GroupKey.FECC,
    roomId: infinity.roomId,
});
```

This is everyone with `participant.canFecc === true` — i.e. they enabled `fecc` in their settings AND their hardware supports PTZ AND the conference allows it.

## Intersecting "can be FECCed" with "currently being FECCed"

Webapp3's `getCurrentRoomFeccParticipantIDs` returns the intersection — only show controls for participants who *can* be controlled and that the user has opted into:

```ts
const getCurrentRoomFeccParticipantIDs = memoize(
    () => {
        const feccEnabledPids = participants.get({
            filterBy: GroupKey.FECC,
            roomId: infinity.roomId,
        });
        const pids: ParticipantID[] = [];
        for (const pid of currentFeccPids.get()) {
            if (feccEnabledPids.has(pid)) {
                pids.push(pid);
            }
        }
        return pids;
    },
    () => [
        participants.get({filterBy: GroupKey.FECC, roomId: infinity.roomId}),
        currentFeccPids.changed,
    ],
);
```

The memoization keys: the FECC group set + the `currentFeccPids` signal. When either changes, recompute. The `participants.get(...)` is itself cached, so this is cheap.

## The FECC button — gating render

```tsx
import {FeccButtonView} from '@pexip/media-components';
import {useIsFeccEnabled, useMeetingContext} from '../hooks/meeting';

export const FeccButton: React.FC<...> = ({onClickFecc, ...props}) => {
    const meeting = useMeetingContext();
    const shouldEnableFecc = useIsFeccEnabled(meeting.getIsFeccEnabled);

    return (
        <FeccButtonView
            isFeccHidden={!shouldEnableFecc}
            iconSource={feccpad}
            onClickFecc={onClickFecc}
            {...props}
        />
    );
};
```

The `isFeccHidden` prop completely hides the button when:
- Conference doesn't have FECC enabled (server config), OR
- No participants in the current room are FECC-capable

`useIsFeccEnabled` subscribes to conference status changes to react when participants come and go.

## Conference-level enable check

`meeting.getIsFeccEnabled` reads `infinity.isFeccEnabled` — set by the server based on the conference's configuration. Pexip admins can disable FECC for an entire conference type. Honor it:

```ts
getIsFeccEnabled: () => infinity.isFeccEnabled,
```

If this returns false, hide all FECC UI even if individual participants have `canFecc: true`.

## See also

- `pexip-participants` — `GroupKey.FECC` filter; `participant.canFecc` flag
- `media-pipeline/video-effects.md` — the PTZ constraints in `getDefaultConstraints`
- `pexip-signals-pattern` — `SignalState` is the behavior-signal pattern in disguise

## Gotchas

- **PTZ requires real hardware.** Software cameras (OBS Virtual Camera, Snap Camera) don't expose `pan`/`tilt`/`zoom`. Don't expect FECC to work in dev with a webcam.
- **Permissions are sticky.** Once granted PTZ access, the browser remembers. If you flip `config.fecc` from true→false mid-call, the constraint update doesn't revoke — you have to re-request media (`getUserMedia`) to drop the capability.
- **`fecc: false` constraint vs absent constraint.** Setting `pan: false` doesn't disable PTZ — it just *requests* off. The user's hardware may still be controllable if the host already has the capability. If you want to *block* control, omit the constraints entirely.
- **The icon (`feccpad.svg`) is webapp3-specific.** It's a stylized D-pad. If you build your own UI, you can use any directional control affordance.
- **Don't subscribe to PTZ track settings yourself.** The browser's `MediaStreamTrack.getSettings().pan` etc. update reactively, but listening for changes is non-trivial. Use the FECC RPC and trust it.
- **`memoize` from `@pexip/utils`** is multi-key — it accepts a function that returns the cache-key array. Don't try to memoize on the `Set` reference directly; use `.changed` from `SignalState` (an incrementing counter).
- **FECC commands are async but non-blocking.** Webapp3 wraps with `toFn` (fire-and-forget). The user sees the camera move ~200ms later when the controlled side processes the request.
- **Pre-v39 conferences may not support FECC over the modern API.** Old gateway calls use legacy DTMF-based PTZ. Check `isFeccEnabled` and don't rely on a specific call type.

## Reference source

- `src/services/InfinityClient.service.ts:815, 1359-1380, 1492-1503` — FECC integration
- `src/viewModels/FeccButton.viewModel.tsx` — button gating (30 LOC)
- `src/viewModels/FeccGw.viewModel.tsx` — gateway-call FECC variant
- `src/hooks/useFeccMenuItem.tsx` — menu integration
- `src/services/Media.service.ts:169-176, 365-368` — `browserSupportsPtzConstraints` + constraint application
- `src/utils/createParticipants.ts:397-399` — `GroupKey.FECC` assignment via `participant.canFecc`
