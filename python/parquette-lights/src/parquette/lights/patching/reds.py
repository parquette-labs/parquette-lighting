from typing import Dict, List

from ..generators import SignalPatchParam, WaveGenerator, BPMGenerator, LoopGenerator
from ..generators.generator import Generator
from ..generators.mixer import Mixer
from ..osc import OSCManager, OSCParam
from .builder import ParamGeneratorBuilder


def _handle_loop_input(gen: LoopGenerator, value: float) -> None:
    gen.input_value = value
    gen.record_sample(value)


class RedsBuilder(ParamGeneratorBuilder):
    def __init__(self, loop_max_samples: int) -> None:
        initial_amp: float = 200
        initial_period: int = 3500

        self.sin_reds = WaveGenerator(
            name="sin_red",
            category="reds",
            amp=initial_amp,
            period=initial_period,
            phase=0,
            offset=0,
            shape=WaveGenerator.Shape.SIN,
        )
        self.bpm_red = BPMGenerator(
            name="bpm_red", category="reds", amp=255, offset=0, duty=100
        )
        self.loop_reds = LoopGenerator(
            name="loop_reds", category="reds", max_samples=loop_max_samples
        )

    def generators(self) -> List[Generator]:
        return [self.sin_reds, self.bpm_red, self.loop_reds]

    def build_params(self, osc: OSCManager, mixer: Mixer) -> Dict[str, List[OSCParam]]:
        return {
            "reds": [
                # Patch params
                SignalPatchParam(
                    osc,
                    "/signal_patchbay/reds",
                    [
                        "left_1.dimming",
                        "left_2.dimming",
                        "left_3.dimming",
                        "left_4.dimming",
                        "right_1.dimming",
                        "right_2.dimming",
                        "right_3.dimming",
                        "right_4.dimming",
                        "front_1.dimming",
                        "front_2.dimming",
                        "reds_mono",
                        "reds_fwd",
                        "reds_back",
                        "reds_zig",
                    ],
                    mixer,
                ),
                # Non-generator params
                OSCParam.bind(
                    osc, "/reds_stutter_period", mixer, "reds_stutter_period"
                ),
                # Generator params
                OSCParam.bind(osc, "/sin_red_amp", self.sin_reds, "amp"),
                OSCParam.bind(osc, "/sin_red_period", self.sin_reds, "period"),
                OSCParam.bind(osc, "/bpm_red_mult", self.bpm_red, "bpm_mult"),
                OSCParam.bind(osc, "/bpm_red_duty", self.bpm_red, "duty"),
                OSCParam.bind(osc, "/bpm_red_lpf_alpha", self.bpm_red, "lpf_alpha"),
                OSCParam.bind(osc, "/bpm_red_amp", self.bpm_red, "amp"),
                OSCParam.bind(
                    osc, "/bpm_red_manual_offset", self.bpm_red, "manual_offset"
                ),
                OSCParam(
                    osc,
                    "/loop_reds_input",
                    lambda: self.loop_reds.input_value,
                    lambda _, args: _handle_loop_input(self.loop_reds, args),
                ),
                OSCParam.bind(osc, "/loop_reds_amp", self.loop_reds, "amp"),
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
