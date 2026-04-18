from typing import Dict, List

from .osc import OSCManager, OSCParam
from .util.session_store import SessionStore


class Category:
    """Represents a preset category.

    Every category owns a master value and binds an OSCParam that keeps it
    in sync with OSC. Master changes trigger a session save.
    """

    def __init__(
        self,
        name: str,
        osc: OSCManager,
        session: SessionStore,
    ) -> None:
        self.name = name
        self.osc = osc
        self.session = session
        self.master: float = 1.0

        self.master_param: OSCParam = OSCParam.bind(
            osc,
            "/{}_master".format(name),
            self,
            "master",
            on_change=session.save,
        )

    def set_master(self, value: float) -> None:
        """Set master value locally and sync to frontend."""
        self.master = value
        self.master_param.sync()


class Categories:
    """Registry of all preset categories."""

    def __init__(self, osc: OSCManager, session: SessionStore) -> None:
        self.reds = Category("reds", osc, session)
        self.plants = Category("plants", osc, session)
        self.booth = Category("booth", osc, session)
        self.spots_light = Category("spots_light", osc, session)
        self.washes = Category("washes", osc, session)
        self.spots_position = Category("spots_position", osc, session)
        self.washes_color = Category("washes_color", osc, session)
        self.audio = Category("audio", osc, session)
        self.strobes = Category("strobes", osc, session)
        self.hazer = Category("hazer", osc, session)
        self.chandelier = Category("chandelier", osc, session)
        self.non_saved = Category("non-saved", osc, session)

        self.all: List[Category] = [
            self.reds,
            self.plants,
            self.booth,
            self.spots_light,
            self.washes,
            self.spots_position,
            self.washes_color,
            self.audio,
            self.strobes,
            self.hazer,
            self.chandelier,
            self.non_saved,
        ]
        self._by_name: Dict[str, Category] = {c.name: c for c in self.all}

    def by_name(self, name: str) -> Category:
        """Look up a category by its string name (for dynamic lookup)."""
        return self._by_name[name]

    def save_masters(self) -> Dict[str, float]:
        """Return a dict of master values for every category."""
        return {c.name: c.master for c in self.all}

    def load_masters(self, data: Dict[str, float]) -> None:
        """Restore master values from a saved session."""
        for name, value in data.items():
            cat = self._by_name.get(name)
            if cat is not None:
                cat.set_master(value)
