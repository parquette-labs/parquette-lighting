from typing import Dict, List

from ..generators.mixer import Mixer
from ..osc import OSCManager, OSCParam
from ..util.session_store import SessionStore
from .builder import ParamGeneratorBuilder


class ChannelLevelsBuilder(ParamGeneratorBuilder):
    def __init__(self, osc: OSCManager, session: SessionStore) -> None:
        self.osc = osc
        self.session = session

    def build_params(self, mixer: Mixer) -> Dict[str, List[OSCParam]]:
        """Build per-channel offset params, grouped by each channel's category."""
        by_category: Dict[str, List[OSCParam]] = {}
        for ch in mixer.mix_channels:
            on_change = self.session.save if ch.name == "sodium.dimming" else None
            param = OSCParam.bind(
                self.osc,
                "/mix_chan_offset/{}".format(ch.name),
                ch,
                "offset",
                on_change=on_change,
            )
            by_category.setdefault(ch.category, []).append(param)
        return by_category
