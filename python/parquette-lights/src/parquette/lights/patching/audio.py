from typing import Dict, List

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
        return {
            self.category: [
                # Standard generator params (/gen/{ClassName}/{name}/{attr}) —
                # FFTGenerator.standard_params() includes the bounds param
                *self.fft1.standard_params(osc),
                *self.fft2.standard_params(osc),
                # Audio tuning params on fft_manager
                OSCParam.bind(
                    osc,
                    "/audio_config/bpm_energy_threshold",
                    self.fft_manager,
                    "energy_threshold",
                ),
                OSCParam.bind(
                    osc,
                    "/audio_config/bpm_tempo_alpha",
                    self.fft_manager,
                    "tempo_alpha",
                ),
                OSCParam.bind(
                    osc,
                    "/audio_config/onset_envelope_floor",
                    self.fft_manager,
                    "onset_envelope_floor",
                ),
                OSCParam.bind(
                    osc,
                    "/audio_config/bpm_business_min",
                    self.fft_manager,
                    "min_business",
                ),
                OSCParam.bind(
                    osc,
                    "/audio_config/bpm_regularity_min",
                    self.fft_manager,
                    "min_regularity",
                ),
            ]
        }
