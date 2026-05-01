from typing import Any, Dict, Optional

import os
import pickle

from .category import Categories, Category
from .dmx import DMXManager
from .generators.chanmap import MixChannel
from .osc import OSCManager
from .preset_manager import PresetManager


class Scene:
    """A named lighting scene that sets category masters and selects presets.

    Each scene registers itself at /scene/{name} on the OSC dispatcher.
    Triggering the address applies the scene: sets each category's master
    to a configured level, optionally sets channel offsets, disables DMX
    passthrough if needed, and selects presets.

    If preset_all is set, all categories are first set to that group.
    If presets_by_category is provided, those per-category overrides are
    applied on top of (or instead of) the base preset_all.
    """

    def __init__(
        self,
        *,
        name: str,
        osc: OSCManager,
        dmx: DMXManager,
        presets: PresetManager,
        masters: Dict[Category, float],
        preset_all: Optional[str] = None,
        presets_by_category: Optional[Dict[Category, str]] = None,
        channel_offsets: Optional[Dict[MixChannel, float]] = None,
        disable_passthrough: bool = False,
        protect_save_clear: bool = False,
    ) -> None:
        self.name = name
        self.osc = osc
        self.dmx = dmx
        self.presets = presets
        self.masters = masters
        self.preset_all = preset_all
        self.presets_by_category = presets_by_category
        self.channel_offsets = channel_offsets or {}
        self.disable_passthrough = disable_passthrough
        self.protect_save_clear = protect_save_clear

    def activate(self) -> None:
        if self.disable_passthrough and self.dmx.passthrough:
            self.dmx.passthrough = False

        for channel, offset in self.channel_offsets.items():
            channel.offset = offset

        for category, level in self.masters.items():
            category.set_master(level)

        if self.preset_all is not None:
            self.presets.select_all(self.preset_all)

        if self.presets_by_category:
            for category, preset_name in self.presets_by_category.items():
                self.presets.select(category.name, preset_name, sync=False)
            self.presets.sync()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a picklable dict (string keys, no object refs)."""
        data: Dict[str, Any] = {
            "masters": {cat.name: level for cat, level in self.masters.items()},
        }
        if self.preset_all is not None:
            data["preset_all"] = self.preset_all
        if self.presets_by_category:
            data["presets"] = {
                cat.name: preset for cat, preset in self.presets_by_category.items()
            }
        return data

    @classmethod
    def from_dict(
        cls,
        name: str,
        data: Dict[str, Any],
        *,
        osc: OSCManager,
        dmx: DMXManager,
        presets: PresetManager,
        categories: Categories,
    ) -> "Scene":
        """Reconstruct a Scene from a serialized dict."""
        masters = {categories.by_name(k): v for k, v in data.get("masters", {}).items()}
        preset_all: Optional[str] = data.get("preset_all")
        raw_presets = data.get("presets", {})
        presets_by_cat: Optional[Dict[Category, str]] = None
        if raw_presets:
            presets_by_cat = {categories.by_name(k): v for k, v in raw_presets.items()}
        return cls(
            name=name,
            osc=osc,
            dmx=dmx,
            presets=presets,
            masters=masters,
            preset_all=preset_all,
            presets_by_category=presets_by_cat,
        )


class SceneManager:
    """Manages scenes with pickle persistence.

    Scenes can be registered from code or created from the UI. All scenes
    live in the same collection and are activated the same way. Scenes
    with protect_save_clear=True cannot be overwritten or deleted from
    the UI.
    """

    # pylint: disable=too-many-positional-arguments
    def __init__(
        self,
        osc: OSCManager,
        dmx: DMXManager,
        presets: PresetManager,
        categories: Categories,
        filename: str = "scenes.pickle",
        debug: bool = False,
    ) -> None:
        self.osc = osc
        self.dmx = dmx
        self.presets = presets
        self.categories = categories
        self.filename = filename
        self.debug = debug

        self.scenes: Dict[str, Scene] = {}
        self.selected_scene: Optional[Scene] = None

        osc.dispatcher.map(
            "/scene/create", lambda addr, *args: self.create_scene(str(args[0]))
        )
        osc.dispatcher.map("/scene/save_current", lambda addr, *args: self.save_scene())
        osc.dispatcher.map(
            "/scene/clear_current", lambda addr, *args: self.clear_scene()
        )
        osc.dispatcher.map(
            "/scene/*", lambda addr, *args: self.on_scene_triggered(addr)
        )
        osc.dispatcher.map("/preset/reload", lambda addr, *args: self.sync())

        self.load()

    def register_scene(self, scene: Scene) -> None:
        """Register a scene so it appears in the dropdown."""
        self.scenes[scene.name] = scene

    def on_scene_triggered(self, addr: str) -> None:
        """Handle all /scene/* messages: activate and track the scene."""
        name = addr.split("/scene/", 1)[1]
        scene = self.scenes.get(name)
        if scene is not None:
            self.selected_scene = scene
            scene.activate()

    def capture_current_state(self) -> Scene:
        """Build a Scene from the current lighting state."""
        masters = {
            cat: cat.master
            for cat in self.categories.all
            if cat is not self.categories.non_saved
        }
        current_presets = self.presets.save_current_selection()
        presets_by_cat: Optional[Dict[Category, str]] = None
        if current_presets:
            presets_by_cat = {
                self.categories.by_name(k): v for k, v in current_presets.items()
            }
        # Return a detached Scene (not yet registered on OSC or in self.scenes)
        return Scene(
            name="",
            osc=self.osc,
            dmx=self.dmx,
            presets=self.presets,
            masters=masters,
            presets_by_category=presets_by_cat,
        )

    def create_scene(self, name: str) -> None:
        """Capture current state as a new or updated scene."""
        if not name or not name.strip():
            return
        name = name.strip()

        if name in self.scenes and self.scenes[name].protect_save_clear:
            if self.debug:
                print("Scene create: '{}' is protected.".format(name), flush=True)
            return

        snapshot = self.capture_current_state()
        scene = Scene(
            name=name,
            osc=self.osc,
            dmx=self.dmx,
            presets=self.presets,
            masters=snapshot.masters,
            presets_by_category=snapshot.presets_by_category,
        )
        self.register_scene(scene)
        self.selected_scene = scene
        self.persist()
        self.sync()
        if self.debug:
            print("Scene created/updated: {}".format(name), flush=True)

    def save_scene(self) -> None:
        """Overwrite the selected scene with current state."""
        if not self.presets.enable_save_clear:
            return
        if self.selected_scene is None:
            return
        self.create_scene(self.selected_scene.name)

    def clear_scene(self) -> None:
        """Delete the currently selected scene."""
        if not self.presets.enable_save_clear:
            return
        if self.selected_scene is None:
            return
        if self.selected_scene.protect_save_clear:
            return

        name = self.selected_scene.name
        del self.scenes[name]
        self.selected_scene = None
        self.persist()
        self.sync()
        if self.debug:
            print("Scene cleared: {}".format(name), flush=True)

    def load(self) -> None:
        """Load scenes from pickle on boot."""
        if not os.path.isfile(self.filename):
            return
        try:
            with open(self.filename, "rb") as f:
                stored_data: Dict[str, Dict[str, Any]] = pickle.load(f)
        # pylint: disable=broad-exception-caught
        except Exception as e:
            if self.debug:
                print("Scene pickle load failed: {}".format(e), flush=True)
            return

        for name, data in stored_data.items():
            try:
                scene = Scene.from_dict(
                    name,
                    data,
                    osc=self.osc,
                    dmx=self.dmx,
                    presets=self.presets,
                    categories=self.categories,
                )
                self.register_scene(scene)
            # pylint: disable=broad-exception-caught
            except Exception as e:
                if self.debug:
                    print("Scene load failed for '{}': {}".format(name, e), flush=True)

    def persist(self) -> None:
        """Write all non-protected scenes to pickle atomically."""
        stored: Dict[str, Dict[str, Any]] = {}
        for name, scene in self.scenes.items():
            if not scene.protect_save_clear:
                stored[name] = scene.to_dict()
        tmp = self.filename + ".tmp"
        with open(tmp, "wb") as f:
            pickle.dump(stored, f)
        os.replace(tmp, self.filename)

    def sync(self) -> None:
        """Push scene list to the UI dropdown."""
        values: Dict[str, str] = {name: name for name in self.scenes}
        self.osc.send_osc("/scene_selector/values", [str(values)])
        if self.selected_scene:
            self.osc.send_osc("/scene_selector", self.selected_scene.name)
