`timescale 1ns/1ps

// RGB888 -> Gray8，1 pixel/clock，采用整数近似：Y=(77R+150G+29B)>>8。
module rgb2gray #(
    parameter DATA_W = 24
) (
    input  wire             clk,
    input  wire             rst_n,
    input  wire [DATA_W-1:0] s_tdata,
    input  wire             s_tvalid,
    output wire             s_tready,
    input  wire             s_tuser,
    input  wire             s_tlast,
    output reg  [7:0]       m_tdata,
    output reg              m_tvalid,
    input  wire             m_tready,
    output reg              m_tuser,
    output reg              m_tlast
);
    wire fire = s_tvalid && s_tready;
    wire [7:0] r = s_tdata[23:16];
    wire [7:0] g = s_tdata[15:8];
    wire [7:0] b = s_tdata[7:0];
    wire [15:0] gray_sum = r * 8'd77 + g * 8'd150 + b * 8'd29;

    assign s_tready = ~m_tvalid | m_tready;

    always @(posedge clk) begin
        if (!rst_n) begin
            m_tdata  <= 8'd0;
            m_tvalid <= 1'b0;
            m_tuser  <= 1'b0;
            m_tlast  <= 1'b0;
        end else if (s_tready) begin
            m_tvalid <= s_tvalid;
            if (fire) begin
                m_tdata <= gray_sum[15:8];
                m_tuser <= s_tuser;
                m_tlast <= s_tlast;
            end
        end
    end
endmodule
