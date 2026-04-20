from abc import ABC, abstractmethod
from typing import ClassVar, List

from ..category import Category
from ..osc import OSCManager, OSCParam


class Generator(ABC):
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

        Addresses follow /gen/{ClassName}/{name}/{attribute}.
        """
        cls_name = type(self).__name__
        return [
            OSCParam.bind(
                osc,
                "/gen/{}/{}/{}".format(cls_name, self.name, attr),
                self,
                attr,
            )
            for attr in self.STANDARD_ATTRS
        ]

    @staticmethod
    def reanchor_phase(
        millis: float,
        old_period: float,
        new_period: float,
        old_phase: float,
    ) -> float:
        """
        Given a generator whose cycle position at time `millis` is
            (millis - old_phase) % old_period
        return a new phase such that
            (millis - new_phase) % new_period
        starts at the same fractional position within the new cycle.

        Returns old_phase unchanged if either period is non-positive.
        """
        if old_period <= 0 or new_period <= 0:
            return old_phase
        elapsed = millis - old_phase
        frac = (elapsed % old_period) / old_period
        return millis - frac * new_period
