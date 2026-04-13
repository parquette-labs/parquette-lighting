from typing import List, Tuple

from ..generators import ImpulseGenerator
from ..generators.generator import Generator
from ..generators.mixer import Mixer
from ..osc import OSCManager, OSCParam
from .builder import ParamGeneratorBuilder


class StrobesBuilder(ParamGeneratorBuilder):
    def __init__(self) -> None:
        self.impulse = ImpulseGenerator(
            name="impulse", category="strobes", amp=255, offset=0, duty=100
        )

    def generators(self) -> List[Generator]:
        return [self.impulse]

    def build_params(
        self, osc: OSCManager, mixer: Mixer
    ) -> List[Tuple[str, List[OSCParam]]]:
        return [
            (
                "strobes",
                [
                    # Generator params
                    OSCParam.bind(osc, "/impulse_amp", self.impulse, "amp"),
                    OSCParam.bind(osc, "/impulse_duty", self.impulse, "duty"),
                ],
            )
        ]
