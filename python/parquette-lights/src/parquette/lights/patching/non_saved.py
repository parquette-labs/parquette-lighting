from typing import Any, Callable, List, Tuple

from ..dmx import DMXManager
from ..generators.mixer import Mixer
from ..osc import OSCManager, OSCParam
from ..util.session_store import SessionStore
from .builder import ParamGeneratorBuilder


class NonSavedBuilder(ParamGeneratorBuilder):
    def __init__(
        self,
        dmx: DMXManager,
        session: SessionStore,
        set_dmx_passthrough: Callable[[Any], None],
    ) -> None:
        self.dmx = dmx
        self.session = session
        self.set_dmx_passthrough = set_dmx_passthrough

    def build_params(
        self, osc: OSCManager, mixer: Mixer
    ) -> List[Tuple[str, List[OSCParam]]]:
        return [
            (
                "non-saved",
                [
                    # Non-generator infrastructure params
                    OSCParam(
                        osc,
                        "/dmx_passthrough",
                        lambda: self.dmx.passthrough,
                        lambda _addr, args: self.set_dmx_passthrough(args),
                    ),
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
                ],
            )
        ]
