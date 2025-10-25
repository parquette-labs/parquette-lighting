from typing import List, Tuple, cast, Dict, Optional

import time
from copy import copy
import math

from . import Generator
from ..osc import OSCManager, OSCParam
from ..dmx import DMXManager
from ..fixtures import SingleLight, Spot, RGBLight
from ..util.math import constrain


class Mixer(object):
    def __init__(
        self,
        *,
        osc: OSCManager,
        dmx: DMXManager,
        generators: List[Generator],
        spots: List[Spot],
        washes: List[RGBLight],
        history_len: float,
    ) -> None:
        self.mode = "MONO"
        self.osc = osc
        self.dmx = dmx
        self.generators = generators
        # TODO use this as the chan name reference throughout to better filter categories
        # should include what master it uses, what it's mapping is in different scenarios (as a lambda)
        self.categorized_channel_names: Dict[str, List[str]] = {
            "reds": ["chan_1", "chan_2", "chan_3", "chan_4", "chan_5"],
            "plants": [
                "ceil_1",
                "ceil_2",
                "ceil_3",
            ],
            "booth": [
                "under_1",
                "under_2",
            ],
            "spots_light": ["spot_1", "spot_2", "spot_3", "tung_spot"],
            "washes": ["wash_1"],
            "non-saved": ["sodium"],
        }

        self.channel_names: List[str] = [
            name
            for _, names in self.categorized_channel_names.items()
            for name in names
        ]

        self.num_channels = len(self.channel_names)

        self.dmx_mappings: Dict[str, List[Spot | RGBLight | SingleLight]] = {
            "left": [
                SingleLight(dmx, 4),
                SingleLight(dmx, 3),
                SingleLight(dmx, 2),
                SingleLight(dmx, 1),
            ],
            "right": [
                SingleLight(dmx, 5),
                SingleLight(dmx, 6),
                SingleLight(dmx, 7),
                SingleLight(dmx, 8),
            ],
            "front": [SingleLight(dmx, 12), SingleLight(dmx, 9)],
            "under": [SingleLight(dmx, 10), SingleLight(dmx, 11)],
            "spot": cast(
                list[Spot | RGBLight | SingleLight], [SingleLight(dmx, 13)] + spots
            ),
            "wash": cast(list[Spot | RGBLight | SingleLight], washes),
            "sodium": [SingleLight(dmx, 20)],
            "ceil": [SingleLight(dmx, 18), SingleLight(dmx, 19), SingleLight(dmx, 17)],
        }

        # TODO control the matrix sizing in open sound control with this var?
        # TODO this could be initialized / resetup in a subfn that can be reused if the live setup changes
        # This is an array of the output values at different time slices, the design is that each timeslice is 20ms back in time, so self.channels[timeslice][chan]
        self.channels = [
            [0.0] * self.num_channels for _ in range(math.ceil(history_len * 1000 / 20))
        ]
        # This is the default base value of each chan
        self.channel_offsets = [0.0] * self.num_channels
        # This is a matrix from the patch bay of what signals go to what chans of shape signal_matrix[num_gen][num_chan]
        self.signal_matrix = [
            [0.0] * self.num_channels for _ in range(len(self.generators))
        ]

        self.stutter_period = 500
        self.reds_master = 1
        self.spots_master = 1
        self.washes_master = 1
        self.booth_master = 1
        self.plants_master = 1

    def setChannelLevel(self, chan_name: str, level: float):
        self.channel_offsets[self.channel_names.index(chan_name)] = level

    def getChannelLevel(self, chan_name: str) -> float:
        return self.channel_offsets[self.channel_names.index(chan_name)]

    def clearSignalMatrix(self, chan_name: Optional[str] = None) -> None:
        # pylint: disable-next=consider-using-enumerate
        for gen_ix in range(len(self.signal_matrix)):
            for chan_ix in range(len(self.signal_matrix[gen_ix])):
                if chan_name is None:
                    self.signal_matrix[gen_ix][chan_ix] = 0
                elif self.channel_names[chan_ix] == chan_name:
                    self.signal_matrix[gen_ix][chan_ix] = 0

    def configureSignalPath(self, target_gen: str, target_chan: str, enable: bool):
        gen_ix = list(map(lambda gen: gen.name, self.generators)).index(target_gen)
        chan_ix = self.channel_names.index(target_chan)
        self.signal_matrix[gen_ix][chan_ix] = int(enable)

    def configureSignalMatrix(
        self, target_gen: str, target_chans: Tuple[str] | List[str]
    ) -> None:
        try:
            gen_ix = list(map(lambda gen: gen.name, self.generators)).index(target_gen)
            destinations = [
                self.channel_names.index(chan_name) for chan_name in target_chans
            ]
            for i in range(len(self.signal_matrix[gen_ix])):
                if i in destinations:
                    self.signal_matrix[gen_ix][i] = 1
                else:
                    self.signal_matrix[gen_ix][i] = 0

        except ValueError:
            print(
                "Couldn't parse signal mapping, gen {}, chans {}".format(
                    target_gen, target_chans
                ),
                flush=True,
            )

    def runChannelMix(self) -> None:
        # slide the channel history back one timestep
        self.channels[1:] = self.channels[0:-1]

        # setup current times
        self.channels[0] = copy(self.channel_offsets)

        ts = time.time() * 1000

        impulse_ix = list(map(lambda gen: gen.name, self.generators)).index("impulse")
        self.channels[0][self.channel_names.index("sodium")] += self.generators[
            impulse_ix
        ].value(ts)

        for gen_idx, gen_connected_chans in enumerate(self.signal_matrix):
            for chan_idx, chan_connected in enumerate(gen_connected_chans):
                self.channels[0][chan_idx] += (
                    self.generators[gen_idx].value(ts) * chan_connected
                )

        for i, val in enumerate(self.channels[0]):
            if not self.channel_names[i] in (
                "tung_spot",
                "under_1",
                "under_2",
                "sodium",
                "ceil_1",
                "ceil_2",
                "ceil_3",
                "spot_1",
                "spot_2",
                "spot_3",
                "wash_1",
            ):
                self.channels[0][i] = val * self.reds_master

        for i, val in enumerate(self.channels[0]):
            if self.channel_names[i] in (
                "ceil_1",
                "ceil_2",
                "ceil_3",
            ):
                self.channels[0][i] = val * self.plants_master

        for i, val in enumerate(self.channels[0]):
            if self.channel_names[i] in (
                "spot_1",
                "spot_2",
                "spot_3",
                "tung_spot",
            ):
                self.channels[0][i] = val * self.spots_master

        for i, val in enumerate(self.channels[0]):
            if self.channel_names[i] in ("wash_1",):
                self.channels[0][i] = val * self.washes_master

        for i, val in enumerate(self.channels[0]):
            if self.channel_names[i] in (
                "under_1",
                "under_2",
            ):
                self.channels[0][i] = val * self.booth_master

    def runOutputMix(self) -> None:
        # spots
        self.dmx_mappings["spot"][0].dimming(
            self.channels[0][self.channel_names.index("tung_spot")]
        )
        self.dmx_mappings["spot"][1].dimming(
            self.channels[0][self.channel_names.index("spot_1")]
        )
        self.dmx_mappings["spot"][2].dimming(
            self.channels[0][self.channel_names.index("spot_2")]
        )
        self.dmx_mappings["spot"][3].dimming(
            self.channels[0][self.channel_names.index("spot_3")]
        )

        # washes
        self.dmx_mappings["wash"][0].dimming(
            self.channels[0][self.channel_names.index("wash_1")]
        )

        # booth
        self.dmx_mappings["under"][0].dimming(
            self.channels[0][self.channel_names.index("under_1")]
        )
        self.dmx_mappings["under"][1].dimming(
            self.channels[0][self.channel_names.index("under_2")]
        )

        # sodium
        self.dmx_mappings["sodium"][0].dimming(
            self.channels[0][self.channel_names.index("sodium")]
        )

        # plants
        self.dmx_mappings["ceil"][0].dimming(
            self.channels[0][self.channel_names.index("ceil_1")]
        )
        self.dmx_mappings["ceil"][1].dimming(
            self.channels[0][self.channel_names.index("ceil_2")]
        )
        self.dmx_mappings["ceil"][2].dimming(
            self.channels[0][self.channel_names.index("ceil_3")]
        )

        if self.mode == "MONO":
            for group, fixtures in self.dmx_mappings.items():
                if group in ("left", "right", "front"):
                    for fixture in fixtures:
                        fixture.dimming(self.channels[0][0])

        elif self.mode == "PENTA":
            for i, (fixture_l, fixture_r) in enumerate(
                zip(self.dmx_mappings["left"], self.dmx_mappings["right"])
            ):
                fixture_l.dimming(self.channels[0][i + 1])
                fixture_r.dimming(self.channels[0][i + 1])

            self.dmx_mappings["front"][0].dimming(self.channels[0][0])
            self.dmx_mappings["front"][1].dimming(self.channels[0][0])

        elif self.mode in ("FWD", "BACK"):
            fixture_zip = list(
                zip(
                    self.dmx_mappings["front"][0:1] + self.dmx_mappings["left"],
                    self.dmx_mappings["front"][1:2] + self.dmx_mappings["right"],
                )
            )
            if self.mode == "BACK":
                fixture_zip = list(reversed(fixture_zip))
            for i, (fixture_l, fixture_r) in enumerate(fixture_zip):
                stutter_index = int(
                    constrain(
                        self.stutter_period * i / 10,
                        0,
                        len(self.channels) - 1,
                    )
                )
                fixture_l.dimming(
                    int(constrain(self.channels[stutter_index][0], 0, 255))
                )
                fixture_r.dimming(
                    int(constrain(self.channels[stutter_index][1], 0, 255))
                )
        elif self.mode == "ZIG":
            interleaved_fixtures = [
                val
                for tup in zip(
                    self.dmx_mappings["front"][0:1] + self.dmx_mappings["left"],
                    self.dmx_mappings["front"][1:2] + self.dmx_mappings["right"],
                )
                for val in tup
            ]

            for i, fixture in enumerate(interleaved_fixtures):
                stutter_index = int(
                    constrain(
                        self.stutter_period * i / 10,
                        0,
                        len(self.channels) - 1,
                    )
                )
                fixture.dimming(int(constrain(self.channels[stutter_index][0], 0, 255)))

    def updateDMX(self) -> None:
        self.dmx.submit()


