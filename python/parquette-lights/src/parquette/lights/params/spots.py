from typing import Any, List

from ..generators import SignalPatchParam
from ..osc import OSCParam
from .deps import ParamDeps


# pylint: disable=protected-access
def build_lights(deps: ParamDeps) -> List[OSCParam]:
    osc = deps.osc
    sin_spot = deps.sin_spot

    params: List[OSCParam] = [
        SignalPatchParam(
            osc,
            "/signal_patchbay/spots_light",
            ["tung_spot.dimming", "spot_1.dimming", "spot_2.dimming"],
            deps.mixer,
        ),
        OSCParam.bind(osc, "/sin_spot_amp", sin_spot, "amp"),
        OSCParam.bind(osc, "/sin_spot_period", sin_spot, "period"),
    ]

    for i, fixture in enumerate(deps.spotlights):
        params.append(
            OSCParam(
                osc,
                "/spot_color_{}".format(i + 1),
                lambda fixture=fixture: fixture.color_index,
                lambda _, args, fixture=fixture: fixture.color(args),
            )
        )
        params.append(
            OSCParam(
                osc,
                "/spot_pattern_{}".format(i + 1),
                lambda fixture=fixture: fixture.pattern_index,
                lambda _, args, fixture=fixture: fixture.pattern(args),
            )
        )
        params.append(
            OSCParam(
                osc,
                "/spot_prisim_{}".format(i + 1),
                lambda fixture=fixture: fixture.prisim_enabled,
                lambda _, args, fixture=fixture: fixture.prisim(
                    args, fixture.prisim_rotation
                ),
            )
        )
        params.append(
            OSCParam(
                osc,
                "/spot_prisim_rotation_{}".format(i + 1),
                lambda fixture=fixture: fixture.prisim_rotation,
                lambda _, args, fixture=fixture: fixture.prisim(
                    fixture.prisim_enabled, args
                ),
            )
        )
    return params


def build_position(deps: ParamDeps) -> List[OSCParam]:
    osc = deps.osc
    spot_pos_gens = [
        deps.sin_spot_pos_1,
        deps.sin_spot_pos_2,
        deps.sin_spot_pos_3,
        deps.sin_spot_pos_4,
    ]

    # Build the list of pan/tilt channel names from spotlights
    pos_chan_names = []
    for fixture in deps.spotlights:
        pos_chan_names.append("{}.pan".format(fixture.name))
        pos_chan_names.append("{}.tilt".format(fixture.name))
        pos_chan_names.append("{}.pan_fine".format(fixture.name))
        pos_chan_names.append("{}.tilt_fine".format(fixture.name))

    params: List[OSCParam] = [
        SignalPatchParam(
            osc,
            "/signal_patchbay/spots_position",
            pos_chan_names,
            deps.mixer,
        ),
    ]
    for i, gen in enumerate(spot_pos_gens, start=1):
        params.append(OSCParam.bind(osc, "/sin_spot_pos_{}_amp".format(i), gen, "amp"))
        params.append(
            OSCParam.bind(osc, "/sin_spot_pos_{}_period".format(i), gen, "period")
        )

    # XY wrappers for pan/tilt offsets (thin layer over individual offsets)
    mixer = deps.mixer
    for fixture in deps.spotlights:
        pan_ch = mixer.channel_lookup["{}.pan".format(fixture.name)]
        tilt_ch = mixer.channel_lookup["{}.tilt".format(fixture.name)]
        params.append(
            OSCParam(
                osc,
                "/{}_pantilt_offset".format(fixture.name),
                lambda pc=pan_ch, tc=tilt_ch: [pc.offset, tc.offset],
                lambda _, *args, pc=pan_ch, tc=tilt_ch: _handle_pantilt_offset(
                    pc, tc, args
                ),
            )
        )
        pan_fine_ch = mixer.channel_lookup["{}.pan_fine".format(fixture.name)]
        tilt_fine_ch = mixer.channel_lookup["{}.tilt_fine".format(fixture.name)]
        params.append(
            OSCParam(
                osc,
                "/{}_pantilt_fine_offset".format(fixture.name),
                lambda pc=pan_fine_ch, tc=tilt_fine_ch: [pc.offset, tc.offset],
                lambda _, *args, pc=pan_fine_ch, tc=tilt_fine_ch: _handle_pantilt_offset(
                    pc, tc, args
                ),
            )
        )

    # Loop generators for spot position (XY pair)
    loop_x = deps.loop_spot_pos_x
    loop_y = deps.loop_spot_pos_y
    params.append(
        OSCParam(
            osc,
            "/loop_spot_pos_input",
            lambda: [loop_x.input_value, loop_y.input_value],
            lambda _, *args: _handle_xy_loop_input(loop_x, loop_y, args),
        )
    )
    params.append(OSCParam.bind(osc, "/loop_spot_pos_x_amp", loop_x, "amp"))
    params.append(OSCParam.bind(osc, "/loop_spot_pos_y_amp", loop_y, "amp"))
    for axis_gen in [loop_x, loop_y]:
        params.append(
            OSCParam(
                osc,
                "/{}_samples".format(axis_gen.name),
                lambda g=axis_gen: g.samples,
                lambda _, *args, g=axis_gen: g.load_samples(
                    list(args[0])
                    if len(args) == 1 and isinstance(args[0], (list, tuple))
                    else list(args)
                ),
            )
        )

    return params


def _handle_pantilt_offset(pan_ch: Any, tilt_ch: Any, args: tuple) -> None:
    if len(args) == 1 and isinstance(args[0], (list, tuple)):
        pan, tilt = args[0][0], args[0][1]
    else:
        pan, tilt = args[0], args[1]
    pan_ch.offset = float(pan)
    tilt_ch.offset = float(tilt)


def _handle_xy_loop_input(loop_x: Any, loop_y: Any, args: tuple) -> None:
    if len(args) == 1 and isinstance(args[0], (list, tuple)):
        x, y = args[0][0], args[0][1]
    else:
        x, y = args[0], args[1]
    loop_x.input_value = x
    loop_y.input_value = y
    loop_x.record_sample(x)
    loop_y.record_sample(y)
