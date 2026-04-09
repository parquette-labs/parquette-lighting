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
    sq1: WaveGenerator
    sq2: WaveGenerator
    sq3: WaveGenerator

    impulse: ImpulseGenerator
    bpm_red: BPMGenerator
    bpm_wash: BPMGenerator

    hazer: RadianceHazer
    washceilf: RGBWLight
    washceilr: RGBWLight
    all_washes: List[Any]
    spotlights: List[Spot]

    set_dmx_passthrough: Callable[[Any], None]
