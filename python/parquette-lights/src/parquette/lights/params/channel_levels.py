from typing import Dict, List

from ..osc import OSCParam
from .deps import ParamDeps


def append_to(exposed: Dict[str, List[OSCParam]], deps: ParamDeps) -> None:
    """Append per-channel-level OSCParams to their owning category lists.

    Mixer exposes a `categorized_channel_names` mapping of category → list of
    channel names; we generate one OSCParam per channel under
    `/chan_levels/{name}`.
    """
    osc = deps.osc
    mixer = deps.mixer
    for category, chan_names in mixer.categorized_channel_names.items():
        for chan_name in chan_names:
            exposed[category].append(
                OSCParam(
                    osc,
                    "/chan_levels/{}".format(chan_name),
                    lambda chan=chan_name: mixer.getChannelLevel(chan),
                    lambda addr, args: mixer.setChannelLevel(addr.split("/")[2], args),
                )
            )
