from typing import Any, Callable, List

from ..audio_analysis import FFTManager
from ..dmx import DMXManager
from ..fixtures.basics import RGBWLight
from ..fixtures.hazers import RadianceHazer
from ..fixtures.spotlights import Spot
from ..osc import OSCManager
from ..util.session_store import SessionStore
from .builder import ParamGeneratorBuilder
from . import audio, booth, channel_levels, hazer, non_saved, plants, reds, spots
from . import strobes, washes


def create_builders(
    *,
    fft_manager: FFTManager,
    dmx: DMXManager,
    session: SessionStore,
    hazer_fixture: RadianceHazer,
    washceilf: RGBWLight,
    washceilr: RGBWLight,
    all_washes: List[Any],
    spotlights: List[Spot],
    set_dmx_passthrough: Callable[[Any], None],
    loop_max_samples: int,
) -> List[ParamGeneratorBuilder]:
    return [
        reds.RedsBuilder(loop_max_samples),
        plants.PlantsBuilder(),
        booth.BoothBuilder(),
        washes.WashesBuilder(washceilf, washceilr, all_washes),
        spots.SpotsBuilder(spotlights, loop_max_samples),
        audio.AudioBuilder(fft_manager),
        strobes.StrobesBuilder(),
        hazer.HazerBuilder(hazer_fixture),
        non_saved.NonSavedBuilder(dmx, session, set_dmx_passthrough),
        channel_levels.ChannelLevelsBuilder(session),
    ]


__all__ = ["ParamGeneratorBuilder", "create_builders"]
