from typing import List

from ..osc import OSCParam
from .deps import ParamDeps


def build(deps: ParamDeps) -> List[OSCParam]:
    """Params that should NOT be persisted into preset pickles.

    Includes the DMX passthrough toggle and the master faders (which persist
    via SessionStore instead of PresetManager).
    """
    osc = deps.osc
    mixer = deps.mixer
    session = deps.session

    return [
        OSCParam(
            osc,
            "/dmx_passthrough",
            lambda: deps.dmx.passthrough,
            lambda _addr, args: deps.set_dmx_passthrough(args),
        ),
        OSCParam.bind(
            osc, "/reds_master", mixer, "reds_master", on_change=session.save
        ),
        OSCParam.bind(
            osc, "/plants_master", mixer, "plants_master", on_change=session.save
        ),
        OSCParam.bind(
            osc, "/booth_master", mixer, "booth_master", on_change=session.save
        ),
        OSCParam.bind(
            osc, "/washes_master", mixer, "washes_master", on_change=session.save
        ),
        OSCParam.bind(
            osc, "/spots_master", mixer, "spots_master", on_change=session.save
        ),
        OSCParam.bind(
            osc, "/synth_visualizer_source", mixer, "synth_visualizer_source"
        ),
    ]
