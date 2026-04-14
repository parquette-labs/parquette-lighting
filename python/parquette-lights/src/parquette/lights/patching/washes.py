from typing import Dict, List, Union

from ..audio_analysis import FFTManager
from ..category import Category
from ..dmx import DMXManager
from ..fixtures.basics import Fixture, RGBLight, RGBWLight
from ..generators import SignalPatchParam, WaveGenerator, BPMGenerator
from ..generators.generator import Generator
from ..generators.mixer import Mixer
from ..osc import OSCManager, OSCParam
from .builder import (
    CategoryBuilder,
    channel_names_for_category,
    register_snap_handler,
)


class WashesBuilder(CategoryBuilder):
    def __init__(
        self,
        osc: OSCManager,
        dmx: DMXManager,
        fft_manager: FFTManager,
        category: Category,
        *,
        color_category: Category,
    ) -> None:
        self.osc = osc
        self.category = category
        self.color_category = color_category
        initial_amp: float = 200
        initial_period: int = 3500

        washfl = RGBLight(name="wash_fl", category=category, dmx=dmx, addr=104, osc=osc)
        washfl.rgb(0, 0, 0)
        washfr = RGBLight(name="wash_fr", category=category, dmx=dmx, addr=107, osc=osc)
        washfr.rgb(0, 0, 0)
        washml = RGBLight(name="wash_ml", category=category, dmx=dmx, addr=110, osc=osc)
        washml.rgb(0, 0, 0)
        washmr = RGBLight(name="wash_mr", category=category, dmx=dmx, addr=113, osc=osc)
        washmr.rgb(0, 0, 0)
        washbl = RGBLight(name="wash_bl", category=category, dmx=dmx, addr=120, osc=osc)
        washbl.rgb(0, 0, 0)
        washbr = RGBLight(name="wash_br", category=category, dmx=dmx, addr=123, osc=osc)
        washbr.rgb(0, 0, 0)
        self.washceilf = RGBWLight(
            name="wash_ceil_f", category=category, dmx=dmx, addr=100, osc=osc
        )
        self.washceilf.rgbw(0, 0, 0, 0)
        self.washceilr = RGBWLight(
            name="wash_ceil_r", category=category, dmx=dmx, addr=116, osc=osc
        )
        self.washceilr.rgbw(0, 0, 0, 0)
        self.all_washes: List[Union[RGBLight, RGBWLight]] = [
            washfl,
            washfr,
            washml,
            washmr,
            washbl,
            washbr,
            self.washceilf,
            self.washceilr,
        ]

        self.sin_wash = WaveGenerator(
            name="sin_wash",
            category=category,
            amp=initial_amp,
            period=initial_period,
            phase=0,
            offset=0,
            shape=WaveGenerator.Shape.SIN,
        )
        self.bpm_wash = BPMGenerator(
            name="bpm_wash", category=category, amp=255, offset=0, duty=100
        )

        register_snap_handler(
            osc,
            "/snap_sin_wash_to_bpm",
            [self.sin_wash],
            "/period_wash",
            self.bpm_wash,
        )
        fft_manager.bpms.append(self.bpm_wash)

    def fixtures(self) -> List[Fixture]:
        return list(self.all_washes)

    def generators(self) -> List[Generator]:
        return [self.sin_wash, self.bpm_wash]

    def build_params(self, mixer: Mixer) -> Dict[Category, List[OSCParam]]:
        osc = self.osc

        def dispatch_wash_color(_addr: str, *rgb: float) -> None:
            if len(rgb) < 3:
                return
            for fixture in self.all_washes:
                fixture.set_dimming_target(r=rgb[0], g=rgb[1], b=rgb[2])

        return {
            self.color_category: [
                # Non-generator fixture params
                OSCParam.bind(
                    osc,
                    "/wash_w",
                    [self.washceilf, self.washceilr],
                    "w_target",
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
            self.category: [
                # Patch params
                SignalPatchParam(
                    osc,
                    "/signal_patchbay/washes",
                    channel_names_for_category(mixer, self.category),
                    mixer,
                ),
                # Non-generator params
                OSCParam.bind(
                    osc,
                    "/washes_stutter_period",
                    mixer,
                    "washes_stutter_period",
                ),
                # Standard generator params (/gen/{type}/{name}/{attr})
                *self.sin_wash.standard_params(osc),
                *self.bpm_wash.standard_params(osc),
            ],
        }
