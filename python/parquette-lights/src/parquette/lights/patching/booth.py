from typing import Dict, List

from ..generators import SignalPatchParam, WaveGenerator
from ..generators.generator import Generator
from ..generators.mixer import Mixer
from ..osc import OSCManager, OSCParam
from .builder import ParamGeneratorBuilder


class BoothBuilder(ParamGeneratorBuilder):
    def __init__(self) -> None:
        initial_amp: float = 200
        initial_period: int = 3500

        self.sin_booth = WaveGenerator(
            name="sin_booth",
            category="booth",
            amp=initial_amp,
            period=initial_period,
            phase=0,
            offset=0,
            shape=WaveGenerator.Shape.SIN,
        )

    def generators(self) -> List[Generator]:
        return [self.sin_booth]

    def build_params(self, osc: OSCManager, mixer: Mixer) -> Dict[str, List[OSCParam]]:
        return {
            "booth": [
                # Patch params
                SignalPatchParam(
                    osc,
                    "/signal_patchbay/booth",
                    ["under_1.dimming", "under_2.dimming"],
                    mixer,
                ),
                # Generator params
                OSCParam.bind(osc, "/sin_booth_amp", self.sin_booth, "amp"),
                OSCParam.bind(osc, "/sin_booth_period", self.sin_booth, "period"),
            ]
        }
