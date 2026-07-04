#!/usr/bin/env python3
"""
Wire the Intrustum brand kit into this Django site's base template.

Idempotent: safe to run repeatedly. Each edit is guarded by an `INTRUSTUM-KIT`
marker, so a second run is a no-op. Reverses cleanly with `git checkout`.

Edits cl/assets/templates/base.html to:
  1. load css/intrustum.css (tokens + lockup),
  2. point the favicon at the block mark,
  3. replace the navbar CourtListener logos with the Intrustum lockup.

Run via brand/install.sh, or directly:  python3 brand/wire_into_site.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "cl" / "assets" / "templates" / "base.html"
MARKER = "INTRUSTUM-KIT"


def patch_css(html: str) -> tuple[str, str]:
    if f"{MARKER}: stylesheet" in html:
        return html, "css       already present"
    anchor = '<link href="{{ STATIC_PREFIX }}css/font-awesome.css" rel="stylesheet">'
    if anchor not in html:
        return html, "css       SKIP (font-awesome anchor not found)"
    inject = (
        anchor
        + '\n  {# ' + MARKER + ': stylesheet #}'
        + '\n  <link href="{{ STATIC_PREFIX }}css/intrustum.css" rel="stylesheet">'
    )
    return html.replace(anchor, inject, 1), "css       wired"


def patch_favicon(html: str) -> tuple[str, str]:
    if f"{MARKER}: favicon" in html:
        return html, "favicon   already present"
    anchor = "{% block icons %}"
    if anchor not in html:
        return html, "favicon   SKIP (icons block not found)"
    inject = (
        anchor
        + '\n  {# ' + MARKER + ': favicon #}'
        + "\n  <link rel=\"icon\" type=\"image/svg+xml\""
        + " href=\"{% static 'svg/intrustum/favicon.svg' %}\">"
    )
    return html.replace(anchor, inject, 1), "favicon   wired"


NAVBAR_LOCKUP = (
    '{# ' + MARKER + ': navbar lockup #}\n'
    '          <a class="navbar-brand intrustum-lockup hidden-xs" href="/"'
    ' aria-label="Intrustum — home" tabindex="1">\n'
    "            <img class=\"intrustum-lockup__mark\""
    " src=\"{% static 'svg/intrustum/mark-block.svg' %}\" alt=\"\">\n"
    '            <span class="intrustum-lockup__wordmark">Intrustum</span>\n'
    '          </a>\n'
    '          <a class="navbar-brand intrustum-lockup intrustum-lockup--running'
    ' visible-xs-block" href="/" aria-label="Intrustum — home" tabindex="1">\n'
    "            <img class=\"intrustum-lockup__mark\""
    " src=\"{% static 'svg/intrustum/mark-block.svg' %}\" alt=\"\">\n"
    '            <span class="intrustum-lockup__wordmark">Intrustum</span>\n'
    '          </a>'
)


def patch_navbar(html: str) -> tuple[str, str]:
    if f"{MARKER}: navbar lockup" in html:
        return html, "navbar    already present"
    # Match the two brand anchors (large logo + initials-only), in order.
    pattern = re.compile(
        r'<a class="navbar-brand hidden-xs".*?</a>\s*'
        r'<a class="navbar-brand visible-xs-block".*?</a>',
        re.DOTALL,
    )
    if not pattern.search(html):
        return html, "navbar    SKIP (brand anchors not found — wire manually)"
    return pattern.sub(NAVBAR_LOCKUP, html, count=1), "navbar    wired"


def main() -> int:
    if not BASE.exists():
        print(f"base template not found: {BASE}")
        return 1
    html = BASE.read_text(encoding="utf-8")
    original = html
    notes = []
    for fn in (patch_css, patch_favicon, patch_navbar):
        html, note = fn(html)
        notes.append(note)

    for n in notes:
        print(f"  {n}")

    if any("SKIP" in n for n in notes):
        print("\nOne or more anchors were not found; edit base.html by hand for those "
              "(see brand/README.md). No partial write performed.")
        return 1
    if html != original:
        BASE.write_text(html, encoding="utf-8")
        print(f"\nUpdated {BASE.relative_to(ROOT)}")
    else:
        print("\nNothing to do — base.html already wired.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
