# Plugin UI Handling and Registration

This document details how the Webapp3 Plugin Host handles UI registration, synchronization, RPC validation, widget resource resolving, and iframe sandboxing.

## Initial sync — telling the plugin what's happening

When a plugin registers, the host emits the current state so the plugin doesn't need to query for everything:

```ts
const syncPlugin = (channel: Channel) => {
    channel.sendEvent({event: 'event:languageSelect', payload: i18next.language});
};

const syncWidget = (channel: Channel) => {
    const meeting = infinity.getMeeting();
    for (const [roomId, status] of meeting.getConferenceStatus()) {
        channel.sendEvent({event: 'event:conferenceStatus', payload: {status, id: roomId}});
    }
    channel.sendEvent({
        event: 'event:conference:authenticated',
        payload: {conferenceAlias: meeting.getConferenceAlias()},
    });
    channel.sendEvent({event: 'event:languageSelect', payload: i18next.language});
    for (const roomId of meeting.getRooms()) {
        const pids = meeting.getParticipants({roomId: meeting.getRoomId()});
        const participants: Participant[] = [];
        for (const pid of pids) {
            const p = meeting.getParticipant(pid, meeting.getRoomId());
            if (p) participants.push(p);
        }
        channel.sendEvent({event: 'event:participants', payload: {id: roomId, participants}});
        const meInRoom = meeting.getMe(roomId);
        if (meInRoom) {
            channel.sendEvent({event: 'event:me', payload: {id: roomId, participant: meInRoom}});
        }
    }
};
```

Widgets get more state than plugins because they may render UI based on participants. Plugins typically register listeners for specific events and don't need the historical replay.

## UI element handlers — the React state pattern

Buttons, forms, prompts, and widgets are stored in `PluginContext`:

```ts
const [pluginsElements, setPluginsElements] = useState<PluginContext>({});

// PluginContext shape:
{
    [chanId]: {
        buttons: ButtonElement[],
        forms: FormElement[],
        prompts: PromptElement[],
        widgets: WidgetElement[],
    }
}
```

Each handler does `structuredClone` to avoid React state mutation:

```ts
export const handleAddButton = (data, setPluginsElements) => {
    // ... validation ...
    setPluginsElements(prev => {
        const next = structuredClone(prev);
        const elements = next[data.chanId];
        if (!elements) return prev;
        elements.buttons.push({...data.payload, id: data.id, chanId: data.chanId});
        return next;
    });
    return {rpc: data.rpc, replyTo: data.id, payload: {status: 'ok', id: data.id, data: undefined}};
};
```

`structuredClone` works because the payload types are JSON-safe. Don't use a shallow spread — the handler may mutate nested arrays.

## Validation per RPC

Each handler validates the payload before applying:

```ts
const validateButton = (payload) => {
    if (
        payload.position !== 'settingsMenu' &&
        typeof payload.icon === 'string' &&
        !isValidIconName(payload.icon)
    ) {
        return {status: 'failed', reason: 'Invalid Icon name'};
    }
    return {status: 'ok'};
};

const validateForm = (payload) => {
    const selectElements = Object.values(payload.form.elements).filter(e => e.type === 'select');
    if (selectElements.find(e => e.options.length === 0)) {
        return {status: 'failed', reason: 'The select elements in the form must have at least one option'};
    }
    if (selectElements.find(e =>
        e.selected && !e.options.map(o => o.id).includes(e.selected)
    )) {
        return {status: 'failed', reason: `A SelectElement's 'selected' value must be one of its options' IDs`};
    }
    return {status: 'ok'};
};
```

Without payload validation, a buggy plugin can crash the host's render. Always validate before `setPluginsElements`.

## Widget URL resolution

Widgets reference HTML files that may live inside the branding folder or at an absolute URL:

```ts
let widgetSrc = data.payload.src;
try {
    new URL(widgetSrc);  // throws if relative
} catch {
    widgetSrc = getBrandingPath(widgetSrc);  // resolve relative to manifest.json
}
```

The try/catch is the JavaScript-idiomatic way to test "is this a valid absolute URL." `URL.canParse` would be cleaner but isn't supported in older Safari.

## Sandbox values

`getValidSandboxValues(plugin)` filters `plugin.sandboxValues` from the manifest against an allowlist and merges in `allow-scripts` (always required for the plugin to run).

**Allowlist:**

```
allow-forms
allow-scripts                  // always merged in
allow-same-origin
allow-popups
allow-popups-to-escape-sandbox
allow-downloads
```

Any token outside this list is dropped with a console warning: `'<value>' is not a valid sandbox value for plugins.`

**Forbidden** (never allowed): `allow-top-navigation`, `allow-modals`, `allow-pointer-lock`, `allow-presentation`. The plugin protocol provides safer alternatives — `ui:prompt:open` instead of `allow-modals`, etc.
