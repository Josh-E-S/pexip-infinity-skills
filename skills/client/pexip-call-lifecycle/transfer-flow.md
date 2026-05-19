# The transfer flow

Pexip can transfer a participant between conferences without dropping the call. There are three transfer types, each with different state-preservation rules. Webapp3 handles all three; this is the pattern.

## The three transfer targets

The `onTransfer` event payload includes a `target` field:

| `target` | Meaning | What happens |
|---|---|---|
| `'conference'` | Move to a different conference (e.g. breakout room) | Disconnect, redirect to new conference URL |
| `'direct'` | Switch from transcoded to peer-to-peer media | Disconnect, immediately rejoin with `directMedia: true`. **Preserve chat + participants.** |
| `'transcoded'` | Switch from direct back to transcoded | Disconnect, immediately rejoin without `directMedia`. **Preserve chat + participants.** |

The chat-preservation rule is the non-obvious bit. If you tear down everything, the user loses chat history mid-call when the server transparently switches media modes.

## The handler

```ts
const handleOnTransfer = createSignalHandler(
    infinityClientSignals.onTransfer,
    ({alias, token, callTag, target, breakoutName}) => {
        // While transferring, suppress splash screens for control-only flows
        if (isReceivingAnyMedia(config.get('callType'))) {
            updateSplashScreen(undefined);
        }

        // Mark the participants as "transferring" in the UI
        participants.transfer(breakoutName ?? alias, target);

        const redirect = (reason: DisconnectReason = 'Transfer') => {
            void end({reason}).then(() =>
                transferSignal.emit({alias, token, callTag, target}),
            );
        };

        if (target === 'direct' || target === 'transcoded') {
            redirect('DirectMediaTransfer');
        } else if (target === 'conference') {
            redirect();
        }
    },
);
```

## State preservation across direct-media transfers

The wrapper layer (in `createInfinity()`) intercepts `onTransfer` *before* the meeting handler runs and snapshots the state into `prevMeetingAttrs`:

```ts
const handleTransfer = (event: GetSignalType<(typeof infinityClientSignals)['onTransfer']>) => {
    switch (event.target) {
        case 'direct':
        case 'transcoded': {
            // Snapshot — these will be passed to the new Meeting instance
            const {participants, activities} = meeting.getAllParticipantsAndActivities();
            prevMeetingAttrs = {
                liveCaptionsEnabled: meeting.getLiveCaptionsEnabled(),
                chatMessages: meeting.getChatMessages(),
                unreadChatMessages: meeting.getUnreadChatMessages(),
                directChatMessages: meeting.getDirectChatMessages(),
                unreadDirectChatMessages: meeting.getUnreadDirectChatMessages(),
                unseenUnreadDirectChatMessages: meeting.getUnseenUnreadDirectChatMessages(),
                previousParticipants: participants,
                previousParticipantActivities: activities,
            };
            break;
        }
        default:
            // 'conference' transfer: clean slate
            prevMeetingAttrs = {};
            break;
    }
    meeting.transfer(event); // Hand off to the meeting-level handler
};
```

Then in `call()`, when creating the next meeting:

```ts
meeting = createMeeting({
    infinity: infinityClient,
    callAttrs: {conferenceAlias, callTag, conferenceExtension},
    meetingAttrs: prevMeetingAttrs, // ← passes the snapshot
    controls: { /* ... */ },
});
prevMeetingAttrs = {}; // Reset for next time
```

`createMeeting` initializes its `chatMessages` and `participants` from `meetingAttrs` if provided, otherwise from empty:

```ts
const props: MeetingProps = {
    chatMessages: meetingAttrs.chatMessages ?? [],
    unreadChatMessages: meetingAttrs.unreadChatMessages ?? [],
    directChatMessages: meetingAttrs.directChatMessages ?? new Map(),
    // ...
    participants: createInMeetingParticipants(
        infinity,
        () => mediaService.media,
        infinityClientSignals,
        participantActivityBatchedSignal,
        {
            participants: meetingAttrs.previousParticipants,
            activities: meetingAttrs.previousParticipantActivities,
        },
    ),
};
```

## Why two layers?

The split is deliberate:
- **Outer layer** (`createInfinity`) owns the lifecycle: it can recreate the inner `Meeting` because it controls `prevMeetingAttrs`.
- **Inner layer** (`createMeeting`) owns the call: it doesn't know about transfers across instances.

If you collapse this into one layer, you can't preserve state across the recreation — the very thing you're trying to do.

## The redirect flow

The `transferSignal` is emitted *after* `end()` resolves. A router-level subscriber listens for it and navigates:

```ts
// Somewhere in the routing layer
transferSignal.add(({alias, token, callTag, target}) => {
    // Build the new meeting URL with the token, navigate
    navigate(`/${alias}?token=${token}&callTag=${callTag}`);
});
```

The token is a one-time conference token issued by the server; it's how the new conference knows you're a transfer (not a fresh join).

## Breakout-specific transfer

Breakouts use `target: 'conference'` with `breakoutName` populated:

```ts
participants.transfer(breakoutName ?? alias, target);
```

If `breakoutName` is set, the UI knows it's a breakout move (different copy, different transition). If not, it's a regular conference transfer.

## Gotchas

- **Don't snapshot `props.participants` directly.** Use `getAllParticipantsAndActivities()` which returns a stable serializable form. Otherwise you carry references that cause memory leaks.
- **`prevMeetingAttrs` must be reset to `{}`** after consumption. Forgetting this means the *next* fresh call starts with stale chat history.
- **Transfer modal timeout** — if the new conference doesn't accept the transfer within `transferTimeout` (default 15s, set via manifest.json), the modal closes. Honor this in your UI.
- **The `end({reason: 'DirectMediaTransfer'})` reason** is special-cased server-side. Don't change it to a custom string for direct-media transfers.

## Source

- `src/services/InfinityClient.service.ts:905-926` — meeting-level `handleOnTransfer`
- `src/services/InfinityClient.service.ts:1622-1648` — outer-level `handleTransfer` with state snapshot
- `src/services/InfinityClient.service.ts:1651-1721` — `call()` showing how `prevMeetingAttrs` is consumed
