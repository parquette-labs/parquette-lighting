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

    @staticmethod
    def _period_for(bpm: float, bpm_mult: float) -> float:
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
                self._period_for(old_bpm, self.bpm_mult),
                self._period_for(new_bpm, self.bpm_mult),
            )
        self._bpm = new_bpm

    def value(self, millis: float) -> float:
        if not self.bpm_valid or not self.rms_valid:
            return self.offset
        try:
            ellapsed: float = millis - self.offset_time - self.manual_offset
            period = 1000 * 60 / (self.bpm * self.bpm_mult)

            if ellapsed % period >= 0 and ellapsed % period < self.duty:
                return self.amp + self.offset
            else:
                return self.offset
        except ZeroDivisionError:
            return 0
