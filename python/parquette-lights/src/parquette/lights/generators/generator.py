from abc import ABC, abstractmethod


class Generator(ABC):
    def __init__(
        self,
        *,
        name: str,
        amp: float = 0.5,
        offset: float = 0.5,
        period: float = 1000,
        phase: float = 0
    ):
        self.name = name
        self.amp = amp
        self.phase = phase
        self.period = period
        self.offset = offset

    @abstractmethod
    def value(self, millis: float) -> float:
        pass

    @staticmethod
    def reanchor_offset(
        millis: float,
        old_period: float,
        new_period: float,
        old_offset: float,
    ) -> float:
        """
        Given a generator whose cycle position at time `millis` is
            (millis - old_offset) % old_period
        return a new_offset such that
            (millis - new_offset) % new_period
        starts at the same fractional position within the new cycle.

        Returns old_offset unchanged if either period is non-positive.
        """
        if old_period <= 0 or new_period <= 0:
            return old_offset
        elapsed = millis - old_offset
        frac = (elapsed % old_period) / old_period
        return millis - frac * new_period
