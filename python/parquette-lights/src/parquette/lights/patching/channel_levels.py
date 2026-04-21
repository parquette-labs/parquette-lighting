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
        """Build per-channel offset params, grouped by each channel's category.

        Virtual channels (e.g. PantiltChannel) are skipped here because the
        builder that owns the underlying fixture is responsible for their
        offset OSCParam — it needs the param reference to drive coord-system
        sync without registering the same OSC address twice.
        """
        by_category: Dict[Category, List[OSCParam]] = {}
        for ch in mixer.mix_channels:
            if ch.is_virtual:
                continue
            on_change = self.session.save if ch.name == "sodium/dimming" else None
            param = ch.register_offset(self.osc, on_change=on_change)
            by_category.setdefault(ch.category, []).append(param)
        return by_category
