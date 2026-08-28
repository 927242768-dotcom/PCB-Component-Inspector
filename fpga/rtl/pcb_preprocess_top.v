`timescale 1ns/1ps

// PCB 实时预处理核：RGB888 -> Gray8 -> Sobel -> Threshold。
// AXI4-Stream 数据面；控制面由外部寄存器（见 pcb_preprocess_regs.v）提供。
module pcb_preprocess_top #(
    parameter IMAGE_WIDTH = 1280
) (
    input  wire        clk,
    input  wire        rst_n,

    input  wire [23:0] s_axis_tdata,
    input  wire        s_axis_tvalid,
    output wire        s_axis_tready,
    input  wire        s_axis_tuser,
    input  wire        s_axis_tlast,

    output wire [7:0]  m_axis_tdata,
    output wire        m_axis_tvalid,
    input  wire        m_axis_tready,
    output wire        m_axis_tuser,
    output wire        m_axis_tlast,

    input  wire        cfg_sobel_enable,
    input  wire        cfg_threshold_enable,
    input  wire [7:0]  cfg_threshold
);
    wire [7:0] gray_data;
    wire gray_valid, gray_ready, gray_user, gray_last;
    wire [7:0] sobel_data;
    wire sobel_valid, sobel_ready, sobel_user, sobel_last;

    rgb2gray u_rgb2gray (
        .clk(clk), .rst_n(rst_n),
        .s_tdata(s_axis_tdata), .s_tvalid(s_axis_tvalid), .s_tready(s_axis_tready),
        .s_tuser(s_axis_tuser), .s_tlast(s_axis_tlast),
        .m_tdata(gray_data), .m_tvalid(gray_valid), .m_tready(gray_ready),
        .m_tuser(gray_user), .m_tlast(gray_last)
    );

    sobel3x3_stream #(.IMAGE_WIDTH(IMAGE_WIDTH)) u_sobel (
        .clk(clk), .rst_n(rst_n),
        .s_tdata(gray_data), .s_tvalid(gray_valid), .s_tready(gray_ready),
        .s_tuser(gray_user), .s_tlast(gray_last), .enable(cfg_sobel_enable),
        .m_tdata(sobel_data), .m_tvalid(sobel_valid), .m_tready(sobel_ready),
        .m_tuser(sobel_user), .m_tlast(sobel_last)
    );

    threshold_stream u_threshold (
        .clk(clk), .rst_n(rst_n),
        .s_tdata(sobel_data), .s_tvalid(sobel_valid), .s_tready(sobel_ready),
        .s_tuser(sobel_user), .s_tlast(sobel_last),
        .enable(cfg_threshold_enable), .threshold(cfg_threshold),
        .m_tdata(m_axis_tdata), .m_tvalid(m_axis_tvalid), .m_tready(m_axis_tready),
        .m_tuser(m_axis_tuser), .m_tlast(m_axis_tlast)
    );
endmodule
