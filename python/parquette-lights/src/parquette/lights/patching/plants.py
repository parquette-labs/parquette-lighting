from typing import Dict, List

from ..category import Category
from ..dmx import DMXManager
from ..fixtures import LightFixture
from ..fixtures.basics import Fixture
from ..generators import SignalPatchParam, WaveGenerator, BPMGenerator
from ..generators.generator import Generator
from ..generators.mixer import Mixer
from ..osc import OSCManager, OSCParam
from .builder import (
    CategoryBuilder,
    channel_names_for_category,
    register_snap_handler,
)


class PlantsBuilder(CategoryBuilder):
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

        self.ceils: List[LightFixture] = [
            LightFixture(name="ceil_1", category=category, dmx=dmx, addr=18, osc=osc),
            LightFixture(name="ceil_2", category=category, dmx=dmx, addr=19, osc=osc),
            LightFixture(name="ceil_3", category=category, dmx=dmx, addr=17, osc=osc),
        ]

        self.sin_plants = WaveGenerator(
            name="sin_plants",
            category=category,
            amp=initial_amp,
            period=initial_period,
            phase=0,
            offset=0,
            shape=WaveGenerator.Shape.SIN,
        )
        self.sq1 = WaveGenerator(
            name="sq_1",
            category=category,
            amp=initial_amp,
            period=initial_period,
            phase=0,
            offset=0,
            shape=WaveGenerator.Shape.SQUARE,
            duty=0.5,
        )
        self.sq2 = WaveGenerator(
            name="sq_2",
            category=category,
            amp=initial_amp,
            period=initial_period,
            phase=476,
            offset=0,
            shape=WaveGenerator.Shape.SQUARE,
            duty=0.5,
        )
        self.sq3 = WaveGenerator(
            name="sq_3",
            category=category,
            amp=initial_amp,
            period=initial_period,
            phase=335,
            offset=0,
            shape=WaveGenerator.Shape.SQUARE,
            duty=0.5,
        )

        register_snap_handler(
            osc,
            "/snap_sin_plants_to_bpm",
            [self.sin_plants],
            "/sin_plants_period",
            bpm_red,
        )
        register_snap_handler(
            osc,
            "/snap_sq_to_bpm",
            [self.sq1, self.sq2, self.sq3],
            "/sq_period",
            bpm_red,
        )

    def fixtures(self) -> List[Fixture]:
        return list(self.ceils)

    def generators(self) -> List[Generator]:
        return [self.sin_plants, self.sq1, self.sq2, self.sq3]

    def build_params(self, mixer: Mixer) -> Dict[Category, List[OSCParam]]:
        osc = self.osc
        return {
            self.category: [
                # Patch params
                SignalPatchParam(
                    osc,
                    "/signal_patchbay/plants",
                    channel_names_for_category(mixer, self.category),
                    mixer,
                ),
                # Standard generator params (/gen/{type}/{name}/{attr})
                *self.sin_plants.standard_params(osc),
                *self.sq1.standard_params(osc),
                *self.sq2.standard_params(osc),
                *self.sq3.standard_params(osc),
            ]
        }
