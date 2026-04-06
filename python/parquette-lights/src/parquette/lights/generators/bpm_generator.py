import time

from .generator import Generator


class BPMGenerator(Generator):
    duty: int
    offset_time: float
    manual_offset: float
    bpm_valid: bool
    _bpm: float

    def __init__(
        self,
        *,
        name: str,
        amp: float = 1,
        offset: float = 0,
        duty: int = 100,
        bpm: float = 126,
        offset_time: int = 0,
        lpf_alpha: float = 1.0,
    ):
        super().__init__(name=name, amp=amp, offset=offset, period=0, phase=0)

        # Order matters: the bpm / bpm_mult property setters read these when
        # re-anchoring on update, so they must exist first. On the very first
        # assignment the setters skip re-anchoring (no prior _bpm/_bpm_mult).
        self.offset_time = offset_time
        self.manual_offset = 0
        self.duty = duty
        self.bpm_mult = 1
        self._bpm = 0
        self.bpm = bpm
        self.rms_valid = False
        self.bpm_valid = False
        # Single-pole EMA low-pass smoothing of value(): 1.0 = no filtering,
        # values closer to 0 produce smoother output. Filtered state is
        # initialized to offset so the first sample doesn't ramp from zero.
        self.lpf_alpha = lpf_alpha
        self._lpf_state = offset

    def current_period(self) -> float:
        return BPMGenerator.period_for(self.bpm, self.bpm_mult)

    @staticmethod
    def period_for(bpm: float, bpm_mult: float) -> float:
        return 1000 * 60 / (bpm * bpm_mult)

    def _reanchor(self, old_period: float, new_period: float) -> None:
        millis = time.time() * 1000
        new_offset = Generator.reanchor_offset(
            millis,
            old_period,
            new_period,
            self.offset_time + self.manual_offset,
        )
        # Absorb the change into manual_offset, leaving offset_time (driven by
        # audio analysis) untouched.
        self.offset_time = new_offset - self.manual_offset

    @property
    def bpm(self) -> float:
        return self._bpm

    @bpm.setter
    def bpm(self, new_bpm: float) -> None:
        old_bpm = self._bpm
        if old_bpm and old_bpm > 0 and new_bpm and new_bpm > 0 and self.bpm_mult > 0:
            self._reanchor(
                self.period_for(old_bpm, self.bpm_mult),
                self.period_for(new_bpm, self.bpm_mult),
            )
        self._bpm = new_bpm

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
