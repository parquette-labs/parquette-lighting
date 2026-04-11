from typing import List

from ..generators import SignalPatchParam
from ..osc import OSCParam
from .deps import ParamDeps


def build(deps: ParamDeps) -> List[OSCParam]:
    osc = deps.osc
    sin_booth = deps.sin_booth

    return [
        SignalPatchParam(
            osc,
            "/signal_patchbay/booth",
            ["under_1.dimming", "under_2.dimming"],
            deps.mixer,
        ),
        OSCParam.bind(osc, "/sin_booth_amp", sin_booth, "amp"),
        OSCParam.bind(osc, "/sin_booth_period", sin_booth, "period"),
    ]
