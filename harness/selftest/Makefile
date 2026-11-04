# Harness self-test: run with `make` from this directory.
SIM ?= icarus
TOPLEVEL_LANG ?= verilog
VERILOG_SOURCES = $(PWD)/loop.v
TOPLEVEL = loop
COCOTB_TEST_MODULES = test_loop
# Lets the test import the harness package from the repository root.
export PYTHONPATH := $(PWD)/../..:$(PYTHONPATH)

include $(shell cocotb-config --makefiles)/Makefile.sim
