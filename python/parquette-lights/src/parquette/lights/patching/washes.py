from typing import Dict, List

from ..audio_analysis import FFTManager
from ..generators import SignalPatchParam, WaveGenerator, BPMGenerator
from ..generators.generator import Generator
from ..generators.mixer import Mixer
from ..fixtures.basics import Fixture, RGBLight, RGBWLight
from ..osc import OSCManager, OSCParam
from .builder import ParamGeneratorBuilder, register_snap_handler


class WashesBuilder(ParamGeneratorBuilder):
    def __init__(
        self, osc: OSCManager, fft_manager: FFTManager, all_fixtures: List[Fixture]
    ) -> None:
        self.osc = osc
        initial_amp: float = 200
        initial_period: int = 3500

        self.all_washes: list[RGBLight] = [
            f
            for f in all_fixtures
            if f.category == "washes" and isinstance(f, RGBLight)
        ]
        rgbw_washes = [f for f in self.all_washes if isinstance(f, RGBWLight)]
        self.washceilf = rgbw_washes[0]
        self.washceilr = rgbw_washes[1]

        self.sin_wash = WaveGenerator(
            name="sin_wash",
            category="washes",
            amp=initial_amp,
            period=initial_period,
            phase=0,
            offset=0,
            shape=WaveGenerator.Shape.SIN,
        )
        self.bpm_wash = BPMGenerator(
            name="bpm_wash", category="washes", amp=255, offset=0, duty=100
        )

        register_snap_handler(
            osc,
            "/snap_sin_wash_to_bpm",
            [self.sin_wash],
            "/period_wash",
            self.bpm_wash,
        )
        fft_manager.bpms.append(self.bpm_wash)

    def generators(self) -> List[Generator]:
        return [self.sin_wash, self.bpm_wash]

    def build_params(self, mixer: Mixer) -> Dict[str, List[OSCParam]]:
        osc = self.osc

        def dispatch_wash_color(_addr: str, *rgb: float) -> None:
            if len(rgb) < 3:
                return
            for fixture in self.all_washes:
                fixture.set_dimming_target(r=rgb[0], g=rgb[1], b=rgb[2])

        return {
            "washes_color": [
                # Non-generator fixture params
                OSCParam.bind(
                    osc,
                    "/wash_w",
                    self.washceilf,
                    "w_target",
                    extra=[self.washceilr],
                ),
                OSCParam(
                    osc,
                    "/wash_color",
                    lambda: [
                        self.washceilf.r_target,
                        self.washceilf.g_target,
                        self.washceilf.b_target,
                    ],
                    dispatch_wash_color,
                ),
            ],
            "washes": [
                # Patch params
                SignalPatchParam(
                    osc,
                    "/signal_patchbay/washes",
                    [
                        "wash_fl.dimming",
                        "wash_fr.dimming",
                        "wash_ml.dimming",
                        "wash_mr.dimming",
                        "wash_bl.dimming",
                        "wash_br.dimming",
                        "wash_ceil_f.dimming",
                        "wash_ceil_r.dimming",
                        "washes_mono",
                        "washes_fwd",
                        "washes_back",
                    ],
                    mixer,
                ),
                # Non-generator params
                OSCParam.bind(
                    osc,
                    "/washes_stutter_period",
                    mixer,
                    "washes_stutter_period",
                ),
                # Generator params
                OSCParam.bind(osc, "/amp_wash", self.sin_wash, "amp"),
                OSCParam.bind(osc, "/period_wash", self.sin_wash, "period"),
                OSCParam.bind(osc, "/bpm_wash_amp", self.bpm_wash, "amp"),
                OSCParam.bind(osc, "/bpm_wash_duty", self.bpm_wash, "duty"),
                OSCParam.bind(osc, "/bpm_wash_lpf_alpha", self.bpm_wash, "lpf_alpha"),
                OSCParam.bind(osc, "/bpm_wash_mult", self.bpm_wash, "bpm_mult"),
                OSCParam.bind(
                    osc,
                    "/bpm_wash_manual_offset",
                    self.bpm_wash,
                    "manual_offset",
                ),
            ],
        }
