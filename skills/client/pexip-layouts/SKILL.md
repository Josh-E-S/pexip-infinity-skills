---
name: pexip-layouts
description: Use when controlling Pexip meeting layouts — host layout vs personal layout, layout overlay text, lecture-mode guest layout, presentation-in-mix detection, fetching available layouts and their SVGs from the server. Triggers on `meeting.changeLayout`, `meeting.changePersonalLayout`, `setLayout`, `setPersonalLayout`, `availableLayouts`, `layoutSvgs`, `currentHostLayout`, `pres_slot_coords`, `transform_layout`, `enable_overlay_text`, `lecture` service type.
license: MIT
---

# Pexip layouts

Layouts control how the conference is composed: equal grid, speaker focus, presenter + thumbnails, etc. Pexip lets you change two layouts independently:

- **Host layout** (`changeLayout`) — what every participant sees by default
- **Personal layout** (`changePersonalLayout`) — overrides the host layout for *your* view only

Plus runtime info you read but rarely write: layout overlay text (name labels), lecture mode (separate guest layout), presentation in mix (server is composing presentation into the layout vs side-by-side).

This skill captures all of it.

## Quick start

```ts
import {MeetingLayout} from '@pexip/media-components';
import {infinityService} from '../services/InfinityClient.service';
import {useMeetingContext} from '../hooks/meeting';

export const LayoutsPanel: React.FC = () => {
    const meeting = useMeetingContext();
    const me = meeting.getMe();
    const currentHostLayout = meeting.getCurrentHostLayout();

    const [layouts, setLayouts] = useState<Map<string, {primary: string; active: string}>>();

    useEffect(() => {
        const fetchLayouts = async () => {
            const availableLayouts = await infinityService.availableLayouts({});
            const svgs = await infinityService.layoutSvgs({});
            setLayouts(buildLayoutMap(svgs, availableLayouts));
        };
        void fetchLayouts();
    }, []);

    return (
        <MeetingLayout
            canChangeLayout={me?.canChangeLayout}
            canChangePersonalLayout={me?.canReceivePersonalMix}
            currentLayout={currentHostLayout}
            currentPersonalLayout={me?.receiveFromVideoMix?.mix_config?.transform_layout?.layout}
            setLayout={meeting.changeLayout}
            setPersonalLayout={meeting.changePersonalLayout}
            resetToMeetingLayout={meeting.resetToMeetingLayout}
            layouts={layouts}
        />
    );
};
```

The `MeetingLayout` component from `@pexip/media-components` does the picker UI. You feed it state + actions; it renders.

## The two SDK calls

### `changeLayout(transforms)` — for everyone

Wraps the SDK's `setLayout`:

```ts
const _changeLayout = async (transforms: LayoutTransforms) => {
    try {
        return await controls?.changeLayout(transforms);
    } catch (error: unknown) {
        if (!(error instanceof Error)) throw error;
        logger.error({context: 'Meeting', error, transforms}, 'failed to change layout');
    }
};

const changeLayout = async (
    layout: Layout,
    onDone?: () => void,
    onFail?: (error: unknown) => void,
) => {
    try {
        await _changeLayout({
            layout,
            // Lecture mode has a separate guest_layout — set it the same as host
            guest_layout: infinity.serviceType === 'lecture' ? layout : undefined,
        });
    } catch (error: unknown) {
        onFail?.(error);
    } finally {
        onDone?.();
    }
};
```

The `serviceType === 'lecture'` check is important — lecture-style conferences have a separate layout for guests vs hosts. Setting both to the same value matches webapp3's behavior; a more sophisticated UI could let the host pick them independently.

### `changePersonalLayout(transforms)` — for me only

```ts
const _changePersonalLayout = async (transforms: LayoutTransforms) => {
    try {
        return await controls?.changePersonalLayout(transforms);
    } catch (error) {
        if (!(error instanceof Error)) throw error;
        logger.error({context: 'Meeting', error, transforms}, 'failed to change layout');
    }
};

const changePersonalLayout = async (layout: Layout, onDone?, onFail?) => {
    try {
        await _changePersonalLayout({layout});
    } catch (error) {
        onFail?.(error);
    } finally {
        onDone?.();
    }
};

// Reset = remove personal override, fall back to host layout
const resetToMeetingLayout = () => infinity.deleteVideoMix({});
```

`canReceivePersonalMix` on `me` tells you whether the conference allows personal layouts. Some server configs disable it (e.g. recording-only conferences).

