from typing import List, Dict, Tuple, Any, Set, Optional

import pickle
import pprint
from copy import copy

from .category import Categories, Category
from .osc import OSCManager, OSCParam
from .util.session_store import SessionStore


class PresetManager(object):
    def __init__(
        self,
        osc: OSCManager,
        exposed_params: Dict[Category, List[OSCParam]],
        categories: Categories,
        filename: str,
        *,
        enable_save_clear: bool = False,
        debug: bool = False,
        session: Optional[SessionStore] = None,
    ) -> None:
        self.osc = osc
        self.exposed_params = exposed_params
        self.categories = categories
        self.filename = filename
        self.stored_presets: Dict[str, Dict[str, List[Tuple[str, Any]]]] = {}
        self.current_presets: Dict[str, str] = {}
        self.prev_current_presets: Dict[str, str] = {}
        self.enable_save_clear = enable_save_clear
        self.debug = debug
        self.session = session

        osc.dispatcher.map(
            "/preset/save/*", lambda addr, args: self.save(addr.split("/")[3])
        )
        osc.dispatcher.map(
            "/preset/clear/*", lambda addr, args: self.clear(addr.split("/")[3])
        )
        osc.dispatcher.map(
            "/preset/selector/*",
            lambda addr, args: self.select(addr.split("/")[3], args),
        )
        osc.dispatcher.map("/preset/reload", lambda _a, _args: self.sync())
        osc.dispatcher.map(
            "/enable_save", lambda _a, args: self.set_enable_save_clear(args)
        )

        self.load()

    def all_categories(self) -> Set[str]:
        all_categories = {
            c.name for c in self.exposed_params if c is not self.categories.non_saved
        }
        for key in self.current_presets:
            all_categories.add(key)
        return all_categories

    def select_all(self, category_preset: str) -> None:
        # Early-out only if we already have a known selection for every
        # category and they all match the target. With empty current_presets
        # (fresh launch, nothing selected yet) `all(...)` over an empty
        # iterable is True and would wrongly skip the call, so the shortcut
        # buttons (all_black / house_lights / class_lights) did nothing
        # until the user manually picked a preset first.
        if self.current_presets and all(
            category_preset == preset for preset in self.current_presets.values()
        ):
            return

        self.prev_current_presets = copy(self.current_presets)

        for cat in self.all_categories():
            # If this category doesn't define the requested preset (e.g.
            # "Static" or "Class"), fall back to "Off" so the channel goes
            # dark instead of holding its previous state.
            if (
                cat in self.stored_presets
                and category_preset in self.stored_presets[cat]
            ):
                self.select(cat, category_preset, sync=False)
            else:
                self.select(cat, "Off", sync=False)

        self.sync()

    def save_current_selection(self) -> Dict[str, str]:
        return dict(self.current_presets)

    def load_current_selection(self, data: Dict[str, str]) -> None:
        for cat, preset_name in data.items():
            try:
                self.select(cat, preset_name, sync=False)
            # pylint: disable=broad-exception-caught
            except Exception as e:
                print(
                    f"  failed to restore preset {cat}={preset_name}: {e}", flush=True
                )

    def set_enable_save_clear(self, enable: bool) -> None:
        self.enable_save_clear = enable

    def load(self):
        try:
            with open(self.filename, "rb") as f:
                self.stored_presets = pickle.load(f)
        # pylint: disable=broad-exception-caught
        except Exception as e:
            print("Pickle load failed, bad or missing pickle", e, flush=True)

    def clear(self, category: str) -> None:
        if not self.enable_save_clear:
            return

        if category not in self.stored_presets:
            # we have never any data for this preset category, no-op
            print(
                "You're requesting to clear a category of preset that doesn't exist, likley something is wrong in your front end. The passed category is \"{}\"".format(
                    category
                )
            )
            return

        if category not in self.current_presets:
            print(
                'You\'re requesting to clear a preset, but no preset is selected currently for the category "{}"'.format(
                    category
                )
            )
            # there is no preset selected for this category, no-op
            return

        category_preset = self.current_presets[category]

        if category_preset in self.stored_presets[category]:
            # clean the current preset for this category
            del self.stored_presets[category][category_preset]

            # write out the cleared data
            with open(self.filename, "wb") as f:
                pickle.dump(self.stored_presets, f)

    def save(self, category: str) -> None:
        """
        Save the current state of the parameters for the category into the pickle. Since we are saving current state we don't require the state to exist in current presets, only for the category to be valid and the preset name to exist
        """
        if not self.enable_save_clear:
            return

        if category == self.categories.non_saved.name:
            return

        cat = self.categories.by_name(category)
        if cat not in self.exposed_params:
            # we have never any data for this preset category, no-op
            print(
                "You're requesting to a save a preset for a category that doesn't exist, likely something is wrong in your front end. The passed category is \"{}\"".format(
                    category
                )
            )
            return

        if category not in self.current_presets:
            print(
                'You\'re requesting to save a preset, but no preset is selected currently for the category "{}"'.format(
                    category
                )
            )
            # there is no preset selected for this category, no-op
            return

        category_preset = self.current_presets[category]

        if category not in self.stored_presets:
            self.stored_presets[category] = {}

        self.stored_presets[category][category_preset] = []

        # Sparse save — skip any param whose current value matches its default.
        for param in self.exposed_params[cat]:
            if param.is_at_default():
                continue
            self.stored_presets[category][category_preset].append(
                (param.addr, param.value_lambda())
            )

        if self.debug:
            print(
                'printing saved presets for category "{}", category_preset "{}"'.format(
                    category, category_preset
                )
            )
            pprint.pp(self.stored_presets[category][category_preset])

        with open(self.filename, "wb") as f:
            pickle.dump(self.stored_presets, f)

    def sync(self):
        for params in self.exposed_params.values():
            for param in params:
                param.sync()

        for category, category_preset in self.current_presets.items():
            self.osc.send_osc("/preset/selector/{}".format(category), category_preset)

        self.osc.send_osc("/enable_save", int(self.enable_save_clear))

    def select(self, category: str, category_preset: str, sync: bool = True) -> None:
        cat = self.categories.by_name(category)
        if cat not in self.exposed_params:
            # there are no valid exposed params in this category to control
            print(
                "You're requesting to a select a preset for a category that doesn't exist, likely something is wrong in your front end. The passed category is \"{}\"".format(
                    category
                )
            )
            return

        self.current_presets[category] = category_preset

        if self.session is not None:
            self.session.save()

        if category not in self.stored_presets:
            # Someone is creating a new preset, nothing to load
            return

        if category_preset not in self.stored_presets[category]:
            # Someone is creating a new preset, nothing to load
            return

        # Reset every param with a default to its default value. Silent:
        # no OSC sync per-param — we issue one final sync at the end.
        for param in self.exposed_params[cat]:
            if param.has_default:
                param.load(param.addr, param.default_value, sync=False)

        # Apply the saved overrides on top of the defaults.
        for param_preset in self.stored_presets[category][category_preset]:
            addr, value = param_preset[0], param_preset[1]
            for param in self.exposed_params[cat]:
                if param.addr == addr:
                    if isinstance(value, (list, tuple)):
                        param.load(addr, *value, sync=False)
                    else:
                        param.load(addr, value, sync=False)

        if sync:
            self.sync()
