import time
from typing import List, Optional

from .generator import Generator


class LoopGenerator(Generator):
    """Records a sequence of values from OSC input and plays them back in a loop.

    During recording, incoming values are appended to a buffer at tick rate.
    On stop, the buffer becomes the playback source. Playback uses linear
    interpolation and loops continuously at the original recording speed.
    """

    def __init__(
        self,
        *,
        name: str,
        category: str,
        amp: float = 1.0,
        offset: float = 0.0,
        max_samples: int = 500,
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
