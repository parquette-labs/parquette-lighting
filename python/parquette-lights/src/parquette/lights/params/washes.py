from typing import List

from ..generators import SignalPatchParam
from ..osc import OSCParam
from .deps import ParamDeps


def build_washes_color(deps: ParamDeps) -> List[OSCParam]:
    osc = deps.osc
    washceilf = deps.washceilf
    washceilr = deps.washceilr
    all_washes = deps.all_washes

    def dispatch_wash_color(_addr: str, *rgb: float) -> None:
        # set_dimming_target accepts None per channel — `w` is omitted so
        # the white target is preserved.
        if len(rgb) < 3:
            return
        for fixture in all_washes:
            fixture.set_dimming_target(r=rgb[0], g=rgb[1], b=rgb[2])

    return [
        OSCParam.bind(osc, "/wash_w", washceilf, "w_target", extra=[washceilr]),
        # Combined RGB target for the wash color picker. Stored in presets so
        # the picker round-trips through save/load and sync.
        OSCParam(
            osc,
            "/wash_color",
            lambda: [washceilf.r_target, washceilf.g_target, washceilf.b_target],
            dispatch_wash_color,
        ),
    ]


def build(deps: ParamDeps) -> List[OSCParam]:
    osc = deps.osc
    mixer = deps.mixer
    sin_wash = deps.sin_wash
    bpm_wash = deps.bpm_wash

    return [
        OSCParam.bind(osc, "/amp_wash", sin_wash, "amp"),
        OSCParam.bind(osc, "/period_wash", sin_wash, "period"),
        OSCParam.bind(osc, "/washes_stutter_period", mixer, "washes_stutter_period"),
        SignalPatchParam(
            osc,
            "/signal_patchbay/washes",
            [
                "wash_1.dimming",
                "wash_2.dimming",
                "wash_3.dimming",
                "wash_4.dimming",
                "wash_5.dimming",
                "wash_6.dimming",
                "wash_7.dimming",
                "wash_8.dimming",
                "washes_mono",
                "washes_fwd",
                "washes_back",
            ],
            mixer,
        ),
        OSCParam.bind(osc, "/bpm_wash_amp", bpm_wash, "amp"),
        OSCParam.bind(osc, "/bpm_wash_duty", bpm_wash, "duty"),
        OSCParam.bind(osc, "/bpm_wash_lpf_alpha", bpm_wash, "lpf_alpha"),
        OSCParam.bind(osc, "/bpm_wash_mult", bpm_wash, "bpm_mult"),
        OSCParam.bind(osc, "/bpm_wash_manual_offset", bpm_wash, "manual_offset"),
    ]
