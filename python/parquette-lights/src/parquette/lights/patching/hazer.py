from typing import Dict, List

from ..fixtures.hazers import RadianceHazer
from ..generators.mixer import Mixer
from ..osc import OSCManager, OSCParam
from .builder import ParamGeneratorBuilder


class HazerBuilder(ParamGeneratorBuilder):
    def __init__(self, hazer: RadianceHazer) -> None:
        self.hazer = hazer

    def build_params(self, osc: OSCManager, mixer: Mixer) -> Dict[str, List[OSCParam]]:
        return {
            "hazer": [
                # Non-generator fixture params
                OSCParam.bind(osc, "/hazer_intensity", self.hazer, "target_output"),
                OSCParam.bind(osc, "/hazer_fan", self.hazer, "target_fan"),
                OSCParam.bind(osc, "/hazer_interval", self.hazer, "interval"),
                OSCParam.bind(osc, "/hazer_duration", self.hazer, "duration"),
            ]
        }
