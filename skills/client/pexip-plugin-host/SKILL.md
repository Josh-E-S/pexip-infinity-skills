---
name: pexip-plugin-host
description: Use when implementing the host side of Pexip's plugin system — loading plugins from manifest.json, sandboxing iframes, RPC handling, panel widgets, toolbar buttons, prompt/form/toast injection, conference RPC routing. Triggers on `@pexip/plugin-api`, `Channel`, `RPCCall`, plugin iframe, sandbox, `ui:button:add`, `ui:widget:add`, `ui:form:open`, `ui:toast:show`, `ui:prompt:open`, plugin manifest, plugin RPC.
license: MIT
---

# Pexip plugin host

Pexip plugins are sandboxed iframes that drive the host app via `postMessage` RPC. The plugin can:
- Add toolbar buttons / participant menu items / settings menu items
- Open panel widgets (visible iframes inside the meeting UI)
- Show modal forms / prompts / toasts
- Call most of the conference SDK (`mute`, `kick`, `setLayout`, `breakout`, `sendMessage`, etc.)
- Subscribe to events (participant joins, conference status, language change, transfer events)

Webapp3's `PluginManager` is the host implementation. ~1,000 LOC across `src/plugins/` plus the `@pexip/plugin-api` SDK. This skill captures the architecture; if you need to write *plugins* (the iframe side), see Pexip's separate plugin developer portal.

## The architecture in one diagram

```
manifest.json declares plugins[]
        ↓
<PluginManager> renders one hidden <iframe sandbox> per plugin
        ↓
plugin loads, calls registerPlugin() which sends "syn" RPC via postMessage
        ↓
host validates: is the message source one of our iframes?
        ↓
host creates Channel, sends "ack" reply, syncs initial state to plugin
        ↓
plugin issues UI/conference RPCs (button:add, widget:add, conference:mute, etc.)
        ↓
host updates React state for UI ops, calls infinity SDK for conference ops
        ↓
host subscribes to all infinity signals → forwards to plugins as events
```

## Manifest entry

```json
{
    "plugins": [
        {
            "src": "./plugins/my-plugin/index.html",
            "id": "my-plugin",
            "sandboxValues": ["allow-scripts", "allow-same-origin"]
        }
    ]
}
```

Webapp3 renders this as:

```tsx
<iframe
    id={plugin.id}
    sandbox={getValidSandboxValues(plugin)}
    src={plugin.src}
    aria-hidden
    className="b-zero"  // 0×0, invisible
/>
```

Plugins are **logical, not visible** — they're invisible iframes that issue commands. To show UI, plugins request a *widget* (a separate visible iframe) or call `ui:button:add` / `ui:form:open` / etc. (rendered natively by the host).

## Two iframe types: plugins vs widgets

| Type | Purpose | Visible? | Registers via |
|---|---|---|---|
| **Plugin** | Logic / event subscriber / button injector | No | `syn` RPC |
| **Widget** | Visible panel UI (e.g. a custom side panel) | Yes | `syn:widget` RPC |

Webapp3 keeps two `Set<HTMLIFrameElement>` references and validates incoming `postMessage` events come from one of them:

```ts
const isMessageSourceAnIframe = (
    source: MessageEventSource | null,
    iframes: Set<HTMLIFrameElement>,
) => {
    for (const iframe of iframes) {
        if (iframe.contentWindow && iframe.contentWindow === source) return true;
    }
    return false;
};

const isPluginIframe = (source) => isMessageSourceAnIframe(source, pluginIframes.current);
const isWidgetIframe = (source) => isMessageSourceAnIframe(source, widgetIframes.current);
```

If a `syn` comes from a widget iframe (or vice versa), the host rejects it. This is the **only** mechanism preventing widgets from claiming plugin privileges.

## The RPC dispatch

```ts
const onMessage = ({source, data}: MessageEvent<RPCCall>) => {
    if (!isRPCCall(data)) return;
    if (!isPluginIframe(source) && !isWidgetIframe(source)) return;

    const chanId = data.chanId;

    // Registration handshake
    if (data.rpc === 'syn') {
        const newChannel = new Channel(source as Window, chanId);
        const response = validateSyn(data.payload, source);
        if (!response.ack) {
            newChannel.replyRPC({rpc: data.rpc, replyTo: data.id, payload: response});
            newChannel.unregister();
            return;
        }
        setupChannel(data, newChannel);
        syncPlugin(newChannel);
        return;
    }

    if (data.rpc === 'syn:widget') {
        // ... similar but with validateSynWidget + syncWidget
    }

    // Established channel — dispatch by RPC name
    const channel = channels.current.get(chanId);
    if (channel) {
        switch (data.rpc) {
            case 'ui:button:add':       channel.replyRPC(handleAddButton(data, setPluginsElements)); break;
            case 'ui:widget:add':       channel.replyRPC(handleAddWidget(data, setPluginsElements, findManifestPluginByChannel(data.chanId))); break;
            case 'ui:form:open':        channel.replyRPC(handleOpenForm(data, setPluginsElements)); break;
            case 'ui:prompt:open':      channel.replyRPC(handleOpenPrompt(data, setPluginsElements)); break;
            case 'ui:toast:show':       channel.replyRPC(handleShowToast(data)); break;
            case 'ui:removeElement':    channel.replyRPC(handleRemoveElement(data, setPluginsElements)); break;
            case 'ui:button:update':    channel.replyRPC(handleUpdateButton(data, setPluginsElements)); break;
            case 'ui:widget:toggle':    channel.replyRPC(handleToggleWidget(data)); break;
            case 'app:setDisconnectDestination':
                channel.replyRPC(handleSetDisconnectDestination(data));
                break;
            // ~25 conference:* and participant:* RPCs all go through one handler:
            case 'conference:mute':
            case 'conference:setLayout':
            case 'participant:transfer':
            // ... 22 more
                handleInfinityCall({data, channel, sendMessage: infinity.getMeeting().sendMessage});
                break;
        }
    }
};
```

