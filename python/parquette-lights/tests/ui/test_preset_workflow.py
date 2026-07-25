"""End-to-end black-box tests that drive the server over real OSC.

Covers the preset save / load lifecycle that the UI depends on:
selecting a preset, saving the current param values under its name,
mutating the values, and reloading the preset to verify they restore.
Also ticks the compute loop to verify DMX output responds to param
changes.
"""

from __future__ import annotations

import shutil
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


def save_scene_via_ui(
    osc_client: SimpleUDPClient, flush: Callable[..., None], name: str
) -> None:
    """Save a scene the way the UI does after the reliability fix: the name
    field streams its committed value to /scene_name_input, then the Save
    button fires a bare /scene/create that uses the server's staged name."""

    osc_client.send_message("/scene_name_input", name)
    flush()
    osc_client.send_message("/scene/create", 1)
    flush()


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


def test_restore_defaults_resets_scenes_to_snapshot(
    server_instance: ServerContext,
    osc_client: SimpleUDPClient,
    flush: Callable[..., None],
) -> None:
    """/preset/restore_defaults must reload scenes from the defaults snapshot:
    scenes present in the snapshot come back, and user scenes created after the
    snapshot are dropped. Exercises the shared restore message that the preset
    restore button sends."""

    sm = server_instance.scene_manager

    # Create a baseline user scene and snapshot it as the restore default,
    # mirroring what deploy's snapshot_defaults() does on the remote.
    save_scene_via_ui(osc_client, flush, "RestoreBaseline")
    assert "RestoreBaseline" in sm.scenes
    shutil.copyfile(sm.filename, sm.defaults_file)

    # A scene created after the snapshot should not survive the restore.
    save_scene_via_ui(osc_client, flush, "RestoreTransient")
    assert "RestoreTransient" in sm.scenes

    osc_client.send_message("/preset/restore_defaults", 1)
    flush()

    assert "RestoreBaseline" in sm.scenes
    assert "RestoreTransient" not in sm.scenes


def test_scene_save_uses_staged_name(
    server_instance: ServerContext,
    osc_client: SimpleUDPClient,
    flush: Callable[..., None],
) -> None:
    """A bare /scene/create saves under the name last staged via
    /scene_name_input. This is the server-side name capture that replaced the
    racy client-side read of the text field (which dropped or truncated
    names, e.g. 'Red Disco' -> 'Re')."""

    sm = server_instance.scene_manager

    save_scene_via_ui(osc_client, flush, "Red Disco")
    assert "Red Disco" in sm.scenes, "staged name was not used for /scene/create"

    # Re-staging a new name and creating must save the full new name, not a
    # stale or partial one.
    save_scene_via_ui(osc_client, flush, "Blue Groove")
    assert "Blue Groove" in sm.scenes
    assert "Red Disco" in sm.scenes  # earlier scene untouched

    # A create with an empty staged name must be a no-op, not save a blank.
    before = set(sm.scenes)
    osc_client.send_message("/scene_name_input", "")
    flush()
    osc_client.send_message("/scene/create", 1)
    flush()
    assert set(sm.scenes) == before, "empty staged name should not create a scene"
