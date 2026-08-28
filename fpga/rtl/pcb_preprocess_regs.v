`timescale 1ns/1ps

// 最小 AXI4-Lite 控制寄存器组。
// 0x00 CONTROL   bit0=sobel_enable, bit1=threshold_enable
// 0x04 THRESHOLD [7:0]
// 0x08 WIDTH     RO
// 0x0C VERSION   RO = 0x0002_0000
module pcb_preprocess_regs #(
    parameter ADDR_W = 6,
    parameter IMAGE_WIDTH = 1280
) (
    input  wire              aclk,
    input  wire              aresetn,
    input  wire [ADDR_W-1:0] s_axi_awaddr,
    input  wire              s_axi_awvalid,
    output reg               s_axi_awready,
    input  wire [31:0]       s_axi_wdata,
    input  wire [3:0]        s_axi_wstrb,
    input  wire              s_axi_wvalid,
    output reg               s_axi_wready,
    output reg  [1:0]        s_axi_bresp,
    output reg               s_axi_bvalid,
    input  wire              s_axi_bready,
    input  wire [ADDR_W-1:0] s_axi_araddr,
    input  wire              s_axi_arvalid,
    output reg               s_axi_arready,
    output reg  [31:0]       s_axi_rdata,
    output reg  [1:0]        s_axi_rresp,
    output reg               s_axi_rvalid,
    input  wire              s_axi_rready,
    output reg               cfg_sobel_enable,
    output reg               cfg_threshold_enable,
    output reg  [7:0]        cfg_threshold
);
    reg [ADDR_W-1:0] awaddr_hold;
    reg [31:0] wdata_hold;
    reg [3:0]  wstrb_hold;
    reg aw_pending, w_pending;
    integer i;

    always @(posedge aclk) begin
        if (!aresetn) begin
            s_axi_awready <= 1'b0;
            s_axi_wready <= 1'b0;
            s_axi_bresp <= 2'b00;
            s_axi_bvalid <= 1'b0;
            s_axi_arready <= 1'b0;
            s_axi_rdata <= 32'd0;
            s_axi_rresp <= 2'b00;
            s_axi_rvalid <= 1'b0;
            cfg_sobel_enable <= 1'b1;
            cfg_threshold_enable <= 1'b0;
            cfg_threshold <= 8'd96;
            aw_pending <= 1'b0;
            w_pending <= 1'b0;
            awaddr_hold <= 0;
            wdata_hold <= 0;
            wstrb_hold <= 0;
        end else begin
            s_axi_awready <= 1'b0;
            s_axi_wready <= 1'b0;
            s_axi_arready <= 1'b0;

            if (s_axi_awvalid && !aw_pending && !s_axi_bvalid) begin
                s_axi_awready <= 1'b1;
                awaddr_hold <= s_axi_awaddr;
                aw_pending <= 1'b1;
            end
            if (s_axi_wvalid && !w_pending && !s_axi_bvalid) begin
                s_axi_wready <= 1'b1;
                wdata_hold <= s_axi_wdata;
                wstrb_hold <= s_axi_wstrb;
                w_pending <= 1'b1;
            end

            if (aw_pending && w_pending && !s_axi_bvalid) begin
                case (awaddr_hold[5:2])
                    4'h0: begin
                        if (wstrb_hold[0]) begin
                            cfg_sobel_enable <= wdata_hold[0];
                            cfg_threshold_enable <= wdata_hold[1];
                        end
                    end
                    4'h1: begin
                        if (wstrb_hold[0]) cfg_threshold <= wdata_hold[7:0];
                    end
                    default: begin end
                endcase
                aw_pending <= 1'b0;
                w_pending <= 1'b0;
                s_axi_bresp <= 2'b00;
                s_axi_bvalid <= 1'b1;
            end else if (s_axi_bvalid && s_axi_bready) begin
                s_axi_bvalid <= 1'b0;
            end

            if (s_axi_arvalid && !s_axi_rvalid) begin
                s_axi_arready <= 1'b1;
                case (s_axi_araddr[5:2])
                    4'h0: s_axi_rdata <= {30'd0, cfg_threshold_enable, cfg_sobel_enable};
                    4'h1: s_axi_rdata <= {24'd0, cfg_threshold};
                    4'h2: s_axi_rdata <= IMAGE_WIDTH;
                    4'h3: s_axi_rdata <= 32'h0002_0000;
                    default: s_axi_rdata <= 32'd0;
                endcase
                s_axi_rresp <= 2'b00;
                s_axi_rvalid <= 1'b1;
            end else if (s_axi_rvalid && s_axi_rready) begin
                s_axi_rvalid <= 1'b0;
            end
        end
    end
endmodule
