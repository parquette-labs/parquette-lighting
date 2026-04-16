"""End-to-end black-box tests that drive the server over real OSC.

Covers the preset save / load lifecycle that the UI depends on:
selecting a preset, saving the current param values under its name,
mutating the values, and reloading the preset to verify they restore.
Also ticks the compute loop to verify DMX output responds to param
changes.
"""

from __future__ import annotations

from typing import Callable, Optional

from pythonosc.udp_client import SimpleUDPClient

from parquette.lights.osc import OSCParam
from tests.conftest import ServerContext

RED_CATEGORY_NAME = "reds"


def _find_numeric_param(ctx: ServerContext, category_name: str) -> Optional[OSCParam]:
    """Return the first exposed OSCParam in the given category whose current
    value is a plain number. Used to drive the save/load round-trip without
    hardcoding a specific address (that address may be renamed in the future)."""

    category = ctx.categories.by_name(category_name)
    params = ctx.exposed_params.get(category, [])
    for param in params:
        value = param.value_lambda()
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return param
    return None


def test_preset_selection_updates_current_presets(
    server_instance: ServerContext,
    osc_client: SimpleUDPClient,
    flush: Callable[..., None],
) -> None:
    """Sending /preset_selector/<cat> <name> must record the selection."""

    preset_name = "UITestSelectionProbe"
    osc_client.send_message(f"/preset/selector/{RED_CATEGORY_NAME}", preset_name)
    flush()

    assert server_instance.presets.current_presets.get(RED_CATEGORY_NAME) == preset_name


def test_preset_save_and_reload_round_trip(
    server_instance: ServerContext,
    osc_client: SimpleUDPClient,
    flush: Callable[..., None],
) -> None:
    """Setting a param, saving, mutating, and reloading must restore the
    saved value — the headline preset workflow the UI exposes."""

    param = _find_numeric_param(server_instance, RED_CATEGORY_NAME)
    assert param is not None, (
        f"No numeric OSCParam found in category {RED_CATEGORY_NAME!r}; "
        "test needs a value-bearing param to exercise save/load."
    )
    preset_name = "UITestRoundTripProbe"

    # Capture a value distinct from both the default and the value we'll
    # mutate to later, so the final assertion is unambiguous.
    raw_default = param.default_value if param.has_default else 0
    default = float(raw_default) if isinstance(raw_default, (int, float)) else 0.0
    saved_value = default + 7.0 if default <= 10 else default - 7.0
    mutated_value = saved_value + 3.0

    # Select the preset slot first so save() has somewhere to write.
    osc_client.send_message(f"/preset/selector/{RED_CATEGORY_NAME}", preset_name)
    flush()

    osc_client.send_message(param.addr, saved_value)
    flush()
    assert param.value_lambda() == saved_value, "param did not update from OSC"

    osc_client.send_message(f"/preset/save/{RED_CATEGORY_NAME}", 1)
    flush()

    osc_client.send_message(param.addr, mutated_value)
    flush()
    assert param.value_lambda() == mutated_value

    osc_client.send_message(f"/preset/selector/{RED_CATEGORY_NAME}", preset_name)
    flush()

    assert param.value_lambda() == saved_value, (
        f"preset reload did not restore {param.addr}: "
        f"expected {saved_value}, got {param.value_lambda()}"
    )


def test_master_change_drives_dmx_output(
    server_instance: ServerContext,
    osc_client: SimpleUDPClient,
    flush: Callable[..., None],
) -> None:
    """Raising the sodium offset and ticking the compute loop must put a
    non-zero value on the DMX buffer. Exercises the full UI→server→mixer
    →DMXManager path without touching hardware."""

    ctx = server_instance
    sodium = ctx.mixer.channel_lookup.get("sodium/dimming")
    assert sodium is not None, "Expected a 'sodium/dimming' mix channel"

    sodium.offset = 0
    ctx.tick()
    baseline = list(ctx.dmx.chans)

    sodium.offset = 200
    # Run several ticks to let any fixture smoothing settle into the new offset.
    for _ in range(5):
        ctx.tick()

    assert ctx.dmx.chans != baseline, (
        "DMX buffer did not change after bumping sodium offset; "
        "mixer→fixture→DMX pipeline may be broken"
    )
    assert max(ctx.dmx.chans) > 0
