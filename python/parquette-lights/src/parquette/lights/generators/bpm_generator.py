from .generator import Generator
from ..category import Category


class BPMGenerator(Generator):
    STANDARD_ATTRS = ["amp", "duty", "bpm_mult", "manual_phase", "lpf_alpha"]

    duty: int
    phase_time: float
    manual_phase: float

    def __init__(
        self,
        *,
        name: str,
        category: Category,
        amp: float = 1,
        offset: float = 0,
        duty: int = 100,
        bpm: float = 126,
        phase_time: int = 0,
        lpf_alpha: float = 1.0,
    ):
        super().__init__(
            name=name, category=category, amp=amp, offset=offset, period=0, phase=0
        )

        self.phase_time = phase_time
        self.manual_phase = 0
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
        self._pulse_end: float = 0.0

    def current_period(self) -> float:
        return 1000 * 60 / (self.bpm * self.bpm_mult)

    def value(self, millis: float) -> float:
        if not self.bpm_valid or not self.rms_valid:
            raw = self.offset
        else:
            try:
                if millis < self._pulse_end:
                    raw = self.amp + self.offset
                else:
                    elapsed: float = millis - self.phase_time - self.manual_phase
                    period = 1000 * 60 / (self.bpm * self.bpm_mult)
                    pos = elapsed % period

                    if pos < self.duty:
                        raw = self.amp + self.offset
                        self._pulse_end = millis + self.duty
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
