from typing import Dict, List

from ..generators.generator import Generator
from ..generators.mixer import Mixer
from ..osc import OSCManager, OSCParam


class ParamGeneratorBuilder:
    """Base class for category-specific parameter and generator builders.

    Each subclass creates its own generators in __init__ and builds all
    OSCParams (including SignalPatchParams) in build_params.
    """

    def generators(self) -> List[Generator]:
        """Return all generators owned by this builder."""
        return []

    # pylint: disable=unused-argument
    def build_params(self, osc: OSCManager, mixer: Mixer) -> Dict[str, List[OSCParam]]:
        """Return a dict mapping category keys to their OSCParam lists."""
        return {}
