import time
from typing import List, Optional

from .generator import Generator
from ..category import Category
from ..osc import OSCManager, OSCParam


class LoopGenerator(Generator):
    """Records a sequence of values from OSC input and plays them back in a loop.

    During recording, incoming values are appended to a buffer at tick rate.
    On stop, the buffer becomes the playback source. Playback uses linear
    interpolation and loops continuously at the original recording speed.
    """

    STANDARD_ATTRS = ["amp"]

    def __init__(
        self,
        *,
        name: str,
        category: Category,
        amp: float = 1.0,
        offset: float = 0.0,
        max_samples: int = 500,
        record_group: Optional[str] = None,
    ) -> None:
        super().__init__(
            name=name, category=category, amp=amp, offset=offset, period=1000, phase=0
        )
        self.max_samples: int = max_samples
        self.samples: List[float] = []
        self.loop_length: int = 0
        self.playback_start: float = 0.0

        self.recording: bool = False
        self.record_buffer: List[float] = []
        self.record_start_ms: float = 0.0

        self.input_value: float = 0.0

        # Two or more loops sharing the same record_group register record
        # handlers at the same OSC address, so one UI toggle starts/stops
        # them in sync. When None, the handler is per-generator.
        self.record_group: Optional[str] = record_group

    def set_recording(self, active: bool, ts_ms: Optional[float] = None) -> None:
        """Start or stop recording. Called from OSC thread."""
        if ts_ms is None:
            ts_ms = time.time() * 1000

        if active:
            self.recording = True
            self.record_buffer = []
            self.record_start_ms = ts_ms
        else:
            if self.recording and len(self.record_buffer) > 0:
                new_samples = list(self.record_buffer)
                duration = ts_ms - self.record_start_ms
                # Thread-safe swap: zero length first so value() returns offset
                self.loop_length = 0
                self.samples = new_samples
                if duration > 0:
                    self.period = duration
                self.playback_start = ts_ms
                self.loop_length = len(new_samples)
            self.recording = False
            self.record_buffer = []

    def record_sample(self, value: float) -> None:
        """Append a sample during recording. Called from OSC thread."""
        if not self.recording:
            return
        if len(self.record_buffer) >= self.max_samples:
            self.set_recording(False)
            return
        self.record_buffer.append(value)

    def load_samples(self, samples: List[float]) -> None:
        """Restore samples from a preset load."""
        self.loop_length = 0
        self.samples = list(samples)
        self.loop_length = len(self.samples)
        self.playback_start = time.time() * 1000

    def value(self, millis: float) -> float:
        if self.recording and self.record_buffer:
            return self.record_buffer[-1] * self.amp + self.offset

        if self.loop_length == 0:
            return self.offset

        elapsed = millis - self.playback_start
        if self.period <= 0:
            return self.offset

        position = (elapsed / self.period) * self.loop_length
        position = position % self.loop_length

        idx = int(position)
        frac = position - idx
        next_idx = (idx + 1) % self.loop_length
        sample = self.samples[idx] * (1.0 - frac) + self.samples[next_idx] * frac
        return sample * self.amp + self.offset

    def standard_params(self, osc: OSCManager) -> List[OSCParam]:
        return super().standard_params(osc) + [self.samples_param(osc)]

    def samples_param(self, osc: OSCManager) -> OSCParam:
        addr = "/gen/{}/{}/samples".format(type(self).__name__, self.name)
        return OSCParam(
            osc,
            addr,
            lambda: self.samples,
            lambda _a, *args: self.load_samples(
                list(args[0])
                if len(args) == 1 and isinstance(args[0], (list, tuple))
                else list(args)
            ),
        )

    def register_record(self, osc: OSCManager) -> None:
        """Register a recording toggle OSC handler for this loop.

        Address: /gen/{ClassName}/{record_group or name}/record. When
        multiple loops share a record_group, each registers its own
        handler at the same OSC address and pythonosc fans the incoming
        message out to every registered handler — paired x/y loops start
        and stop together without a separate group helper.

        Not exposed via standard_params because recording is an action,
        not a persisted parameter — presets should not re-issue a record
        toggle on load.
        """
        name = self.record_group or self.name
        addr = "/gen/{}/{}/record".format(type(self).__name__, name)
        osc.dispatcher.map(addr, lambda _addr, *args: self.set_recording(bool(args[0])))
