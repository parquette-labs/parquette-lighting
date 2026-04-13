from typing import Any, Dict, List, Tuple

from ..audio_analysis import FFTManager
from ..generators import FFTGenerator
from ..generators.generator import Generator
from ..generators.mixer import Mixer
from ..osc import OSCManager, OSCParam
from .builder import ParamGeneratorBuilder


class AudioBuilder(ParamGeneratorBuilder):
    def __init__(self, fft_manager: FFTManager) -> None:
        self.fft_manager = fft_manager

        self.fft1 = FFTGenerator(
            name="fft_1",
            category="audio",
            amp=1,
            offset=0,
            subdivisions=1,
            memory_length=20,
        )
        self.fft2 = FFTGenerator(
            name="fft_2",
            category="audio",
            amp=1,
            offset=0,
            subdivisions=1,
            memory_length=20,
        )

    def generators(self) -> List[Generator]:
        return [self.fft1, self.fft2]

    def build_params(self, osc: OSCManager, mixer: Mixer) -> Dict[str, List[OSCParam]]:
        def fft_dispatch_wedge(fft: Any, args: Tuple[Any, ...]) -> None:
            if len(args) == 1:
                fft.set_bounds(args[0][0], args[0][2])
            else:
                fft.set_bounds(args[0], args[2])

        return {
            "audio": [
                # Generator params
                OSCParam.bind(osc, "/fft1_amp", self.fft1, "amp"),
                OSCParam.bind(osc, "/fft2_amp", self.fft2, "amp"),
                OSCParam.bind(
                    osc,
                    "/fft_lpf_alpha",
                    self.fft1,
                    "lpf_alpha",
                    extra=[self.fft2],
                ),
                OSCParam.bind(osc, "/fft_threshold_1", self.fft1, "thres"),
                OSCParam.bind(osc, "/fft_threshold_2", self.fft2, "thres"),
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
