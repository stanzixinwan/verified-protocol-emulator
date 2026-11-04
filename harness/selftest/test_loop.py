"""Round trip in the simulator: drive a UART waveform, record it, decode it."""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

from harness.uart import UartConfig, decode_uart, uart_transitions
from harness.waveform import PinRecorder, bit_reader


async def drive(dut, transitions, until):
    i, cycle = 0, 0
    while cycle < until:
        while i < len(transitions) and transitions[i][0] == cycle:
            dut.line_in.value = transitions[i][1]
            i += 1
        await RisingEdge(dut.clk)
        cycle += 1


@cocotb.test()
async def uart_round_trip(dut):
    cfg = UartConfig(clocks_per_bit=16)
    payload = [0x55, 0x00, 0xFF, 0xA5, 0x3C]

    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())
    dut.line_in.value = 1
    rec = PinRecorder(dut.clk, bit_reader(dut.line_out)).start()

    tr, end = uart_transitions(payload, cfg, start_cycle=20)
    await drive(dut, tr, end + 40)
    rec.stop()

    rep = decode_uart(rec.transitions, cfg, end_cycle=rec.cycle)
    problems = rep.check_against(payload)
    assert problems == [], problems
    dut._log.info("decoded %s, worst edge error %.1f cycles", rep.data, rep.max_edge_error_cycles)
