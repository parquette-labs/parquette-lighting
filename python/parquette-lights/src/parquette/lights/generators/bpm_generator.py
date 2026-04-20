import math

from .generator import Generator
from ..category import Category


class BPMGenerator(Generator):
    STANDARD_ATTRS = ["amp", "duty", "bpm_mult", "manual_phase", "lpf_alpha"]

    duty: int
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
        lpf_alpha: float = 1.0,
    ):
        super().__init__(
            name=name, category=category, amp=amp, offset=offset, period=0, phase=0
        )

        self.manual_phase: float = 0
        self.duty = duty
        self.bpm_mult = 1
        self.bpm = bpm
        self.rms_valid = False
        self.bpm_valid = False
        # phase_ref is an absolute time reference kept near current millis.
        # Beats fire when (millis - phase_ref) % period = 0. Using a nearby
        # reference avoids precision loss from modulus on huge wall-clock
        # timestamps (~1.7e12 ms).
        self.phase_ref: float = 0.0
        # Single-pole EMA low-pass smoothing of value(): 1.0 = no filtering,
        # values closer to 0 produce smoother output. Filtered state is
        # initialized to offset so the first sample doesn't ramp from zero.
        self.lpf_alpha = lpf_alpha
        self._lpf_state = offset
        self._pulse_end: float = 0.0
        self._last_pulse_start: float = -60000.0

    def current_period(self) -> float:
        return 60000.0 / (self.bpm * self.bpm_mult)

    def update_bpm_phase(
        self, new_bpm: float, beat_time_ms: float, alpha: float
    ) -> None:
        """Update BPM and smoothly align phase with detected beat time.

        1. Reanchor phase_ref to preserve cycle position under the new period
        2. Compute target phase_ref aligned with beat_time_ms
        3. PLL: nudge phase_ref toward target by alpha fraction of the error
        4. Re-anchor phase_ref to stay near current time
        """
        millis = self._last_pulse_start if self._last_pulse_start > 0 else 0.0
        old_period = self.current_period()
        self.bpm = new_bpm
        new_period = self.current_period()

        # Preserve cycle position under new period
        if old_period > 0 and new_period > 0:
            self.phase_ref = Generator.reanchor_phase(
                millis, old_period, new_period, self.phase_ref
            )

        # Target: phase_ref where (beat_time_ms - target) % period = 0
        # Bring target near millis for precision
        target_ref = beat_time_ms
        if new_period > 0:
            target_ref += math.floor((millis - beat_time_ms) / new_period) * new_period

            # PLL correction: circular error in phase_ref space
            error = (self.phase_ref - target_ref) % new_period
            if error > new_period / 2:
                error -= new_period
            self.phase_ref -= error * alpha

            # Keep phase_ref near millis
            drift = millis - self.phase_ref
            if abs(drift) > new_period:
                self.phase_ref += math.floor(drift / new_period) * new_period

    def value(self, millis: float) -> float:
        if not self.bpm_valid or not self.rms_valid:
            raw = self.offset
        else:
            try:
                if millis < self._pulse_end:
                    raw = self.amp + self.offset
                else:
                    period = self.current_period()
                    elapsed = (millis - self.phase_ref - self.manual_phase) % period
                    since_last = millis - self._last_pulse_start
                    if elapsed < self.duty and since_last >= period:
                        raw = self.amp + self.offset
                        self._pulse_end = millis + self.duty
                        self._last_pulse_start = millis
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
