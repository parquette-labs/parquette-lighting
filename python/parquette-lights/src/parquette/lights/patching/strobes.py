from typing import Dict, List

from ..category import Category
from ..generators import ImpulseGenerator
from ..generators.generator import Generator
from ..generators.mixer import Mixer
from ..osc import OSCManager, OSCParam
from .builder import CategoryBuilder


class StrobesBuilder(CategoryBuilder):
    def __init__(self, osc: OSCManager, category: Category) -> None:
        self.osc = osc
        self.category = category
        self.impulse = ImpulseGenerator(
            name="impulse", category=category, amp=255, offset=0, duty=100
        )
        self.impulse.register_punch(osc)

    def generators(self) -> List[Generator]:
        return [self.impulse]

    def build_params(self, mixer: Mixer) -> Dict[Category, List[OSCParam]]:
        return {
            self.category: [
                # Standard generator params (/gen/{type}/{name}/{attr})
                *self.impulse.standard_params(self.osc),
            ]
        }
