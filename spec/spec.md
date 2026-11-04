# Protocol Emulator Specification (v1 draft)

The contract between the AI implementer and the verification harness. The
architecture and instruction set below are fixed by me; the AI implements
them in RTL. Not given to the AI in E0. Freeze before E1.

## 1. Hard limits

| Item | Requirement |
| --- | --- |
| Process | Tiny Tapeout IHP CMOS5L template |
| Area | 6x4 tiles after place and route |
| Clock | 50 MHz (`clock_hz: 50000000`); fallback 25 MHz |
| Precheck | Tiny Tapeout precheck passes |
| License | Apache-2.0 |

## 2. Platform

| Element | Value |
| --- | --- |
| State machines | 1 |
| Instruction memory | 64 x 16, SRAM where possible; loaded by the host |
| Registers | X, Y (16-bit scratch), ISR, OSR (16-bit shift registers) |
| FIFOs | TX (host to engine) and RX (engine to host), 4 entries x 16 bits each |
| Input path | 2-flop synchronizer on every protocol pin: an input change is visible 2 cycles later |
| Protocol pins | `uio[7:0]`, per-pin output value and output enable |

No protocol-specific blocks (UART, SPI or I2C controllers).

## 3. Pins

| Pins | Use |
| --- | --- |
| `ui_in[0]` | Host SPI SCK |
| `ui_in[1]` | Host SPI MOSI |
| `ui_in[2]` | Host SPI CS_N (active low) |
| `uo_out[0]` | Host SPI MISO |
| `uio[7:0]` | Protocol pins |
| `ui_in[7:3]`, `uo_out[7:1]` | Unused; drive outputs to 0 |

Open-drain lines: drive low with output enable 1 and value 0; release with
output enable 0. The harness models a pull-up on released pins.

## 4. Host interface

SPI mode 0, MSB first, host SCK at most clk/8. Each transaction starts with
CS_N falling; the first byte is a command.

| Command | Bytes after it | Effect |
| --- | --- | --- |
| `0x01` WRITE_MEM | addr, then 2 bytes per word (high, low) | Write instruction words from addr, auto-increment |
| `0x02` RUN | none | Reset registers and FIFOs, start at address 0 |
| `0x03` HALT | none | Stop execution; pins keep their state |
| `0x10` PUSH | byte | Push the byte, zero-extended, into the TX FIFO |
| `0x11` POP | dummy | Next MISO byte = low byte popped from the RX FIFO |
| `0x12` STATUS | dummy | MISO byte: bit0 running, bit1 TX FIFO full, bit2 RX FIFO empty |

## 5. Instruction set

Word format: `[15:13]` opcode, `[12:8]` delay (0-31), `[7:0]` operands.

**Timing.** An instruction executes in one cycle, then the engine idles for
`delay` cycles. Total: 1 + delay cycles. `WAIT`, blocking `PULL` and blocking
`PUSH` stall first; the delay starts when the stall ends. Pin outputs change
at the end of the cycle in which the instruction executes.

| Opcode | Name | Operands `[7:0]` | Effect |
| --- | --- | --- | --- |
| `000` | JMP | `[7:6]` cond, `[5:0]` addr | cond 00 always; 01 X != 0, then X--; 10 Y != 0, then Y--; 11 X != Y |
| `001` | WAIT | `[7]` level, `[2:0]` pin | Stall until synchronized `uio[pin]` equals level |
| `010` | IN | `[7:5]` base pin, `[4:0]` count (0 = 16) | Shift `count` bits from pins base, base+1, ... into ISR from the top; ISR shifts right |
| `011` | OUT | `[7:5]` base pin, `[4:0]` count (0 = 16) | Shift `count` bits out of OSR LSB first onto pins base, base+1, ...; OSR shifts right |
| `100` | PUSH/PULL | `[7]` 0 PUSH, 1 PULL; `[6]` block | PUSH: ISR to RX FIFO, ISR cleared. PULL: TX FIFO to OSR. Non-blocking on full/empty: PUSH drops, PULL copies X |
| `101` | MOV | `[7:5]` dst, `[4:2]` src, `[1:0]` op | Registers: 000 X, 001 Y, 010 ISR, 011 OSR, 100 PINS (read: synchronized inputs; write: output values), 101 NULL (0). op 00 copy, 01 invert, 10 reverse low 8 bits (upper bits cleared) |
| `110` | SET | `[7:6]` target, `[5:0]` value | target 00: pin `[5:3]` value `[0]`; 01: pin `[5:3]` output enable `[0]`; 10: X = value; 11: Y = value |
| `111` | NOP | none | Idle 1 + delay cycles |

On RUN: X, Y, ISR, OSR = 0; all output enables = 0; all output values = 1.

## 6. Firmware

- Assembler: `python firmware/asm.py <source.s> -o <image.bin>` (AI writes it;
  syntax follows the names above)
- Sources: `firmware/uart_tx.s`, `uart_rx.s`, `spi.s`, `i2c.s`
- Parameters come first through the TX FIFO: bit period in cycles (UART) or
  half SCK period (SPI, I2C), as two pushes, low byte then high byte; then data.

| Protocol | Pins |
| --- | --- |
| UART | TX `uio[0]`, RX `uio[1]` |
| SPI controller | SCK `uio[0]`, MOSI `uio[1]`, MISO `uio[2]`, CS_N `uio[3]` |
| I2C controller | SCL `uio[0]`, SDA `uio[1]` (open drain) |

## 7. Out of scope

Low-speed USB, 10 Mbit Ethernet, electrical I2C limits.
