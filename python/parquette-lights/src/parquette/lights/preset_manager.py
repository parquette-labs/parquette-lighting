from typing import List, Dict, Tuple, Any

import pickle
import pprint

from .osc import OSCManager, OSCParam


class PresetManager(object):
    def __init__(
        self,
        osc: OSCManager,
        exposed_params: Dict[str, List[OSCParam]],
        filename: str,
        debug: bool = False,
    ) -> None:
        self.osc = osc
        self.exposed_params = exposed_params
        self.filename = filename
        self.stored_presets: Dict[str, Dict[str, List[Tuple[str, Any]]]] = {}
        self.current_presets: Dict[str, str] = {}
        self.debug = debug

        osc.dispatcher.map("/save_preset", lambda addr, args: self.save(args))
        osc.dispatcher.map("/clear_preset", lambda addr, args: self.clear(args))
        osc.dispatcher.map(
            "/preset_selector", lambda _, *args: self.select(args[0], args[1])
        )

        self.load()

    def load(self):
        try:
            with open(self.filename, "rb") as f:
                self.stored_presets = pickle.load(f)
        # pylint: disable=broad-exception-caught
        except Exception as e:
            print("Pickle load failed, bad or missing pickle", e, flush=True)

    def clear(self, category: str) -> None:
        if not category in self.stored_presets:
            # we have never any data for this preset category, no-op
            print(
                "You're requesting to clear a category of preset that doesn't exist, likley something is wrong in your front end. The passed category is \"{}\"".format(
                    category
                )
            )
            return

        if not category in self.current_presets:
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
            with open("./params.pickle", "wb") as f:  # type: ignore
                pickle.dump(self.stored_presets, f)

    def save(self, category: str) -> None:
        """
        Save the current state of the parameters for the category into the pickle. Since we are saving current state we don't require the state to exist in current presets, only for the category to be valid and the preset name to exist
        """
        if not category in self.exposed_params:
            # we have never any data for this preset category, no-op
            print(
                "You're requesting to a save a preset for a category that doesn't exist, likely something is wrong in your front end. The passed category is \"{}\"".format(
                    category
                )
            )
            return

        if not category in self.current_presets:
            print(
                'You\'re requesting to save a preset, but no preset is selected currently for the category "{}"'.format(
                    category
                )
            )
            # there is no preset selected for this category, no-op
            return

        category_preset = self.current_presets[category]

        if not category in self.stored_presets:
            self.stored_presets[category] = {}

        self.stored_presets[category][category_preset] = []

        for param in self.exposed_params[category]:
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

        with open("./params.pickle", "wb") as f:  # type: ignore
            pickle.dump(self.stored_presets, f)

    def sync(self):
        for category, params in self.exposed_params.items():
            for param in params:
                param.sync()

        for category, category_preset in self.current_presets.items():
            self.osc.send_osc("/preset_selector/{}".format(category), category_preset)

    def select(self, category: str, category_preset: str) -> None:
        if not category in self.exposed_params:
            # there are no valid exposed params in this category to control
            print(
                "You're requesting to a select a preset for a category that doesn't exist, likely something is wrong in your front end. The passed category is \"{}\"".format(
                    category
                )
            )
            return

        self.current_presets[category] = category_preset

        if not category in self.stored_presets:
            # Someone is creating a new preset, nothing to load
            return

        if not category_preset in self.stored_presets[category_preset]:
            # Someone is creating a new preset, nothing to load
            return

        for param_preset in self.stored_presets[category][category_preset]:
            addr, value = param_preset[0], param_preset[1]
            for param in self.exposed_params[category]:
                if param.addr == addr:
                    param.load(addr, value)
