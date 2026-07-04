# Intrustum Brand Kit

Single source of truth for the Intrustum marks on the web, implementing the
**Mark Correction & Production Handoff v1.0**. The goal is *consistent
reproduction*: every surface references the same vector and the same tokens, and
an automated gate fails the build if any asset drifts from the spec.

> These files are **working-file status** per handoff §0/§6 until reconstructed
> or verified in Adobe Illustrator against the live-type master. They are the
> web production copies, not the legal authoring source.

## What's here

| File | Role |
|---|---|
| `assets/mark-block.svg` | Primary block mark — favicon, headers (§3a) |
| `assets/mark-outline.svg` | Secondary outline mark — line-art, engraving (§3b) |
| `assets/seal-full.svg` | Full seal, ring text live in Interface (§3c) — inline in HTML so fonts render |
| `assets/seal-micro.svg` | Micro seal ≤48px — footers, stamps (§3e) |
| `assets/seal-die.svg` | Blind-deboss die variant, colorless (§3d) |
| `assets/favicon.svg` | Block mark as SVG favicon |
| `brand.css` | Design tokens (color §4, type §1.3, lockup ratios §1.5, tracking §1.6) + the `.intrustum-lockup` component (§3f) |
| `lockup.html` | Framework-free lockup snippet |
| `django/_intrustum_lockup.html` | Django include wired to this project's `{% static %}` pipeline |
| `index.html` | Mark reference page (open in the Replit webview) |
| `verify_marks.py` | Zero-dependency QA gate — re-derives §2 geometry, §4 color, §0 prohibitions, §9 checklist from the raw SVGs |
| `serve.py` | Replit run-target: verify, then serve the reference page |

## Run on Replit

Press **Run** (configured in `.replit`), or:

```bash
python3 brand/verify_marks.py   # gate only — exit 0 = conformant, 1 = drift
python3 brand/serve.py          # gate, then serve the reference page
```

`serve.py` refuses to start if any mark is non-conformant, so drifted marks can
never be previewed or shipped.

## How consistency is enforced

1. **One vector, referenced everywhere.** Components point at the SVGs in
   `assets/`; the wordmark is never baked into an SVG (it must render live in
   `miller-banner`, §3f). The lockup lives once, in `brand.css` + the include.
2. **Tokens, not literals.** Colors, fonts, lockup ratios, and tracking are CSS
   custom properties in `brand.css`. Never hard-code `#8C6A3F` in a component —
   use `var(--intrustum-bronze)`.
3. **An executable contract.** `verify_marks.py` parses each SVG and asserts the
   canonical relationships numerically, e.g.:
   - keystone top/bottom/height = 0.52 / 0.30 / 0.44 of the field (§2, §9.1);
   - seal keystone top width = 0.44 × inner-ring diameter (§3c);
   - seal rings at r=64 and r=96, ring text set in Interface (§9.2/§9.3);
   - die variant colorless with no inner ring, `MMXXIII` only (§9.5);
   - no gradients / shadows / filters on any mark (§0);
   - **served copies are byte-identical to `brand/assets`** (§9.6).

   Wire it into CI so drift is caught before merge.

## Using the lockup on the site (Django)

The kit's assets are already mirrored into this project's static tree:

- `cl/assets/static-global/svg/intrustum/*.svg`
- `cl/assets/static-global/css/intrustum.css`
- `cl/assets/templates/includes/_intrustum_lockup.html`

Load the stylesheet once in `base.html`:

```django
<link href="{{ STATIC_PREFIX }}css/intrustum.css" rel="stylesheet">
```

Point the favicon at the mark:

```django
<link rel="icon" href="{% static 'svg/intrustum/favicon.svg' %}">
```

Drop the lockup wherever the brand appears (e.g. the navbar):

```django
{% include "includes/_intrustum_lockup.html" %}
{% include "includes/_intrustum_lockup.html" with variant="running" %}
{% include "includes/_intrustum_lockup.html" with descriptor="Governed Matter Administration & Recovery" %}
```

> After editing any asset in `brand/assets/`, re-copy into the static tree
> (`cp brand/assets/*.svg cl/assets/static-global/svg/intrustum/`) and re-run
> the verifier — the sync check (§9.6) will otherwise fail.

## Standing rules (handoff §0)

No eagles, shields, stars, scales, columns, state outlines, or dollar glyphs; no
gradients, bevels, or drop shadows on the marks; never caption the seal
"certified/approved/accredited"; ™ only, never ®. Print bronze is PANTONE 872 C
(metallic) / 4515 C (flat); CMYK fallback 40/48/78/22. Nothing in `assets/`
changes without a handoff version bump.
