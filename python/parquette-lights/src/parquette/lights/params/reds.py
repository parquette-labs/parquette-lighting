from typing import List

from ..generators import SignalPatchParam
from ..osc import OSCParam
from .deps import ParamDeps


def build(deps: ParamDeps) -> List[OSCParam]:
    osc = deps.osc
    sin_reds = deps.sin_reds
    mixer = deps.mixer
    bpm_red = deps.bpm_red

    return [
        SignalPatchParam(
            osc,
            "/signal_patchbay/reds",
            ["chan_1", "chan_2", "chan_3", "chan_4", "chan_5", "synth_visualizer"],
            mixer,
        ),
        OSCParam.bind(osc, "/sin_red_amp", sin_reds, "amp"),
        OSCParam.bind(osc, "/sin_red_period", sin_reds, "period"),
        OSCParam.bind(osc, "/mode_switch", mixer.reds_mapper, "mode"),
        OSCParam.bind(osc, "/stutter_period", mixer.reds_mapper, "stutter_period"),
        OSCParam.bind(osc, "/bpm_red_mult", bpm_red, "bpm_mult"),
        OSCParam.bind(osc, "/bpm_red_duty", bpm_red, "duty"),
        OSCParam.bind(osc, "/bpm_red_lpf_alpha", bpm_red, "lpf_alpha"),
        OSCParam.bind(osc, "/bpm_red_amp", bpm_red, "amp"),
        OSCParam.bind(osc, "/bpm_red_manual_offset", bpm_red, "manual_offset"),
    ]
