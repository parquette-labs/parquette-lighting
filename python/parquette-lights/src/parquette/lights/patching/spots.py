from typing import Any, Dict, List

from ..category import Category
from ..dmx import DMXManager
from ..fixtures import LightFixture, YRXY200Spot
from ..fixtures.basics import Fixture
from ..generators import SignalPatchParam, WaveGenerator, BPMGenerator, LoopGenerator
from ..generators.generator import Generator
from ..generators.mixer import Mixer
from ..osc import OSCManager, OSCParam
from .builder import (
    CategoryBuilder,
    channel_names_for_category,
    register_snap_handler,
    register_loop_record_handler,
)


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
        initial_amp: float = 200
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
            amp=initial_amp,
            period=initial_period,
            phase=0,
            offset=0,
            shape=WaveGenerator.Shape.SIN,
        )
        self.sin_spot_pos_1 = WaveGenerator(
            name="sin_spot_pos_1",
            category=position_category,
            amp=initial_amp,
            period=initial_period,
            phase=0,
            offset=0,
            shape=WaveGenerator.Shape.SIN,
        )
        self.sin_spot_pos_2 = WaveGenerator(
            name="sin_spot_pos_2",
            category=position_category,
            amp=initial_amp,
            period=initial_period,
            phase=0,
            offset=0,
            shape=WaveGenerator.Shape.SIN,
        )
        self.sin_spot_pos_3 = WaveGenerator(
            name="sin_spot_pos_3",
            category=position_category,
            amp=initial_amp,
            period=initial_period,
            phase=0,
            offset=0,
            shape=WaveGenerator.Shape.SIN,
        )
        self.sin_spot_pos_4 = WaveGenerator(
            name="sin_spot_pos_4",
            category=position_category,
            amp=initial_amp,
            period=initial_period,
            phase=0,
            offset=0,
            shape=WaveGenerator.Shape.SIN,
        )
        self.loop_spot_pos_1_x = LoopGenerator(
            name="loop_spot_pos_1_x",
            category=position_category,
            max_samples=loop_max_samples,
        )
        self.loop_spot_pos_1_y = LoopGenerator(
            name="loop_spot_pos_1_y",
            category=position_category,
            max_samples=loop_max_samples,
        )
        self.loop_spot_pos_2_x = LoopGenerator(
            name="loop_spot_pos_2_x",
            category=position_category,
            max_samples=loop_max_samples,
        )
        self.loop_spot_pos_2_y = LoopGenerator(
            name="loop_spot_pos_2_y",
            category=position_category,
            max_samples=loop_max_samples,
        )

        register_snap_handler(
            osc,
            "/snap_sin_spot_to_bpm",
            [self.sin_spot],
            "/sin_spot_period",
            bpm_red,
        )
        spot_pos_gens = [
            self.sin_spot_pos_1,
            self.sin_spot_pos_2,
            self.sin_spot_pos_3,
            self.sin_spot_pos_4,
        ]
        register_snap_handler(
            osc,
            "/snap_sin_spot_pos_to_bpm",
            spot_pos_gens,
            [
                "/sin_spot_pos_1_period",
                "/sin_spot_pos_2_period",
                "/sin_spot_pos_3_period",
                "/sin_spot_pos_4_period",
            ],
            bpm_red,
        )

        loop_pairs = [
            (self.loop_spot_pos_1_x, self.loop_spot_pos_1_y, 1),
            (self.loop_spot_pos_2_x, self.loop_spot_pos_2_y, 2),
        ]
        for loop_x, loop_y, idx in loop_pairs:
            register_loop_record_handler(
                osc,
                "/loop_spot_pos_{}_record".format(idx),
                [loop_x, loop_y],
            )

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
            # Patch params
            SignalPatchParam(
                osc,
                "/signal_patchbay/spots_light",
                channel_names_for_category(mixer, self.light_category),
                mixer,
            ),
            # Generator params
            OSCParam.bind(osc, "/sin_spot_amp", self.sin_spot, "amp"),
            OSCParam.bind(osc, "/sin_spot_period", self.sin_spot, "period"),
        ]

        for i, fixture in enumerate(self.spotlights):
            # Non-generator fixture params
            light_params.append(
                OSCParam(
                    osc,
                    "/spot_color_{}".format(i + 1),
                    lambda fixture=fixture: fixture.color_index,
                    lambda _, args, fixture=fixture: fixture.color(args),
                )
            )
            light_params.append(
                OSCParam(
                    osc,
                    "/spot_pattern_{}".format(i + 1),
                    lambda fixture=fixture: fixture.pattern_index,
                    lambda _, args, fixture=fixture: fixture.pattern(args),
                )
            )
            light_params.append(
                OSCParam(
                    osc,
                    "/spot_prisim_{}".format(i + 1),
                    lambda fixture=fixture: fixture.prisim_enabled,
                    lambda _, args, fixture=fixture: fixture.prisim(
                        args, fixture.prisim_rotation
                    ),
                )
            )
            light_params.append(
                OSCParam(
                    osc,
                    "/spot_prisim_rotation_{}".format(i + 1),
                    lambda fixture=fixture: fixture.prisim_rotation,
                    lambda _, args, fixture=fixture: fixture.prisim(
                        fixture.prisim_enabled, args
                    ),
                )
            )

        # Position params
        spot_pos_gens = [
            self.sin_spot_pos_1,
            self.sin_spot_pos_2,
            self.sin_spot_pos_3,
            self.sin_spot_pos_4,
        ]

        pos_params: List[OSCParam] = [
            # Patch params
            SignalPatchParam(
                osc,
                "/signal_patchbay/spots_position",
                channel_names_for_category(mixer, self.position_category),
                mixer,
            ),
        ]
        for i, gen in enumerate(spot_pos_gens, start=1):
            # Generator params
            pos_params.append(
                OSCParam.bind(osc, "/sin_spot_pos_{}_amp".format(i), gen, "amp")
            )
            pos_params.append(
                OSCParam.bind(osc, "/sin_spot_pos_{}_period".format(i), gen, "period")
            )

        for fixture in self.spotlights:
            pan_ch = mixer.channel_lookup["{}.pan".format(fixture.name)]
            tilt_ch = mixer.channel_lookup["{}.tilt".format(fixture.name)]
            # Non-generator mixer params
            pos_params.append(
                OSCParam(
                    osc,
                    "/{}_pantilt_offset".format(fixture.name),
                    lambda pc=pan_ch, tc=tilt_ch: [pc.offset, tc.offset],
                    lambda _, *args, pc=pan_ch, tc=tilt_ch: _handle_pantilt_offset(
                        pc, tc, args
                    ),
                )
            )
            pan_fine_ch = mixer.channel_lookup["{}.pan_fine".format(fixture.name)]
            tilt_fine_ch = mixer.channel_lookup["{}.tilt_fine".format(fixture.name)]
            # Non-generator mixer params
            pos_params.append(
                OSCParam(
                    osc,
                    "/{}_pantilt_fine_offset".format(fixture.name),
                    lambda pc=pan_fine_ch, tc=tilt_fine_ch: [pc.offset, tc.offset],
                    lambda _, *args, pc=pan_fine_ch, tc=tilt_fine_ch: (
                        _handle_pantilt_offset(pc, tc, args)
                    ),
                )
            )

        loop_pairs = [
            (self.loop_spot_pos_1_x, self.loop_spot_pos_1_y, 1),
            (self.loop_spot_pos_2_x, self.loop_spot_pos_2_y, 2),
        ]
        for loop_x, loop_y, idx in loop_pairs:
            # Generator params
            pos_params.append(
                OSCParam(
                    osc,
                    "/loop_spot_pos_{}_input".format(idx),
                    lambda lx=loop_x, ly=loop_y: [lx.input_value, ly.input_value],
                    lambda _, *args, lx=loop_x, ly=loop_y: _handle_xy_loop_input(
                        lx, ly, args
                    ),
                )
            )
            pos_params.append(
                OSCParam.bind(osc, "/loop_spot_pos_{}_x_amp".format(idx), loop_x, "amp")
            )
            pos_params.append(
                OSCParam.bind(osc, "/loop_spot_pos_{}_y_amp".format(idx), loop_y, "amp")
            )
            for axis_gen in [loop_x, loop_y]:
                pos_params.append(
                    OSCParam(
                        osc,
                        "/{}_samples".format(axis_gen.name),
                        lambda g=axis_gen: g.samples,
                        lambda _, *args, g=axis_gen: g.load_samples(
                            list(args[0])
                            if len(args) == 1 and isinstance(args[0], (list, tuple))
                            else list(args)
                        ),
                    )
                )

        return {
            self.light_category: light_params,
            self.position_category: pos_params,
        }


def _handle_pantilt_offset(pan_ch: Any, tilt_ch: Any, args: tuple) -> None:
    if len(args) == 1 and isinstance(args[0], (list, tuple)):
        pan, tilt = args[0][0], args[0][1]
    else:
        pan, tilt = args[0], args[1]
    pan_ch.offset = float(pan)
    tilt_ch.offset = float(tilt)


def _handle_xy_loop_input(loop_x: Any, loop_y: Any, args: tuple) -> None:
    if len(args) == 1 and isinstance(args[0], (list, tuple)):
        x, y = args[0][0], args[0][1]
    else:
        x, y = args[0], args[1]
    loop_x.input_value = x
    loop_y.input_value = y
    loop_x.record_sample(x)
    loop_y.record_sample(y)
