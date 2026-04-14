from typing import Dict, List

from ..category import Category
from ..dmx import DMXManager
from ..fixtures.basics import Fixture
from ..fixtures.hazers import RadianceHazer
from ..generators.mixer import Mixer
from ..osc import OSCManager, OSCParam
from .builder import CategoryBuilder


class HazerBuilder(CategoryBuilder):
    def __init__(
        self,
        osc: OSCManager,
        dmx: DMXManager,
        category: Category,
        *,
        debug: bool = False,
    ) -> None:
        self.osc = osc
        self.category = category
        self.hazer = RadianceHazer(
            name="hazer",
            category=category,
            dmx=dmx,
            addr=250,
            debug=debug,
        )

    def fixtures(self) -> List[Fixture]:
        return [self.hazer]

    def build_params(self, mixer: Mixer) -> Dict[Category, List[OSCParam]]:
        return {
            self.category: [
                # Non-generator fixture params
                OSCParam.bind(
                    self.osc, "/hazer_intensity", self.hazer, "target_output"
                ),
                OSCParam.bind(self.osc, "/hazer_fan", self.hazer, "target_fan"),
                OSCParam.bind(self.osc, "/hazer_interval", self.hazer, "interval"),
                OSCParam.bind(self.osc, "/hazer_duration", self.hazer, "duration"),
            ]
        }
