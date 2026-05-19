---
name: pexip-chat
description: Use when implementing Pexip in-meeting chat — sending messages, handling incoming `onMessage` events, optimistic UI with pending state, retry-queue reconciliation, character limits, dedup. Triggers on `infinityClient.sendMessage`, `onMessage`, `ChatMessage`, `chatMessages`, `onRetryQueueFlushed`, character limit, pending message, chat panel. Cover both group chat and direct (1:1) messages.
license: MIT
---

# Pexip chat

Pexip's chat is signaling-channel chat, not a separate WebSocket. Messages flow through the same event source as everything else — which means they share the same retry/queue/reconnect machinery. This is good (chat survives ICE restart automatically) but introduces edge cases (server may dedup, queue, or drop messages during reconnect).

Webapp3 handles these correctly with **optimistic UI + retry-queue reconciliation**. This skill captures that pattern.

## Sending: optimistic add, then reconcile

The pattern: add the message immediately as `pending: true`, then resolve it once the server confirms — possibly later via the retry queue.

```ts
import {v4 as uuid} from 'uuid';
import {toTime} from '@pexip/media-components';

const sendMessage = async (message: string, toParticipantUuid?: ParticipantID) => {
    const me = infinity.getMe();
    if (!me) return;

    const chatMessage = {
        displayName: me.displayName || 'User',
        id: uuid(),                    // client-generated id, used for dedup
        message,
        timestamp: toTime(new Date()),
        type: 'user-message',
        userId: me.uuid,
    } as const;

    // 1. Optimistic add
    const isDirectMessage = !!toParticipantUuid;
    if (isDirectMessage) {
        addDirectChatMessage(toParticipantUuid, {...chatMessage, pending: true});
    } else {
        updateChatMessages([...chatMessages, {...chatMessage, pending: true}]);
    }

    // 2. Send via the SDK
    const result = await infinity.sendMessage({
        payload: message,
        participantUuid: toParticipantUuid,
    });

    const setMsgSuccess = () => {
        // Replace the pending message with the confirmed one
        if (isDirectMessage) {
            deleteDirectChatMessage(toParticipantUuid, chatMessage.id);
            addDirectChatMessage(toParticipantUuid, chatMessage); // no `pending`
        } else {
            const filtered = chatMessages.filter(({id}) => id !== chatMessage.id);
            updateChatMessages([...filtered, chatMessage]);
        }
    };

    // 3. Reconcile
    if (result) {
        setMsgSuccess(); // Sent immediately
    } else {
        // Got queued — wait for the SDK's retry queue to flush, then mark sent
        infinityClientSignals.onRetryQueueFlushed.addOnce(() => setMsgSuccess());
    }
};
```

The `result` boolean is what the SDK returns. **Falsy doesn't mean failed** — it means the request was queued (e.g. during reconnect). The retry queue will flush eventually; subscribe once and you'll get the confirmation. If the queue never flushes (e.g. the call ends), the message stays `pending: true` forever — that's fine, it'll disappear when the meeting ends.

## Receiving: filter, format, dispatch

Webapp3's incoming-message handler:

```ts
const CHARACTER_LIMIT = 5000;

const handleOnChatMessage = createSignalHandler(
    infinityClientSignals.onMessage,
    message => {
        // 1. Filter messages that are too long (server bug or malicious client)
        if (message.message.length > CHARACTER_LIMIT) {
            logger.warn(`Message too big. Length: ${message.message.length}`);
            return;
        }

        // 2. Normalize
        const chatMessage: ChatMessage = {
            ...message,
            displayName: message.displayName || 'User',
            timestamp: toTime(message.at),
            type: 'user-message',
        };

        // 3. Emit to listeners that want every message (e.g. notifications)
        chatMessageSignal.emit(chatMessage);

        // 4. Route to direct-vs-group buckets
        if (message.direct) {
            addDirectChatMessage(message.userId, chatMessage);
            addUnreadDirectChatMessage(message.userId, chatMessage);
        } else {
            updateChatMessages([...chatMessages, chatMessage]);
            updateUnreadChatMessages([...unreadChatMessages, chatMessage]);
        }
    },
);
```

