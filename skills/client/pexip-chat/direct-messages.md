# Direct messages

Pexip supports per-participant direct chat alongside group chat. Two participants can have a 1:1 thread; the panel UI lists conversations sorted by most recent. The state is messier than group chat (per-thread unread + global unseen counters, conversation reordering), so this doc walks through the full lifecycle.

## State shape

```ts
// All messages ever received in any direct thread
directChatMessages: Map<ParticipantID, ChatMessage[]>;

// Unread per-thread (cleared when user opens that specific thread)
unreadDirectChatMessages: Map<ParticipantID, ChatMessage[]>;

// Unseen globally (cleared when message scrolls into view)
unseenUnreadDirectChatMessages: ChatMessageID[];
```

Why three structures? Each clears at a different time:

- **Conversation list** uses `directChatMessages` — needs every message ever
- **Per-thread unread badge** uses `unreadDirectChatMessages` — clears when thread opens
- **Toolbar global badge** uses `unseenUnreadDirectChatMessages` — clears as messages scroll into view

A single counter wouldn't capture all three states.

## Adding a message to a thread

```ts
const addDirectChatMessage = (
    withParticipantID: ParticipantID,
    chatMessage: ChatMessage,
) => {
    const currentMessagesWithParticipant =
        getDirectChatMessagesWithParticipant(withParticipantID) ?? [];

    // Reorder: delete first, then set, so this thread becomes "most recent"
    const newDirectChatMessages = new Map(directChatMessages);
    newDirectChatMessages.delete(withParticipantID);
    newDirectChatMessages.set(withParticipantID, [
        ...currentMessagesWithParticipant,
        {...chatMessage},
    ]);
    updateDirectChatMessages(newDirectChatMessages);
};
```

The `delete` + `set` pattern is webapp3's way to reorder a `Map`. JavaScript Maps preserve insertion order, so re-inserting moves the key to the end. The conversation-list UI then renders entries in iteration order (most recent thread first via `.entries()`).

## Adding to unread + unseen (incoming only)

When a *received* message arrives:

```ts
const addUnreadDirectChatMessage = (
    withParticipantID: ParticipantID,
    chatMessage: ChatMessage,
) => {
    const unreadMessages =
        getUnreadDirectChatMessagesWithParticipant(withParticipantID) ?? [];
    const newUnreadDirectChatMessages = new Map(unreadDirectChatMessages);
    newUnreadDirectChatMessages.delete(withParticipantID); // reorder
    newUnreadDirectChatMessages.set(withParticipantID, [
        ...unreadMessages,
        {...chatMessage},
    ]);
    updateUnreadDirectChatMessages(newUnreadDirectChatMessages);
    addUnseenUnreadDirectChatMessage(chatMessage.id); // also flag as unseen
};
```

Sent messages don't go into unread/unseen — only received ones.

## Clearing unread (user opens a thread)

```ts
const deleteUnreadDirectChatMessagesWithParticipant = (
    withParticipantID: ParticipantID,
) => {
    const newUnreadDirectChatMessages = new Map(unreadDirectChatMessages);
    deleteAllUnseenUnreadDirectChatMessagesWithParticipant(withParticipantID);
    newUnreadDirectChatMessages.delete(withParticipantID);
    updateUnreadDirectChatMessages(newUnreadDirectChatMessages);
};

const deleteAllUnseenUnreadDirectChatMessagesWithParticipant = (
    withParticipantID: ParticipantID,
) => {
    const unreadMessages =
        getUnreadDirectChatMessagesWithParticipant(withParticipantID) ?? [];
    deleteUnseenUnreadDirectChatMessages(unreadMessages.map(({id}) => id));
};
```

Opening a thread clears both that thread's unread *and* removes those message ids from the global unseen list.

## Clearing unseen (messages scroll into view)

