from typing import Dict, List

from .osc import OSCManager, OSCParam
from .util.interpolator import Interpolator
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
        self.master_interp: Interpolator = Interpolator(1.0)

        self.master_param: OSCParam = OSCParam.bind(
            osc,
            "/{}_master".format(name),
            self,
            "master",
            on_change=session.save,
        )

    @property
    def master(self) -> float:
        """Current master level, read straight from the interpolator.

        Making this a property (rather than a plain attribute) gives a single
        source of truth: direct writes -- e.g. the UI master fader arriving via
        OSCParam.obj_param_setter -- and scene fades share the same backing
        value and can never diverge. Previously a direct write left
        master_interp.current stale, so the next scene fade started from that
        stale value and the master (and thus spot brightness) jumped at the
        start of the crossfade.
        """
        return self.master_interp.current

    @master.setter
    def master(self, value: float) -> None:
        # A direct write snaps the interpolator to the value and cancels any
        # in-flight fade -- mirrors MixChannel.offset. Grabbing the master
        # fader mid-fade thus takes over cleanly instead of being clobbered.
        self.master_interp.set_target(float(value), 0)

    def set_master(self, value: float, fade_ticks: int = 0) -> None:
        """Set master value, optionally interpolating over fade_ticks."""
        if fade_ticks > 0:
            self.master_interp.set_target(value, fade_ticks)
        else:
            self.master = value
            self.master_param.sync()

    def tick_interpolator(self) -> None:
        """Advance the master interpolator and sync if active."""
        if self.master_interp.active:
            self.master_interp.tick()
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
