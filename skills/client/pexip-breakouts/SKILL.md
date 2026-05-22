---
name: pexip-breakouts
description: Use when implementing Pexip breakout rooms — opening rooms, assigning participants automatically or manually, joining/closing rooms, ask-for-help flow, returning to main room, breakout chat scoping, breakout transfer details. Triggers on `meeting.openRooms`, `joinBreakoutRoom`, `closeBreakoutRoom`, `breakoutAskForHelp`, `MainBreakoutRoomId`, `breakoutUuid`, `onBreakoutEnd`, `onBreakoutRefer`, `BreakoutRoomsScreen`.
license: MIT
---

# Pexip breakout rooms

Breakouts are sub-conferences inside the main conference. The host can open N rooms, assign participants (auto or manual), set a duration, and close them all at once. Each breakout has its own chat, its own participant list, and its own host. Participants can ask for help; hosts get a notification with a "join this room" shortcut.

The whole flow is server-orchestrated — the SDK exposes ~10 RPCs and 2 events. Webapp3 wraps these into a panel-driven UX. This skill captures the API shape; consult `@pexip/media-components` for ready-made panel components if you don't want to build from scratch.

## The API surface

```ts
// On the meeting object (created via createInfinityClient → wrapped in Meeting service)
meeting.openRooms(roomDetails: BreakoutRoomDetail[], onDone?, onFail?);
meeting.closeBreakoutRoom(roomId: RoomID);
meeting.closeAllBreakoutRooms();
meeting.joinBreakoutRoom(roomId: RoomID, onDone?, onFail?);
meeting.askForHelp(roomId, onDone?, onFail?);
meeting.cancelAskingForHelp(roomId, onDone?, onFail?);
meeting.breakoutRequestGuestToken(breakoutUuid, onDone?, onFail?);
meeting.breakout(roomDetail);              // create one breakout
meeting.moveParticipants(...);             // reassign mid-flight

// State accessors
meeting.getBreakoutRooms();                // all breakouts the SDK knows about
meeting.getBreakoutRoomNames();            // ordered names
meeting.isBreakoutRoom(roomId);            // is this a breakout vs main?
meeting.getParticipantRoomID(participantUuid);

// Filter participants by breakout-eligibility
meeting.getSupportedBreakoutParticipants();  // wraps participants.get with filter
```

## Opening rooms

A `BreakoutRoomDetail`:

```ts
{
    name: string,                  // unique name (NOT 'main' — that's reserved)
    description: string,           // shown in UI
    duration: number,              // seconds; 0 = no timer
    end_action: 'transfer',        // when timer expires, move participants back
    participants: {
        [breakoutRoomName]: ParticipantID[],  // assignment manifest
    },
    guests_allowed_to_leave: boolean,         // can guests return without help?
}
```

Webapp3's `openRooms` iterates and creates each breakout serially:

```ts
const openRooms = async (
    roomDetails: BreakoutRoomDetail[],
    onDone?: () => void,
    onFail?: (error: unknown) => void,
) => {
    try {
        for (const roomDetail of roomDetails) {
            if (roomDetail.name === MainBreakoutRoomId) {
                throw new Error('Breakout with name "main" is not allowed');
            }
            await breakout(roomDetail);
        }
    } catch (error: unknown) {
        onFail?.(error);
    } finally {
        onDone?.();
    }
};
```

Note the `MainBreakoutRoomId` guard — `'main'` is the name webapp3 uses to mean "the main conference" in panel state. Don't let users name a breakout `'main'`.

The webapp3 panel calls it like this:

```ts
meeting.openRooms(
    Array.from(participants.entries())
        .filter(([name]) => name !== MainBreakoutRoomId) // skip the main-room "container"
        .map(([breakoutRoomName, roomParticipants]) => ({
            name: breakoutRoomName,
            description: breakoutRoomName,
            duration: breakoutDurationSec,
            end_action: 'transfer',
            participants: {
                ...(mainParticipants.length > 0 && {
                    [MainBreakoutRoomId]: mainParticipants,
                }),
            },
            guests_allowed_to_leave: breakoutParticipantsCanLeave,
        })),
    undefined,
    e => {
        setIsOpeningRooms(false);
        setShowOpenRoomsErrorModal(true);
        logger.error(e);
    },
);
```

## Assignment modes

Two patterns ship with `@pexip/media-components`:

| Mode | What it does |
|---|---|
| `Automatically` | Server divides participants evenly across N rooms. Hosts stay in main. |
| `Manually` | Host drags participants between rooms in the panel before opening |

The auto mode is just "skip the participants assignment" — the server decides. Manual mode requires the panel to track a `Map<roomName, ParticipantID[]>` and pass it.

