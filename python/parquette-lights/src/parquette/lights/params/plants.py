from typing import List

from ..generators import SignalPatchParam
from ..osc import OSCParam
from .deps import ParamDeps


def build(deps: ParamDeps) -> List[OSCParam]:
    osc = deps.osc
    sin_plants = deps.sin_plants
    sq1, sq2, sq3 = deps.sq1, deps.sq2, deps.sq3

    return [
        SignalPatchParam(
            osc,
            "/signal_patchbay/plants",
            ["ceil_1", "ceil_2", "ceil_3", "synth_visualizer"],
            deps.mixer,
        ),
        OSCParam.bind(osc, "/sin_plants_amp", sin_plants, "amp"),
        OSCParam.bind(osc, "/sin_plants_period", sin_plants, "period"),
        OSCParam.bind(osc, "/sq_amp", sq1, "amp", extra=[sq2, sq3]),
        OSCParam.bind(osc, "/sq_period", sq1, "period", extra=[sq2, sq3]),
    ]
