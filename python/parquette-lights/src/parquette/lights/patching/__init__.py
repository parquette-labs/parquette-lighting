from typing import List

from ..audio_analysis import FFTManager
from ..category import Categories
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
    categories: Categories,
    fft_manager: FFTManager,
    dmx: DMXManager,
    session: SessionStore,
    loop_max_samples: int,
    debug: bool = False,
) -> List[ParamGeneratorBuilder]:
    fft_manager.bpms = []

    reds_b = reds.RedsBuilder(osc, fft_manager, categories.reds, loop_max_samples)

    return [
        reds_b,
        plants.PlantsBuilder(osc, categories.plants, reds_b.bpm_red),
        booth.BoothBuilder(osc, categories.booth, reds_b.bpm_red),
        washes.WashesBuilder(
            osc,
            fft_manager,
            categories.washes,
            categories.washes_color,
            all_fixtures=all_fixtures,
        ),
        spots.SpotsBuilder(
            osc,
            categories.spots_light,
            categories.spots_position,
            all_fixtures=all_fixtures,
            loop_max_samples=loop_max_samples,
            bpm_red=reds_b.bpm_red,
        ),
        audio.AudioBuilder(osc, categories.audio, fft_manager, debug=debug),
        strobes.StrobesBuilder(osc, categories.strobes),
        hazer.HazerBuilder(osc, categories.hazer, all_fixtures),
        non_saved.NonSavedBuilder(osc, categories.non_saved, dmx, session),
        channel_levels.ChannelLevelsBuilder(osc, session),
    ]
