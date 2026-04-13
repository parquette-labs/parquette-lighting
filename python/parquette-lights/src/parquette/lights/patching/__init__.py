from typing import List

from ..audio_analysis import FFTManager
from ..dmx import DMXManager
from ..fixtures.basics import Fixture
from ..util.session_store import SessionStore
from .builder import ParamGeneratorBuilder
from . import audio, booth, channel_levels, hazer, non_saved, plants, reds, spots
from . import strobes, washes


def create_builders(
    *,
    all_fixtures: List[Fixture],
    fft_manager: FFTManager,
    dmx: DMXManager,
    session: SessionStore,
    loop_max_samples: int,
) -> List[ParamGeneratorBuilder]:
    return [
        reds.RedsBuilder(loop_max_samples),
        plants.PlantsBuilder(),
        booth.BoothBuilder(),
        washes.WashesBuilder(all_fixtures),
        spots.SpotsBuilder(all_fixtures, loop_max_samples),
        audio.AudioBuilder(fft_manager),
        strobes.StrobesBuilder(),
        hazer.HazerBuilder(all_fixtures),
        non_saved.NonSavedBuilder(dmx, session),
        channel_levels.ChannelLevelsBuilder(session),
    ]


__all__ = ["ParamGeneratorBuilder", "create_builders"]