`handleInfinityCall` looks up the matching SDK method and calls it with type-narrowed args. Centralizing this means adding a new conference RPC = one switch case + one entry in `handleInfinityCall`.

## Validation: prevent ID collision and identity confusion

```ts
const validateSyn = (payload, source) => {
    if (!isPluginIframe(source)) {
        return {ack: false, reason: 'Not a plugin. You are likely trying to register a widget as a plugin'};
    }
    for (const key of channels.current.keys()) {
        if (key.startsWith(`${payload.id}-`)) {
            return {ack: false, reason: 'A plugin with the same id already exists'};
        }
    }
    return {ack: true};
};
```

Channel IDs include the plugin id as a prefix (`my-plugin-<random>`). The duplicate-id check prevents a buggy or malicious plugin from claiming another's namespace.

## Initial sync — telling the plugin what's happening

For details on the handshake sync sequences and state serialization sent to plugins and widgets during initial load, see [Plugin UI Handling and Registration](plugin-ui-handling.md).

## Forwarding ongoing events to plugins

Webapp3 has a separate file (`src/plugins/signals/RegisterInfinityClient.signals.ts`) that subscribes to all `infinityClientSignals` and forwards them to every channel:

```ts
useEffect(() => {
    const detachSignals = registerInfinityClientSignals(channels.current, infinity);
    detachSignals.push(
        userInitiatedDisconnectSignal.add(() => {
            for (const channel of channels.current.values()) {
                channel.sendEvent({event: 'event:userInitiatedDisconnect', payload: undefined});
            }
        }),
    );
    return () => {
        for (const detachSignal of detachSignals) detachSignal();
    };
}, [infinity]);
```

Iterating `channels.current.values()` on every event is fine because plugin counts are typically 0–5. Don't optimize prematurely.

## UI element state, validation, and sandboxing

For details on how webapp3 manages native React state for plugins (buttons, forms, prompts), validates incoming RPC payloads, resolves widget iframe URLs, and filters sandbox tokens, see [Plugin UI Handling and Registration](plugin-ui-handling.md).

## See also

- `pexip-branding-manifest` — `manifest.json` declares plugins, host loads them
- `pexip-signals-pattern` — plugin events forward through the same signal hubs
- `pexip-participants` — `event:participants` payload comes from `meeting.getParticipants`
- `pexip-call-lifecycle` — `event:userInitiatedDisconnect` and conference RPCs route through the meeting service

## Gotchas

- **Plugins and widgets aren't interchangeable.** A widget can't call `participant:transfer`. A plugin can't render UI directly. The split is enforced via `validateSyn` / `validateSynWidget`.
- **Channel IDs include a random suffix.** Don't try to predict them. Use `findManifestPluginByChannel(chanId)` to map back to the manifest entry.
- **`structuredClone` doesn't preserve functions.** RPC payloads are pure data — that's fine. But if you ever store functions in `pluginsElements`, switch to a manual deep clone.
- **`channels.current.values()` iteration on every event** is cheap because plugin count is small. If you build something with hundreds of plugins, switch to a publish-subscribe map.
- **Don't expose `infinityService` directly to plugins.** Always go through `meeting.getMeeting()` so transfer-aware methods work correctly.
- **The plugin iframe `aria-hidden` and `className="b-zero"`** keep it invisible. Don't remove those — visible plugin iframes are widgets.
- **`ui:toast:show` doesn't queue.** If a plugin spams toasts, they all fire. Add rate-limiting at the host if needed.
- **Forms must validate `select.selected ∈ select.options[].id`.** This is the most common plugin author mistake — the form opens looking blank if `selected` doesn't match.

## Reference source

- `src/plugins/index.tsx` — `PluginManager` (433 LOC)
- `src/plugins/handleUiRPC.ts` — UI element handlers (337 LOC)
- `src/plugins/handleAppRPC.ts` — app-level RPCs
- `src/plugins/infinityCalls.ts` — conference/participant RPC dispatcher
- `src/plugins/signals/RegisterInfinityClient.signals.ts` — event forwarding
- `src/plugins/utils/sandbox.utils.ts` — sandbox value filtering
- `src/plugins/components/Toolbar/`, `Widgets/`, `Form/`, `Prompts.tsx` — React renderers for plugin UI
- `pexip-sdks/plugin-api/src/channel.ts` — `Channel` class
