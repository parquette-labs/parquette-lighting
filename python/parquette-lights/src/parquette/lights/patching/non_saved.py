from typing import Dict, List

from ..dmx import DMXManager
from ..generators.mixer import Mixer
from ..osc import OSCManager, OSCParam
from ..util.session_store import SessionStore
from .builder import ParamGeneratorBuilder


class NonSavedBuilder(ParamGeneratorBuilder):
    def __init__(
        self,
        osc: OSCManager,
        dmx: DMXManager,
        session: SessionStore,
    ) -> None:
        self.osc = osc
        self.dmx = dmx
        self.session = session

    def build_params(self, mixer: Mixer) -> Dict[str, List[OSCParam]]:
        osc = self.osc
        return {
            "non-saved": [
                # Non-generator infrastructure params
                OSCParam.bind(osc, "/dmx_passthrough", self.dmx, "passthrough"),
                OSCParam.bind(
                    osc,
                    "/reds_master",
                    mixer,
                    "reds_master",
                    on_change=self.session.save,
                ),
                OSCParam.bind(
                    osc,
                    "/plants_master",
                    mixer,
                    "plants_master",
                    on_change=self.session.save,
                ),
                OSCParam.bind(
                    osc,
                    "/booth_master",
                    mixer,
                    "booth_master",
                    on_change=self.session.save,
                ),
                OSCParam.bind(
                    osc,
                    "/washes_master",
                    mixer,
                    "washes_master",
                    on_change=self.session.save,
                ),
                OSCParam.bind(
                    osc,
                    "/spots_master",
                    mixer,
                    "spots_master",
                    on_change=self.session.save,
                ),
                OSCParam.bind(
                    osc,
                    "/synth_visualizer_source",
                    mixer,
                    "synth_visualizer_source",
                ),
            ]
        }
