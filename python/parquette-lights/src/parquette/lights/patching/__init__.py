from typing import List

from ..audio_analysis import FFTManager
from ..dmx import DMXManager
from ..fixtures.basics import Fixture
from ..osc import OSCManager
from ..util.session_store import SessionStore
from .builder import ParamGeneratorBuilder
from . import audio, booth, channel_levels, hazer, non_saved, plants, reds, spots
from . import strobes, washes


def create_builders(
    *,
    osc: OSCManager,
    all_fixtures: List[Fixture],
    fft_manager: FFTManager,
    dmx: DMXManager,
    session: SessionStore,
    loop_max_samples: int,
    debug: bool = False,
) -> List[ParamGeneratorBuilder]:
    # Initialize fft_manager.bpms so builders can append to it
    fft_manager.bpms = []

    reds_b = reds.RedsBuilder(osc, fft_manager, loop_max_samples)

    return [
        reds_b,
        plants.PlantsBuilder(osc, reds_b.bpm_red),
        booth.BoothBuilder(osc, reds_b.bpm_red),
        washes.WashesBuilder(osc, fft_manager, all_fixtures),
        spots.SpotsBuilder(osc, all_fixtures, loop_max_samples, reds_b.bpm_red),
        audio.AudioBuilder(osc, fft_manager, debug=debug),
        strobes.StrobesBuilder(osc),
        hazer.HazerBuilder(osc, all_fixtures),
        non_saved.NonSavedBuilder(osc, dmx, session),
        channel_levels.ChannelLevelsBuilder(osc, session),
    ]


__all__ = ["ParamGeneratorBuilder", "create_builders"]
