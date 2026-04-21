"""Global coord-system state holder.

Owns the active CoordSystem and the list of fixtures that need to be
notified when it changes. Exposes a single OSC param `/coord_system`
whose value is the system name (e.g. "pantilt", "latlon"). Persists the
active name in the session pickle so the user's choice survives restarts.

The coord toggle is intentionally NOT a preset value — it is a UI / shell
preference, decoupled from the lighting state captured by presets.
"""

from typing import Any, Callable, Dict, List, Optional

from .osc import OSCManager, OSCParam
from .util.coord_system import CoordSystem
from .util.session_store import SessionStore


class CoordSystemState:
    def __init__(
        self,
        systems: Dict[str, CoordSystem],
        osc: OSCManager,
        session: SessionStore,
        initial_active: Optional[str] = None,
    ) -> None:
        if not systems:
            raise ValueError("systems dict cannot be empty")
        self.systems = systems
        self.osc = osc
        self.session = session
        # Late-bound list — fixtures register after construction.
        self.listeners: List[Any] = []

        if initial_active is not None and initial_active in systems:
            self._active_name = initial_active
        else:
            # Default to the first key — typically "pantilt".
            self._active_name = next(iter(systems))

        self.osc_param = OSCParam(
            osc,
            "/coord_system",
            value_lambda=lambda: self._active_name,
            dispatch_lambda=self._handle_osc,
            default_value=self._active_name,
        )

    @property
    def active(self) -> CoordSystem:
        return self.systems[self._active_name]

    @property
    def active_name(self) -> str:
        return self._active_name

    def register(self, listener: Any) -> None:
        """Register a fixture to be notified of coord-system changes.

        The listener must implement `rebind_coords(old, new)`.
        """
        self.listeners.append(listener)

    def set_active(self, name: str) -> None:
        if name not in self.systems:
            print(
                "Ignoring unknown coord system '{}'; known: {}".format(
                    name, list(self.systems.keys())
                ),
                flush=True,
            )
            return
        if name == self._active_name:
            return
        old = self.active
        self._active_name = name
        new = self.active
        for listener in self.listeners:
            listener.rebind_coords(old, new)
        # Persist the choice. Session.save is debounced.
        self.session.save()
        # Sync the OSC param so any other clients see the new value.
        self.osc_param.sync()

    def _handle_osc(self, _addr: str, *args: Any) -> None:
        if not args:
            return
        value = args[0]
        if isinstance(value, (list, tuple)):
            value = value[0] if value else None
        if value is None:
            return
        self.set_active(str(value))


def coord_system_snapshot_fields(state: CoordSystemState) -> Dict[str, Any]:
    """Snapshot the state for inclusion in the session pickle."""
    return {"coord_system": state.active_name}


def restore_coord_system(
    state: CoordSystemState, restored: Optional[Dict[str, Any]]
) -> None:
    """Apply a saved coord_system name from a session restore.

    No-op if the saved data is missing or names an unknown system. The
    state's initial active name will already be the seeded value, so this
    only matters when state was constructed before session.load().
    """
    if not restored:
        return
    name = restored.get("coord_system")
    if isinstance(name, str):
        state.set_active(name)


_Listener = Callable[..., Any]  # for documentation
