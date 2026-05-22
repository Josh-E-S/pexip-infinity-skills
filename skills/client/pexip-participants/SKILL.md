---
name: pexip-participants
description: Use when building participant lists, mute/kick/admit controls, host vs guest filters, raise-hand handling, participant search, or anything reading the meeting roster. Triggers on `createInMeetingParticipants`, `GroupKey`, `onParticipantJoined`, `onParticipantUpdated`, `onParticipantLeft`, `onParticipants`, `participants.get`, `InMeetingParticipant`, `RoomParticipantMap`, `ParticipantActivity`, FECC, raised hand, waiting in lobby.
license: MIT
---

# Pexip participants

The participants list seems simple — *show users in the meeting* — but webapp3's implementation is the most architecturally dense file in the project. Reasons:

- A participant has 5+ orthogonal axes (host/guest, in-meeting/external/lobby/transferring, raised-hand, can-fecc, supports-direct-chat)
- The UI needs *filtered, sorted, searched, and cached* projections of these
- Breakout rooms add another dimension (every group has a breakout variant)
- Participant events fire in batches during reconnect (server replays everyone)
- Cache invalidation has dependency chains (changing host/guest invalidates "in-meeting" filter)

Webapp3 solves all of this with `GroupKey` (a 15-value enum) and a reverse-dependency cache invalidation graph. **Use it.** Don't roll your own — you'll spend a week getting the edge cases right.

## Participant groupings and GroupKeys

A single participant typically belongs to multiple groups (e.g., `Host`, `Guest`, `RaisedHand`, `FECC`). Webapp3 maps these using a `GroupKey` enum. For detailed definitions of all 15 `GroupKey` values and how they are assigned, see [Participant Caching and Groupings](participants-caching.md).

## Quick start: wire it up

```ts
import {createInMeetingParticipants, GroupKey} from './utils/createParticipants';
import {participantActivityBatchedSignal} from './signals/Participant.signals';

const participants = createInMeetingParticipants(
    infinityClient,                       // exposes admit/kick/mute/setRole
    () => mediaService.media,             // for self-mute (can't use clientApis on self)
    infinityClientSignals,                // onParticipants, onParticipantJoined, etc.
    participantActivityBatchedSignal,     // emits join/leave/update activities
    {                                     // optional: prior state from a transfer
        participants: previousParticipantsMap,
        activities: previousActivitiesArray,
    },
);

// Read filtered participants
const hosts = participants.get({filterBy: GroupKey.Host});
const handsRaised = participants.get({filterBy: GroupKey.RaisedHand});
const lobby = participants.get({filterBy: GroupKey.WaitingInLobby});
const everyone = participants.get({filterBy: GroupKey.InMeeting});

// Search
const filteredHosts = participants.get({
    filterBy: GroupKey.InMeeting,
    searchQuery: 'alice',
});

// Cleanup (call on call end / transfer)
participants.release();
```

## What `participants.get(...)` returns

A `Set<ParticipantID>` (just uuids), already sorted appropriately:

| Filter | Sort order |
|---|---|
| `RaisedHand` / `BreakoutRaisedHand` | By `handRaisedTime` (oldest hand first) |
| `InMeeting` / `BreakoutInMeeting` | Hosts first (alphabetical), then guests (alphabetical) |
| Everything else | Alphabetical by display name (case-insensitive) |

To get full `InMeetingParticipant` objects, look them up:

```ts
for (const pid of participants.get({filterBy: GroupKey.Host})) {
    const participant = participants.getCurrent(pid, infinityClient.roomId);
    if (participant) {
        console.log(participant.displayName, participant.isMuted);
    }
}
```

## What's on `InMeetingParticipant`

The base SDK `Participant` plus webapp3-injected action methods (bound to `this` participant):

```ts
interface InMeetingParticipant extends Participant {
    displayName: string;       // overlayText || displayName (raise-hand can override)
    highlightedCharacters: {start: number; end: number}[]; // for search highlighting
    mute(): void;              // toggles audio mute (self uses media, others uses SDK)
    muteVideo(): void;         // self only
    kick(): void;
    admit(): void;             // promotes to guest if pending
    spotlight(): void;         // toggles
    setRole(): void;           // toggles host ↔ guest
    lowerHand(): void;         // server-side lower
    roomId: RoomID;
}
```

The actions internally choose between media-service (self) and clientApis (others):

```ts
const muteAudio = isSelf
    ? () => {
          if (getMedia()?.audioMuted !== undefined) {
              getMedia()?.muteAudio(!getMedia()?.audioMuted);
          }
      }
    : () => {
          clientAPIs.mute({
              participantUuid: participant.uuid,
              mute: !participant.isMuted,
              breakoutUuid,
          });
      };
```

**Don't bypass these.** If you call `clientAPIs.mute` directly on the local participant, the local media state stays unmuted while the server thinks you're muted — tracks keep transmitting and the user's UI is wrong.

## How participant events flow

The infinity SDK's `infinityClientSignals` produce these:

