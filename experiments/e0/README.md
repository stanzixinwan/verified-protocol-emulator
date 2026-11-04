# E0: plain Claude Code baseline

Claude Code gets only the competition brief and the template. No spec, no
harness, no help during the run.

## Run

1. Create a separate repository from the CMOS5L template (same steps as the
   main repo), named e.g. `e0-baseline`. Do not copy `spec/` or `harness/` in.
2. Clone it and start Claude Code there with the prompt in `prompt.md`.
   Headless, with the full log saved (check flags with `claude --help`):

   ```
   claude -p "$(cat ../verified-protocol-emulator/experiments/e0/prompt.md)" \
     --output-format stream-json --verbose \
     --allowedTools "Read Edit Write Bash WebFetch" \
     > e0_log.jsonl
   ```

3. Do not intervene. If it stops early, record that as the result.
4. Push the final state of `e0-baseline` so CI runs the GDS flow on it.

## Record in results.md

| Item | Value |
| --- | --- |
| Model and Claude Code version | |
| Start, end, wall time | |
| Tokens / cost (from the log) | |
| Self-reported working protocols (from DONE.md) | |
| CI gds / test result | |
| Harness score: UART | (after the harness can load its design) |
| Notes: architecture chosen, fixed blocks or programmable? | |
