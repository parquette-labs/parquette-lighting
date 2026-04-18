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


class ChandelierBuilder(CategoryBuilder):
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

        self.fixtures_list: List[LightFixture] = [
            LightFixture(name="chand_1", category=category, dmx=dmx, addr=28, osc=osc),
            LightFixture(name="chand_2", category=category, dmx=dmx, addr=29, osc=osc),
            LightFixture(name="chand_3", category=category, dmx=dmx, addr=30, osc=osc),
        ]

        self.sin_chand_1 = WaveGenerator(
            name="sin_chand_1",
            category=category,
            amp=initial_amp,
            period=initial_period,
            phase=0,
            offset=0,
            shape=WaveGenerator.Shape.SIN,
        )
        self.sin_chand_2 = WaveGenerator(
            name="sin_chand_2",
            category=category,
            amp=initial_amp,
            period=initial_period,
            phase=0,
            offset=0,
            shape=WaveGenerator.Shape.SIN,
        )
        self.sin_chand_3 = WaveGenerator(
            name="sin_chand_3",
            category=category,
            amp=initial_amp,
            period=initial_period,
            phase=0,
            offset=0,
            shape=WaveGenerator.Shape.SIN,
        )

        for wave in (self.sin_chand_1, self.sin_chand_2, self.sin_chand_3):
            wave.register_snap_to(bpm_red, osc)

    def fixtures(self) -> List[Fixture]:
        return list(self.fixtures_list)

    def generators(self) -> List[Generator]:
        return [self.sin_chand_1, self.sin_chand_2, self.sin_chand_3]

    def build_params(self, mixer: Mixer) -> Dict[Category, List[OSCParam]]:
        osc = self.osc
        return {
            self.category: [
                mixer.patchbay_param(self.category),
                *self.sin_chand_1.standard_params(osc),
                *self.sin_chand_2.standard_params(osc),
                *self.sin_chand_3.standard_params(osc),
            ]
        }
