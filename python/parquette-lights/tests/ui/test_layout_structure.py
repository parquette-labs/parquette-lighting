"""Static checks on `open-stage-control/layout-config.json`.

These tests catch regressions that don't need a browser or running server:
duplicate widget IDs (which cause OSC address collisions), overlapping
siblings, children exceeding their parent, and missing `patchbay` CSS.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

import pytest

from tests.conftest import Widget

# Containers whose direct children share a coordinate space and should not
# overlap with each other. `tab` and `panel`-with-tabs are rendered one-at-a-
# time, so their siblings inside the *parent* do overlap by design — they're
# excluded as parents in the overlap check.
OVERLAP_CONTAINER_TYPES = {"panel"}

# Parent types to skip when checking "child fits inside parent": root-level
# tabs have no fixed geometry, and scrollable panels are free to have
# children exceed the visible bounds.
FIT_IN_PARENT_SKIP_TYPES = {"tab", "root"}

# Child widget types that we never overlap-check — they're ephemeral or
# auto-positioned at runtime.
OVERLAP_IGNORE_CHILD_TYPES = {"variable"}

# Sub-pixel overlaps come from fractional grid-layout positions and don't
# render as actual visual overlaps.
OVERLAP_EPSILON = 0.5

# Intentionally co-located widget pairs. Each entry is a frozenset of two
# widget IDs: when both appear as siblings inside the same container, the
# overlap check skips them.
ALLOWED_OVERLAYS: set = {
    # Loop reds: origin fader overlays the input fader.
    frozenset({"loop_reds_origin", "gen/LoopGenerator/loop_reds/input"}),
    # FFT visualizer: the bounds multixy widgets sit on top of the FFT plot
    # so the user can drag frequency band boundaries on the audio view.
    frozenset({"visualizer/fft", "gen/FFTGenerator/fft_1/bounds"}),
    frozenset({"visualizer/fft", "gen/FFTGenerator/fft_2/bounds"}),
    # Pantilt XY pads intentionally overlap their own text labels (user layout).
    frozenset({"chan/spot_1/pantilt/offset", "spot_1_pantilt_offset_label"}),
    frozenset({"chan/spot_1/pantilt_fine/offset", "spot_1_pantilt_fine_offset_label"}),
    # Nudge buttons sit at the edges of the XY pads; the gap between spot 1
    # and spot 2 is too narrow for two side-by-side buttons without overlap.
    frozenset({"chan/spot_1/pantilt/offset", "spot_2_pantilt_nudge_left"}),
    frozenset({"chan/spot_2/pantilt/offset", "spot_1_pantilt_nudge_right"}),
    frozenset({"spot_1_pantilt_nudge_right", "spot_2_pantilt_nudge_left"}),
}

# Minimum required css fragments for a patchbay widget per CLAUDE.md.
# Match what the shared block actually uses (width:30% for the input/output
# node panels, break-word for long-label wrapping via word-break/overflow-wrap).
PATCHBAY_REQUIRED_CSS_TOKENS = ("width: 30%", "break-word")

# Widget IDs that are allowed to appear multiple times. The master faders
# and their level readouts are intentionally cloned across several tabs
# (e.g. tab_preset and tab_master_levelss) so the user can reach them from
# wherever they are in the UI; Open Stage Control keeps the copies in sync.
ALLOWED_DUPLICATE_IDS = {
    "reds_master",
    "reds_master_level_text",
    "plants_master",
    "plants_master_text",
    "booth_master",
    "booth_master_text",
    "spots_light_master",
    "spots_light_master_text",
    "washes_master",
    "washes_master_text",
    "chan/sodium/dimming/offset",
}


def _numeric(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _rect(w: Widget) -> Optional[Tuple[float, float, float, float]]:
    """Return (top, left, bottom, right) in pixels, or None if any side
    isn't a concrete numeric value (e.g. "auto")."""

    top = _numeric(w.top)
    left = _numeric(w.left)
    width = _numeric(w.width)
    height = _numeric(w.height)
    if None in (top, left, width, height):
        return None
    assert top is not None and left is not None
    assert width is not None and height is not None
    return (top, left, top + height, left + width)


def _rects_overlap(
    a: Tuple[float, float, float, float],
    b: Tuple[float, float, float, float],
) -> bool:
    a_top, a_left, a_bot, a_right = a
    b_top, b_left, b_bot, b_right = b
    # Treat sub-pixel overlaps as non-overlaps — they come from fractional
    # grid-layout positions and don't render as visible overlap.
    if a_right - b_left <= OVERLAP_EPSILON or b_right - a_left <= OVERLAP_EPSILON:
        return False
    if a_bot - b_top <= OVERLAP_EPSILON or b_bot - a_top <= OVERLAP_EPSILON:
        return False
    return True


