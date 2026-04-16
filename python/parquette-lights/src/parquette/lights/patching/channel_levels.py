from typing import Dict, List

from ..category import Category
from ..generators.mixer import Mixer
from ..osc import OSCManager, OSCParam
from ..util.session_store import SessionStore
from .builder import CategoryBuilder


class ChannelLevelsBuilder(CategoryBuilder):
    def __init__(self, osc: OSCManager, session: SessionStore) -> None:
        self.osc = osc
        self.session = session

    def build_params(self, mixer: Mixer) -> Dict[Category, List[OSCParam]]:
        """Build per-channel offset params, grouped by each channel's category."""
        by_category: Dict[Category, List[OSCParam]] = {}
        for ch in mixer.mix_channels:
            on_change = self.session.save if ch.name == "sodium/dimming" else None
            param = ch.register_offset(self.osc, on_change=on_change)
            by_category.setdefault(ch.category, []).append(param)
        return by_category
