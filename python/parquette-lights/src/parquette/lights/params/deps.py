from dataclasses import dataclass
from typing import Any, Callable, List

from ..audio_analysis import FFTManager
from ..dmx import DMXManager
from ..fixtures import RGBWLight, Spot
from ..fixtures.hazers import RadianceHazer
from ..generators import (
    BPMGenerator,
    FFTGenerator,
    ImpulseGenerator,
    LoopGenerator,
    Mixer,
    WaveGenerator,
)
from ..osc import OSCManager
from ..util.session_store import SessionStore


@dataclass(frozen=True)
class ParamDeps:
    """Bundle of collaborators that param builders need.

    Replaces the implicit closure-capture from server.run()'s scope with an
    explicit dependency graph passed into each builder module.
    """

    osc: OSCManager
    dmx: DMXManager
    mixer: Mixer
    session: SessionStore

    fft_manager: FFTManager
    fft1: FFTGenerator
    fft2: FFTGenerator

    sin_reds: WaveGenerator
    sin_plants: WaveGenerator
    sin_booth: WaveGenerator
    sin_wash: WaveGenerator
    sin_spot: WaveGenerator
    sin_spot_pos_1: WaveGenerator
    sin_spot_pos_2: WaveGenerator
    sin_spot_pos_3: WaveGenerator
    sin_spot_pos_4: WaveGenerator
    sq1: WaveGenerator
    sq2: WaveGenerator
    sq3: WaveGenerator

    impulse: ImpulseGenerator
    bpm_red: BPMGenerator
    bpm_wash: BPMGenerator

    loop_reds: LoopGenerator
    loop_spot_pos_1_x: LoopGenerator
    loop_spot_pos_1_y: LoopGenerator
    loop_spot_pos_2_x: LoopGenerator
    loop_spot_pos_2_y: LoopGenerator
    loop_max_samples: int

    hazer: RadianceHazer
    washceilf: RGBWLight
    washceilr: RGBWLight
    all_washes: List[Any]
    spotlights: List[Spot]

    set_dmx_passthrough: Callable[[Any], None]
