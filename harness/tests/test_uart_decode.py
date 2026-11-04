"""Checks on the UART checker itself: it must pass good waveforms and catch bad ones."""

import pytest

from harness.uart import UartConfig, decode_uart, uart_transitions

PAYLOAD = [0x55, 0x00, 0xFF, 0xA5, 0x3C, 0x81]


@pytest.mark.parametrize("cpb", [4, 16, 434])
def test_ideal_waveform_passes(cpb):
    cfg = UartConfig(clocks_per_bit=cpb)
    tr, end = uart_transitions(PAYLOAD, cfg)
    rep = decode_uart(tr, cfg, end)
    assert rep.check_against(PAYLOAD) == []
    assert rep.max_edge_error_cycles == 0


def test_back_to_back_frames_without_gap():
    cfg = UartConfig(clocks_per_bit=16)
    tr, end = uart_transitions(PAYLOAD, cfg, gap_bits=0)
    assert decode_uart(tr, cfg, end).check_against(PAYLOAD) == []


def test_wrong_data_is_reported():
    cfg = UartConfig(clocks_per_bit=16)
    tr, end = uart_transitions([0x41], cfg)
    assert any("expected 0x42" in p for p in decode_uart(tr, cfg, end).check_against([0x42]))


def test_missing_byte_is_reported():
    cfg = UartConfig(clocks_per_bit=16)
    tr, end = uart_transitions([0x41], cfg)
    assert decode_uart(tr, cfg, end).check_against([0x41, 0x42]) != []


def test_bad_stop_bit_is_framing_error():
    cfg = UartConfig(clocks_per_bit=16)
    bad = UartConfig(clocks_per_bit=16, stop_bits=1, idle_level=1)
    tr, end = uart_transitions([0x00], bad)
    # Pull the line low through the stop bit.
    stop_start = 10 + 9 * 16
    tr = [t for t in tr if t[0] < stop_start] + [(stop_start + 20, 1)]
    rep = decode_uart(tr, cfg, end + 40)
    assert any("framing" in e for e in rep.all_errors())


def test_bit_five_percent_long_is_timing_error():
    cfg = UartConfig(clocks_per_bit=100)
    tr, end = uart_transitions([0x55], cfg, bit_cycles=lambda f, b: 105)
    rep = decode_uart(tr, cfg, end)
    assert not rep.ok
    assert any("bit boundary" in e for e in rep.all_errors())


def test_small_drift_within_tolerance_passes():
    cfg = UartConfig(clocks_per_bit=100)  # tolerance = 2 cycles
    tr, end = uart_transitions([0x55], cfg, bit_cycles=lambda f, b: 100 + (1 if b == 3 else 0))
    assert decode_uart(tr, cfg, end).ok


def test_glitch_inside_bit_is_reported():
    cfg = UartConfig(clocks_per_bit=16)
    tr, end = uart_transitions([0xFF], cfg)
    mid = 10 + 3 * 16 + 4  # inside data bit 2, which is high
    tr = sorted(tr + [(mid, 0), (mid + 2, 1)])
    assert not decode_uart(tr, cfg, end).ok


def test_parity_error_is_reported():
    good = UartConfig(clocks_per_bit=16, parity="even")
    tr, end = uart_transitions([0x07], good)
    odd = UartConfig(clocks_per_bit=16, parity="odd")
    assert any("parity" in e for e in decode_uart(tr, odd, end).all_errors())


def test_unknown_level_is_reported():
    cfg = UartConfig(clocks_per_bit=16)
    tr = [(0, 1), (30, None), (40, 1)]
    assert any("unknown" in e for e in decode_uart(tr, cfg, 200).all_errors())


def test_truncated_frame_is_reported():
    cfg = UartConfig(clocks_per_bit=16)
    tr, end = uart_transitions([0x12], cfg)
    assert any("truncated" in e for e in decode_uart(tr, cfg, 60).all_errors())


def test_line_low_at_start_is_reported():
    cfg = UartConfig(clocks_per_bit=16)
    rep = decode_uart([(0, 0), (5, 1)], cfg, 100)
    assert any("not idle" in e for e in rep.all_errors())
