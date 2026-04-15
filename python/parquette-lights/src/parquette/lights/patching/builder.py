from typing import Dict, List

from ..category import Category
from ..fixtures.basics import Fixture
from ..generators.generator import Generator
from ..generators.mixer import Mixer
from ..osc import OSCParam


class CategoryBuilder:
    """Base class for category-specific builders.

    Each subclass creates its own fixtures and generators in __init__,
    wires any cross-object OSC handlers (snap-to-BPM, loop record),
    and builds all OSCParams in build_params.
    """

    def fixtures(self) -> List[Fixture]:
        """Return all fixtures owned by this builder."""
        return []

    def generators(self) -> List[Generator]:
        """Return all generators owned by this builder."""
        return []

    # pylint: disable=unused-argument
    def build_params(self, mixer: Mixer) -> Dict[Category, List[OSCParam]]:
        """Return a dict mapping Category objects to their OSCParam lists."""
        return {}