Two destination buckets, both updated:
- **Total messages list** — the chat panel renders from this
- **Unread list** — the toolbar badge counts from this; cleared when the user opens the panel

## Character limit

Webapp3 enforces 5000 characters on **both** send and receive paths. The send-side validation happens in the input component; the receive-side filter (above) catches malicious or buggy senders.

You can tune this — but if you increase it, both sides need to agree, or the receive filter will drop your own messages.

## Unread vs unseen — they're different things

| State | Meaning | Cleared when |
|---|---|---|
| **Unread** | Message exists, user hasn't opened the panel | User opens the chat panel |
| **Unseen** | Message exists in a direct chat thread that isn't currently visible | User scrolls to that specific direct chat |

For group chat, only "unread" exists. For direct messages, you need both: the panel is open (unread cleared) but the user is looking at a different person's thread (so messages from a third person are still "unseen").

```ts
const addUnreadDirectChatMessage = (
    withParticipantID: ParticipantID,
    chatMessage: ChatMessage,
) => {
    const unreadMessages =
        getUnreadDirectChatMessagesWithParticipant(withParticipantID) ?? [];
    const newUnreadDirectChatMessages = new Map(unreadDirectChatMessages);
    newUnreadDirectChatMessages.delete(withParticipantID); // delete first to reorder
    newUnreadDirectChatMessages.set(withParticipantID, [...unreadMessages, {...chatMessage}]);
    updateUnreadDirectChatMessages(newUnreadDirectChatMessages);
    addUnseenUnreadDirectChatMessage(chatMessage.id); // add to unseen too
};
```

The `delete` + `set` pattern reorders the Map so the most-recent conversation is first. JavaScript Maps preserve insertion order — webapp3 uses this as the conversation-list sort key.

## See also

- `pexip-signals-pattern` — `onMessage` is on `infinityClientSignals`; `chatMessageSignal` is a local hub
- `pexip-call-lifecycle` — chat state survives direct-media transfers (see `transfer-flow.md`)
- `pexip-participants` — direct messages need participant uuids; the participants util is the source

## Sibling references

- `direct-messages.md` — the complete direct-chat flow including thread management, conversation list ordering, and the unseen lifecycle

## Gotchas

- **Don't dedup by message *content*.** Use the client-generated `id` field. Two users can legitimately send the same text in the same second.
- **Server can echo your own message back.** Webapp3 doesn't dedup these — the optimistic message has the same `id`, so when `onMessage` fires for it, the filter in the message list already has it. If you don't use the optimistic-then-replace pattern, you'll get duplicates.
- **`message.direct` is the discriminator.** Don't infer direct-ness from `participantUuid` matching `me.uuid` — the server has the truth.
- **Direct chat requires capability.** Both sender and recipient must have `supportsDirectChat: true`. Webapp3 filters the recipient picker via `GroupKey.DirectChat`.
- **Pending messages persist across `onPeerDisconnect` / ICE restart.** The retry queue carries them. So if you mark them as failed on disconnect, you'll show false errors when they actually do send.
- **Breakout chat is scoped per-room.** When the user is moved to a breakout, webapp3 clears the chat (`infinityClientSignals.onBreakoutRefer.add(_ => updateChatMessages([]))`). Don't try to merge breakout chat with main-room chat.

## Reference source

- `src/services/InfinityClient.service.ts:835-889` — `sendMessage` with reconciliation
- `src/services/InfinityClient.service.ts:1114-1144` — `handleOnChatMessage` receive flow
- `src/services/InfinityClient.service.ts:469-538` — direct-message bucket management
- `src/hooks/useActivityChatMessages.ts`, `useChatType.ts`, `useCleanupUnreadAndUnseenChatMessages.ts`
