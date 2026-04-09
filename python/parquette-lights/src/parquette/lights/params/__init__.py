from typing import Dict, List

from ..osc import OSCParam
from . import (
    audio,
    booth,
    channel_levels,
    hazer,
    non_saved,
    plants,
    reds,
    spots,
    strobes,
    washes,
)
from .deps import ParamDeps


def build_exposed_params(deps: ParamDeps) -> Dict[str, List[OSCParam]]:
    """Construct the full `exposed_params` dict consumed by PresetManager.

    Category keys and OSC addresses match the original inline construction in
    server.run() so existing preset pickles and the open-stage-control layout
    JSON keep working without migration.
    """
    exposed: Dict[str, List[OSCParam]] = {
        "fft": [],
        "reds": reds.build(deps),
        "plants": plants.build(deps),
        "booth": booth.build(deps),
        "strobes": strobes.build(deps),
        "washes_color": washes.build_washes_color(deps),
        "washes": washes.build(deps),
        "spots_light": spots.build_lights(deps),
        "spots_position": spots.build_position(deps),
        "audio": audio.build(deps),
        "hazer": hazer.build(deps),
        "non-saved": non_saved.build(deps),
    }
    channel_levels.append_to(exposed, deps)
    return exposed


__all__ = ["ParamDeps", "build_exposed_params"]
