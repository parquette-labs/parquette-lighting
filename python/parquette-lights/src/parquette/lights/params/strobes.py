from typing import List

from ..osc import OSCParam
from .deps import ParamDeps


def build(deps: ParamDeps) -> List[OSCParam]:
    osc = deps.osc
    impulse = deps.impulse
    return [
        OSCParam.bind(osc, "/impulse_amp", impulse, "amp"),
        OSCParam.bind(osc, "/impulse_duty", impulse, "duty"),
    ]
