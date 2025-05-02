from typing import Optional
from abc import ABC, abstractmethod


class Generator(ABC):

    def __init__(
        self,
        *,
        name: Optional[str] = None,
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
