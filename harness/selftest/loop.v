// Test fixture for the harness self-test only; not part of the chip.
// Copies one input pin to one output pin so the recorder can be checked
// inside a real simulator.
`default_nettype none
`timescale 1ns / 1ps

module loop (
    input  wire clk,
    input  wire line_in,
    output wire line_out
);
  assign line_out = line_in;

  initial begin
    $dumpfile("loop.fst");
    $dumpvars(0, loop);
  end
endmodule
