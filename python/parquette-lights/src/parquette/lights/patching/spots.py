from typing import Dict, List

from ..category import Category
from ..coord_system_state import CoordSystemState
from ..dmx import DMXManager
from ..fixtures import LightFixture, YRXY200Spot
from ..fixtures.spotlights import PinSpot
from ..fixtures.basics import Fixture
from ..generators import WaveGenerator, BPMGenerator, LoopGenerator
from ..generators.generator import Generator
from ..generators.mixer import Mixer
from ..osc import OSCManager, OSCParam
from .builder import CategoryBuilder


# pylint: disable=too-many-arguments
class SpotsBuilder(CategoryBuilder):
    def __init__(
        self,
        osc: OSCManager,
        dmx: DMXManager,
        light_category: Category,
        position_category: Category,
        *,
        coord_state: CoordSystemState,
        loop_max_samples: int,
        bpm_red: BPMGenerator,
        spot_color_fade: float,
        spot_mechanical_time: float,
    ) -> None:
        self.osc = osc
        self.coord_state = coord_state
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
                addr=216,
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
        # Wire each spot to the coord-system state. Spots register so they
        # receive rebind_coords() when the active coord system changes.
        for spot in self.spotlights:
            spot.coord_state = coord_state
            coord_state.register(spot)

        self.pin_1 = PinSpot(
            name="pin_1", category=light_category, dmx=dmx, addr=231, osc=osc
        )
        self.pin_1.rgbw(0, 0, 0, 0)

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
        self.sqr_spot = WaveGenerator(
            name="sqr_spot",
            category=light_category,
            amp=initial_dimming_amp,
            period=initial_period,
            phase=0,
            offset=0,
            shape=WaveGenerator.Shape.SQUARE,
            duty=0.5,
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
        self.sqr_spot.register_snap_to(bpm_red, osc)
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
        return [self.tung_spot, *self.spotlights, self.pin_1]

    def generators(self) -> List[Generator]:
        return [
            self.sin_spot,
            self.sqr_spot,
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
            *self.sqr_spot.standard_params(osc),
        ]

        for fixture in self.spotlights:
            # Standard fixture params (/fixture/{ClassName}/{name}/{attr})
            light_params.extend(fixture.standard_params(osc))

        # PinSpot RGBW color target params (class-level broadcast)
        light_params.append(self.pin_1.color_param(osc))
        light_params.append(self.pin_1.w_target_param(osc))

        # Register the virtual /chan/{spot}/pantilt/offset 2-vec OSCParam
        # for each spot here (rather than letting ChannelLevelsBuilder do it)
        # so we can hand the param back to the spot — rebind_coords needs
        # it to push refreshed UI values when the active coord system changes.

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
        for spot in self.spotlights:
            pantilt_ch = mixer.channel_lookup.get("{}/pantilt".format(spot.name))
            if pantilt_ch is not None:
                param = pantilt_ch.register_offset(osc)
                spot.pantilt_param = param
                pos_params.append(param)
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
