from typing import Dict, List

from ..category import Category
from ..dmx import DMXManager
from ..fixtures import LightFixture
from ..fixtures.basics import Fixture
from ..generators.mixer import Mixer
from ..osc import OSCManager, OSCParam
from ..util.session_store import SessionStore
from .builder import CategoryBuilder


class NonSavedBuilder(CategoryBuilder):
    def __init__(
        self,
        osc: OSCManager,
        dmx: DMXManager,
        category: Category,
        session: SessionStore,
    ) -> None:
        self.osc = osc
        self.category = category
        self.dmx = dmx
        self.session = session

        self.sodium = LightFixture(
            name="sodium", category=category, dmx=dmx, addr=20, osc=osc
        )

    def fixtures(self) -> List[Fixture]:
        return [self.sodium]

    def build_params(self, mixer: Mixer) -> Dict[Category, List[OSCParam]]:
        osc = self.osc
        return {
            self.category: [
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
