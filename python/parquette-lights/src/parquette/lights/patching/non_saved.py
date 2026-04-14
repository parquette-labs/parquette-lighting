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

        # Master values live on MixChannels and are registered from there.
        # We just need to trigger a session save whenever one changes so
        # the new value persists across restarts.
        for cat in ("reds", "plants", "booth", "washes", "spots_light"):
            osc.dispatcher.map(
                "/{}_master".format(cat),
                lambda addr, *args: session.save(),
            )

    def build_params(self, mixer: Mixer) -> Dict[str, List[OSCParam]]:
        osc = self.osc
        return {
            "non-saved": [
                # Non-generator infrastructure params
                OSCParam.bind(osc, "/dmx_passthrough", self.dmx, "passthrough"),
                OSCParam.bind(
                    osc,
                    "/synth_visualizer_source",
                    mixer,
                    "synth_visualizer_source",
                ),
            ]
        }
