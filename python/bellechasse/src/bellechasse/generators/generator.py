from abc import ABC, abstractmethod


class Generator(ABC):

    def __init__(self, *, name=None, amp=0.5, offset=0.5, period=1000, phase=0):
        self.name = name
        self.amp = amp
        self.phase = phase
        self.period = period
        self.offset = offset

    @abstractmethod
    def value(self, millis):
        pass
