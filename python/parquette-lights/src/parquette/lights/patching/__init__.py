from typing import List

from ..audio_analysis import FFTManager
from ..category import Categories
from ..dmx import DMXManager
from ..osc import OSCManager
from ..util.session_store import SessionStore
from .builder import CategoryBuilder
from . import audio, booth, chandelier, channel_levels, hazer, non_saved, plants, reds
from . import spots, strobes, washes


def create_builders(
    *,
    osc: OSCManager,
    dmx: DMXManager,
    categories: Categories,
    fft_manager: FFTManager,
    session: SessionStore,
    loop_max_samples: int,
    spot_color_fade: float,
    spot_mechanical_time: float,
    debug: bool = False,
    debug_hazer: bool = False,
) -> List[CategoryBuilder]:
    fft_manager.bpms = []

    reds_b = reds.RedsBuilder(
        osc,
        dmx,
        fft_manager,
        categories.reds,
        loop_max_samples=loop_max_samples,
    )

    return [
        reds_b,
        plants.PlantsBuilder(osc, dmx, categories.plants, reds_b.bpm_red),
        booth.BoothBuilder(osc, dmx, categories.booth, reds_b.bpm_red),
        washes.WashesBuilder(
            osc,
            dmx,
            fft_manager,
            categories.washes,
            color_category=categories.washes_color,
        ),
        spots.SpotsBuilder(
            osc,
            dmx,
            categories.spots_light,
            categories.spots_position,
            loop_max_samples=loop_max_samples,
            bpm_red=reds_b.bpm_red,
            spot_color_fade=spot_color_fade,
            spot_mechanical_time=spot_mechanical_time,
        ),
        audio.AudioBuilder(osc, categories.audio, fft_manager, debug=debug),
        strobes.StrobesBuilder(osc, categories.strobes),
        hazer.HazerBuilder(osc, dmx, categories.hazer, debug=debug_hazer),
        chandelier.ChandelierBuilder(osc, dmx, categories.chandelier, reds_b.bpm_red),
        non_saved.NonSavedBuilder(osc, dmx, categories.non_saved, session),
        channel_levels.ChannelLevelsBuilder(osc, session),
    ]


__all__ = ["Categories", "CategoryBuilder", "create_builders"]
