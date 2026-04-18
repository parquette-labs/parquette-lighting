from typing import Dict, List

from ..category import Category
from ..dmx import DMXManager
from ..fixtures import LightFixture, YRXY200Spot
from ..fixtures.basics import Fixture
from ..generators import WaveGenerator, BPMGenerator, LoopGenerator
from ..generators.generator import Generator
from ..generators.mixer import Mixer
from ..osc import OSCManager, OSCParam
from .builder import CategoryBuilder


class SpotsBuilder(CategoryBuilder):
    def __init__(
        self,
        osc: OSCManager,
        dmx: DMXManager,
        light_category: Category,
        position_category: Category,
        *,
        loop_max_samples: int,
        bpm_red: BPMGenerator,
        spot_color_fade: float,
        spot_mechanical_time: float,
    ) -> None:
        self.osc = osc
        self.light_category = light_category
        self.position_category = position_category
        initial_dimming_amp: float = 200
        initial_pos_amp: float = 51200
        initial_period: int = 3500

        self.tung_spot = LightFixture(
            name="tung_spot", category=light_category, dmx=dmx, addr=13, osc=osc
        )

        self.spotlights: List[YRXY200Spot] = [
            YRXY200Spot(
                name="spot_1",
                category=light_category,
                position_category=position_category,
                dmx=dmx,
                addr=21,
                osc=osc,
            ),
            YRXY200Spot(
                name="spot_2",
                category=light_category,
                position_category=position_category,
                dmx=dmx,
                addr=200,
                osc=osc,
            ),
        ]
        for spot in self.spotlights:
            spot.dimming(255)
            spot.strobe(False)
            spot.color(0)
            spot.no_pattern()
            spot.prisim(False)
            spot.colorful(False)
            spot.self_propelled(YRXY200Spot.YRXY200SelfPropelled.NONE)
            spot.light_strip_scene(YRXY200Spot.YRXY200RingScene.OFF)
            spot.scene_speed(0)
            spot.pan(0)
            spot.tilt(0)
            spot.color_swap_fade_time = spot_color_fade
            spot.color_swap_mechanical_time = spot_mechanical_time

        self.sin_spot = WaveGenerator(
            name="sin_spot",
            category=light_category,
            amp=initial_dimming_amp,
            period=initial_period,
            phase=0,
            offset=0,
            shape=WaveGenerator.Shape.SIN,
        )
        self.sin_spot_pos_1 = WaveGenerator(
            name="sin_spot_pos_1",
            category=position_category,
            amp=initial_pos_amp,
            period=initial_period,
            phase=0,
            offset=0,
            shape=WaveGenerator.Shape.SIN,
        )
        self.sin_spot_pos_2 = WaveGenerator(
            name="sin_spot_pos_2",
            category=position_category,
            amp=initial_pos_amp,
            period=initial_period,
            phase=0,
            offset=0,
            shape=WaveGenerator.Shape.SIN,
        )
        self.sin_spot_pos_3 = WaveGenerator(
            name="sin_spot_pos_3",
            category=position_category,
            amp=initial_pos_amp,
            period=initial_period,
            phase=0,
            offset=0,
            shape=WaveGenerator.Shape.SIN,
        )
        self.sin_spot_pos_4 = WaveGenerator(
            name="sin_spot_pos_4",
            category=position_category,
            amp=initial_pos_amp,
            period=initial_period,
            phase=0,
            offset=0,
            shape=WaveGenerator.Shape.SIN,
        )
        self.loop_spot_pos_1_x = LoopGenerator(
            name="loop_spot_pos_1_x",
            category=position_category,
            max_samples=loop_max_samples,
            record_group="loop_spot_pos_1",
        )
        self.loop_spot_pos_1_y = LoopGenerator(
            name="loop_spot_pos_1_y",
            category=position_category,
            max_samples=loop_max_samples,
            record_group="loop_spot_pos_1",
        )
        self.loop_spot_pos_2_x = LoopGenerator(
            name="loop_spot_pos_2_x",
            category=position_category,
            max_samples=loop_max_samples,
            record_group="loop_spot_pos_2",
        )
        self.loop_spot_pos_2_y = LoopGenerator(
            name="loop_spot_pos_2_y",
            category=position_category,
            max_samples=loop_max_samples,
            record_group="loop_spot_pos_2",
        )

        self.sin_spot.register_snap_to(bpm_red, osc)
        for wave in (
            self.sin_spot_pos_1,
            self.sin_spot_pos_2,
            self.sin_spot_pos_3,
            self.sin_spot_pos_4,
        ):
            wave.register_snap_to(bpm_red, osc)

        for loop in (
            self.loop_spot_pos_1_x,
            self.loop_spot_pos_1_y,
            self.loop_spot_pos_2_x,
            self.loop_spot_pos_2_y,
        ):
            loop.register_record(osc)

    def fixtures(self) -> List[Fixture]:
        return [self.tung_spot, *self.spotlights]

    def generators(self) -> List[Generator]:
        return [
            self.sin_spot,
            self.sin_spot_pos_1,
            self.sin_spot_pos_2,
            self.sin_spot_pos_3,
            self.sin_spot_pos_4,
            self.loop_spot_pos_1_x,
            self.loop_spot_pos_1_y,
            self.loop_spot_pos_2_x,
            self.loop_spot_pos_2_y,
        ]

    # pylint: disable=protected-access
    def build_params(self, mixer: Mixer) -> Dict[Category, List[OSCParam]]:
        osc = self.osc
        light_params: List[OSCParam] = [
            mixer.patchbay_param(self.light_category),
            # Standard generator params (/gen/{ClassName}/{name}/{attr})
            *self.sin_spot.standard_params(osc),
        ]

        for fixture in self.spotlights:
            # Standard fixture params (/fixture/{ClassName}/{name}/{attr})
            light_params.extend(fixture.standard_params(osc))

        # Position params
        spot_pos_gens = [
            self.sin_spot_pos_1,
            self.sin_spot_pos_2,
            self.sin_spot_pos_3,
            self.sin_spot_pos_4,
        ]

        pos_params: List[OSCParam] = [
            mixer.patchbay_param(self.position_category),
        ]
        for gen in spot_pos_gens:
            # Standard generator params (/gen/{type}/{name}/{attr})
            pos_params.extend(gen.standard_params(osc))

        loop_pairs = [
            (self.loop_spot_pos_1_x, self.loop_spot_pos_1_y),
            (self.loop_spot_pos_2_x, self.loop_spot_pos_2_y),
        ]
        for loop_x, loop_y in loop_pairs:
            # Standard generator params for each axis (amp, samples)
            pos_params.extend(loop_x.standard_params(osc))
            pos_params.extend(loop_y.standard_params(osc))
            # Paired XY input writes to both axes and records during capture
            pos_params.append(LoopGenerator.pair_input_param(osc, loop_x, loop_y))

        return {
            self.light_category: light_params,
            self.position_category: pos_params,
        }
