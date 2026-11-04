# Personal Proposal: Verification-First Protocol Emulator

Jane Street Protocol Emulator ASIC Competition
Nov 3, 2026
Stan Wan

## Question

**Can a small, human-specified protocol engine be implemented entirely by an AI agent and accepted by an independent, cycle-accurate verifier, and how much does that verifier change what the AI delivers?**

I specify a deliberately conventional, PIO-style engine and its instruction set. Claude Code writes all RTL, the assembler and the firmware. A verifier I build decides what is accepted. The platform is a set of engineering choices; the research variable is the verification feedback.

Negative results are valid: if the AI delivers the same quality without the verifier, or the frozen engine cannot run a new protocol, the proposal reports that.

## Division of work

I own every design decision; the AI owns the implementation. No RTL is written by hand.


| Part                                             | Owner |
| ------------------------------------------------ | ----- |
| Platform choices and instruction set             | Me    |
| Python cycle-accurate reference model of the ISA | Me    |
| Verification harness and protocol checkers       | Me    |
| Experiment harness and logging                   | Me    |
| RTL (Verilog)                                    | AI    |
| Assembler and firmware                           | AI    |


The harness is architecture-independent at the pin level, so it can verify any implementation that follows the same pin contract.

## Platform and the choices behind it

**Design rule:** spend area only when it lets the engine run a protocol it otherwise cannot, or buys a timing point that is verified.


| Choice                                      | Trade-off                    | Why this point                                                                                                                             |
| ------------------------------------------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| 1 state machine                             | Area ↔ concurrency           | Simplest engine to specify and verify; full-duplex SPI fits in one program. A second machine is added only if a held-out protocol needs it |
| 64×16 instruction SRAM                      | Area ↔ program length        | Smallest SRAM macro in the flow; 64 instructions cover UART, SPI and I2C                                                                   |
| 16-bit instructions                         | Encoding room ↔ memory       | Opcode, operand and delay field fit one SRAM word                                                                                          |
| 16-bit shift and scratch registers          | Area ↔ word length           | Covers 8-bit bytes and 16-bit frames at half the area of 32-bit                                                                            |
| Delay field on every instruction            | Encoding bits ↔ program size | Each instruction takes exactly 1 + delay cycles; tight timing loops need no extra instructions                                             |
| 4-entry TX and RX FIFOs                     | Area ↔ buffering             | Minimum that lets the host refill between bytes                                                                                            |
| 50 MHz clock                                | Timing closure ↔ resolution  | 20 ns resolution; UART at 115200 baud is 434 cycles per bit; fallback 25 MHz                                                               |
| 2-flop input synchronizer                   | Robustness ↔ latency         | Safe default; its two-cycle observation cost is known and fixed                                                                            |
| 8 bidirectional pins, per-pin output enable | Pins ↔ protocol coverage     | Open-drain I2C and 1-Wire without extra hardware                                                                                           |


All choices share one 6×4-tile budget, and instruction memory is the largest single block. More generality costs area and cycles per bit, which is why the engine stays minimal and protocol-specific blocks are excluded.

## Instruction set sketch

Eight PIO-style opcodes (PULL and PUSH share one) in a 16-bit word: 3-bit opcode, 5-bit delay, 8-bit operands. Every instruction takes 1 + delay cycles, except `WAIT`, whose timing is measured from the awaited edge.


| Instruction       | Effect                                                                    |
| ----------------- | ------------------------------------------------------------------------- |
| `SET pins, v`     | Drive values on selected pins                                             |
| `DIR pins, v`     | Set output enables; releasing a pin gives open drain                      |
| `OUT pins, n`     | Shift n bits from the output shift register to pins                       |
| `IN pins, n`      | Shift n bits from pins into the input shift register                      |
| `WAIT pin, level` | Stall until a pin reaches a level                                         |
| `JMP cond, addr`  | Always, X−− ≠ 0, Y−− ≠ 0, pin high, output register empty                 |
| `PULL` / `PUSH`   | Move a word between a FIFO and a shift register; block when empty or full |
| `MOV dst, src`    | Copy between X, Y, shift registers and pins                               |


This is deliberately close to a PIO subset. The difference is not the instruction set but its contract: a written specification plus an executable reference model, so any implementation can be checked cycle by cycle. The exact encoding is frozen before the AI sees it.

