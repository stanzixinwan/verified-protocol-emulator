# Verification harness

Hand-written and read-only to the AI implementer.

| File | Purpose |
| --- | --- |
| `uart.py` | UART decoder and timing checker; `uart_transitions` builds ideal waveforms |
| `waveform.py` | `PinRecorder` records a pin in cocotb; `bit_reader` handles X/Z and open drain |
| `tests/` | Checks on the checker: good waveforms pass, faulty ones are caught |
| `selftest/` | Simulator round trip through a wire fixture |

## Run

From the repository root:

```
pip install -r test/requirements.txt
python -m pytest -q harness/tests
make -C harness/selftest
```

## Next

1. `refmodel.py`: cycle-accurate Python model of the ISA in `spec/spec.md`, with its own tests.
2. `host.py`: drive the host SPI interface to load programs and push bytes.
3. `cosim.py`: run the RTL and the reference model on the same program; compare pins and registers every cycle.
4. `run_uart.py`: load `firmware/uart_tx.s`, push random bytes, record `uio[0]`, decode, write a JSON report.
5. SPI and I2C checkers in the same style as `uart.py`.
