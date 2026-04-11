from typing import Dict, List

from ..osc import OSCParam
from .deps import ParamDeps


def append_to(exposed: Dict[str, List[OSCParam]], deps: ParamDeps) -> None:
    """Append per-channel-level OSCParams to their owning category lists.

    Iterates mix_channels directly; each channel knows its own category.
    We generate one OSCParam per channel under `/chan_levels/{name}`.
    """
    osc = deps.osc
    mixer = deps.mixer
    session = deps.session
    for ch in mixer.mix_channels:
        # Sodium is persisted via SessionStore alongside the master
        # faders, so its slider needs to trigger a debounced save on
        # every change. Other channel levels live in preset pickles
        # via PresetManager and don't need an on_change hook.
        on_change = session.save if ch.name == "sodium.dimming" else None
        exposed[ch.category].append(
            OSCParam(
                osc,
                "/chan_levels/{}".format(ch.name),
                lambda chan=ch.name: mixer.getChannelLevel(chan),
                lambda addr, args: mixer.setChannelLevel(addr.split("/")[2], args),
                on_change=on_change,
            )
        )
