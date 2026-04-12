from typing import TYPE_CHECKING, List

from ..generators import SignalPatchParam
from ..osc import OSCParam
from .deps import ParamDeps

if TYPE_CHECKING:
    from ..generators.loop_generator import LoopGenerator


def _handle_loop_input(gen: "LoopGenerator", value: float) -> None:
    gen.input_value = value
    gen.record_sample(value)


def build(deps: ParamDeps) -> List[OSCParam]:
    osc = deps.osc
    sin_reds = deps.sin_reds
    mixer = deps.mixer
    bpm_red = deps.bpm_red
    loop_reds = deps.loop_reds

    return [
        SignalPatchParam(
            osc,
            "/signal_patchbay/reds",
            [
                "left_1.dimming",
                "left_2.dimming",
                "left_3.dimming",
                "left_4.dimming",
                "right_1.dimming",
                "right_2.dimming",
                "right_3.dimming",
                "right_4.dimming",
                "front_1.dimming",
                "front_2.dimming",
                "reds_mono",
                "reds_fwd",
                "reds_back",
                "reds_zig",
            ],
            mixer,
        ),
        OSCParam.bind(osc, "/sin_red_amp", sin_reds, "amp"),
        OSCParam.bind(osc, "/sin_red_period", sin_reds, "period"),
        OSCParam.bind(osc, "/reds_stutter_period", mixer, "reds_stutter_period"),
        OSCParam.bind(osc, "/bpm_red_mult", bpm_red, "bpm_mult"),
        OSCParam.bind(osc, "/bpm_red_duty", bpm_red, "duty"),
        OSCParam.bind(osc, "/bpm_red_lpf_alpha", bpm_red, "lpf_alpha"),
        OSCParam.bind(osc, "/bpm_red_amp", bpm_red, "amp"),
        OSCParam.bind(osc, "/bpm_red_manual_offset", bpm_red, "manual_offset"),
        # Loop generator for reds
        OSCParam(
            osc,
            "/loop_reds_input",
            lambda: loop_reds.input_value,
            lambda _, args: _handle_loop_input(loop_reds, args),
        ),
        OSCParam.bind(osc, "/loop_reds_amp", loop_reds, "amp"),
        OSCParam(
            osc,
            "/loop_reds_samples",
            lambda: loop_reds.samples,
            lambda _, *args: loop_reds.load_samples(
                list(args[0])
                if len(args) == 1 and isinstance(args[0], (list, tuple))
                else list(args)
            ),
        ),
    ]
