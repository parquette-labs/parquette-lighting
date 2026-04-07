#!/usr/bin/env python3
"""Strip default/auto values from open-stage-control's layout-config.json.

The OSC layout editor inflates every widget with all its properties (most
holding "auto" or empty defaults). On mobile Safari the resulting ~400KB
JSON noticeably delays first paint. Stripping defaults roughly halves the
file size with no behavioural change — the OSC server fills the same
defaults back in at load time.

Run after editing the layout in the OSC GUI editor:

    poetry run poe strip-layout
"""

import json
import os
import sys
from pathlib import Path

# Resolve layout path relative to repo root (two levels up from this file's
# parquette-lights package).
REPO_ROOT = Path(__file__).resolve().parents[3]
LAYOUT_PATH = REPO_ROOT / "open-stage-control" / "layout-config.json"

# Keys safe to drop when they hold their open-stage-control default value.
DEFAULT_DROPS = {
    "lock": False,
    "visible": True,
    "comments": "",
    "html": "",
    "css": "",
    "preArgs": "",
    "typeTags": "",
    "target": "",
    "linkId": "",
    "onCreate": "",
    "onValue": "",
    "onTouch": "",
    "onPreload": "",
    "expand": False,
    "ignoreDefaults": False,
}

# Structural / behaviour-defining keys we never touch.
KEEP_ALWAYS = {
    "type",
    "id",
    "widgets",
    "tabs",
    "value",
    "default",
    "top",
    "left",
    "width",
    "height",
    "address",
    "lazy",
}


def clean_widget(w: dict) -> int:
    stripped = 0
    for key in list(w.keys()):
        if key in KEEP_ALWAYS:
            continue
        v = w[key]
        if v == "auto":
            del w[key]
            stripped += 1
            continue
        if key in DEFAULT_DROPS and v == DEFAULT_DROPS[key]:
            del w[key]
            stripped += 1
    return stripped


def walk(node, is_root: bool = True) -> int:
    stripped = 0
    if isinstance(node, dict):
        if not is_root and node.get("type") and node.get("type") != "root":
            stripped += clean_widget(node)
        for container_key in ("widgets", "tabs"):
            for child in node.get(container_key, []) or []:
                stripped += walk(child, is_root=False)
    return stripped


def main() -> int:
    if not LAYOUT_PATH.exists():
        print(f"layout file not found: {LAYOUT_PATH}", file=sys.stderr)
        return 1

    before = os.path.getsize(LAYOUT_PATH)
    with open(LAYOUT_PATH, encoding="utf-8") as f:
        data = json.load(f)

    stripped = walk(data["content"], is_root=True)

    with open(LAYOUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    after = os.path.getsize(LAYOUT_PATH)
    pct = 100 * (before - after) / before if before else 0
    print(f"stripped {stripped} keys")
    print(f"size: {before} -> {after} bytes ({pct:.1f}% reduction)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
