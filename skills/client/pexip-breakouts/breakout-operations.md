# Breakout Operations

This document details common runtime operations for Pexip breakouts, including summoning hosts, guest tokens, and filtering participants.

## Ask for help

A guest in a breakout can summon a host:

```ts
const askForHelp = async (roomId = infinity.roomId, onDone?, onFail?) => {
    try {
        await infinity.breakoutAskForHelp({breakoutUuid: roomId});
        onDone?.();
    } catch (error: unknown) {
        onFail?.(error);
    }
};

const cancelAskingForHelp = async (roomId = infinity.roomId, onDone?, onFail?) => {
    try {
        await infinity.breakoutRemoveAskForHelp({breakoutUuid: roomId});
        onDone?.();
    } catch (error: unknown) {
        onFail?.(error);
    }
};
```

The host sees a notification with a "Join this room" button. Webapp3 wires it to:

```ts
onJoinRoomViaHelp: roomId => {
    meeting.cancelAskingForHelp(roomId, () => {
        meeting.joinBreakoutRoom(roomId);
    });
}
```

The cancel-then-join sequencing matters — without canceling first, the help indicator stays on after the host arrives.

## Guest tokens (advanced — for moderator-only join)

Some flows want a host to generate a one-time token a guest can use to enter a specific breakout (e.g. SMS link). `breakoutRequestGuestToken` returns a token from the server:

```ts
const breakoutRequestGuestToken = async (
    breakoutUuid: RoomID,
    onDone?: (token: string) => void,
    onFail?: (error: unknown) => void,
) => {
    try {
        const res = await infinity.breakoutRequestGuestToken({breakoutUuid});
        const token = res?.data.result;
        if (!token) throw new Error('No guest token returned');
        onDone?.(token);
    } catch (error) {
        onFail?.(error);
    }
};
```

You build the URL with `?token=<token>` and the SDK accepts it on join. Lifetime is server-controlled (typically 1 hour). Don't cache tokens client-side beyond a single use.

## Filtering participants

Use `GroupKey.Breakout` (or its breakout-specific variants) from the participants util:

```ts
import {GroupKey} from './utils/createParticipants';

// Everyone eligible to be in a breakout (excludes API-only hosts)
const eligible = meeting.getParticipants({filterBy: GroupKey.Breakout});

// People currently in a specific breakout room
const inRoomA = meeting.getParticipants({
    roomId: 'breakout-uuid-a',
    filterBy: GroupKey.BreakoutInMeeting,
});

// People asking for help in their current breakout
const helpRequests = ...; // see useBreakoutAskForHelp hook
```

The `assignGroups` logic in `createParticipants.ts`:

```ts
// Only Guest or Host with media Capability are breakout-capable
const isBreakoutParticipant =
    !participant.isHost || (participant.isHost && participant.hasMedia);
if (isBreakoutParticipant) {
    keys.push(GroupKey.Breakout);
    if (breakoutRoom) {
        if (isWaitingToBeAdmitted(participant)) keys.push(GroupKey.BreakoutWaitingInLobby);
        else if (participant.isExternal)        keys.push(GroupKey.BreakoutExternal);
        else                                    keys.push(GroupKey.BreakoutInMeeting);
    }
}
```
