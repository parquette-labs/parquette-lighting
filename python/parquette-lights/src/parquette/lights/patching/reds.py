from typing import Dict, List

from ..audio_analysis import FFTManager
from ..category import Category
from ..dmx import DMXManager
from ..fixtures import LightFixture
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


def _handle_loop_input(gen: LoopGenerator, value: float) -> None:
    gen.input_value = value
    gen.record_sample(value)


class RedsBuilder(CategoryBuilder):
    def __init__(
        self,
        osc: OSCManager,
        dmx: DMXManager,
        fft_manager: FFTManager,
        category: Category,
        *,
        loop_max_samples: int,
    ) -> None:
        self.osc = osc
        self.category = category
        initial_amp: float = 200
        initial_period: int = 3500

        self.dimmers: List[LightFixture] = [
            LightFixture(name="left_1", category=category, dmx=dmx, addr=4, osc=osc),
            LightFixture(name="left_2", category=category, dmx=dmx, addr=3, osc=osc),
            LightFixture(name="left_3", category=category, dmx=dmx, addr=2, osc=osc),
            LightFixture(name="left_4", category=category, dmx=dmx, addr=1, osc=osc),
            LightFixture(name="right_1", category=category, dmx=dmx, addr=5, osc=osc),
            LightFixture(name="right_2", category=category, dmx=dmx, addr=6, osc=osc),
            LightFixture(name="right_3", category=category, dmx=dmx, addr=7, osc=osc),
            LightFixture(name="right_4", category=category, dmx=dmx, addr=8, osc=osc),
            LightFixture(name="front_1", category=category, dmx=dmx, addr=12, osc=osc),
            LightFixture(name="front_2", category=category, dmx=dmx, addr=9, osc=osc),
        ]

        self.sin_reds = WaveGenerator(
            name="sin_red",
            category=category,
            amp=initial_amp,
            period=initial_period,
            phase=0,
            offset=0,
            shape=WaveGenerator.Shape.SIN,
        )
        self.bpm_red = BPMGenerator(
            name="bpm_red", category=category, amp=255, offset=0, duty=100
        )
        self.loop_reds = LoopGenerator(
            name="loop_reds", category=category, max_samples=loop_max_samples
        )

        register_snap_handler(
            osc,
            "/snap_sin_red_to_bpm",
            [self.sin_reds],
            "/sin_red_period",
            self.bpm_red,
        )
        register_loop_record_handler(osc, "/loop_reds_record", [self.loop_reds])
        fft_manager.bpms.append(self.bpm_red)

    def fixtures(self) -> List[Fixture]:
        return list(self.dimmers)

    def generators(self) -> List[Generator]:
        return [self.sin_reds, self.bpm_red, self.loop_reds]

    def build_params(self, mixer: Mixer) -> Dict[Category, List[OSCParam]]:
        osc = self.osc
        return {
            self.category: [
                # Patch params
                SignalPatchParam(
                    osc,
                    "/signal_patchbay/reds",
                    channel_names_for_category(mixer, self.category),
                    mixer,
                ),
                # Non-generator params
                OSCParam.bind(
                    osc, "/reds_stutter_period", mixer, "reds_stutter_period"
                ),
                # Standard generator params (/gen/{type}/{name}/{attr})
                *self.sin_reds.standard_params(osc),
                *self.bpm_red.standard_params(osc),
                *self.loop_reds.standard_params(osc),
                # Custom loop params
                OSCParam(
                    osc,
                    "/loop_reds_input",
                    lambda: self.loop_reds.input_value,
                    lambda _, args: _handle_loop_input(self.loop_reds, args),
                ),
                OSCParam(
                    osc,
                    "/loop_reds_samples",
                    lambda: self.loop_reds.samples,
                    lambda _, *args: self.loop_reds.load_samples(
                        list(args[0])
                        if len(args) == 1 and isinstance(args[0], (list, tuple))
                        else list(args)
                    ),
                ),
            ]
        }
