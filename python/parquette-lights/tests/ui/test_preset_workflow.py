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

from parquette.lights.fixtures.spotlights import Spot
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
    field's commit sends /scene/create with its value, so the name and the
    save trigger arrive as one atomic message (no cross-message race)."""

    osc_client.send_message("/scene/create", name)
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


def test_scene_save_creates_named_scene(
    server_instance: ServerContext,
    osc_client: SimpleUDPClient,
    flush: Callable[..., None],
) -> None:
    """/scene/create carries the scene name in a single message (the field's
    own commit), so the full name is saved atomically — no cross-message race,
    no partial or dropped names (the 'Red Disco' -> 'Re' bug)."""

    sm = server_instance.scene_manager

    save_scene_via_ui(osc_client, flush, "Red Disco")
    assert "Red Disco" in sm.scenes, "scene name from /scene/create was not saved"

    save_scene_via_ui(osc_client, flush, "Blue Groove")
    assert "Blue Groove" in sm.scenes
    assert "Red Disco" in sm.scenes  # earlier scene untouched

    # An empty name must be a no-op, not create a blank scene.
    before = set(sm.scenes)
    osc_client.send_message("/scene/create", "")
    flush()
    assert set(sm.scenes) == before, "empty name should not create a scene"


def test_non_house_scenes_zero_sodium(
    server_instance: ServerContext,
    osc_client: SimpleUDPClient,
    flush: Callable[..., None],
) -> None:
    """House Lights keeps sodium raised; every other scene -- including
    user-created ones, which never capture sodium -- drops it to zero via the
    SceneManager default offset."""

    ctx = server_instance
    sodium = ctx.mixer.channel_lookup.get("sodium/dimming")
    assert sodium is not None, "expected a 'sodium/dimming' mix channel"

    osc_client.send_message("/scene/house_lights", 1)
    flush()
    assert sodium.offset > 0, "house_lights should raise sodium"

    # A user scene (no captured sodium) must reset it on activation.
    save_scene_via_ui(osc_client, flush, "SodiumProbe")
    sodium.offset = 200
    osc_client.send_message("/scene/SodiumProbe", 1)
    flush()
    assert sodium.offset == 0, "a user scene should zero the sodium offset"

    # class_lights is also non-House -> sodium zeroed.
    sodium.offset = 200
    osc_client.send_message("/scene/class_lights", 1)
    flush()
    assert sodium.offset == 0, "class_lights should zero the sodium offset"


def test_scene_update_captures_new_preset_selection(
    server_instance: ServerContext,
    osc_client: SimpleUDPClient,
    flush: Callable[..., None],
) -> None:
    """Re-saving an existing scene must capture the CURRENT preset selection,
    not the one from when the scene was first saved. The server-side update
    (create_scene overwriting by name) has always worked -- this pins that
    contract down; the reported "update doesn't stick" bug was in the Save
    button, which failed to send /scene/create when the name field was
    pre-filled by selecting a scene rather than typed."""

    sm = server_instance.scene_manager
    reds = server_instance.categories.by_name(RED_CATEGORY_NAME)

    osc_client.send_message(f"/preset/selector/{RED_CATEGORY_NAME}", "UpdatePresetOne")
    flush()
    save_scene_via_ui(osc_client, flush, "UpdateProbe")
    scene = sm.find_scene("UpdateProbe")
    assert scene is not None and scene.presets_by_category is not None
    assert scene.presets_by_category[reds] == "UpdatePresetOne"

    # Change the selection and re-save under the SAME name (an update).
    osc_client.send_message(f"/preset/selector/{RED_CATEGORY_NAME}", "UpdatePresetTwo")
    flush()
    save_scene_via_ui(osc_client, flush, "UpdateProbe")
    scene = sm.find_scene("UpdateProbe")
    assert scene is not None and scene.presets_by_category is not None
    assert (
        scene.presets_by_category[reds] == "UpdatePresetTwo"
    ), "re-saving an existing scene did not capture the new preset selection"


def test_master_fade_starts_from_current_master(
    server_instance: ServerContext,
    osc_client: SimpleUDPClient,
    flush: Callable[..., None],
) -> None:
    """A scene fade must interpolate the master from its CURRENT value, not a
    stale master_interp value. A direct write (what the UI master fader does via
    OSCParam.obj_param_setter) used to leave master_interp.current stale, so the
    next scene fade jumped the master -- and thus spot brightness -- to that
    stale value at the start of the crossfade."""

    cat = server_instance.categories.spots_light

    # Simulate a UI master fader move: a direct field write, exactly what
    # OSCParam.obj_param_setter does for a bound plain attribute.
    cat.master = 0.8
    assert cat.master == 0.8

    # A scene now crossfades the master down to 0.5 over 10 ticks.
    cat.set_master(0.5, fade_ticks=10)
    cat.tick_interpolator()

    # One tick of a 0.8 -> 0.5 fade should ease the master slightly below 0.8;
    # it must NOT jump upward toward a stale interpolator value.
    assert (
        0.5 <= cat.master < 0.8
    ), f"master jumped to {cat.master} at fade start instead of easing from 0.8"

    # Leave a clean, non-fading state so session-scoped siblings are unaffected.
    cat.master = 1.0


def test_spot_color_swap_dips_then_fades_up(
    server_instance: ServerContext,
    osc_client: SimpleUDPClient,
    flush: Callable[..., None],
) -> None:
    """A moving-head colour change over a scene fade runs a tick-based dip:
    the multiplier fades out to 0, the wheel swaps only while dark, holds for
    the mechanical settle, then fades back to 1. fade_out = fade_in =
    (fade_ticks - dark_gap) / 2, dark_gap = the wheel-change time."""

    spot = next((f for f in server_instance.all_fixtures if isinstance(f, Spot)), None)
    assert spot is not None, "expected a moving-head Spot fixture"

    spot.color_swap_mechanical_time = 0.1  # 5 ticks at 20 ms
    spot.color_index_value = 0
    spot._dimming = 200
    spot.color_swap_fade_multiplier = 1.0
    spot.swap_phase = "idle"

    # Kick off a swap to a different colour over a 20-tick scene fade, the way
    # a preset load does (pending_fade_ticks set around the color_index write).
    spot.pending_fade_ticks = 20
    spot.color(3)
    spot.pending_fade_ticks = 0

    # (20 - 5) / 2 = 7 ticks per side.
    assert spot.swap_phase == "fade_out"
    assert spot.swap_fade_out_ticks == 7
    assert spot.swap_settle_ticks == 5
    assert spot.swap_fade_in_ticks == 7

    mults = []
    swap_tick = None
    for i in range(30):
        spot.tick_interpolators()
        mults.append(spot.color_swap_fade_multiplier)
        if spot.color_index_value == 3 and swap_tick is None:
            swap_tick = i

    assert min(mults) == 0.0, "spot never dipped fully to black"
    # The wheel swaps only after the fade-out completes (while dark).
    assert swap_tick is not None and swap_tick == 6
    assert mults[swap_tick] == 0.0, "wheel swapped while still lit"
    # Fades back up and settles.
    assert spot.color_swap_fade_multiplier == 1.0
    assert spot.swap_phase == "idle"
    assert spot.color_index_value == 3

    # Same colour with a fade must NOT dip -- just a normal (no-op) fade.
    spot.swap_phase = "idle"
    spot.color_swap_fade_multiplier = 1.0
    spot.pending_fade_ticks = 20
    spot.color(3)
    spot.pending_fade_ticks = 0
    assert spot.swap_phase == "idle", "unchanged colour should not trigger a dip"
