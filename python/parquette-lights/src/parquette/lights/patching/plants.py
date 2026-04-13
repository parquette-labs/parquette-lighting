from typing import List, Tuple

from ..generators import SignalPatchParam, WaveGenerator
from ..generators.generator import Generator
from ..generators.mixer import Mixer
from ..osc import OSCManager, OSCParam
from .builder import ParamGeneratorBuilder


class PlantsBuilder(ParamGeneratorBuilder):
    def __init__(self) -> None:
        initial_amp: float = 200
        initial_period: int = 3500

        self.sin_plants = WaveGenerator(
            name="sin_plants",
            category="plants",
            amp=initial_amp,
            period=initial_period,
            phase=0,
            offset=0,
            shape=WaveGenerator.Shape.SIN,
        )
        self.sq1 = WaveGenerator(
            name="sq_1",
            category="plants",
            amp=initial_amp,
            period=initial_period,
            phase=0,
            offset=0,
            shape=WaveGenerator.Shape.SQUARE,
            duty=0.5,
        )
        self.sq2 = WaveGenerator(
            name="sq_2",
            category="plants",
            amp=initial_amp,
            period=initial_period,
            phase=476,
            offset=0,
            shape=WaveGenerator.Shape.SQUARE,
            duty=0.5,
        )
        self.sq3 = WaveGenerator(
            name="sq_3",
            category="plants",
            amp=initial_amp,
            period=initial_period,
            phase=335,
            offset=0,
            shape=WaveGenerator.Shape.SQUARE,
            duty=0.5,
        )

    def generators(self) -> List[Generator]:
        return [self.sin_plants, self.sq1, self.sq2, self.sq3]

    def build_params(
        self, osc: OSCManager, mixer: Mixer
    ) -> List[Tuple[str, List[OSCParam]]]:
        return [
            (
                "plants",
                [
                    # Patch params
                    SignalPatchParam(
                        osc,
                        "/signal_patchbay/plants",
                        ["ceil_1.dimming", "ceil_2.dimming", "ceil_3.dimming"],
                        mixer,
                    ),
                    # Generator params
                    OSCParam.bind(osc, "/sin_plants_amp", self.sin_plants, "amp"),
                    OSCParam.bind(osc, "/sin_plants_period", self.sin_plants, "period"),
                    OSCParam.bind(
                        osc,
                        "/sq_amp",
                        self.sq1,
                        "amp",
                        extra=[self.sq2, self.sq3],
                    ),
                    OSCParam.bind(
                        osc,
                        "/sq_period",
                        self.sq1,
                        "period",
                        extra=[self.sq2, self.sq3],
                    ),
                ],
            )
        ]
