"""
tb_generator.py — generates tb_tile.v for VeriFlow integration.

Pre-stimulus comments are derived from the port mapping.
"""

from typing import Dict

from tilewizard.core.validator import TILE_PORTS


_TB_HEADER = """\
`timescale 1ns / 1ps

module tb;

parameter CSR_IN_WIDTH  = 16;
parameter CSR_OUT_WIDTH = 16;
parameter REG_WIDTH     = 32;

reg clk;
reg arst_n;
reg  [CSR_IN_WIDTH-1:0]  csr_in;
reg  [REG_WIDTH-1:0]     data_reg_a;
reg  [REG_WIDTH-1:0]     data_reg_b;
wire [REG_WIDTH-1:0]     data_reg_c;
wire [CSR_OUT_WIDTH-1:0] csr_out;
wire                     csr_in_re;
wire                     csr_out_we;

`include "tb_tasks.v"

always #5 clk = ~clk;

/* MODULE_INSTANTIATION */

initial begin
    $dumpfile("waves.vcd");
    $dumpvars(0, tb);
end

initial begin
    clk        = 0;
    arst_n     = 0;
    csr_in     = 0;
    data_reg_a = 0;
    data_reg_b = 0;
    repeat(2) @(posedge clk);
    arst_n = 1;
    repeat(1) @(posedge clk);

    /* USER_TEST */
    // USER TEST STARTS HERE //

"""

_TB_FOOTER = """\
    // USER TEST ENDS HERE //

    $finish;
end

endmodule
"""


def _slice_str(hi, lo) -> str:
    if hi is None:
        return ""
    if hi == lo:
        return f"[{hi}]"
    return f"[{hi}:{lo}]"


def generate_tb(cfg: Dict, parsed_ports: Dict) -> str:
    """Return the tb_tile.v content string."""

    write_lines = []   # stimulus writes (inputs to IP)
    read_lines  = []   # read / display (outputs from IP)
    unmapped    = []

    for ip_port, (tile_port, hi, lo) in parsed_ports.items():
        if tile_port is None:
            unmapped.append(ip_port)
            continue

        width = TILE_PORTS[tile_port]
        sl = _slice_str(hi, lo)

        if tile_port == "data_reg_a":
            write_lines.append(
                f"    write_data_reg_a(32'h00000000); // {ip_port} (IP input)"
            )
        elif tile_port == "data_reg_b":
            write_lines.append(
                f"    write_data_reg_b(32'h00000000); // {ip_port} (IP input)"
            )
        elif tile_port == "csr_in":
            write_lines.append(
                f"    write_csr_in(16'h0000); // {ip_port} → csr_in{sl}"
            )
        elif tile_port == "data_reg_c":
            read_lines.append(
                f'    $display("{ip_port} = %0h", data_reg_c);'
            )
        elif tile_port == "csr_out":
            if sl:
                read_lines.append(
                    f'    $display("{ip_port} = %0b", csr_out{sl});'
                )
            else:
                read_lines.append(
                    f'    $display("{ip_port} = %0h", csr_out);'
                )
        # clk, arst_n, csr_in_re, csr_out_we — handled by reset sequence or assigns

    # Check if data_reg_b was never mapped
    data_reg_b_mapped = any(
        tp == "data_reg_b" for (tp, _, _) in parsed_ports.values() if tp is not None
    )
    if not data_reg_b_mapped:
        write_lines.append(
            "    // write_data_reg_b(32'h00000000); // sin mapeo"
        )

    # Build stimulus block
    stimulus_lines = []

    if write_lines:
        for line in write_lines:
            stimulus_lines.append(line)
        stimulus_lines.append("")

    if write_lines and read_lines:
        stimulus_lines.append("    @(posedge clk);")
        stimulus_lines.append("")

    if read_lines:
        for line in read_lines:
            stimulus_lines.append(line)
        stimulus_lines.append("")

    if unmapped:
        stimulus_lines.append(
            "    // Puertos IP sin mapeo (TW-W01): "
            + ", ".join(unmapped)
        )
        stimulus_lines.append("")

    stimulus_block = "\n".join(stimulus_lines)

    return _TB_HEADER + stimulus_block + "\n" + _TB_FOOTER
