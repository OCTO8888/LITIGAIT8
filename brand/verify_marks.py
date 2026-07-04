#!/usr/bin/env python3
"""
Intrustum mark verifier — enforces the Production Handoff v1.0 as executable QA.

This is the guarantee that the website reproduces the marks *consistently*: it
re-derives every geometric relationship from the raw SVG coordinates and fails
the build if any asset drifts from the canonical spec (§2 geometry, §4 color,
§0 prohibitions, §9 falsifiable checklist).

Zero dependencies — pure standard library. Run on Replit as a build/CI gate:

    python3 brand/verify_marks.py         # exit 0 = all marks conform

The contract is the handoff, not this file: change §3 assets only with a
version bump, then update the expectations below to match.
"""
from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ASSETS = Path(__file__).parent / "assets"

# -- Canonical constants (§2, §4) --------------------------------------------
INK, BRONZE, PAPER = "#1A1C20", "#8C6A3F", "#FAF8F4"
KEYSTONE = {"top_w": 0.52, "bot_w": 0.30, "height": 0.44, "top_edge": 0.281}
RATIO_TOL = 0.015          # 1.5% — absorbs coordinate rounding, honors §9.1's 1%
FORBIDDEN = ("lineargradient", "radialgradient", "<filter", "fegaussianblur",
             "drop-shadow", "feoffset", "fedropshadow")

_NUM = re.compile(r"-?\d*\.?\d+")


class Fail(Exception):
    pass


# -- Minimal absolute-path tokenizer (handles M/L/H/V/Z used by our assets) ---
def subpaths(d: str) -> list[list[tuple[float, float]]]:
    """Return each subpath as a list of (x, y) vertices."""
    tokens = re.findall(r"[MLHVZmlhvz]|-?\d*\.?\d+", d)
    paths: list[list[tuple[float, float]]] = []
    cur: list[tuple[float, float]] = []
    x = y = 0.0
    i, cmd = 0, None
    while i < len(tokens):
        t = tokens[i]
        if t in "MLHVZmlhvz":
            cmd = t
            i += 1
            if cmd in "Zz":
                if cur:
                    paths.append(cur)
                    cur = []
            continue
        if cmd in ("M", "L"):
            x, y = float(tokens[i]), float(tokens[i + 1]); i += 2
            if cmd == "M" and cur:
                paths.append(cur); cur = []
            cur.append((x, y))
            cmd = "L" if cmd == "M" else cmd  # implicit lineto after moveto
        elif cmd == "H":
            x = float(tokens[i]); i += 1; cur.append((x, y))
        elif cmd == "V":
            y = float(tokens[i]); i += 1; cur.append((x, y))
        else:  # lowercase / unsupported relative — our assets never use these
            raise Fail(f"unsupported path command {cmd!r}")
    if cur:
        paths.append(cur)
    return paths


def keystone_metrics(pts: list[tuple[float, float]]) -> dict:
    """Given the 4 keystone corners, derive its trapezoid measurements."""
    ys = sorted({round(p[1], 3) for p in pts})
    top_y, bot_y = ys[0], ys[-1]
    top = [p[0] for p in pts if abs(p[1] - top_y) < 1e-6]
    bot = [p[0] for p in pts if abs(p[1] - bot_y) < 1e-6]
    return {
        "top_w": max(top) - min(top),
        "bot_w": max(bot) - min(bot),
        "height": bot_y - top_y,
        "top_edge": top_y,
        "top_center": (max(top) + min(top)) / 2,
        "bot_center": (max(bot) + min(bot)) / 2,
    }


def approx(actual: float, expected: float, tol: float, what: str) -> None:
    if expected == 0:
        ok = abs(actual) <= tol
    else:
        ok = abs(actual - expected) / abs(expected) <= tol
    if not ok:
        raise Fail(f"{what}: got {actual:.4g}, want {expected:.4g} (±{tol:.1%})")


def load(name: str) -> tuple[ET.Element, str]:
    p = ASSETS / name
    if not p.exists():
        raise Fail(f"missing asset {name}")
    raw = p.read_text(encoding="utf-8")
    low = raw.lower()
    for bad in FORBIDDEN:
        if bad in low:
            raise Fail(f"prohibited effect {bad!r} present (§0: no gradients/"
                       f"bevels/shadows on the marks)")
    return ET.fromstring(raw), raw


def keystone_path(root: ET.Element) -> list[tuple[float, float]]:
    """The keystone is the smallest 4-corner quad (block mark's compound path
    also contains the full field square, which we must exclude)."""
    ns = "{http://www.w3.org/2000/svg}"
    quads = []
    for el in root.findall(f".//{ns}path"):
        try:
            sps = subpaths(el.get("d", ""))
        except (Fail, IndexError):
            continue  # arc/curve paths (e.g. seal textPath rails) — not the keystone
        for sp in sps:
            if len(sp) == 4:
                xs = [p[0] for p in sp]; ys = [p[1] for p in sp]
                area = (max(xs) - min(xs)) * (max(ys) - min(ys))
                quads.append((area, sp))
    if not quads:
        raise Fail("no 4-corner keystone path found")
    return min(quads, key=lambda q: q[0])[1]


def check_keystone(name: str, side: float) -> None:
    root, _ = load(name)
    m = keystone_metrics(keystone_path(root))
    approx(m["top_w"] / side, KEYSTONE["top_w"], RATIO_TOL, f"{name} top width/s")
    approx(m["bot_w"] / side, KEYSTONE["bot_w"], RATIO_TOL, f"{name} bottom width/s")
    approx(m["height"] / side, KEYSTONE["height"], RATIO_TOL, f"{name} height/s")
    approx(m["top_edge"] / side, KEYSTONE["top_edge"], RATIO_TOL, f"{name} top edge/s")
    approx(m["top_center"], side / 2, RATIO_TOL, f"{name} top centered")
    approx(m["bot_center"], side / 2, RATIO_TOL, f"{name} bottom centered")


