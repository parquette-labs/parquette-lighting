from typing import List

from ..osc import OSCParam
from .deps import ParamDeps


def build(deps: ParamDeps) -> List[OSCParam]:
    osc = deps.osc
    hazer = deps.hazer
    return [
        OSCParam.bind(osc, "/hazer_intensity", hazer, "target_output"),
        OSCParam.bind(osc, "/hazer_fan", hazer, "target_fan"),
        OSCParam.bind(osc, "/hazer_interval", hazer, "interval"),
        OSCParam.bind(osc, "/hazer_duration", hazer, "duration"),
    ]
