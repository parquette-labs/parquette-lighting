# Open Stage Control branding

Custom browser-tab icon and PWA metadata for the Open Stage Control UI.

Open Stage Control serves its favicon, apple-touch icon, and (if present) web
manifest from **inside its own app bundle** (`.../open-stage-control.app/Contents/
Resources/app/assets/`), not from the session/layout. There is no config or
session option to override them, so `launchd/install.sh` copies these files into
the app bundle on every install and idempotently injects the manifest `<link>`
into the app's `client/index.html`.

Because they live in the app bundle, **updating/reinstalling Open Stage Control
overwrites them** — just re-run `launchd/install.sh` (or `poetry run poe deploy`)
afterwards to reapply.

OSC serves app-bundle assets under a `/__APP_DIR__/assets/…` URL prefix (it
strips `__APP_DIR__/` from the incoming request path to locate the file). That
is why the manifest `<link>` and the icon `src` entries in
`manifest.webmanifest` must keep the `/__APP_DIR__/assets/…` prefix — a plain
`/assets/…` path returns 404.

## Files

| File | Installed to | Purpose |
| --- | --- | --- |
| `favicon.png` | `assets/favicon.png` | 256×256 transparent — browser tab icon |
| `logo.png` | `assets/logo.png` | 512×512 opaque, maskable safe zone — apple-touch / PWA icon |
| `manifest.webmanifest` | `assets/manifest.webmanifest` | Web app manifest (name, icons, theme, standalone display) |

## Regenerating the icons

`make_icons.py` renders the disco ball (Pillow required) and writes
`favicon.png`, `logo.png`, and a `preview_on_theme.png`:

```
python3 make_icons.py .
```
