`timescale 1ns/1ps

// 8-bit 灰度流 3x3 Sobel。仅使用两行 BRAM/分布式 RAM + 3 列移位寄存器，
// 每接受一个像素即可产生一个输出像素；前两行/前两列输出 0 作为边界处理。
// 梯度幅值采用 |Gx|+|Gy| 的硬件友好近似，并饱和到 8 bit。
module sobel3x3_stream #(
    parameter IMAGE_WIDTH = 1280
) (
    input  wire       clk,
    input  wire       rst_n,
    input  wire [7:0] s_tdata,
    input  wire       s_tvalid,
    output wire       s_tready,
    input  wire       s_tuser,
    input  wire       s_tlast,
    input  wire       enable,
    output reg  [7:0] m_tdata,
    output reg        m_tvalid,
    input  wire       m_tready,
    output reg        m_tuser,
    output reg        m_tlast
);
    reg [7:0] line1 [0:IMAGE_WIDTH-1];
    reg [7:0] line2 [0:IMAGE_WIDTH-1];

    reg [15:0] x;
    reg [15:0] y;
    reg [7:0] top_a, top_b;
    reg [7:0] mid_a, mid_b;
    reg [7:0] bot_a, bot_b;

    wire fire = s_tvalid && s_tready;
    assign s_tready = ~m_tvalid | m_tready;

    // 当前输入到来前，line2[x]/line1[x] 分别是 y-2/y-1 行当前列像素。
    wire signed [11:0] gx =
          $signed({1'b0, line2[x]}) - $signed({1'b0, top_a})
        + ($signed({1'b0, line1[x]}) <<< 1) - ($signed({1'b0, mid_a}) <<< 1)
        + $signed({1'b0, s_tdata}) - $signed({1'b0, bot_a});

    wire signed [11:0] gy =
          $signed({1'b0, bot_a}) + ($signed({1'b0, bot_b}) <<< 1) + $signed({1'b0, s_tdata})
        - $signed({1'b0, top_a}) - ($signed({1'b0, top_b}) <<< 1) - $signed({1'b0, line2[x]});

    wire [11:0] abs_gx = gx[11] ? (~gx + 1'b1) : gx;
    wire [11:0] abs_gy = gy[11] ? (~gy + 1'b1) : gy;
    wire [12:0] mag = abs_gx + abs_gy;
    wire [7:0] sobel_pixel = (mag > 13'd255) ? 8'hff : mag[7:0];
    wire border = (x < 16'd2) || (y < 16'd2);

    always @(posedge clk) begin
        if (!rst_n) begin
            x <= 0;
            y <= 0;
            top_a <= 0; top_b <= 0;
            mid_a <= 0; mid_b <= 0;
            bot_a <= 0; bot_b <= 0;
            m_tdata <= 0;
            m_tvalid <= 0;
            m_tuser <= 0;
            m_tlast <= 0;
        end else if (s_tready) begin
            m_tvalid <= s_tvalid;
            if (fire) begin
                m_tdata <= enable ? (border ? 8'd0 : sobel_pixel) : s_tdata;
                m_tuser <= s_tuser;
                m_tlast <= s_tlast;

                // 两级行缓存滚动。
                line2[x] <= line1[x];
                line1[x] <= s_tdata;

                // 3 列窗口滚动。
                top_a <= top_b;
                top_b <= line2[x];
                mid_a <= mid_b;
                mid_b <= line1[x];
                bot_a <= bot_b;
                bot_b <= s_tdata;

                if (s_tuser) begin
                    x <= s_tlast ? 0 : 1;
                    y <= s_tlast ? 1 : 0;
                    top_a <= 0; top_b <= 0;
                    mid_a <= 0; mid_b <= 0;
                    bot_a <= 0; bot_b <= 0;
                end else if (s_tlast) begin
                    x <= 0;
                    y <= y + 1'b1;
                    top_a <= 0; top_b <= 0;
                    mid_a <= 0; mid_b <= 0;
                    bot_a <= 0; bot_b <= 0;
                end else begin
                    x <= x + 1'b1;
                end
            end
        end
    end
endmodule
