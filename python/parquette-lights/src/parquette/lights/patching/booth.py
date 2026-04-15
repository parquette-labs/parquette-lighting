from typing import Dict, List

from ..category import Category
from ..dmx import DMXManager
from ..fixtures import LightFixture
from ..fixtures.basics import Fixture
from ..generators import WaveGenerator, BPMGenerator
from ..generators.generator import Generator
from ..generators.mixer import Mixer
from ..osc import OSCManager, OSCParam
from .builder import CategoryBuilder


class BoothBuilder(CategoryBuilder):
    def __init__(
        self,
        osc: OSCManager,
        dmx: DMXManager,
        category: Category,
        bpm_red: BPMGenerator,
    ) -> None:
        self.osc = osc
        self.category = category
        initial_amp: float = 200
        initial_period: int = 3500

        self.unders: List[LightFixture] = [
            LightFixture(name="under_1", category=category, dmx=dmx, addr=10, osc=osc),
            LightFixture(name="under_2", category=category, dmx=dmx, addr=11, osc=osc),
        ]

        self.sin_booth = WaveGenerator(
            name="sin_booth",
            category=category,
            amp=initial_amp,
            period=initial_period,
            phase=0,
            offset=0,
            shape=WaveGenerator.Shape.SIN,
        )

        self.sin_booth.register_snap_to(bpm_red, osc)

    def fixtures(self) -> List[Fixture]:
        return list(self.unders)

    def generators(self) -> List[Generator]:
        return [self.sin_booth]

    def build_params(self, mixer: Mixer) -> Dict[Category, List[OSCParam]]:
        osc = self.osc
        return {
            self.category: [
                # Patch params
                mixer.patchbay_param(self.category),
                # Standard generator params (/gen/{type}/{name}/{attr})
                *self.sin_booth.standard_params(osc),
            ]
        }