def test_widget_ids_globally_unique(layout_widgets: List[Widget]) -> None:
    """Duplicate IDs cause widgets to receive each other's OSC values
    (CLAUDE.md flags this as a real bug source)."""

    ids = [w.id for w in layout_widgets if w.id]
    counts = Counter(ids)
    duplicates = {
        wid: n
        for wid, n in counts.items()
        if n > 1 and wid not in ALLOWED_DUPLICATE_IDS
    }
    assert not duplicates, (
        "Duplicate widget IDs in layout-config.json "
        "(Open Stage Control will route OSC to all of them): "
        f"{sorted(duplicates.items())}"
    )


def test_patchbay_widgets_have_shared_css(layout_widgets: List[Widget]) -> None:
    """Every `patchbay` must carry the shared CSS block that widens node
    panels and word-wraps long labels (CLAUDE.md convention)."""

    missing: List[str] = []
    for w in layout_widgets:
        if w.type != "patchbay":
            continue
        css = w.raw.get("css") or ""
        if not all(token in css for token in PATCHBAY_REQUIRED_CSS_TOKENS):
            missing.append(w.id or "<unnamed>")
    assert not missing, (
        "Patchbay widgets missing the shared CSS block (see CLAUDE.md): " f"{missing}"
    )


def test_siblings_do_not_overlap(layout_widgets: List[Widget]) -> None:
    """Within every overlap-checkable container, no two children's bounding
    boxes overlap. Only widgets with fully-numeric geometry are considered."""

    by_parent: Dict[Optional[str], List[Widget]] = defaultdict(list)
    for w in layout_widgets:
        by_parent[w.parent_id].append(w)
    widget_by_id = {w.id: w for w in layout_widgets if w.id is not None}

    conflicts: List[str] = []
    for parent_id, children in by_parent.items():
        if parent_id is None:
            continue
        parent = widget_by_id.get(parent_id)
        if parent is None or parent.type not in OVERLAP_CONTAINER_TYPES:
            continue

        rects: List[Tuple[Widget, Tuple[float, float, float, float]]] = []
        for child in children:
            if child.type in OVERLAP_IGNORE_CHILD_TYPES:
                continue
            rect = _rect(child)
            if rect is None:
                continue
            rects.append((child, rect))

        for i, (a, ra) in enumerate(rects):
            for b, rb in rects[i + 1 :]:
                if not _rects_overlap(ra, rb):
                    continue
                if frozenset({a.id, b.id}) in ALLOWED_OVERLAYS:
                    continue
                conflicts.append(
                    f"parent={parent_id}: {a.id!r} ({a.type}) overlaps "
                    f"{b.id!r} ({b.type})"
                )

    assert not conflicts, "Overlapping siblings in layout:\n  " + "\n  ".join(conflicts)


def test_children_fit_inside_parent(layout_widgets: List[Widget]) -> None:
    """Every child with numeric geometry must fit inside its parent's
    numeric width/height. Scrollable and layout-only parents are skipped."""

    by_parent: Dict[Optional[str], List[Widget]] = defaultdict(list)
    for w in layout_widgets:
        by_parent[w.parent_id].append(w)
    widget_by_id = {w.id: w for w in layout_widgets if w.id is not None}

    overflows: List[str] = []
    for parent_id, children in by_parent.items():
        if parent_id is None:
            continue
        parent = widget_by_id.get(parent_id)
        if parent is None or parent.type in FIT_IN_PARENT_SKIP_TYPES:
            continue
        if parent.raw.get("scroll"):
            continue
        pw = _numeric(parent.width)
        ph = _numeric(parent.height)
        if pw is None or ph is None:
            continue
        for child in children:
            if child.type in OVERLAP_IGNORE_CHILD_TYPES:
                continue
            rect = _rect(child)
            if rect is None:
                continue
            top, left, bot, right = rect
            if left < 0 or top < 0 or right > pw or bot > ph:
                overflows.append(
                    f"parent={parent_id} ({pw}x{ph}): "
                    f"{child.id!r} rect=({left},{top})→({right},{bot})"
                )

    assert not overflows, "Children extending outside their parent:\n  " + "\n  ".join(
        overflows
    )


@pytest.mark.parametrize(
    "expected_id",
    [
        "tab_user_count",
        "tab_preset",
        "tab_master_levelss",
        "tab_loops",
        "tab_synth_controls",
        "tab_punch",
        "tab_hazer",
        "tab_visualizer",
        "tab_chan_offsets",
        "tab_fft_dmx",
    ],
)
def test_top_level_tabs_present(layout_widgets: List[Widget], expected_id: str) -> None:
    """Guards against accidental deletion of a top-level tab."""

    ids = {w.id for w in layout_widgets if w.type == "tab"}
    assert (
        expected_id in ids
    ), f"Top-level tab {expected_id!r} missing from layout-config.json"
