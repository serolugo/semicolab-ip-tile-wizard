// counter.v — simple up-counter example for TileWizard
`timescale 1ns / 1ps

module counter (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [31:0] load_val,
    input  wire        load_en,
    output wire [31:0] count,
    output wire        overflow
);
    reg [31:0] cnt;
    assign count    = cnt;
    assign overflow = (cnt == 32'hFFFFFFFF);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            cnt <= 32'd0;
        else if (load_en)
            cnt <= load_val;
        else
            cnt <= cnt + 1;
    end
endmodule
