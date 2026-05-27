---
name: pexip-branding-manifest
description: Use when implementing Pexip branding — loading manifest.json, applying color palette, hiding UI elements, customizing translations, configuring application defaults via the branding system. Triggers on `manifest.json`, `loadBranding`, `colorPalette`, `applicationConfig`, `defaultUserConfig`, `hiddenFunctionality`, `availableLanguages`, `customStepConfig`, `bgImageAssets`, brand customization, white-label, ConfigManager.
license: MIT
---

# Pexip branding manifest

Pexip's official extensibility surface (other than plugins and call SDKs) is `manifest.json` — a single JSON file shipped under `branding/` that declares colors, images, translations, hidden UI elements, app defaults, and plugins. Webapp3 loads it on startup and applies it before the React tree renders.

This skill captures the loader pattern. The manifest schema itself is documented in [Pexip's docs](https://docs.pexip.com/admin/customizing_webapp3.htm) (and in your project's pasted docs from earlier in this session) — this skill is about the **runtime side**: how to fetch, validate, apply, and react to manifest values.

## The shape of the manifest

```ts
export interface Manifest {
    version: 0;                                   // schema version
    meta: {name: string; brandVersion: string};   // not used by app
    appTitle?: string;                            // browser tab title
    brandName: string;                            // {{brandName}} variable in translations
    backgroundColor?: string;
    overlay?: 'light' | 'dark';
    overlayOpacity?: number;
    colorPalette?: string[];                       // 11 hex strings (light → dark)
    images: {logo?, jumbotron?, background?};
    favicon?: {href: string; sizes?: string; type?: string};
    translations: Record<string, string>;          // {lang: path-to-json}
    availableLanguages?: string[];
    applicationConfig: Partial<ApplicationConfig>; // overrides for app-wide settings
    defaultUserConfig: Partial<DefaultUserConfig>; // overrides for user-tunable defaults
    plugins?: Plugin[];                            // see plugin-host skill
    customStepConfig?: CustomStepConfig;           // optional join-flow card
}
```

## Loading

```ts
import type {Manifest} from './branding';

const path = new URL('./branding/manifest.json', document.baseURI);
const BRANDING_MANIFEST_PATH = path.toString();

export const getBrandingPath = (path: string) =>
    new URL(path, BRANDING_MANIFEST_PATH).toString();

export async function loadBranding(): Promise<Manifest> {
    const res = await fetch(BRANDING_MANIFEST_PATH, {
        credentials: 'include',  // for auth-protected branding paths
        mode: 'no-cors',         // allow same-origin only
    });
    return res.json() as Promise<Manifest>;
}
```

The `getBrandingPath` helper is critical: every relative path in the manifest (logo, translations, plugin src, custom step source) must be resolved relative to `manifest.json`'s URL, not the current page URL. Use it everywhere you reference a branding asset.

## React hook: `useBrandingLoader`

```ts
export function useBrandingLoader() {
    const [brand, setBrand] = useState<Manifest>();

    useEffect(() => {
        let ignore = false;
        loadBranding()
            .then(brand => { if (!ignore) setBrand(brand); })
            .catch((error) => {
                if (!ignore) setBrand(DEFAULT);
                logger.warn({error}, 'failed to load branding');
            });
        return () => { ignore = true; };
    }, []);

    useEffect(() => {
        if (!brand) return;
        try {
            setBrandApplicationConfig(brand.applicationConfig);
            setFavicon(brand.favicon);
            setBrandDefaultUserConfig(brand.defaultUserConfig);
            setBrandApplicationTitle(brand.appTitle);
            setBrandPalette(brand.colorPalette);
            setBrandBgColor(brand.backgroundColor);
            setBrandTranslations(brand.translations);
            setBgReplacementAssets(
                brand.applicationConfig?.bgImageAssets,
                brand.defaultUserConfig?.bgImageUrl,
            );
            setLanguages(brand.availableLanguages, brand.translations);
        } catch (error) {
            setBrand(DEFAULT);
            logger.error({error}, 'branding manifest is invalid');
        }
    }, [brand]);

    return brand;
}
```

The `ignore` flag handles the StrictMode double-mount and unmount-during-fetch case. The split between the two `useEffect`s lets the brand load asynchronously before the apply step runs synchronously.

If anything in the apply step throws, **fall back to `DEFAULT`** (an empty manifest). Never crash the app on a malformed branding file — admins customize these and typos happen.

## Applying color palette

The palette is a flat array of 11 hex colors mapping to CSS custom properties (`--color-brand-50` through `--color-brand-950`):

```ts
const SHADES = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950];

const setBrandPalette = (colorPalette: Manifest['colorPalette']) => {
    if (colorPalette && colorPalette.length > 0) {
        if (colorPalette.length !== SHADES.length) {
            logger.warn('color palette has too many/few elements');
        }
        colorPalette.forEach((color, idx) => {
            document.documentElement.style.setProperty(
                `--color-brand-${SHADES[idx]}`,
                color,
            );
        });
    } else {
        // No palette → remove any previously set values (lets defaults take over)
        for (const shade of SHADES) {
            document.documentElement.style.removeProperty(`--color-brand-${shade}`);
        }
    }
};
```

