from typing import Dict, List

from ..fixtures.basics import Fixture
from ..fixtures.hazers import RadianceHazer
from ..generators.mixer import Mixer
from ..osc import OSCManager, OSCParam
from .builder import ParamGeneratorBuilder


class HazerBuilder(ParamGeneratorBuilder):
    def __init__(self, osc: OSCManager, all_fixtures: List[Fixture]) -> None:
        self.osc = osc
        self.hazer = next(f for f in all_fixtures if isinstance(f, RadianceHazer))

    def build_params(self, mixer: Mixer) -> Dict[str, List[OSCParam]]:
        return {
            "hazer": [
                # Non-generator fixture params
                OSCParam.bind(
                    self.osc, "/hazer_intensity", self.hazer, "target_output"
                ),
                OSCParam.bind(self.osc, "/hazer_fan", self.hazer, "target_fan"),
                OSCParam.bind(self.osc, "/hazer_interval", self.hazer, "interval"),
                OSCParam.bind(self.osc, "/hazer_duration", self.hazer, "duration"),
            ]
        }
