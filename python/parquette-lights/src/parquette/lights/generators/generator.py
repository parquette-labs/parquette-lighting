from abc import ABC, abstractmethod
from typing import ClassVar, List

from ..category import Category
from ..osc import OSCManager, OSCParam


class Generator(ABC):
    OSC_TYPE: ClassVar[str] = ""
    STANDARD_ATTRS: ClassVar[List[str]] = []

    def __init__(
        self,
        *,
        name: str,
        category: Category,
        amp: float = 0.5,
        offset: float = 0.5,
        period: float = 1000,
        phase: float = 0,
    ):
        self.name = name
        self.category = category
        self.amp = amp
        self.phase = phase
        self.period = period
        self.offset = offset

    @abstractmethod
    def value(self, millis: float) -> float:
        pass

    def standard_params(self, osc: OSCManager) -> List[OSCParam]:
        """Return OSCParam binds for this generator's standard attributes.

        Addresses follow /gen/{type}/{name}/{attribute}. Binds happen for
        every attribute regardless of whether the frontend UI uses them.
        """
        return [
            OSCParam.bind(
                osc,
                "/gen/{}/{}/{}".format(self.OSC_TYPE, self.name, attr),
                self,
                attr,
            )
            for attr in self.STANDARD_ATTRS
        ]

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
