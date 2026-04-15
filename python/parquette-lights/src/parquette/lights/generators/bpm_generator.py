from .generator import Generator
from ..category import Category


class BPMGenerator(Generator):
    STANDARD_ATTRS = ["amp", "duty", "bpm_mult", "manual_offset", "lpf_alpha"]

    duty: int
    offset_time: float
    manual_offset: float

    def __init__(
        self,
        *,
        name: str,
        category: Category,
        amp: float = 1,
        offset: float = 0,
        duty: int = 100,
        bpm: float = 126,
        offset_time: int = 0,
        lpf_alpha: float = 1.0,
    ):
        super().__init__(
            name=name, category=category, amp=amp, offset=offset, period=0, phase=0
        )

        self.offset_time = offset_time
        self.manual_offset = 0
        self.duty = duty
        self.bpm_mult = 1
        self.bpm = bpm
        self.rms_valid = False
        self.bpm_valid = False
        # Single-pole EMA low-pass smoothing of value(): 1.0 = no filtering,
        # values closer to 0 produce smoother output. Filtered state is
        # initialized to offset so the first sample doesn't ramp from zero.
        self.lpf_alpha = lpf_alpha
        self._lpf_state = offset

    def current_period(self) -> float:
        return 1000 * 60 / (self.bpm * self.bpm_mult)

    def value(self, millis: float) -> float:
        if not self.bpm_valid or not self.rms_valid:
            raw = self.offset
        else:
            try:
                ellapsed: float = millis - self.offset_time - self.manual_offset
                period = 1000 * 60 / (self.bpm * self.bpm_mult)

                if ellapsed % period >= 0 and ellapsed % period < self.duty:
                    raw = self.amp + self.offset
                else:
                    raw = self.offset
            except ZeroDivisionError:
                return 0

        alpha = self.lpf_alpha
        if alpha >= 1.0:
            self._lpf_state = raw
        else:
            self._lpf_state = alpha * raw + (1.0 - alpha) * self._lpf_state
        return self._lpf_state
