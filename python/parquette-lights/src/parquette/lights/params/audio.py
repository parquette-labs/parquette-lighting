from typing import Any, List, Tuple

from ..osc import OSCParam
from .deps import ParamDeps


def build(deps: ParamDeps) -> List[OSCParam]:
    osc = deps.osc
    fft1 = deps.fft1
    fft2 = deps.fft2
    fft_manager = deps.fft_manager

    def fft_dispatch_wedge(fft: Any, args: Tuple[Any, ...]) -> None:
        if len(args) == 1:
            fft.set_bounds(args[0][0], args[0][2])
        else:
            fft.set_bounds(args[0], args[2])

    return [
        OSCParam.bind(osc, "/fft1_amp", fft1, "amp"),
        OSCParam.bind(osc, "/fft2_amp", fft2, "amp"),
        OSCParam.bind(osc, "/fft_lpf_alpha", fft1, "lpf_alpha", extra=[fft2]),
        OSCParam.bind(osc, "/fft_threshold_1", fft1, "thres"),
        OSCParam.bind(osc, "/fft_threshold_2", fft2, "thres"),
        OSCParam(
            osc,
            "/fft_bounds_1",
            lambda: (fft1.fft_bounds[0], 0, fft1.fft_bounds[1], 0),
            lambda _addr, *args: fft_dispatch_wedge(fft1, args),
        ),
        OSCParam(
            osc,
            "/fft_bounds_2",
            lambda: (fft2.fft_bounds[0], 0, fft2.fft_bounds[1], 0),
            lambda _addr, *args: fft_dispatch_wedge(fft2, args),
        ),
        OSCParam.bind(osc, "/bpm_energy_threshold", fft_manager, "energy_threshold"),
        OSCParam.bind(osc, "/bpm_tempo_alpha", fft_manager, "tempo_alpha"),
        OSCParam.bind(
            osc, "/onset_envelope_floor", fft_manager, "onset_envelope_floor"
        ),
        OSCParam.bind(osc, "/bpm_business_min", fft_manager, "min_business"),
        OSCParam.bind(osc, "/bpm_regularity_min", fft_manager, "min_regularity"),
    ]
