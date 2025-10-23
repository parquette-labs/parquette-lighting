from typing import List, Dict, Tuple, Any

import pickle
import pprint

from .osc import OSCManager, OSCParam


class PresetManager(object):
    def __init__(
        self,
        osc: OSCManager,
        exposed_params: List[OSCParam],
        filename: str,
        debug: bool = False,
    ) -> None:
        self.osc = osc
        self.exposed_params = exposed_params
        self.filename = filename
        self.stored_presets: Dict[str, List[Tuple[str, Any]]] = {}
        self.current_preset = "default"
        self.debug = debug

        osc.dispatcher.map("/save_preset", lambda addr, args: self.save())
        osc.dispatcher.map("/clear_preset", lambda addr, args: self.clear())
        osc.dispatcher.map("/preset_selector", lambda _, args: self.select(args))

    def load(self):
        try:
            with open(self.filename, "rb") as f:
                self.stored_presets = pickle.load(f)
        # pylint: disable=broad-exception-caught
        except Exception as e:
            print("Pickle load failed, bad or missing pickle", e, flush=True)

    def clear(self) -> None:
        del self.stored_presets[self.current_preset]

        with open("./params.pickle", "wb") as f:  # type: ignore
            pickle.dump(self.stored_presets, f)

    def save(self) -> None:
        self.stored_presets[self.current_preset] = []
        for param in self.exposed_params:
            self.stored_presets[self.current_preset].append(
                (param.addr, param.value_lambda())
            )
        if self.debug:
            pprint.pp(self.stored_presets)

        with open("./params.pickle", "wb") as f:  # type: ignore
            pickle.dump(self.stored_presets, f)

    def sync(self):
        for param in self.exposed_params:
            param.sync()
        self.osc.send_osc("/preset_selector", self.current_preset)

    def select(self, preset_name: str) -> None:
        self.current_preset = preset_name
        if self.current_preset not in self.stored_presets.keys():
            return

        for param_preset in self.stored_presets[self.current_preset]:
            addr, value = param_preset[0], param_preset[1]
            for param in self.exposed_params:
                if param.addr == addr:
                    param.load(addr, value)
