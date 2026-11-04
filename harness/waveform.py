"""Record pin levels from a cocotb simulation as (cycle, level) transitions."""

from __future__ import annotations

import cocotb
from cocotb.triggers import RisingEdge


def bit_reader(handle, index: int | None = None, oe_handle=None, pull: int | None = None):
    """Return a function that reads one pin as 0, 1 or None (X/Z).

    With oe_handle and pull, a released pin (output enable low) reads as the
    pull level, which models open-drain lines such as I2C and 1-Wire.
    """

    def read() -> int | None:
        try:
            if oe_handle is not None and pull is not None:
                oe = oe_handle.value if index is None else oe_handle.value[index]
                if int(oe) == 0:
                    return pull
            v = handle.value if index is None else handle.value[index]
            return int(v)
        except ValueError:
            return None

    return read


class PinRecorder:
    """Samples a pin on every rising clock edge and keeps only level changes."""

    def __init__(self, clk, read_level):
        self.clk = clk
        self.read_level = read_level
        self.transitions: list[tuple[int, int | None]] = []
        self.cycle = 0
        self._task = None

    def start(self):
        self._task = cocotb.start_soon(self._run())
        return self

    def stop(self):
        if self._task is not None:
            self._task.cancel()

    async def _run(self):
        last = object()
        while True:
            await RisingEdge(self.clk)
            v = self.read_level()
            if v != last:
                self.transitions.append((self.cycle, v))
                last = v
            self.cycle += 1
