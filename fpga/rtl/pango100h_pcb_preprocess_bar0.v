`timescale 1ns/1ps

// PG2L100H + RK3568 专用 PCB 图像预处理核。
// 直接挂在 PANGO PCIe DMA 示例工程的 BAR0 RAM 位置：
//   0x000~0x0ff : 控制/状态头
//   0x100~      : 灰度输入帧；处理完成后同窗口读回输出
//
// 默认安全尺寸：112x64=7168 bytes；最大保留 7936 bytes，
// 与 RK3568 侧已经验证过的单 BAR resource0 访问方式一致。
module pango100h_pcb_preprocess_bar0 #(
    parameter ADDR_WIDTH = 12,
    parameter HEADER_WORDS = 16,
    parameter MAX_FRAME_WORDS = 496,
    parameter MAX_ROW_WORDS = 64
) (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  i_bar0_wr_en,
    input  wire [ADDR_WIDTH-1:0] i_bar0_wr_addr,
    input  wire [127:0]          i_bar0_wr_data,
    input  wire [15:0]           i_bar0_wr_be,
    input  wire                  i_bar0_rd_clk_en,
    input  wire [ADDR_WIDTH-1:0] i_bar0_rd_addr,
    output reg  [127:0]          o_bar0_rd_data
);

localparam integer FRAME_CAP_BYTES = MAX_FRAME_WORDS * 16;
localparam [3:0] ST_IDLE     = 4'd0;
localparam [3:0] ST_LOAD     = 4'd1;
localparam [3:0] ST_SETTLE_1 = 4'd2;
localparam [3:0] ST_SETTLE_2 = 4'd3;
localparam [3:0] ST_PROCESS  = 4'd4;
localparam [3:0] ST_COMMIT   = 4'd5;
localparam OP_GAUSSIAN = 1'b0;
localparam OP_FINAL    = 1'b1;
localparam SRC_RAW     = 1'b0;
localparam SRC_STAGE_A = 1'b1;

wire start_pulse;
wire clear_done_pulse;
wire continuous_mode;
wire [15:0] frame_width;
wire [15:0] frame_height;
wire [7:0] threshold;
wire [15:0] roi_x;
wire [15:0] roi_y;
wire [15:0] roi_w;
wire [15:0] roi_h;
wire [15:0] preprocess_cfg;
wire [31:0] frame_bytes_cfg;

wire cfg_invert      = preprocess_cfg[0];
wire cfg_passthrough = preprocess_cfg[1];
wire cfg_sobel       = preprocess_cfg[2];
wire cfg_binary      = preprocess_cfg[3];
wire cfg_gaussian    = preprocess_cfg[4];

reg busy_reg;
reg done_reg;
reg error_reg;
reg [31:0] frame_counter_reg;
reg [31:0] active_pixels_reg;
reg [31:0] written_bytes_reg;

reg [3:0] engine_state;
reg operation_select;
reg source_select;
reg [15:0] frame_width_work_reg;
reg [15:0] frame_height_work_reg;
reg [15:0] words_per_row_reg;
reg [15:0] row_index_reg;
reg [ADDR_WIDTH-1:0] row_base_reg;
reg [1:0] load_plane_reg;
reg [15:0] load_column_reg;
reg [15:0] process_column_reg;
reg load_wait_reg;

reg [127:0] raw_frame [0:MAX_FRAME_WORDS-1] /* synthesis syn_ramstyle = "block_ram" */;
reg [127:0] stage_a   [0:MAX_FRAME_WORDS-1] /* synthesis syn_ramstyle = "block_ram" */;
reg [127:0] stage_b   [0:MAX_FRAME_WORDS-1] /* synthesis syn_ramstyle = "block_ram" */;
reg [127:0] line_top    [0:MAX_ROW_WORDS-1];
reg [127:0] line_middle [0:MAX_ROW_WORDS-1];
reg [127:0] line_bottom [0:MAX_ROW_WORDS-1];

reg [127:0] raw_read_data_reg;
reg [127:0] stage_a_read_data_reg;
reg [127:0] stage_b_read_data_reg;
reg [ADDR_WIDTH-1:0] rd_addr_ff;

wire reg_wr_en = i_bar0_wr_en && (i_bar0_wr_addr < HEADER_WORDS);
wire frame_host_wr_en = i_bar0_wr_en &&
                        (i_bar0_wr_addr >= HEADER_WORDS) &&
                        ((i_bar0_wr_addr - HEADER_WORDS) < MAX_FRAME_WORDS);
wire [ADDR_WIDTH-1:0] frame_host_wr_addr = i_bar0_wr_addr - HEADER_WORDS;
wire [31:0] effective_frame_bytes =
    (frame_bytes_cfg != 0) ? frame_bytes_cfg : (frame_width * frame_height);

wire [31:0] status_dword0 = 32'h50434250; // "PCBP"
wire [31:0] status_dword1 = {28'd0, continuous_mode, error_reg, done_reg, busy_reg};
wire [31:0] status_dword2 = {frame_height, frame_width};
wire [31:0] status_dword3 = frame_counter_reg;
wire [31:0] status_dword4 = {8'd0, preprocess_cfg[15:0], threshold};
wire [31:0] status_dword5 = {roi_y, roi_x};
wire [31:0] status_dword6 = {roi_h, roi_w};
wire [31:0] status_dword7 = effective_frame_bytes;
wire [31:0] status_dword8 = active_pixels_reg;
wire [31:0] status_dword9 = FRAME_CAP_BYTES;
wire [31:0] status_dword10 = 32'h02000001; // board pipeline ABI 2.0.1
wire [31:0] status_dword11 = {27'd0, cfg_gaussian, cfg_binary, cfg_sobel, cfg_passthrough, cfg_invert};
wire [127:0] header_word0 = {status_dword3, status_dword2, status_dword1, status_dword0};
wire [127:0] header_word1 = {status_dword7, status_dword6, status_dword5, status_dword4};
wire [127:0] header_word2 = {status_dword11, status_dword10, status_dword9, status_dword8};

pango100h_pcb_register_bank #(
    .ADDR_WIDTH(ADDR_WIDTH)
) u_register_bank (
    .clk(clk),
    .rst_n(rst_n),
    .i_wr_en(reg_wr_en),
    .i_wr_addr(i_bar0_wr_addr),
    .i_wr_data(i_bar0_wr_data),
    .i_wr_byte_en(i_bar0_wr_be),
    .o_start_pulse(start_pulse),
    .o_clear_done_pulse(clear_done_pulse),
    .o_continuous_mode(continuous_mode),
    .o_frame_width(frame_width),
    .o_frame_height(frame_height),
    .o_threshold(threshold),
    .o_roi_x(roi_x),
    .o_roi_y(roi_y),
    .o_roi_w(roi_w),
    .o_roi_h(roi_h),
    .o_preprocess_cfg(preprocess_cfg),
    .o_frame_bytes(frame_bytes_cfg)
);

function [7:0] triplet_byte;
    input [127:0] left_word;
    input [127:0] center_word;
    input [127:0] right_word;
    input integer byte_index;
    integer selected_index;
    begin
        if (byte_index < 0) begin
            selected_index = byte_index + 16;
            triplet_byte = left_word[selected_index * 8 +: 8];
        end else if (byte_index > 15) begin
            selected_index = byte_index - 16;
            triplet_byte = right_word[selected_index * 8 +: 8];
        end else begin
            triplet_byte = center_word[byte_index * 8 +: 8];
        end
    end
endfunction

function [127:0] gaussian_word;
    input [127:0] top_left;
    input [127:0] top_center;
    input [127:0] top_right;
    input [127:0] middle_left;
    input [127:0] middle_center;
    input [127:0] middle_right;
    input [127:0] bottom_left;
    input [127:0] bottom_center;
    input [127:0] bottom_right;
    input [15:0] row_index;
    input [15:0] word_column;
    input [15:0] image_width;
    input [15:0] image_height;
    integer idx;
    integer pixel_x;
    integer weighted_sum;
    reg [7:0] center_pixel;
    begin
        gaussian_word = 128'd0;
        for (idx = 0; idx < 16; idx = idx + 1) begin
            pixel_x = word_column * 16 + idx;
            center_pixel = triplet_byte(middle_left, middle_center, middle_right, idx);
            if ((pixel_x < image_width) && (row_index > 0) &&
                ((row_index + 1) < image_height) && (pixel_x > 0) &&
                ((pixel_x + 1) < image_width)) begin
                weighted_sum =
                    triplet_byte(top_left, top_center, top_right, idx - 1) +
                    (triplet_byte(top_left, top_center, top_right, idx) << 1) +
                    triplet_byte(top_left, top_center, top_right, idx + 1) +
                    (triplet_byte(middle_left, middle_center, middle_right, idx - 1) << 1) +
                    (center_pixel << 2) +
                    (triplet_byte(middle_left, middle_center, middle_right, idx + 1) << 1) +
                    triplet_byte(bottom_left, bottom_center, bottom_right, idx - 1) +
                    (triplet_byte(bottom_left, bottom_center, bottom_right, idx) << 1) +
                    triplet_byte(bottom_left, bottom_center, bottom_right, idx + 1);
                gaussian_word[idx * 8 +: 8] = weighted_sum >> 4;
            end else if (pixel_x < image_width) begin
                gaussian_word[idx * 8 +: 8] = center_pixel;
            end
        end
    end
endfunction

function [127:0] final_word;
    input [127:0] top_left;
    input [127:0] top_center;
    input [127:0] top_right;
    input [127:0] middle_left;
    input [127:0] middle_center;
    input [127:0] middle_right;
    input [127:0] bottom_left;
    input [127:0] bottom_center;
    input [127:0] bottom_right;
    input [15:0] row_index;
    input [15:0] word_column;
    input [15:0] image_width;
    input [15:0] image_height;
    input [7:0] threshold_value;
    input [15:0] roi_x_value;
    input [15:0] roi_y_value;
    input [15:0] roi_w_value;
    input [15:0] roi_h_value;
    input enable_sobel;
    input enable_binary;
    input enable_passthrough;
    input invert_output;
    integer idx;
    integer pixel_x;
    integer gx;
    integer gy;
    integer magnitude;
    reg [7:0] pixel_value;
    reg roi_enabled;
    reg roi_hit;
    begin
        final_word = 128'd0;
        roi_enabled = (roi_w_value != 0) && (roi_h_value != 0);
        for (idx = 0; idx < 16; idx = idx + 1) begin
            pixel_x = word_column * 16 + idx;
            pixel_value = triplet_byte(middle_left, middle_center, middle_right, idx);

            if (!enable_passthrough && enable_sobel &&
                (row_index > 0) && ((row_index + 1) < image_height) &&
                (pixel_x > 0) && ((pixel_x + 1) < image_width)) begin
                gx =
                    -triplet_byte(top_left, top_center, top_right, idx - 1) +
                     triplet_byte(top_left, top_center, top_right, idx + 1) -
                    (triplet_byte(middle_left, middle_center, middle_right, idx - 1) << 1) +
                    (triplet_byte(middle_left, middle_center, middle_right, idx + 1) << 1) -
                     triplet_byte(bottom_left, bottom_center, bottom_right, idx - 1) +
                     triplet_byte(bottom_left, bottom_center, bottom_right, idx + 1);
                gy =
                    -triplet_byte(top_left, top_center, top_right, idx - 1) -
                    (triplet_byte(top_left, top_center, top_right, idx) << 1) -
                     triplet_byte(top_left, top_center, top_right, idx + 1) +
                     triplet_byte(bottom_left, bottom_center, bottom_right, idx - 1) +
                    (triplet_byte(bottom_left, bottom_center, bottom_right, idx) << 1) +
                     triplet_byte(bottom_left, bottom_center, bottom_right, idx + 1);
                if (gx < 0) gx = -gx;
                if (gy < 0) gy = -gy;
                magnitude = gx + gy;
                pixel_value = (magnitude > 255) ? 8'hff : magnitude[7:0];
            end

            if (!enable_passthrough && enable_binary)
                pixel_value = (pixel_value >= threshold_value) ? 8'hff : 8'h00;

            roi_hit = !roi_enabled ||
                ((pixel_x >= roi_x_value) && (pixel_x < (roi_x_value + roi_w_value)) &&
                 (row_index >= roi_y_value) && (row_index < (roi_y_value + roi_h_value)));

            if ((pixel_x < image_width) && roi_hit)
                final_word[idx * 8 +: 8] = invert_output ? ~pixel_value : pixel_value;
        end
    end
endfunction

function [31:0] count_active_word;
    input [127:0] source_word;
    integer idx;
    begin
        count_active_word = 32'd0;
        for (idx = 0; idx < 16; idx = idx + 1)
            if (source_word[idx * 8 +: 8] != 8'h00)
                count_active_word = count_active_word + 1'b1;
    end
endfunction

reg [ADDR_WIDTH-1:0] source_addr_comb;
reg source_valid_comb;
reg [127:0] source_word_comb;
reg [127:0] top_left_comb;
reg [127:0] top_center_comb;
reg [127:0] top_right_comb;
reg [127:0] middle_left_comb;
reg [127:0] middle_center_comb;
reg [127:0] middle_right_comb;
reg [127:0] bottom_left_comb;
reg [127:0] bottom_center_comb;
reg [127:0] bottom_right_comb;
reg [127:0] processed_word_comb;
reg [127:0] processed_word_reg;
reg [127:0] final_word_reg;

wire [ADDR_WIDTH-1:0] engine_read_addr = source_addr_comb;
wire [ADDR_WIDTH-1:0] host_read_addr =
    (i_bar0_rd_addr >= HEADER_WORDS) ? (i_bar0_rd_addr - HEADER_WORDS) : {ADDR_WIDTH{1'b0}};
wire [31:0] final_active_count = count_active_word(final_word_reg);

always @(*) begin
    source_valid_comb = 1'b1;
    source_addr_comb = row_base_reg + load_column_reg[ADDR_WIDTH-1:0];
    case (load_plane_reg)
        2'd0: begin
            if (row_index_reg == 0)
                source_valid_comb = 1'b0;
            else
                source_addr_comb = row_base_reg - words_per_row_reg[ADDR_WIDTH-1:0] +
                                   load_column_reg[ADDR_WIDTH-1:0];
        end
        2'd1: begin
            source_addr_comb = row_base_reg + load_column_reg[ADDR_WIDTH-1:0];
        end
        default: begin
            if ((row_index_reg + 1) >= frame_height_work_reg)
                source_valid_comb = 1'b0;
            else
                source_addr_comb = row_base_reg + words_per_row_reg[ADDR_WIDTH-1:0] +
                                   load_column_reg[ADDR_WIDTH-1:0];
        end
    endcase

    source_word_comb = 128'd0;
    if (source_valid_comb && (source_addr_comb < MAX_FRAME_WORDS)) begin
        if (source_select == SRC_STAGE_A)
            source_word_comb = stage_a_read_data_reg;
        else
            source_word_comb = raw_read_data_reg;
    end
end

always @(posedge clk) begin
    if (engine_read_addr < MAX_FRAME_WORDS) begin
        raw_read_data_reg <= raw_frame[engine_read_addr];
        stage_a_read_data_reg <= stage_a[engine_read_addr];
    end else begin
        raw_read_data_reg <= 128'd0;
        stage_a_read_data_reg <= 128'd0;
    end

    if (i_bar0_rd_clk_en) begin
        rd_addr_ff <= i_bar0_rd_addr;
        if (host_read_addr < MAX_FRAME_WORDS)
            stage_b_read_data_reg <= stage_b[host_read_addr];
        else
            stage_b_read_data_reg <= 128'd0;
    end
end

always @(*) begin
    top_left_comb = 128'd0;
    top_center_comb = line_top[process_column_reg];
    top_right_comb = 128'd0;
    middle_left_comb = 128'd0;
    middle_center_comb = line_middle[process_column_reg];
    middle_right_comb = 128'd0;
    bottom_left_comb = 128'd0;
    bottom_center_comb = line_bottom[process_column_reg];
    bottom_right_comb = 128'd0;

    if (process_column_reg > 0) begin
        top_left_comb = line_top[process_column_reg - 1'b1];
        middle_left_comb = line_middle[process_column_reg - 1'b1];
        bottom_left_comb = line_bottom[process_column_reg - 1'b1];
    end
    if ((process_column_reg + 1'b1) < words_per_row_reg) begin
        top_right_comb = line_top[process_column_reg + 1'b1];
        middle_right_comb = line_middle[process_column_reg + 1'b1];
        bottom_right_comb = line_bottom[process_column_reg + 1'b1];
    end

    if (operation_select == OP_GAUSSIAN) begin
        processed_word_comb = gaussian_word(
            top_left_comb, top_center_comb, top_right_comb,
            middle_left_comb, middle_center_comb, middle_right_comb,
            bottom_left_comb, bottom_center_comb, bottom_right_comb,
            row_index_reg, process_column_reg,
            frame_width_work_reg, frame_height_work_reg
        );
    end else begin
        processed_word_comb = final_word(
            top_left_comb, top_center_comb, top_right_comb,
            middle_left_comb, middle_center_comb, middle_right_comb,
            bottom_left_comb, bottom_center_comb, bottom_right_comb,
            row_index_reg, process_column_reg,
            frame_width_work_reg, frame_height_work_reg,
            threshold, roi_x, roi_y, roi_w, roi_h,
            cfg_sobel, cfg_binary, cfg_passthrough, cfg_invert
        );
    end
end

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        busy_reg <= 1'b0;
        done_reg <= 1'b0;
        error_reg <= 1'b0;
        frame_counter_reg <= 32'd0;
        active_pixels_reg <= 32'd0;
        written_bytes_reg <= 32'd0;
        engine_state <= ST_IDLE;
        operation_select <= OP_FINAL;
        source_select <= SRC_RAW;
        frame_width_work_reg <= 16'd0;
        frame_height_work_reg <= 16'd0;
        words_per_row_reg <= 16'd0;
        row_index_reg <= 16'd0;
        row_base_reg <= {ADDR_WIDTH{1'b0}};
        load_plane_reg <= 2'd0;
        load_column_reg <= 16'd0;
        process_column_reg <= 16'd0;
        load_wait_reg <= 1'b0;
        processed_word_reg <= 128'd0;
        final_word_reg <= 128'd0;
    end else begin
        if (clear_done_pulse) begin
            busy_reg <= 1'b0;
            done_reg <= 1'b0;
            error_reg <= 1'b0;
            active_pixels_reg <= 32'd0;
            written_bytes_reg <= 32'd0;
            engine_state <= ST_IDLE;
        end

        if (frame_host_wr_en && (engine_state == ST_IDLE) &&
            (i_bar0_wr_be == 16'hffff)) begin
            raw_frame[frame_host_wr_addr] <= i_bar0_wr_data;
            if (frame_host_wr_addr == 0) begin
                written_bytes_reg <= 32'd16;
                done_reg <= 1'b0;
                error_reg <= 1'b0;
            end else begin
                written_bytes_reg <= written_bytes_reg + 32'd16;
            end
        end

        if (start_pulse && (engine_state == ST_IDLE)) begin
            if ((effective_frame_bytes == 0) ||
                (effective_frame_bytes > FRAME_CAP_BYTES) ||
                (frame_width == 0) || (frame_height == 0) ||
                (frame_width[3:0] != 0) ||
                ((frame_width >> 4) > MAX_ROW_WORDS) ||
                (written_bytes_reg < effective_frame_bytes)) begin
                busy_reg <= 1'b0;
                done_reg <= 1'b0;
                error_reg <= 1'b1;
            end else begin
                busy_reg <= 1'b1;
                done_reg <= 1'b0;
                error_reg <= 1'b0;
                active_pixels_reg <= 32'd0;
                frame_width_work_reg <= frame_width;
                frame_height_work_reg <= frame_height;
                words_per_row_reg <= frame_width >> 4;
                row_index_reg <= 16'd0;
                row_base_reg <= {ADDR_WIDTH{1'b0}};
                load_plane_reg <= 2'd0;
                load_column_reg <= 16'd0;
                process_column_reg <= 16'd0;
                load_wait_reg <= 1'b0;
                if (cfg_gaussian && !cfg_passthrough) begin
                    operation_select <= OP_GAUSSIAN;
                    source_select <= SRC_RAW;
                end else begin
                    operation_select <= OP_FINAL;
                    source_select <= SRC_RAW;
                end
                engine_state <= ST_LOAD;
            end
        end else begin
            case (engine_state)
                ST_LOAD: begin
                    if (!load_wait_reg) begin
                        load_wait_reg <= 1'b1;
                    end else begin
                        load_wait_reg <= 1'b0;
                        case (load_plane_reg)
                            2'd0: line_top[load_column_reg] <= source_word_comb;
                            2'd1: line_middle[load_column_reg] <= source_word_comb;
                            default: line_bottom[load_column_reg] <= source_word_comb;
                        endcase

                        if ((load_column_reg + 1'b1) >= words_per_row_reg) begin
                            load_column_reg <= 16'd0;
                            if (load_plane_reg == 2'd2) begin
                                load_plane_reg <= 2'd0;
                                process_column_reg <= 16'd0;
                                engine_state <= ST_SETTLE_1;
                            end else begin
                                load_plane_reg <= load_plane_reg + 1'b1;
                            end
                        end else begin
                            load_column_reg <= load_column_reg + 1'b1;
                        end
                    end
                end

                ST_SETTLE_1: engine_state <= ST_SETTLE_2;
                ST_SETTLE_2: engine_state <= ST_PROCESS;

                ST_PROCESS: begin
                    processed_word_reg <= processed_word_comb;
                    final_word_reg <= processed_word_comb;
                    engine_state <= ST_COMMIT;
                end

                ST_COMMIT: begin
                    if (operation_select == OP_GAUSSIAN) begin
                        stage_a[row_base_reg + process_column_reg[ADDR_WIDTH-1:0]] <= processed_word_reg;
                    end else begin
                        stage_b[row_base_reg + process_column_reg[ADDR_WIDTH-1:0]] <= final_word_reg;
                        active_pixels_reg <= active_pixels_reg + final_active_count;
                    end

                    if ((process_column_reg + 1'b1) >= words_per_row_reg) begin
                        process_column_reg <= 16'd0;
                        if ((row_index_reg + 1'b1) >= frame_height_work_reg) begin
                            if (operation_select == OP_GAUSSIAN) begin
                                operation_select <= OP_FINAL;
                                source_select <= SRC_STAGE_A;
                                row_index_reg <= 16'd0;
                                row_base_reg <= {ADDR_WIDTH{1'b0}};
                                load_plane_reg <= 2'd0;
                                load_column_reg <= 16'd0;
                                load_wait_reg <= 1'b0;
                                engine_state <= ST_LOAD;
                            end else begin
                                busy_reg <= 1'b0;
                                done_reg <= 1'b1;
                                error_reg <= 1'b0;
                                frame_counter_reg <= frame_counter_reg + 1'b1;
                                engine_state <= ST_IDLE;
                            end
                        end else begin
                            row_index_reg <= row_index_reg + 1'b1;
                            row_base_reg <= row_base_reg + words_per_row_reg[ADDR_WIDTH-1:0];
                            load_plane_reg <= 2'd0;
                            load_column_reg <= 16'd0;
                            load_wait_reg <= 1'b0;
                            engine_state <= ST_LOAD;
                        end
                    end else begin
                        process_column_reg <= process_column_reg + 1'b1;
                        engine_state <= ST_SETTLE_1;
                    end
                end

                default: begin end
            endcase
        end
    end
end

always @(*) begin
    case (rd_addr_ff)
        12'd0: o_bar0_rd_data = header_word0;
        12'd1: o_bar0_rd_data = header_word1;
        12'd2: o_bar0_rd_data = header_word2;
        default: begin
            if ((rd_addr_ff >= HEADER_WORDS) &&
                ((rd_addr_ff - HEADER_WORDS) < MAX_FRAME_WORDS))
                o_bar0_rd_data = stage_b_read_data_reg;
            else
                o_bar0_rd_data = 128'd0;
        end
    endcase
end

endmodule