## Joining a breakout

```ts
const joinBreakoutRoom = async (
    roomId: RoomID,
    onDone?: () => void,
    onFail?: (error: unknown) => void,
) => {
    try {
        await infinity.joinBreakoutRoom({
            ...getCallConfigs(),
            breakoutUuid: infinity.isBreakoutRoom(roomId) ? roomId : undefined,
        });
    } catch (error: unknown) {
        onFail?.(error);
    } finally {
        onDone?.();
    }
};
```

The `breakoutUuid: undefined` case = "go back to main room." The same RPC handles both directions.

`getCallConfigs()` is critical — when joining a breakout, you re-establish a peer connection with the same constraints (bandwidth, callType, displayName, etc.) as the main call. Don't pass empty configs or the breakout will inherit defaults.

## Ask for help and guest tokens

For details on summoning a host using the "ask for help" flow and generating guest entry tokens for breakouts, see [Breakout Operations](breakout-operations.md).

## Events

Two breakout-specific signals:

```ts
// Server is moving you to a breakout (or back to main).
// Webapp3 uses this to clear the chat (breakout chat is room-scoped).
infinityClientSignals.onBreakoutRefer.add(_roomUuid => {
    updateChatMessages([]);
});

// A breakout dissolved (timer expired, or host closed it).
// The participants util uses this to drop the breakout's roster.
participantsSignals.onBreakoutEnd.add(({breakout_uuid}) => {
    // Clean up any breakout-scoped state
});
```

Note: the actual transfer event for "you're being moved" is `infinityClientSignals.onTransfer` with `target: 'conference'` and `breakoutName` set — see `call-lifecycle/transfer-flow.md`. `onBreakoutRefer` is just the "your chat is now scoped to a different room" signal.

## Filtering participants

For details on breakout eligibility checks and grouping participants by breakout state, see [Breakout Operations](breakout-operations.md).

## The `BreakoutRoomsScreen` state machine

Webapp3's panel cycles through:

```
ModeAssignment       ← "Auto vs manual? How many rooms?"
     ↓
InitialConfiguration ← drag participants between rooms
     ↓ (open rooms)
RoomsOpened          ← live status, can edit, can close
     ↓ (edit)
EditConfiguration    ← reassign while rooms are live
     ↓
RoomsOpened
```

A `BreakoutRooms.signals` `setBreakoutStepSignal` lets external code force a step transition (used for "host received an ask-for-help, jump to the rooms-opened panel").

## See also

- `pexip-participants` — `GroupKey.Breakout*` filters; the per-room participant tracking
- `pexip-chat` — chat is cleared on `onBreakoutRefer`
- `call-lifecycle/transfer-flow.md` — the underlying transfer mechanism
- `pexip-signals-pattern` — `setBreakoutStepSignal` is a local signal hub

## Gotchas

- **Don't await `openRooms` for each room in parallel.** The server expects them serial; parallel opens can race and produce weird participant assignments. Webapp3's loop awaits each.
- **Breakout chat is per-room.** When you join a breakout, your group chat resets. When you return to main, you get the main-room chat back (if you're still showing the same `Meeting` instance — but you usually aren't, see transfer-flow).
- **`MainBreakoutRoomId` is `'main'` (a string constant).** Check `@pexip/media-components` exports for the canonical value. Don't hardcode `'main'`.
- **Hosts can't be reassigned by auto-mode.** Even if you put a host in `participants[breakoutName]`, the server keeps them in main unless they manually join.
- **Asking for help requires a host present.** If all hosts have left, the SDK still accepts the call but no one will see it.
- **`closeAllBreakoutRooms` doesn't take a roomId.** It closes everything. There's no "close all except this one" — you'd loop `closeBreakoutRoom` for each.
- **Edit mid-flight = server-side reassignment.** Participants in motion get split-second blank screens during the transfer. Time it carefully or pre-warn the user.
- **The `transferTimeout` setting in manifest.json** controls how long the "Moving you to breakout..." modal shows. Default 15s. Set to 0 to skip the modal entirely.

## Reference source

- `src/services/InfinityClient.service.ts:682-796` — all breakout RPC wrappers
- `src/viewModels/BreakoutRoomsPanel.viewModel.tsx` — the panel state machine
- `src/hooks/useBreakoutAskForHelp.tsx`, `useBreakoutRoomsCount.ts`, `useIsABreakoutSessionActive.ts`, `useOnBreakoutsEditSave.ts`
- `src/signals/BreakoutRooms.signals.ts`
- `src/utils/createParticipants.ts` — `GroupKey.Breakout*` semantics
