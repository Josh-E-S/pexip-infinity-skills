# Applying Manifest Properties

This document detail how various configuration elements from `manifest.json` are applied within the Webapp3 runtime.

## Applying applicationConfig — through the typed setter

`applicationConfig` is mostly pass-through, but a few keys need normalization. Webapp3 routes everything through `setApplicationConfig`:

```ts
const setBrandApplicationConfig = (
    brandingApplicationConfig: Manifest['applicationConfig'] = {},
) => {
    for (const [key, value] of Object.entries(brandingApplicationConfig)) {
        setApplicationConfig(
            key as keyof Manifest['applicationConfig'],
            key === 'hiddenFunctionality'
                ? transformHiddenFunctionalityArrayToObject(value as TestIdValue[])
                : value,
        );
    }
};
```

The `setApplicationConfig` switch validates each key:

```ts
case 'bandwidths':
    if (Array.isArray(value)) {
        const accepted = value
            .flatMap(v => +v ? [v] : [])  // 0 is invalid
            .sort((a, b) => +a - +b)
            .slice(0, BANDWIDTHS.length);  // only accept exactly 4
        if (accepted.length === BANDWIDTHS.length) {
            applicationConfig.bandwidths = accepted as StringQuadruple;
        }
    }
    break;
```

Without this validation, an admin who passes 3 bandwidths or strings like `"medium"` would silently break the bandwidth selector. **Don't bypass `setApplicationConfig`** — write through it for everything from the manifest.

## Applying defaultUserConfig — only if untouched

The `defaultUserConfig` settings are only applied **if the user hasn't already changed that setting**:

```ts
const setBrandDefaultUserConfig = (
    defaultUserConfig: Manifest['defaultUserConfig'] = {},
) => {
    for (const [k, value] of Object.entries(defaultUserConfig)) {
        const key = k as keyof Manifest['defaultUserConfig'];
        if (config.isDefaultValue(key)) {
            if (key === 'callType' && typeof value === 'string') {
                config.set({key, value: getClientCallType(value) ?? CALL_TYPE});
                continue;
            }
            config.set({key, value});
        }
    }
};
```

`config.isDefaultValue(key)` returns true if the user hasn't touched that setting. Without this guard, every page load would clobber the user's preferences (mute state, blur amount, etc.) with the brand defaults.

The `callType` case is special — manifests use the long string form (`'AudioSendRecvVideoSendRecvPresentationSendRecv'`) and webapp3 has to map it via `getClientCallType`.

## Hidden functionality

Admins can hide UI by `data-testid`. The manifest has it as an array; webapp3 stores it as an object for O(1) lookup:

```json
{
    "applicationConfig": {
        "hiddenFunctionality": ["button-chat", "user-menu-add-participant"]
    }
}
```

In code:

```ts
import {isFunctionalityHiddenByBranding} from './utils/isFunctionalityHiddenByBranding';

if (isFunctionalityHiddenByBranding('button-chat')) {
    return null; // don't render
}
```

The transform from array to object:

```ts
export const transformHiddenFunctionalityArrayToObject = (
    arr: TestIdValue[],
): Record<TestIdValue, true> =>
    Object.fromEntries(arr.map(id => [id, true])) as Record<TestIdValue, true>;
```

Don't bother iterating the array on every render — convert once at load time.

## Favicon

```ts
const setFavicon = (favicon?: Favicon) => {
    if (!favicon || !('href' in favicon)) return;
    const link =
        (document.querySelector('link[rel=icon]') as HTMLLinkElement) ??
        document.createElement('link');
    link.href = getBrandingPath(favicon.href);
    document.head.appendChild(link);
};
```

`appendChild` on an existing element is a no-op move (the element is already there). Cleaner than tracking insert vs update.

Supported formats: `.ICO`, `.SVG`, `.WEBP`, `.PNG`. Pexip's docs note this option **isn't configurable via the branding portal** — must be done manually.

## Custom step (terms-of-service iframe)

The `customStepConfig` adds an extra card to the join flow showing arbitrary HTML in an iframe. Webapp3 reads:

```ts
{
    customStepConfig: {
        active: true,
        source: {
            default: './index_default.html',
            en: './index_en.html',
            de: './index_de.html'
        },
        confirmation: 'checkbox',  // user must check before "Next"
        mandatory: true,           // shown even on direct-join URLs
        width: '80%', height: '80%',
        mobileWidth: '100%', mobileHeight: '100%',
    }
}
```

The flow: `MeetingFlow.CustomStep` step inserted before `ReadyToJoin`. The iframe `src` is `getBrandingPath(source[currentLang] ?? source.default)`.

The card text (title, "Next" button label, checkbox) comes from the language file's `custom-step` block — not from the manifest.