## Reading current state

The host layout is updated via `onRequestedLayout`:

```ts
const handleOnRequestedLayout = createSignalHandler(
    infinityClientSignals.onRequestedLayout,
    layout => {
        currentHostLayout = layout.primaryScreen.hostLayout;
    },
);
```

Your personal layout lives on the participant object:

```ts
me?.receiveFromVideoMix?.mix_config?.transform_layout?.layout
```

This is `undefined` if you have no personal override — UI should show "follows host layout" in that case.

## Layout overlay text (name labels)

For details on toggling server-drawn participant name overlay labels, see [Layout Configurations and SVG Fetching](layouts-config.md).

## Presentation-in-mix detection

When someone presents, the server can either:
- **Compose** the presentation into the layout (one of the tiles becomes the screen) — `pres_slot_coords` is set
- **Send it as a separate stream** — `pres_slot_coords` is undefined; UI should render a separate presentation tile

```ts
const handleOnLayout = createSignalHandler(
    infinityClientSignals.onLayoutUpdate,
    layout => {
        isPresentationInMixActive = !!layout.pres_slot_coords;
    },
);
```

The `presInMix` SDK call lets the user toggle this preference:

```ts
const presInMix = async (...args: Parameters<typeof infinity.presInMix>) => {
    if (
        infinity.conferenceFeatureFlags === undefined ||
        infinity.conferenceFeatureFlags.isDirectMedia
    ) {
        return; // Direct-media conferences don't support presInMix
    }
    await infinity.presInMix(...args);
};

// Wired to user config
config.subscribe('preferPresInMix', preferPresInMix => {
    if (callStage >= CallStage.EventStreamConnected) {
        void presInMix({state: preferPresInMix});
    }
});
```

If the conference is `directMedia: true`, the `presInMix` API is a no-op — the SDK throws. Webapp3 short-circuits before calling.

## Fetching available layouts and their SVG previews

For details on fetching available layouts and parsing SVG layout icons for display picker options, see [Layout Configurations and SVG Fetching](layouts-config.md).

## Lecture mode

A `lecture` service type (Virtual Auditorium) gives hosts a separate layout from guests. Webapp3 keeps them in sync:

```ts
guest_layout: infinity.serviceType === 'lecture' ? layout : undefined,
```

To support independent layouts, expose two pickers and call `changeLayout({layout, guest_layout})` with both. Otherwise, treat it as a single setting.

## See also

- `call-lifecycle/reference.md` — `onRequestedLayout`, `onLayoutUpdate`, `onLayoutOverlayTextEnabled` event handlers
- `pexip-presentation` — `pres_slot_coords` interacts with layout state
- `pexip-participants` — `me.canChangeLayout`, `me.canReceivePersonalMix` are participant capability flags

## Gotchas

- **`changeLayout` is async but the UI shouldn't wait.** Optimistic-update the picker, the server will push the actual state via `onRequestedLayout` shortly.
- **`infinityService.availableLayouts({})` may return strings or objects.** Normalize both forms: `typeof layout === 'string' ? {name: layout} : layout`.
- **Personal layout doesn't survive ICE restart.** The server may or may not preserve it depending on conference config. Treat it as transient.
- **`resetToMeetingLayout` calls `deleteVideoMix({})`, not `setPersonalLayout(undefined)`.** Removing your personal override is a separate API.
- **Guest layouts in non-lecture conferences are ignored.** Don't pass `guest_layout` outside lecture mode — the server warns.
- **Available layout names look like `1:0`, `2:21`, `1:7`** — they're Pexip codes, not human-readable. The SVG previews are how users pick.
- **The replace order matters in the SVG hack.** `currentColor` must be replaced before `#`, or the data-URI escaping breaks `currentColor` itself.
- **`presInMix` requires `EventStreamConnected` stage.** Calling it before the SSE connection is up will fail. Webapp3 gates with `callStage >= CallStage.EventStreamConnected`.

## Reference source

- `src/services/InfinityClient.service.ts:624-681` — `changeLayout` / `changePersonalLayout` wrappers
- `src/services/InfinityClient.service.ts:715-719` — overlay text toggle
- `src/services/InfinityClient.service.ts:801-811` — `presInMix` with direct-media guard
- `src/services/InfinityClient.service.ts:1100-1112` — layout event handlers
- `src/viewModels/Layouts.viewModel.tsx` — the SVG-fetching picker (124 LOC)
