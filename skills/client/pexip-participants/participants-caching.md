# Participant Caching and Groupings

This document covers Webapp3's participant grouping strategies, including the 15 `GroupKey` values, the `assignGroups` logic, and the cache invalidation graph.

## The 15 GroupKey values

```ts
export enum GroupKey {
    None,                    // Everyone
    Breakout,                // Has media — eligible for breakout assignment
    DirectChat,              // Capability flag
    FECC,                    // Capability flag (far-end camera control)
    Host,                    // Role — only when in-meeting
    Guest,                   // Role — only when in-meeting
    RaisedHand,
    External,                // Service-type connections (recordings, gateway)
    InMeeting,               // The active roster
    Transferring,            // In transit between conferences/rooms
    WaitingInLobby,          // Pending admission
    BreakoutRaisedHand,
    BreakoutExternal,
    BreakoutInMeeting,
    BreakoutWaitingInLobby,
}
```

A participant can belong to **multiple groups** (e.g., `[None, Breakout, DirectChat, InMeeting, Host, FECC]`). The `assignGroups` helper in `createParticipants.ts` derives the full set from a `Participant` object plus a `breakoutRoom` boolean.

## Cache invalidation graph

Because some filter results depend on others (e.g., the `InMeeting` filter is "Host ∪ Guest"), changing host/guest invalidates `InMeeting`. Webapp3 expresses this as a forward-dependency map and computes the reverse at startup:

```ts
const cacheInvalidationMap = createReversedDependencyAdjacencyList(
    new Map([
        [GroupKey.Host, new Set([GroupKey.Transferring])],
        [GroupKey.Guest, new Set([GroupKey.Transferring])],
        [GroupKey.Breakout, new Set([GroupKey.Transferring])],
        [GroupKey.DirectChat, new Set([GroupKey.Transferring])],
        [GroupKey.FECC, new Set([GroupKey.Transferring])],
        [GroupKey.InMeeting, new Set([GroupKey.Host, GroupKey.Guest])],
        [GroupKey.External, new Set([GroupKey.Transferring])],
        [GroupKey.RaisedHand, new Set([GroupKey.Transferring])],
        [GroupKey.WaitingInLobby, new Set([GroupKey.Transferring])],
        [GroupKey.BreakoutInMeeting, new Set([GroupKey.Host, GroupKey.Guest])],
        // ... etc
    ]),
);
```

When a participant's `Transferring` flag changes, all groups that depend on it (`Host`, `Guest`, `Breakout`, `DirectChat`, `FECC`, `External`, `RaisedHand`, `WaitingInLobby`) get their caches invalidated. The DFS-builder in `createReversedDependencyAdjacencyList` checks for cycles and throws if a cycle is detected.

You don't need to touch this map unless you add a new `GroupKey`. If you do, declare its forward dependencies and the rest is handled automatically.
