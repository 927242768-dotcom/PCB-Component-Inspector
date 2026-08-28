`timescale 1ns/1ps

// Gray8 二值阈值核，支持旁路。阈值模式输出 0/255，保持 AXI4-Stream 边界标记。
module threshold_stream (
    input  wire       clk,
    input  wire       rst_n,
    input  wire [7:0] s_tdata,
    input  wire       s_tvalid,
    output wire       s_tready,
    input  wire       s_tuser,
    input  wire       s_tlast,
    input  wire       enable,
    input  wire [7:0] threshold,
    output reg  [7:0] m_tdata,
    output reg        m_tvalid,
    input  wire       m_tready,
    output reg        m_tuser,
    output reg        m_tlast
);
    assign s_tready = ~m_tvalid | m_tready;

    always @(posedge clk) begin
        if (!rst_n) begin
            m_tdata  <= 8'd0;
            m_tvalid <= 1'b0;
            m_tuser  <= 1'b0;
            m_tlast  <= 1'b0;
        end else if (s_tready) begin
            m_tvalid <= s_tvalid;
            if (s_tvalid) begin
                m_tdata <= enable ? ((s_tdata >= threshold) ? 8'hff : 8'h00) : s_tdata;
                m_tuser <= s_tuser;
                m_tlast <= s_tlast;
            end
        end
    end
endmodule