class SignalPatchParam(OSCParam):
    def __init__(
        self,
        osc: OSCManager,
        addr: str,
        mixer: Mixer,
    ) -> None:
        super().__init__(osc, addr, self.value_builder, self.dispatch_patch)
        self.mixer = mixer

    def value_builder(self) -> List[List[str]]:
        mappings: List[List[str]] = []
        # pylint: disable-next=consider-using-enumerate
        for gen_ix in range(len(self.mixer.signal_matrix)):
            gen_mapping = [self.mixer.generators[gen_ix].name]
            for chan_ix in range(len(self.mixer.signal_matrix[gen_ix])):
                if self.mixer.signal_matrix[gen_ix][chan_ix]:
                    gen_mapping.append(self.mixer.channel_names[chan_ix])
            mappings.append(gen_mapping)
        return mappings

    def load(self, addr: str, args: List[List[str]]) -> None:
        chan_names = set()
        for conf in args:
            for chan_name in conf[1:]:
                chan_names.add(chan_name)

        for chan_name in list(chan_names):
            self.mixer.clearSignalMatrix(chan_name)

        for conf in args:
            for chan_name in conf[1:]:
                self.mixer.configureSignalPath(conf[0], chan_name, True)

        self.sync()

    def dispatch_patch(self, _: str, *args):
        for chan_name in args[1:]:
            self.mixer.configureSignalPath(args[0], chan_name, True)

    def sync(self) -> None:
        for gen_ix in range(len(self.mixer.signal_matrix)):
            output_val = [self.mixer.generators[gen_ix].name]
            self.osc.send_osc(self.addr, output_val)

        # pylint: disable-next=consider-using-enumerate
        for gen_ix in range(len(self.mixer.signal_matrix)):
            output_val = [self.mixer.generators[gen_ix].name]
            for chan_ix in range(len(self.mixer.signal_matrix[gen_ix])):
                if self.mixer.signal_matrix[gen_ix][chan_ix]:
                    output_val.append(self.mixer.channel_names[chan_ix])

            self.osc.send_osc(self.addr, output_val)
