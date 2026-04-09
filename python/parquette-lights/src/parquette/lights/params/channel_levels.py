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
    session = deps.session
    for category, chan_names in mixer.categorized_channel_names.items():
        for chan_name in chan_names:
            # Sodium is persisted via SessionStore alongside the master
            # faders, so its slider needs to trigger a debounced save on
            # every change. Other channel levels live in preset pickles
            # via PresetManager and don't need an on_change hook.
            on_change = session.save if chan_name == "sodium" else None
            exposed[category].append(
                OSCParam(
                    osc,
                    "/chan_levels/{}".format(chan_name),
                    lambda chan=chan_name: mixer.getChannelLevel(chan),
                    lambda addr, args: mixer.setChannelLevel(addr.split("/")[2], args),
                    on_change=on_change,
                )
            )
