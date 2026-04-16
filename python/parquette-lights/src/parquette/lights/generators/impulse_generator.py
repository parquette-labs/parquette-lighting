from .generator import Generator
from ..category import Category
from ..osc import OSCManager


class ImpulseGenerator(Generator):
    STANDARD_ATTRS = ["amp", "duty"]

    punch_point: float = 0
    _punch_pending: bool

    def __init__(
        self,
        *,
        name: str,
        category: Category,
        amp: float = 1,
        offset: float = 0,
        duty: float = 100,
    ):
        super().__init__(
            name=name, category=category, amp=amp, offset=offset, period=1, phase=0
        )

        self.duty = duty
        self._punch_pending = False

    def punch(self) -> None:
        # Defer the actual punch start to the next value() call so that the
        # impulse begins exactly at the start of the next runChannelMix tick.
        # Otherwise a punch fired between ticks can land partway through (or
        # entirely past) a short duty window and be missed by the mix loop.
        self._punch_pending = True

    def register_punch(self, osc: OSCManager) -> None:
        """Register /gen/ImpulseGenerator/{name}/punch on the dispatcher."""
        addr = "/gen/{}/{}/punch".format(type(self).__name__, self.name)
        osc.dispatcher.map(addr, lambda _addr, *args: self.punch())

    def value(self, millis: float) -> float:
        if self._punch_pending:
            self.punch_point = millis
            self._punch_pending = False

        ellapsed: float = millis - self.punch_point

        if ellapsed < self.duty:
            return self.amp + self.offset
        else:
            return self.offset
