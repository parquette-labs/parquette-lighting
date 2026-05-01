"""Cross-reference every UI widget's OSC address against the set of
addresses actually registered on the running server.

The UI is only useful if moving a control produces a message the server
understands. Refactors that rename an OSCParam without renaming the
matching widget (or vice versa) silently break features; this test
catches that class of regression.
"""

from __future__ import annotations

from typing import List

import pytest

from tests.conftest import VALUE_BEARING_WIDGET_TYPES, ServerContext, Widget

# Concrete addresses in layout-config.json that are intentionally *not*
# backed by a server handler. Add entries with a comment explaining why.
KNOWN_UI_ONLY_ADDRESSES: set[str] = {
    # Scene selector dropdown uses onValue script to send to /scene/{name};
    # its own address is only used to receive values updates from the server.
    "/scene_selector",
}


def _widget_addresses_to_check(widgets: List[Widget]) -> List[tuple[str, Widget]]:
    """Return (resolved_address, widget) pairs that must have server handlers."""

    pairs: List[tuple[str, Widget]] = []
    for w in widgets:
        if w.type not in VALUE_BEARING_WIDGET_TYPES:
            continue
        addr = w.resolved_address
        if addr is None or addr == "":
            continue
        # Bypass skips messages — these widgets are intentionally UI-only.
        if w.raw.get("bypass") is True:
            continue
        # `address: "@{other}"` redirects to another widget; not a server addr.
        if addr.startswith("@"):
            continue
        # Patchbay uses its own messaging model (inputs/outputs arrays
        # rather than a single address that a handler listens on).
        if w.type == "patchbay":
            continue
        # Visualizer faders are display-only: the server pushes fixture
        # state TO them but never listens for input FROM them.
        if addr.startswith("/visualizer/fixture/") or addr.startswith(
            "/visualizer/fftgen"
        ):
            continue
        pairs.append((addr, w))
    return pairs


def test_every_ui_address_has_server_handler(
    server_instance: ServerContext,
    layout_widgets: List[Widget],
) -> None:
    """Every value-bearing widget's OSC address must be matched by at least
    one handler registered on the server's dispatcher."""

    dispatcher = server_instance.osc.dispatcher
    orphans: List[str] = []

    seen_addresses: set[str] = set()
    for addr, widget in _widget_addresses_to_check(layout_widgets):
        if addr in seen_addresses:
            continue
        seen_addresses.add(addr)
        if addr in KNOWN_UI_ONLY_ADDRESSES:
            continue
        handlers = dispatcher.handlers_for_address(addr)
        if not list(handlers):
            orphans.append(f"{addr} (widget id={widget.id!r} type={widget.type})")

    assert not orphans, (
        "UI widgets whose OSC address has no matching server handler — "
        "either the server param was renamed/removed, or the widget "
        "address is wrong:\n  " + "\n  ".join(sorted(orphans))
    )


def test_registered_addresses_accessor_matches_dispatcher(
    server_instance: ServerContext,
) -> None:
    """Smoke test for the `OSCManager.registered_addresses()` helper."""

    addrs = server_instance.osc.registered_addresses()
    assert isinstance(addrs, list)
    assert len(addrs) > 0
    # Every returned address should actually resolve in the dispatcher.
    for addr in addrs[:10]:
        # Addresses returned here are the *patterns* registered, not concrete
        # messages. Patterns with wildcards won't self-match via
        # handlers_for_address, so we just sanity-check non-wildcard ones.
        if any(ch in addr for ch in "*?[{"):
            continue
        handlers = server_instance.osc.dispatcher.handlers_for_address(addr)
        assert list(handlers), f"Pattern {addr!r} resolves to no handlers"


@pytest.mark.parametrize(
    "expected_pattern",
    [
        "/preset/save/reds",
        "/preset/clear/reds",
        "/preset/selector/reds",
        "/visualizer/enable_fft",
        "/visualizer/enable_synth",
        "/visualizer/enable_fixture",
        "/scene/all_black",
        "/scene/house_lights",
        "/scene/class_lights",
        "/reds_master",
    ],
)
def test_known_critical_addresses_have_handlers(
    server_instance: ServerContext, expected_pattern: str
) -> None:
    """Pin the addresses the UI relies on for its headline workflows so a
    refactor that deletes them fails loudly."""

    handlers = server_instance.osc.dispatcher.handlers_for_address(expected_pattern)
    assert list(handlers), f"No handler registered for {expected_pattern!r}"
