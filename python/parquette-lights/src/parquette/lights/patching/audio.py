from typing import Any, Dict, List, Tuple

from ..audio_analysis import FFTManager
from ..category import Category
from ..generators import FFTGenerator
from ..generators.generator import Generator
from ..generators.mixer import Mixer
from ..osc import OSCManager, OSCParam
from .builder import CategoryBuilder


class AudioBuilder(CategoryBuilder):
    def __init__(
        self,
        osc: OSCManager,
        category: Category,
        fft_manager: FFTManager,
        *,
        debug: bool = False,
    ) -> None:
        self.osc = osc
        self.category = category
        self.fft_manager = fft_manager

        self.fft1 = FFTGenerator(
            name="fft_1",
            category=category,
            amp=1,
            offset=0,
            subdivisions=1,
            memory_length=20,
        )
        self.fft2 = FFTGenerator(
            name="fft_2",
            category=category,
            amp=1,
            offset=0,
            subdivisions=1,
            memory_length=20,
        )

        if debug:
            self.fft1.debug = True
            self.fft2.debug = True

        fft_manager.downstream = [self.fft1, self.fft2]

    def generators(self) -> List[Generator]:
        return [self.fft1, self.fft2]

    def build_params(self, mixer: Mixer) -> Dict[Category, List[OSCParam]]:
        osc = self.osc

        def fft_dispatch_wedge(fft: Any, args: Tuple[Any, ...]) -> None:
            if len(args) == 1:
                fft.set_bounds(args[0][0], args[0][2])
            else:
                fft.set_bounds(args[0], args[2])

        return {
            self.category: [
                # Standard generator params (/gen/{type}/{name}/{attr})
                *self.fft1.standard_params(osc),
                *self.fft2.standard_params(osc),
                # Custom FFT bounds params (not simple scalar attrs)
                OSCParam(
                    osc,
                    "/fft_bounds_1",
                    lambda: (
                        self.fft1.fft_bounds[0],
                        0,
                        self.fft1.fft_bounds[1],
                        0,
                    ),
                    lambda _addr, *args: fft_dispatch_wedge(self.fft1, args),
                ),
                OSCParam(
                    osc,
                    "/fft_bounds_2",
                    lambda: (
                        self.fft2.fft_bounds[0],
                        0,
                        self.fft2.fft_bounds[1],
                        0,
                    ),
                    lambda _addr, *args: fft_dispatch_wedge(self.fft2, args),
                ),
                # Non-generator params (fft_manager)
                OSCParam.bind(
                    osc,
                    "/bpm_energy_threshold",
                    self.fft_manager,
                    "energy_threshold",
                ),
                OSCParam.bind(osc, "/bpm_tempo_alpha", self.fft_manager, "tempo_alpha"),
                OSCParam.bind(
                    osc,
                    "/onset_envelope_floor",
                    self.fft_manager,
                    "onset_envelope_floor",
                ),
                OSCParam.bind(
                    osc, "/bpm_business_min", self.fft_manager, "min_business"
                ),
                OSCParam.bind(
                    osc,
                    "/bpm_regularity_min",
                    self.fft_manager,
                    "min_regularity",
                ),
            ]
        }
