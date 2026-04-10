from typing import Any, List, Tuple

from ..generators import SignalPatchParam
from ..osc import OSCParam
from .deps import ParamDeps


def fix_pantilt_wedge(fixture: Any, args: Tuple[Any, ...], fine: bool = False) -> None:
    # Needed because of weirdness with arduino OSC: args may be a single
    # tuple or two scalars depending on origin.
    if fine:
        if len(args) == 1:
            fixture.pantilt_fine(args[0][0], args[0][1])
        else:
            fixture.pantilt_fine(args[0], args[1])
    else:
        if len(args) == 1:
            fixture.pantilt(args[0][0], args[0][1])
        else:
            fixture.pantilt(args[0], args[1])


# pylint: disable=protected-access
def build_lights(deps: ParamDeps) -> List[OSCParam]:
    osc = deps.osc
    params: List[OSCParam] = [
        SignalPatchParam(
            osc,
            "/signal_patchbay/spots_lights",
            ["tung_spot", "spot_1", "spot_2", "synth_visualizer"],
            deps.mixer,
        )
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
    params: List[OSCParam] = []
    for i, fixture in enumerate(deps.spotlights):
        params.append(
            OSCParam(
                osc,
                "/spot_joystick_{}".format(i + 1),
                lambda fixture=fixture: [fixture._pan, fixture._tilt],
                lambda _, *args, fixture=fixture: fix_pantilt_wedge(
                    fixture, args, False
                ),
            )
        )
        params.append(
            OSCParam(
                osc,
                "/spot_joystick_fine_{}".format(i + 1),
                lambda fixture=fixture: [fixture._pan_fine, fixture._tilt_fine],
                lambda _, *args, fixture=fixture: fix_pantilt_wedge(
                    fixture, args, True
                ),
            )
        )
    return params