## Verification

Every requirement traces to evidence: requirement → property or test → result. The harness takes a design directory and returns one JSON report per run.

1. **Reference-model co-simulation:** the RTL and my Python ISA model run the same program; pins and registers must match on every cycle.
2. **Protocol checkers:** independent UART, SPI and I2C models decode the pin waveforms; they need no knowledge of the RTL.
3. **Randomized tests:** random programs for the ISA, and random baud rates, SPI modes, addresses and payloads; fixed seeds.
4. **Formal properties:** 2–3 pin-level safety properties in SVA, checked with SymbiYosys: no X after reset, no conflicting drive on bidirectional pins.
5. **Physical checks:** synthesis and place and route on every iteration; area, timing and precheck enter the report.
6. **Post-freeze generality:** PS/2, 1-Wire and one invented protocol, written as firmware only after the RTL is frozen.
7. **Checking the checker:** about 20 hand-injected bugs in a passing design; the harness must catch them.

The harness and the hidden tests are read-only to the AI.

## Experiments and decision rules

All runs use the same model, token budget and iteration cap.


| Run           | Setup                                                               | Answers                        |
| ------------- | ------------------------------------------------------------------- | ------------------------------ |
| E0            | AI gets the competition brief only; it designs and tests on its own | How far plain AI gets          |
| E1            | AI gets my spec and ISA; harness report after every iteration       | What the verifier adds         |
| E2 (optional) | Same pipeline on a second, independently written spec               | Whether the pipeline transfers |


Measured: iterations to acceptance, tokens, bugs caught per verification layer, self-reported versus checked completion, area and timing.


| Observed result                         | Interpretation                                          |
| --------------------------------------- | ------------------------------------------------------- |
| E1 passes every layer; E0 does not      | The verifier is what makes AI output acceptable         |
| E0 does as well as E1                   | The verifier adds little at this scale; report it       |
| E1 does not converge within budget      | Spec too hard for current AI; report where it stalls    |
| A held-out protocol needs an RTL change | The ISA is not general enough; report the failure       |
| Design exceeds 6×4 or misses 50 MHz     | Shrink memory or drop to 25 MHz before adding anything  |
| Harness catches < 90% of injected bugs  | Strengthen the harness before trusting any result above |


## Deliverables and success criteria

One Tiny Tapeout repository, submittable as is. Targets are proposed and can be adjusted.


| Deliverable                                  | Success target                                      |
| -------------------------------------------- | --------------------------------------------------- |
| ISA specification and Python reference model | Frozen before E1; covers every instruction          |
| AI-generated RTL, assembler, firmware, GDS   | Fits 6×4; closes at 50 MHz; precheck passes         |
| UART, SPI, I2C firmware                      | Pass co-simulation and protocol checkers            |
| Post-freeze generality                       | At least 2 of 3 new protocols with no RTL change    |
| Verification harness in `test/`              | Catches ≥ 90% of injected bugs                      |
| Technical write-up                           | E0 vs E1, bugs per layer, iteration data; 2–3 pages |


## Steps

1. Repository from the CMOS5L template, CI green; UART checker tested against known waveforms. (Done.)
2. Write and freeze the ISA specification; build the Python reference model with its own tests.
3. Run E0 and score it.
4. Run E1: the AI implements the ISA; co-simulation and protocol checkers report after every iteration.
5. Add the SPI and I2C checkers, physical checks and the safety properties to the loop.
6. Freeze the RTL; write the three new protocols as firmware only.
7. Build the injected-bug suite and measure the catch rate.
8. Optional E2 on a second spec; write up the results.

## Risks and questions


| Risk                                | Mitigation                                                                |
| ----------------------------------- | ------------------------------------------------------------------------- |
| The AI does not converge            | Cap iterations and tokens; non-convergence is a result                    |
| The reference model itself is wrong | It has its own tests, and the protocol checkers judge independently of it |
| Area overflow found late            | Synthesis on every iteration                                              |
| The AI games the tests              | Read-only harness, hidden tests, post-freeze protocols                    |


Questions for Mark:

1. Is a deliberately conventional engine acceptable when the contribution is the verified AI implementation?
2. Which second specification would make the most convincing test for E2?
3. Does the group have API credits for the experiment runs?