def colors(raw: str) -> set[str]:
    return {c.upper() for c in re.findall(r"#[0-9A-Fa-f]{6}", raw)}


# -- Checks (mirror §9 QA checklist) -----------------------------------------
def check_block_mark():
    # §9.1 keystone 0.52/0.30/0.44 within 1%; §4 exactly two brand colors.
    check_keystone("mark-block.svg", 96.0)
    root, raw = load("mark-block.svg")
    assert INK in colors(raw), "block mark must use ink #1A1C20"
    if root.get("viewBox") != "0 0 96 96":
        raise Fail("mark-block viewBox must be 0 0 96 96")


def check_outline_mark():
    check_keystone("mark-outline.svg", 96.0)
    _, raw = load("mark-outline.svg")
    got = colors(raw)
    assert INK in got and BRONZE in got, "outline mark needs ink stroke + bronze keystone"


def check_seal_full():
    # Keystone scaled to the INNER field (§3c, §1.4): top width = 0.44 * inner Ø.
    root, raw = load("seal-full.svg")
    ns = "{http://www.w3.org/2000/svg}"
    radii = sorted(float(c.get("r")) for c in root.findall(f".//{ns}circle"))
    if radii != sorted((64.0, 96.0)):
        raise Fail(f"seal rings must be r=64 & r=96, got {radii}")
    inner_d = 2 * min(radii)
    m = keystone_metrics(keystone_path(root))
    approx(m["top_w"] / inner_d, 0.44, RATIO_TOL, "seal keystone top / inner Ø")
    approx(m["top_center"], 100.0, RATIO_TOL, "seal keystone centered on axis")
    got = colors(raw)
    assert INK in got and BRONZE in got, "seal must use ink + bronze only"
    if PAPER in got:
        raise Fail("seal must not paint the paper field; leave it transparent")
    # Ring text must read the wordmark + jurisdiction, in Interface (§1.3).
    texts = " ".join(t.text or "" for t in root.iter() if (t.text or "").strip())
    for word in ("INTRUSTUM", "TEXAS", "MMXXIII"):
        assert word in texts, f"seal ring text missing {word!r}"
    for fam in root.findall(f".//{ns}text"):
        if "interface" not in (fam.get("font-family") or "").lower():
            raise Fail("ring text must be set in Interface (§1.3/§9.3)")


def check_seal_micro():
    root, raw = load("seal-micro.svg")
    ns = "{http://www.w3.org/2000/svg}"
    # No inner ring at micro size; single outer ring + bronze keystone.
    circles = root.findall(f".//{ns}circle")
    if len(circles) != 1:
        raise Fail("micro seal carries exactly one ring")
    assert BRONZE in colors(raw), "micro seal keystone is bronze"


def check_seal_die():
    # §9.5 / §3d: single color, no inner ring, MMXXIII only, colorless die.
    root, raw = load("seal-die.svg")
    ns = "{http://www.w3.org/2000/svg}"
    if len(root.findall(f".//{ns}circle")) != 1:
        raise Fail("die variant must delete the fine inner ring (§3d)")
    palette = colors(raw) | set(re.findall(r"#[0-9A-Fa-f]{3}\b", raw))
    brand = {INK, BRONZE, PAPER}
    if palette & brand:
        raise Fail("die is colorless — must not carry brand colors, only #000")
    texts = " ".join(t.text or "" for t in root.iter() if (t.text or "").strip())
    assert texts.strip() == "MMXXIII", "die ring text is MMXXIII only (§3d)"


def check_served_copies_in_sync():
    """The website must serve the canonical bytes, not a re-drawn copy. Assert
    the Django static tree (if present) is byte-identical to brand/assets."""
    served = ASSETS.parent.parent / "cl" / "assets" / "static-global" / "svg" / "intrustum"
    if not served.exists():
        return  # kit not yet wired into this project's static tree — nothing to drift
    for svg in ASSETS.glob("*.svg"):
        mirror = served / svg.name
        if not mirror.exists():
            raise Fail(f"served copy missing: {mirror}")
        if mirror.read_bytes() != svg.read_bytes():
            raise Fail(f"served {svg.name} differs from canonical brand/assets — "
                       f"re-copy, never hand-edit the served copy")


CHECKS = [
    ("block mark keystone 0.52/0.30/0.44 (§9.1)", check_block_mark),
    ("outline mark keystone (§3b)", check_outline_mark),
    ("full seal geometry, rings & Interface text (§3c/§9.2/§9.3)", check_seal_full),
    ("micro seal — single ring, bronze keystone (§3e)", check_seal_micro),
    ("deboss die — colorless, no inner ring, MMXXIII (§3d/§9.5)", check_seal_die),
    ("served copies byte-identical to canonical (§9.6)", check_served_copies_in_sync),
]


def main() -> int:
    failures = 0
    for label, fn in CHECKS:
        try:
            fn()
        except (Fail, AssertionError) as e:
            failures += 1
            print(f"  \033[31mFAIL\033[0m  {label}\n          {e}")
        else:
            print(f"  \033[32m OK \033[0m  {label}")
    print()
    if failures:
        print(f"Intrustum marks NON-CONFORMANT — {failures} check(s) failed.")
        return 1
    print("All Intrustum marks conform to Production Handoff v1.0.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
