import time
from typing import Callable, Dict, List, Sequence, Union

from ..category import Category
from ..generators.bpm_generator import BPMGenerator
from ..generators.generator import Generator
from ..generators.loop_generator import LoopGenerator
from ..generators.mixer import Mixer
from ..osc import OSCManager, OSCParam


class ParamGeneratorBuilder:
    """Base class for category-specific parameter and generator builders.

    Each subclass creates its own generators in __init__, registers any
    OSC action handlers (snap-to-BPM, loop record, etc.), and builds all
    OSCParams in build_params.
    """

    def generators(self) -> List[Generator]:
        """Return all generators owned by this builder."""
        return []

    # pylint: disable=unused-argument
    def build_params(self, mixer: Mixer) -> Dict[Category, List[OSCParam]]:
        """Return a dict mapping Category objects to their OSCParam lists."""
        return {}


def register_snap_handler(
    osc: OSCManager,
    snap_addr: str,
    gens: Sequence[Generator],
    period_addrs: Union[str, List[str]],
    bpm_gen: BPMGenerator,
) -> None:
    """Register a snap-to-BPM OSC handler.

    When triggered, sets each generator's period to the BPM generator's
    current period and syncs the value to the frontend.
    """
    if isinstance(period_addrs, str):
        period_addrs = [period_addrs]

    def handler() -> None:
        if bpm_gen.bpm > 0 and bpm_gen.bpm_mult > 0:
            period = bpm_gen.current_period()
            for gen in gens:
                gen.period = period
            for addr in period_addrs:
                osc.send_osc(addr, period)

    osc.dispatcher.map(snap_addr, lambda addr, *args: handler())


def register_loop_record_handler(
    osc: OSCManager,
    record_addr: str,
    loop_gens: List[LoopGenerator],
) -> None:
    """Register a loop recording toggle OSC handler."""
    if len(loop_gens) == 1:
        gen = loop_gens[0]
        osc.dispatcher.map(
            record_addr,
            lambda addr, *args: gen.set_recording(bool(args[0])),
        )
    else:

        def make_handler(
            gens: List[LoopGenerator],
        ) -> Callable:
            # pylint: disable-next=unused-argument
            def handler(addr: str, *args: object) -> None:
                ts = time.time() * 1000
                for g in gens:
                    g.set_recording(bool(args[0]), ts)

            return handler

        osc.dispatcher.map(record_addr, make_handler(loop_gens))