The remove-on-empty branch matters for hot-reload during development — without it, switching between branded and unbranded states leaves stale CSS variables.

## Applying app config, default user config, and hidden functionality

For details on how webapp3 applies specific manifest properties (such as validation of `applicationConfig`, guarding `defaultUserConfig` modifications, and resolving `hiddenFunctionality` test IDs), see [Applying Manifest Properties](applying-manifest-properties.md).

## Translations

The manifest references per-language JSON files relative to `manifest.json`:

```json
{
    "translations": {
        "en": "./en.json",
        "af": "./af.json"
    }
}
```

Webapp3 registers them with i18next and forces a reload:

```ts
const setBrandTranslations = (translations: Manifest['translations'] = {}) => {
    for (const [lng, path] of Object.entries(translations)) {
        brandingLngs.set(lng, getBrandingPath(path));
        // Force i18next to refetch instead of using its cached state
        delete i18n.services.backendConnector?.state?.[`${lng}|translation`];
    }
    i18n.reloadResources().catch(() => logger.warn(`Can't reload translation`));
};
```

The `delete` is a hack — i18next's docs don't expose a clean way to invalidate cached language state. The internal `state` key is `${lng}|translation`. If you upgrade i18next, retest this.

## `availableLanguages` filtering

If the manifest declares `availableLanguages: ['en', 'fr']`, all other supported languages are removed from the user's language picker:

```ts
export const setLanguages = (
    availableLanguages: Manifest['availableLanguages'],
    translations: Manifest['translations'],
) => {
    let allLanguages = [
        ...ALLOWED_LANGUAGES,
        ...Object.keys(translations).filter(k => !ALLOWED_LANGUAGES.includes(k)),
    ];

    if (isValidAvailableLanguages(availableLanguages, allLanguages)) {
        allLanguages = allLanguages.filter(lng => availableLanguages?.includes(lng));
    }

    void initI18next(allLanguages, true).then(() => i18n.changeLanguage(undefined));
    return allLanguages;
};
```

`changeLanguage(undefined)` triggers i18next-browser-languagedetector to re-pick. If the user's browser language is no longer in the allowed set, it falls back to `en`.

## Favicon and custom step

For details on applying favicons and setting up custom join-flow steps (such as terms-of-service screen configurations), see [Applying Manifest Properties](applying-manifest-properties.md).

## See also

- `pexip-plugin-host` — manifest's `plugins` array drives plugin loading
- `pexip-signals-pattern` — `config.subscribe(key, handler)` is how branding-driven config changes propagate
- `pexip-preflight` — `bgImageAssets` and `customStepConfig` affect the join flow

## Gotchas

- **Always wrap loader in try/catch + DEFAULT fallback.** Never let a malformed manifest crash the app.
- **`getBrandingPath` is non-optional.** Forgetting it works in dev (when manifest is at `/branding/manifest.json`) but breaks in production (when branding lives at `/sales/branding/manifest.json` etc).
- **`config.isDefaultValue(key)` only works for keys the user can touch.** For `applicationConfig` keys (which the user never sets directly), there's no equivalent — the manifest always wins.
- **`colorPalette` is exactly 11 colors.** Fewer = warning logged but not crash; more = trailing colors silently dropped. Use a tool to generate the palette from a base color.
- **`hiddenFunctionality` matches `data-testid`, not class names.** Hidden elements still render in JSDoc tests unless tests respect the same flag.
- **The `transferTimeout` setting is in seconds.** A common mistake: `manifest.json` writes `"15"` (seconds), `applicationConfig.transferTimeout` is parsed as a number. Don't pass milliseconds.
- **`favicon` config doesn't apply via the branding portal.** Even if you set it, the portal silently strips it. Required for manual deployments only.
- **Mode `'no-cors'`** in the fetch is intentional — branding files are same-origin or behind auth. Don't change to `'cors'` thinking it's safer.

## Reference source

- **Authoritative Pexip docs:**
  - Customizing Webapp3 (branding / manifest schema): https://docs.pexip.com/admin/customizing_webapp3.htm
  - Pexip client SDK overview: https://docs.pexip.com/developer/clientapi.htm
- **Reference implementation (webapp3):**

- `src/branding/index.ts` — manifest types + `loadBranding` + `getBrandingPath`
- `src/branding/useBrandingLoader.ts` — the React hook + apply functions (212 LOC)
- `src/branding/Context.ts` — exposes the loaded manifest via React context
- `src/applicationConfig.ts` — typed `setApplicationConfig` with validation
- `src/config.ts` — `ConfigManager` for user-tunable settings
- `src/utils/transformHiddenFunctionalityArrayToObject.ts`
- `pexip-sdks/config-manager/src/` — the underlying ConfigManager + `configHook`
