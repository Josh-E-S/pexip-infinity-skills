# Layout Configurations and SVG Fetching

This document describes how layout options are fetched, how name label overlay text is toggled, and how SVG layout previews are dynamically constructed in Webapp3.

## Fetching available layouts + their SVG previews

The server returns the list of layouts the current conference allows, plus an SVG for each (for the picker UI):

```ts
const availableLayouts = await infinityService.availableLayouts({});
// → ['1:0', '1:7', '2:0', '2:21', ...] or [{name: '1:0'}, ...]

const svgs = await infinityService.layoutSvgs({});
// → { '1:0': '<svg>...</svg>', ... }
```

Webapp3 builds a Map of `{name → {primary, active}}` SVG data URIs:

```ts
const BASE_COLOR = '#FFFFFF';
const PRIMARY_COLOR = '#777777';
const ACTIVE_COLOR = '#0068F4';

const getSource = (source: string, color: string) =>
    source &&
    `data:image/svg+xml;utf8,${source
        .replaceAll('currentColor', BASE_COLOR)
        .replaceAll('#BBBFC3', color)}`.replaceAll('#', '%23');

const getLayouts = (layouts: Record<string, string> | undefined, availableLayouts) =>
    new Map(
        Object.entries(layouts ?? {}).flatMap(([name, source]) =>
            availableLayouts.some(l => l.name === name)
                ? [[name, {
                    primary: getSource(source, PRIMARY_COLOR),
                    active: getSource(source, ACTIVE_COLOR),
                }]]
                : [],
        ),
    );
```

The replaceAll operations:
- `currentColor` → fixed white (the SVG uses CSS `currentColor` for the participant tile color)
- `#BBBFC3` → primary or active color (the SVG uses a hardcoded gray for the "border" or accent)
- `#` → `%23` so the data URI parses correctly

The webapp3 source comment calls this "super hacky" — that's because rendering the SVG inline via `dangerouslySetInnerHTML` would inject server-controlled markup (XSS risk). Data URI is safer.

## Layout overlay text (name labels)

Server-side toggle: should participant names be drawn over their video tiles?

```ts
const handleOnLayoutOverlayTextEnabled = createSignalHandler(
    infinityClientSignals.onLayoutOverlayTextEnabled,
    updateLayoutOverlayTextEnabled,
);

// Toggling it (host action):
const toggleLayoutOverlayTextEnabled = async () => {
    await _changeLayout({
        enable_overlay_text: !props.layoutOverlayTextEnabled,
    });
};
```

Note: `enable_overlay_text` goes through `changeLayout` (not a separate API). It's part of the layout transform.
