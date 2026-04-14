from typing import Dict, List

from ..generators import ImpulseGenerator
from ..generators.generator import Generator
from ..generators.mixer import Mixer
from ..osc import OSCManager, OSCParam
from .builder import ParamGeneratorBuilder


class StrobesBuilder(ParamGeneratorBuilder):
    def __init__(self, osc: OSCManager) -> None:
        self.osc = osc
        self.impulse = ImpulseGenerator(
            name="impulse", category="strobes", amp=255, offset=0, duty=100
        )

        osc.dispatcher.map("/impulse_punch", lambda addr, *args: self.impulse.punch())

    def generators(self) -> List[Generator]:
        return [self.impulse]

    def build_params(self, mixer: Mixer) -> Dict[str, List[OSCParam]]:
        return {
            "strobes": [
                # Generator params
                OSCParam.bind(self.osc, "/impulse_amp", self.impulse, "amp"),
                OSCParam.bind(self.osc, "/impulse_duty", self.impulse, "duty"),
            ]
        }
