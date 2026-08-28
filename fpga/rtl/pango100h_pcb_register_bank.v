`timescale 1ns/1ps

// PG2L100H PCIe BAR0 控制寄存器。
// BAR0 数据通路宽度为 128 bit，因此这里的地址是 16-byte word 地址：
// 0x0~0x7 对应 ARM 侧字节偏移 0x00~0x70。
module pango100h_pcb_register_bank #(
    parameter ADDR_WIDTH = 12
) (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  i_wr_en,
    input  wire [ADDR_WIDTH-1:0] i_wr_addr,
    input  wire [127:0]          i_wr_data,
    input  wire [15:0]           i_wr_byte_en,

    output reg                   o_start_pulse,
    output reg                   o_clear_done_pulse,
    output reg                   o_continuous_mode,
    output reg  [15:0]           o_frame_width,
    output reg  [15:0]           o_frame_height,
    output reg  [7:0]            o_threshold,
    output reg  [15:0]           o_roi_x,
    output reg  [15:0]           o_roi_y,
    output reg  [15:0]           o_roi_w,
    output reg  [15:0]           o_roi_h,
    output reg  [15:0]           o_preprocess_cfg,
    output reg  [31:0]           o_frame_bytes
);

localparam REG_CONTROL     = 12'h000;
localparam REG_WIDTH       = 12'h001;
localparam REG_HEIGHT      = 12'h002;
localparam REG_THRESHOLD   = 12'h003;
localparam REG_ROI_XY      = 12'h004;
localparam REG_ROI_WH      = 12'h005;
localparam REG_PREPROC_CFG = 12'h006;
localparam REG_FRAME_BYTES = 12'h007;

wire lower_dword_write = i_wr_en && (|i_wr_byte_en[3:0]);
wire [31:0] wr_dword = i_wr_data[31:0];

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        o_start_pulse      <= 1'b0;
        o_clear_done_pulse <= 1'b0;
        o_continuous_mode  <= 1'b0;
        o_frame_width      <= 16'd112;
        o_frame_height     <= 16'd64;
        o_threshold        <= 8'd96;
        o_roi_x            <= 16'd0;
        o_roi_y            <= 16'd0;
        o_roi_w            <= 16'd0;
        o_roi_h            <= 16'd0;
        // bit4 Gaussian, bit3 binary, bit2 Sobel, bit1 passthrough, bit0 invert
        o_preprocess_cfg   <= 16'h001c;
        o_frame_bytes      <= 32'd7168;
    end else begin
        o_start_pulse      <= 1'b0;
        o_clear_done_pulse <= 1'b0;

        if (lower_dword_write) begin
            case (i_wr_addr)
                REG_CONTROL: begin
                    o_start_pulse      <= wr_dword[0];
                    o_continuous_mode  <= wr_dword[1];
                    o_clear_done_pulse <= wr_dword[2];
                end
                REG_WIDTH:       o_frame_width <= wr_dword[15:0];
                REG_HEIGHT:      o_frame_height <= wr_dword[15:0];
                REG_THRESHOLD:   o_threshold <= wr_dword[7:0];
                REG_ROI_XY: begin
                    o_roi_x <= wr_dword[15:0];
                    o_roi_y <= wr_dword[31:16];
                end
                REG_ROI_WH: begin
                    o_roi_w <= wr_dword[15:0];
                    o_roi_h <= wr_dword[31:16];
                end
                REG_PREPROC_CFG: o_preprocess_cfg <= wr_dword[15:0];
                REG_FRAME_BYTES: o_frame_bytes <= wr_dword;
                default: begin end
            endcase
        end
    end
end

endmodule