```ts
const deleteUnseenUnreadDirectChatMessages = (messageIDs: ChatMessageID[]) => {
    const newList = unseenUnreadDirectChatMessages.filter(
        id => !messageIDs.includes(id),
    );
    if (newList.length !== unseenUnreadDirectChatMessages.length) {
        unseenUnreadDirectChatMessages = newList;
        unseenUnreadDirectChatMessagesSignal.emit();
    }
};
```

Wire this to the `IntersectionObserver` in your message-list view: when a message scrolls into view, call this with its id. The global toolbar badge updates as the user reads.

The `length` check is a no-op guard — if no ids matched, don't emit a signal that triggers re-renders.

## Sending a direct message: pending → confirmed

The flow is the same as group chat (see `SKILL.md`), but with the `participantUuid` set:

```ts
if (toParticipantUuid) {
    addDirectChatMessage(toParticipantUuid, {...chatMessage, pending: true});
}

const result = await infinity.sendMessage({
    payload: message,
    participantUuid: toParticipantUuid,
});

const setMsgSuccess = () => {
    // Remove the pending entry first, then add the confirmed one
    deleteDirectChatMessage(toParticipantUuid, chatMessage.id);
    addDirectChatMessage(toParticipantUuid, chatMessage);
};
```

`deleteDirectChatMessage` removes the pending entry by id:

```ts
const deleteDirectChatMessage = (
    withParticipantID: ParticipantID,
    chatMessageIDToDelete: string,
) => {
    if (!directChatMessages.has(withParticipantID)) return;
    const currentMessages =
        getDirectChatMessagesWithParticipant(withParticipantID) ?? [];
    const newMessages = currentMessages.filter(
        m => m.id !== chatMessageIDToDelete,
    );
    const newDirectChatMessages = new Map(directChatMessages);
    newDirectChatMessages.set(withParticipantID, newMessages);
    updateDirectChatMessages(newDirectChatMessages);
};
```

Note: this *doesn't* delete the thread itself, just one message inside it.

## Conversation list (the chat panel sidebar)

Render via `directChatMessages.entries()` — Map iteration order is insertion order, and `addDirectChatMessage` re-inserts on every update, so the most-recent thread is last. Reverse for "newest first" display:

```tsx
{Array.from(directChatMessages.entries()).reverse().map(([uuid, messages]) => (
    <ConversationItem
        key={uuid}
        participantUuid={uuid}
        lastMessage={messages[messages.length - 1]}
        unreadCount={unreadDirectChatMessages.get(uuid)?.length ?? 0}
    />
))}
```

## "New direct message" picker

Webapp3 uses `GroupKey.DirectChat` to filter the participant list to only those who support direct chat:

```ts
const eligibleParticipants = meeting.getParticipants({
    filterBy: GroupKey.DirectChat,
});
```

Excludes API-only participants and any participants with `supportsDirectChat: false`.

## Gotchas

- **The Map reordering only works because we reinsert.** If you mutate the Map's value in place, the order doesn't change. Always create a new Map and `delete` + `set`.
- **Pending direct messages don't show as "unread" to the sender.** They're only added to `directChatMessages`, not `unreadDirectChatMessages`. Only received messages go into unread.
- **Don't share state between group and direct buckets.** A user might be participating in group chat and have unread direct messages — the badges should show separately.
- **Breakout transfers preserve direct chat.** Unlike group chat (which clears on `onBreakoutRefer`), direct messages persist because they're between users, not scoped to a room. The `prevMeetingAttrs` snapshot pattern (see `call-lifecycle/transfer-flow.md`) carries them across.
- **`unseenUnreadDirectChatMessages` is an array, not a Map.** Don't try to filter it by participant — use the *thread-level* clear function instead.

## Reference source

- `src/services/InfinityClient.service.ts:405-538` — full direct-message state machine
- `src/viewModels/ChatPanel.viewModel.tsx`, `ChatNewDirectMessage.viewModel.tsx`, `DirectChatLobby.view.tsx`
