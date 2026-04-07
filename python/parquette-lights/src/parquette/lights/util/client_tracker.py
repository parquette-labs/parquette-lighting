import time
from threading import Thread
from typing import Dict

from ..osc import OSCManager


class ClientTracker:
    """Tracks connected open-stage-control UI sessions via /heartbeat OSC.

    Each UI session's root onCreate sends /heartbeat <session_id> on a fixed
    interval. We record last-seen time per id, prune stale entries, and push
    the live count to the UI at /client_count whenever it changes.
    """

    def __init__(
        self,
        osc: OSCManager,
        *,
        heartbeat_addr: str = "/heartbeat",
        count_addr: str = "/client_count",
        timeout: float = 6.0,
        poll_interval: float = 1.0,
    ) -> None:
        self.osc = osc
        self.heartbeat_addr = heartbeat_addr
        self.count_addr = count_addr
        self.timeout = timeout
        self.poll_interval = poll_interval

        self._heartbeats: Dict[int, float] = {}
        self._last_count = -1
        self._thread: Thread | None = None

        osc.dispatcher.map(heartbeat_addr, self._on_heartbeat)

    def _on_heartbeat(self, _addr: str, *args) -> None:
        if not args:
            return
        try:
            client_id = int(args[0])
        except (TypeError, ValueError):
            return
        self._heartbeats[client_id] = time.time()

    def _prune_loop(self) -> None:
        while True:
            now = time.time()
            stale = [
                cid
                for cid, seen in self._heartbeats.items()
                if now - seen > self.timeout
            ]
            for cid in stale:
                self._heartbeats.pop(cid, None)
            count = len(self._heartbeats)
            if count != self._last_count:
                self.osc.send_osc(self.count_addr, count)
                self._last_count = count
            time.sleep(self.poll_interval)

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = Thread(target=self._prune_loop, daemon=True)
        self._thread.start()
