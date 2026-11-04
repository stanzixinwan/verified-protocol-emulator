"""Pin-level UART checker.

Works only on the recorded levels of one line, so it does not depend on how
the design under test is built. Input is a list of (cycle, level) transitions,
as produced by harness.waveform.PinRecorder.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field


@dataclass
class UartConfig:
    clocks_per_bit: int
    data_bits: int = 8
    parity: str = "none"  # "none" | "even" | "odd"
    stop_bits: int = 1
    idle_level: int = 1
    # Largest allowed distance between an observed edge and the ideal bit
    # boundary. Default: 2% of a bit period, at least 1 clock cycle.
    max_edge_error_cycles: float | None = None

    def tolerance(self) -> float:
        if self.max_edge_error_cycles is not None:
            return self.max_edge_error_cycles
        return max(1.0, 0.02 * self.clocks_per_bit)

    def frame_bits(self) -> int:
        return 1 + self.data_bits + (0 if self.parity == "none" else 1) + self.stop_bits


@dataclass
class UartFrame:
    start_cycle: int
    value: int | None
    errors: list[str] = field(default_factory=list)


@dataclass
class UartReport:
    frames: list[UartFrame]
    errors: list[str]
    max_edge_error_cycles: float

    @property
    def data(self) -> list[int | None]:
        return [f.value for f in self.frames]

    @property
    def ok(self) -> bool:
        return not self.errors and all(not f.errors for f in self.frames)

    def all_errors(self) -> list[str]:
        out = list(self.errors)
        for f in self.frames:
            out += [f"frame@{f.start_cycle}: {e}" for e in f.errors]
        return out

    def check_against(self, expected: list[int]) -> list[str]:
        """Compare decoded bytes with the expected bytes; return mismatches."""
        problems = self.all_errors()
        got = self.data
        if len(got) != len(expected):
            problems.append(f"expected {len(expected)} bytes, decoded {len(got)}")
        for i, (g, e) in enumerate(zip(got, expected)):
            if g != e:
                problems.append(f"byte {i}: expected 0x{e:02X}, got {_hex(g)}")
        return problems

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "data": self.data,
            "max_edge_error_cycles": self.max_edge_error_cycles,
            "errors": self.all_errors(),
        }


def _hex(v: int | None) -> str:
    return "None" if v is None else f"0x{v:02X}"


class _Line:
    """Level lookup over a transition list."""

    def __init__(self, transitions: list[tuple[int, int | None]], idle: int):
        if not transitions or transitions[0][0] > 0:
            transitions = [(0, idle)] + list(transitions)
        self.cycles = [c for c, _ in transitions]
        self.levels = [v for _, v in transitions]

    def level_at(self, cycle: float) -> int | None:
        i = bisect_right(self.cycles, cycle) - 1
        return self.levels[max(i, 0)]

    def edges_between(self, lo: float, hi: float) -> list[tuple[int, int | None]]:
        return [(c, v) for c, v in zip(self.cycles, self.levels) if lo < c <= hi]

    def next_edge_to(self, level: int, after: float) -> int | None:
        for c, v in zip(self.cycles, self.levels):
            if c > after and v == level:
                return c
        return None


def decode_uart(
    transitions: list[tuple[int, int | None]],
    cfg: UartConfig,
    end_cycle: int,
) -> UartReport:
    """Decode every UART frame on the line and check its timing."""
    line = _Line(transitions, cfg.idle_level)
    cpb = cfg.clocks_per_bit
    nbits = cfg.frame_bits()
    tol = cfg.tolerance()
    active = 1 - cfg.idle_level

    frames: list[UartFrame] = []
    errors: list[str] = []
    worst = 0.0

    unknown = [c for c, v in zip(line.cycles, line.levels) if v is None]
    if unknown:
        errors.append(f"line unknown (X/Z) at cycle {unknown[0]}")
    if line.level_at(0) == active:
        errors.append("line not idle when recording started")

    cursor = 0.0
    while True:
        t0 = line.next_edge_to(active, cursor)
        if t0 is None:
            break
        frame = UartFrame(start_cycle=t0, value=None)
        frames.append(frame)

        last_sample = t0 + (nbits - 0.5) * cpb
        if last_sample > end_cycle:
            frame.errors.append("frame truncated by end of recording")
            break

        samples = [line.level_at(t0 + (i + 0.5) * cpb) for i in range(nbits)]
        if samples[0] != active:
            frame.errors.append("start bit not held (glitch)")
            cursor = t0
            continue

        data_samples = samples[1 : 1 + cfg.data_bits]
        if any(s is None for s in data_samples):
            frame.errors.append("unknown level inside data bits")
        else:
            bits = [s if cfg.idle_level == 1 else 1 - s for s in data_samples]
            frame.value = sum(b << i for i, b in enumerate(bits))

        idx = 1 + cfg.data_bits
        if cfg.parity != "none":
            p = samples[idx]
            ones = sum(data_samples) + (p or 0)
            want_even = cfg.parity == "even"
            if (ones % 2 == 0) != want_even:
                frame.errors.append("parity error")
            idx += 1

        for k in range(cfg.stop_bits):
            if samples[idx + k] != cfg.idle_level:
                frame.errors.append("framing error: stop bit not at idle level")

        for c, _ in line.edges_between(t0, last_sample):
            k = round((c - t0) / cpb)
            err = abs(c - t0 - k * cpb)
            worst = max(worst, err)
            if err > tol:
                frame.errors.append(
                    f"edge at cycle {c} is {err:.1f} cycles from bit boundary {k} "
                    f"(limit {tol:.1f})"
                )

        cursor = last_sample

    return UartReport(frames=frames, errors=errors, max_edge_error_cycles=worst)


def uart_transitions(
    data: list[int],
    cfg: UartConfig,
    start_cycle: int = 10,
    gap_bits: int = 1,
    bit_cycles=None,
) -> tuple[list[tuple[int, int]], int]:
    """Build an ideal UART waveform as transitions; for stimulus and self-tests.

    bit_cycles(frame_index, bit_index) may return a custom length for a bit,
    which lets tests create timing faults on purpose.
    """
    idle = cfg.idle_level
    out: list[tuple[int, int]] = [(0, idle)]
    t = start_cycle
    level = idle

    def put(v: int):
        nonlocal level
        if v != level:
            out.append((t, v))
            level = v

    for fi, byte in enumerate(data):
        bits = [1 - idle]
        bits += [((byte >> i) & 1) if idle == 1 else 1 - ((byte >> i) & 1) for i in range(cfg.data_bits)]
        if cfg.parity != "none":
            ones = bin(byte & ((1 << cfg.data_bits) - 1)).count("1")
            p = ones % 2 if cfg.parity == "even" else 1 - ones % 2
            bits.append(p)
        bits += [idle] * cfg.stop_bits
        for bi, b in enumerate(bits):
            put(b)
            t += bit_cycles(fi, bi) if bit_cycles else cfg.clocks_per_bit
        t += gap_bits * cfg.clocks_per_bit
    return out, t
