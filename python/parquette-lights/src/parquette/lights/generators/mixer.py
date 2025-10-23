from typing import List, Tuple, cast

import time
from copy import copy
import math

from . import Generator
from ..osc import OSCManager, OSCParam
from ..dmx import DMXManager
from ..fixtures import SingleLight
from ..util.math import constrain


class Mixer(object):
    def __init__(
        self,
        *,
        osc: OSCManager,
        dmx: DMXManager,
        generators: List[Generator],
        history_len: float,
    ) -> None:
        self.mode = "MONO"
        self.osc = osc
        self.dmx = dmx
        self.generators = generators
        self.channel_names: List[str] = [
            "chan_1",
            "chan_2",
            "chan_3",
            "chan_4",
            "chan_5",
            "chan_6",
            "chan_7",
            "chan_8",
            "chan_9",
            "chan_10",
            "under_1",
            "under_2",
            "chan_spot",
            "sodium",
            "ceil_1",
            "ceil_2",
            "ceil_3",
        ]
        self.num_channels = len(self.channel_names)

        self.dmx_mappings = {
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
            "spot": [SingleLight(dmx, 13)],
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
        self.master_amp = 1
        self.wash_master = 1

    def setChannelLevel(self, chan_name: str, level: float):
        self.channel_offsets[self.channel_names.index(chan_name)] = level

    def getChannelLevel(self, chan_name: str) -> float:
        return self.channel_offsets[self.channel_names.index(chan_name)]

    def clearSignalMatrix(self) -> None:
        # pylint: disable-next=consider-using-enumerate
        for gen_ix in range(len(self.signal_matrix)):
            for chan_ix in range(len(self.signal_matrix[gen_ix])):
                self.signal_matrix[gen_ix][chan_ix] = 0

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
        for gen_idx, gen_connected_chans in enumerate(self.signal_matrix):
            for chan_idx, chan_connected in enumerate(gen_connected_chans):
                self.channels[0][chan_idx] += (
                    self.generators[gen_idx].value(ts) * chan_connected
                )

        for i, val in enumerate(self.channels[0]):
            if not self.channel_names[i] in (
                "chan_spot",
                "under_1",
                "under_2",
                "sodium",
                "ceil_1",
                "ceil_2",
                "ceil_3",
            ):
                self.channels[0][i] = val * self.master_amp

        for i, val in enumerate(self.channels[0]):
            if self.channel_names[i] in (
                "under_1",
                "under_2",
                "ceil_1",
                "ceil_2",
                "ceil_3",
            ):
                self.channels[0][i] = val * self.wash_master

    def runOutputMix(self) -> None:
        self.dmx_mappings["spot"][0].on(
            self.channels[0][self.channel_names.index("chan_spot")]
        )
        self.dmx_mappings["under"][0].on(
            self.channels[0][self.channel_names.index("under_1")]
        )
        self.dmx_mappings["under"][1].on(
            self.channels[0][self.channel_names.index("under_2")]
        )
        self.dmx_mappings["sodium"][0].on(
            self.channels[0][self.channel_names.index("sodium")]
        )
        self.dmx_mappings["ceil"][0].on(
            self.channels[0][self.channel_names.index("ceil_1")]
        )
        self.dmx_mappings["ceil"][1].on(
            self.channels[0][self.channel_names.index("ceil_2")]
        )
        self.dmx_mappings["ceil"][2].on(
            self.channels[0][self.channel_names.index("ceil_3")]
        )

        if self.mode == "MONO":
            for group, fixtures in self.dmx_mappings.items():
                if not group in ("spot", "under", "ceil", "sodium"):
                    for fixture in fixtures:
                        fixture.on(self.channels[0][0])

        elif self.mode == "PENTA":
            for i, (fixture_l, fixture_r) in enumerate(
                zip(self.dmx_mappings["left"], self.dmx_mappings["right"])
            ):
                fixture_l.on(self.channels[0][i + 1])
                fixture_r.on(self.channels[0][i + 1])

            self.dmx_mappings["front"][0].on(self.channels[0][0])
            self.dmx_mappings["front"][1].on(self.channels[0][0])
        elif self.mode == "DECA":
            for i, fixture in enumerate(
                self.dmx_mappings["left"]
                + self.dmx_mappings["right"]
                + self.dmx_mappings["front"]
            ):
                fixture.on(self.channels[0][i])
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
                fixture_l.on(int(constrain(self.channels[stutter_index][0], 0, 255)))
                fixture_r.on(int(constrain(self.channels[stutter_index][1], 0, 255)))
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
                fixture.on(int(constrain(self.channels[stutter_index][0], 0, 255)))

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
        self.mixer.clearSignalMatrix()

        for conf in args:
            self.mixer.configureSignalMatrix(conf[0], cast(List[str], conf[1:]))

        self.sync()

    def dispatch_patch(self, _: str, *args):
        self.mixer.configureSignalMatrix(args[0], args[1:])

    def sync(self) -> None:
        for gen_ix in range(len(self.mixer.signal_matrix)):
            output_val = [self.mixer.generators[gen_ix].name]
            self.osc.send_osc("/signal_patchbay", output_val)

        # pylint: disable-next=consider-using-enumerate
        for gen_ix in range(len(self.mixer.signal_matrix)):
            output_val = [self.mixer.generators[gen_ix].name]
            for chan_ix in range(len(self.mixer.signal_matrix[gen_ix])):
                if self.mixer.signal_matrix[gen_ix][chan_ix]:
                    output_val.append(self.mixer.channel_names[chan_ix])

            self.osc.send_osc("/signal_patchbay", output_val)
