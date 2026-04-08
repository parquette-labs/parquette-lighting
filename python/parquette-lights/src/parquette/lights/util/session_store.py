import os
import pickle
from threading import Lock, Timer
from typing import Any, Callable, Dict, Optional

SCHEMA_VERSION = 1


class SessionStore:
    """Persists per-session UI state (active presets, master fader values)
    to a pickle file and restores it on launch.

    Writes are debounced so dragging a fader doesn't thrash the disk.
    """

    def __init__(self, filename: str, *, debounce_seconds: float = 0.25) -> None:
        self.filename = filename
        self.debounce_seconds = debounce_seconds
        self._snapshot_fn: Optional[Callable[[], Dict[str, Any]]] = None
        self._timer: Optional[Timer] = None
        self._lock = Lock()

    def bind(self, snapshot_fn: Callable[[], Dict[str, Any]]) -> None:
        """Register the function used to capture current state at write time.

        Bound separately from construction so the snapshot closure can
        capture references to PresetManager / Mixer that are built after
        SessionStore.
        """
        self._snapshot_fn = snapshot_fn

    def load(self) -> Optional[Dict[str, Any]]:
        try:
            with open(self.filename, "rb") as f:
                data = pickle.load(f)
        # pylint: disable=broad-exception-caught
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"Session pickle load failed: {e}", flush=True)
            return None

        if not isinstance(data, dict) or data.get("version") != SCHEMA_VERSION:
            print(
                f"Session pickle has unexpected schema, ignoring: {data!r}",
                flush=True,
            )
            return None
        return data

    def save(self) -> None:
        """Schedule a debounced write. Coalesces rapid calls."""
        if self._snapshot_fn is None:
            return
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = Timer(self.debounce_seconds, self._flush)
            self._timer.daemon = True
            self._timer.start()

    def _flush(self) -> None:
        if self._snapshot_fn is None:
            return
        try:
            data = self._snapshot_fn()
            data["version"] = SCHEMA_VERSION
            tmp = self.filename + ".tmp"
            with open(tmp, "wb") as f:
                pickle.dump(data, f)
            os.replace(tmp, self.filename)
        # pylint: disable=broad-exception-caught
        except Exception as e:
            print(f"Session pickle save failed: {e}", flush=True)
