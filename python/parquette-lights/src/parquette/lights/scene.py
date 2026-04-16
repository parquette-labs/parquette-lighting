from typing import Dict, Optional

from .category import Category
from .dmx import DMXManager
from .generators.chanmap import MixChannel
from .osc import OSCManager
from .preset_manager import PresetManager


class Scene:
    """A named lighting scene that sets category masters and selects a preset.

    Each scene registers itself at /scene/{name} on the OSC dispatcher.
    Triggering the address applies the scene: sets each category's master
    to a configured level, optionally sets channel offsets, disables DMX
    passthrough if needed, and selects the corresponding preset group.
    """

    def __init__(
        self,
        *,
        name: str,
        osc: OSCManager,
        dmx: DMXManager,
        presets: PresetManager,
        masters: Dict[Category, float],
        preset_group: str,
        channel_offsets: Optional[Dict[MixChannel, float]] = None,
        disable_passthrough: bool = False,
    ) -> None:
        self.name = name
        self.dmx = dmx
        self.presets = presets
        self.masters = masters
        self.preset_group = preset_group
        self.channel_offsets = channel_offsets or {}
        self.disable_passthrough = disable_passthrough

        osc.dispatcher.map(
            "/scene/{}".format(name),
            lambda addr, *args: self.activate(),
        )

    def activate(self) -> None:
        if self.disable_passthrough and self.dmx.passthrough:
            self.dmx.passthrough = False

        for channel, offset in self.channel_offsets.items():
            channel.offset = offset

        for category, level in self.masters.items():
            category.set_master(level)

        self.presets.select_all(self.preset_group)