| Signal | Variant | Payload | When |
|---|---|---|---|
| `onParticipants` | generic | `{id: RoomID, participants: Participant[]}` | Initial sync, reconnect resync |
| `onParticipantJoined` | **batched** | `RoomParticipantEvent[]` | New joins (collected in batches) |
| `onParticipantUpdated` | **batched** | `RoomParticipantEvent[]` | State changes |
| `onParticipantLeft` | **batched** | `RoomParticipantEvent[]` | Departures |
| `onBreakoutEnd` | generic | `{breakout_uuid: RoomID}` | Breakout dissolves |

The batched signals are critical during reconnect, when the server replays the entire roster. Without batching, you'd render-thrash. The batching is configured at signal creation:

```ts
export const infinityClientSignals = createInfinityClientSignals([], {
    batchScheduleTimeoutMS: 100,    // PARTICIPANT_EVENT_BATCHING_TIMEOUT_MS
    batchBufferSize: 50,            // PARTICIPANT_EVENT_BATCHING_SIZE
});
```

## Search

Webapp3 ships a fuzzy `ParticipantSearcher` (uses `@leeoniya/ufuzzy` per dependencies.txt) that returns matches with character offsets:

```ts
const result = participantSearcher.search(participants, 'alice');
// Map<ParticipantID, {participantId, matches: {start, end}[]}>
```

`participants.get({searchQuery: 'alice'})` runs this for the filter and stores `highlightedCharacters` on each matched participant for the UI to render. Empty search clears the highlights.

Search results are **cached** by `(roomId, filterBy, searchQuery)`. New query → recompute. Same query → return cached `Set`. The cache lives until the underlying group changes.

## Cache invalidation graph

To avoid recalculating participant lists from scratch, webapp3 utilizes a reverse-dependency cache invalidation graph to selectively clear group caches when a participant's flags change. For details on how this graph is constructed and cleared, see [Participant Caching and Groupings](participants-caching.md).

## Activity stream (for chat-side join/leave indicators)

`createInMeetingParticipants` emits batched activities to a separate signal:

```ts
import {createSignal} from '@pexip/signal';

export const participantActivityBatchedSignal = createSignal<ParticipantActivity, ParticipantActivity[]>({
    name: 'participant:activity',
    variant: 'batched',
    schedule: task => setTimeout(task, 500),
    bufferSize: 100,
    emitImmediatelyWhenFull: true,
});
```

Used to render "Alice joined" / "Bob left" lines in the chat panel without spamming individual events. The 500ms tick batches rapid-fire joins/leaves into one render.

## Self-mute & guests-can-unmute

When the user unmutes locally, webapp3 also clears the server-side mute *if* the user is allowed:

```ts
const handleAudioMute = createDebounceMute(
    {timerId: 0, muted: undefined},
    muted => {
        void clientMute({mute: muted});
        const me = infinity.getMe();
        if (
            !muted &&
            me?.isMuted &&
            (me?.isHost || infinity.conferenceStatus.get(infinity.roomId)?.guestsCanUnmute)
        ) {
            void mute({mute: false});
        }
    },
);
```

`clientMute` is the local-state sync (one-way). `mute({mute: false})` is the server-side action that requires permission. If a host has muted you and `guestsCanUnmute` is false, your local unmute won't propagate — you'll see yourself unmuted but everyone else hears nothing.

## See also

- `pexip-signals-pattern` — `infinityClientSignals` is a batched-aware hub
- `pexip-call-lifecycle` — `getMe()` and the FECC pid signal state
- `pexip-chat` — direct messages need the `DirectChat` group filter
- `pexip-breakouts` — every breakout has its own room id with its own participant list
- `pexip-fecc` — `GroupKey.FECC` filters who can be remote-controlled
- `pexip-plugin-host` — plugins receive `event:participants` events sourced from this util

## Gotchas

- **Don't iterate `currentParticipants` directly.** Use `participants.get({filterBy})` so the cache works. Iterating bypasses the sort + cache.
- **`participants.release()` must be called before recreating.** Otherwise the SDK signal subscriptions leak across calls.
- **`getMe()` takes a roomId.** In a breakout, `getMe()` is `getMe(breakoutRoomId)` — calling it without an arg returns the main-room identity.
- **`participant.isHost && !participant.hasMedia` = "API host"** (a control-only participant, e.g. a recording bot). Don't show full UI for these.
- **`isWaitingToBeAdmitted` checks `serviceType === 'ivr'` too.** IVR-routed participants count as lobby. Use the helper, don't roll your own.
- **Activities buffer survives transfers.** When you snapshot for direct-media transfer, the `consumeActivities()` call drains it; if you forget, the new meeting will replay old joins/leaves.
- **`searchQuery: ''` is different from `undefined`.** Empty string clears the search-result cache and highlights. Undefined leaves them alone.

## Reference source

- `src/utils/createParticipants.ts` — the full implementation (~1,200 LOC)
- `src/utils/participantSearcher.ts` — fuzzy search (uses `@leeoniya/ufuzzy`)
- `src/utils/createReversedMapSet.ts`, `createReversedMapObject.ts` — bi-directional maps
- `src/utils/createConsumableKeyedBuffer.ts` — activity buffer
- `src/signals/Participant.signals.ts` — the batched activity hub
- `src/viewModels/Participant.viewModel.tsx`, `ParticipantsMenu.viewModel.tsx`
