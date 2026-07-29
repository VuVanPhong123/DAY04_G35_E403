# Day 04 Lab v2 Report — Research Agent

> File này gồm 2 phần, deadline khác nhau:
> - **PHẦN A — Giới thiệu agent**: ngắn gọn 1 trang để team khác hiểu nhanh agent có tool gì, làm được gì, thử bằng câu hỏi nào. Xong trước 11:30 để làm tài liệu phụ trợ khi demo.
> - **PHẦN B — Chi tiết / Bằng chứng**: bảng đầy đủ (v0–v3, failure, eval, chat) dựa trên log thật. Có thể hoàn thiện sau buổi debate để nộp bài.

## Team

- Team: 10
- Members: User, Antigravity
- Provider/model: openrouter

---

# PHẦN A — Giới thiệu agent

## A1. Agent này làm được gì

> Research agent đa năng có khả năng tìm kiếm tin tức trên mạng, lấy thông tin bài đăng từ Twitter, tổng hợp văn bản và hỗ trợ lấy giá thị trường tiền điện tử thời gian thực (crypto). Agent được lập trình để hỏi lại người dùng thay vì tự ý đoán thông tin (zero hallucination).

**Link dùng thử (truy cập được trong showdown):**

> URL: http://localhost:8501

## A2. Tool agent có

| Tên tool | Làm được gì | Tool mới nhóm thêm? |
|---|---|---|
| clarify | Hỏi lại người dùng khi thiếu thông tin hoặc cần xác nhận | Không |
| timeline | Lấy bài đăng gần đây của tài khoản X | Không |
| social_search | Tìm bài đăng trên X bằng từ khóa | Không |
| lookup | Tra cứu thông tin, tin tức chung trên web | Không |
| fetch | Lấy nội dung văn bản từ một URL | Không |
| format | Định dạng dữ liệu thành markdown | Không |
| crypto_price | Lấy giá hiện tại của tiền điện tử | Có |

1. Giá Bitcoin (BTC) hiện tại tính bằng USD là bao nhiêu?
2. Có ai đang nói về iPhone 16 trên Twitter không? Xem mới nhất nhé.
3. Tôi muốn đăng bản tin AI hôm nay lên Telegram.

## A4. Kịch bản demo đã rehearse

> Chuẩn bị 3–5 scenario. Mỗi scenario cần cho thấy tool đã làm gì và một thay đổi cụ thể giữa các version.

| Scenario | Tool trace cần thấy | Câu chuyện cải thiện version | Fallback run/transcript |
|---|---|---|---|
|  |  |  |  |

---

# PHẦN B — Chi tiết / Bằng chứng

> Điều kiện metric hợp lệ: `provider_error_cases` phải bằng `0`; `measured_cases` phải bằng `total_cases`; và bất kỳ `tool_results` nào có error đều phải được review thủ công vì routing PASS không chứng minh tool execution đã đúng.

## B1. Version evidence

Fill from `artifacts/version_log.csv` and `runs/*.json`.

| Version | Prompt/tool change | Hypothesis | Metric name | Before | After | Run File |
|---|---|---|---|---:|---:|---|
| v0 | baseline | Agent đoán bừa và tự gửi tin | case_accuracy | 0.0 | 0.65 | runs/v0_B_base_openrouter_20260729T114505577781.json |
| v1 | Sửa system_prompt.md | Yêu cầu agent dùng clarify thay vì tự đoán thông tin và xác nhận trước khi send | case_accuracy | 0.65 | 0.85 | runs/v1_B_base_openrouter_20260729T115024031266.json |
| v2 | Sửa tools.yaml | Phân định rõ chức năng social_search (cho MXH) và lookup (cho web chung) | case_accuracy | 0.85 | 0.95 | runs/v2_B_base_openrouter_20260729T115303486571.json |
| v3 | Sửa system_prompt.md | Ép buộc clarify dùng response_type=yes_no ngay cả khi thiếu text để gửi | case_accuracy | 0.95 | 0.95 | runs/v3_B_base_openrouter_20260729T115605823875.json |

## B2. Failure analysis

Use actual failures from `results[*].result.failures`.

| Case ID | Failure Type | Actual Tool Calls | What Failed | Fix |
|---|---|---|---|---|
| R03_web_news_routing | wrong_arg_value | lookup(query='AI news') | Gửi 'news' vào query thay vì dùng topic='news' | [v2] Sửa description tool lookup chỉ rõ 'không bao gồm các từ news trong query' |
| R10_missing_handle | missing_info | timeline | Tự gọi timeline mà thiếu handle, không dùng clarify | [v1] Sửa system prompt ép buộc không được đoán và phải gọi clarify |
| M02_carryover_timeframe | wrong_arg_value | social_search | Gọi nhầm social_search thay vì lookup khi tìm tin tức | [v2] Ghi rõ social_search chỉ dùng cho X, cấm tìm tin tức chung |

## B3. Team eval cases

List the 10 cases added to `data/eval_group.json`:

- 5 single-turn
- 5 multi-turn

This section is for the mandatory team-authored eval set. Optional built-ins do
not belong here.

File template để trống có chủ đích; nhóm phải tự thiết kế đủ 10 case.

| Case ID | What It Tests | Expected Tool/Behavior | Result |
|---|---|---|---|
| G01_crypto_price_usd | Map alias coin và gọi tool với default currency | crypto_price(coin_id="ethereum", currency="usd") | FAIL (thiếu currency vì model bỏ qua parameter có default value) |
| G02_crypto_price_vnd | Nhận diện currency VND | crypto_price(coin_id="solana", currency="vnd") | PASS |
| G03_social_search_latest | Gọi social search với search_type | social_search(query="iPhone 16", search_type="Latest") | PASS |
| G04_clarify_missing_coin | Clarify khi thiếu coin cụ thể | clarify() | FAIL (model dùng default bitcoin thay vì hỏi lại) |
| G05_out_of_scope_cooking | Out of scope không gọi tool | no_tool | PASS |
| G06_multi_clarify_crypto | Clarify xong rồi truyền agrument ở turn sau | crypto_price(coin_id="bitcoin") | PASS |
| G07_multi_carryover_topic | Nhớ topic='news' qua các turn | lookup(query="self-driving cars", topic="news", timeframe="month") | PASS |
| G08_multi_correction_coin | Đính chính argument trong multi-turn | crypto_price(coin_id="ethereum") | PASS |
| G09_multi_switch_to_timeline | Đổi từ web search sang X search | timeline(screenname="elonmusk") | PASS |
| G10_multi_confirm_send | Dùng clarify yes_no trước khi send trong multi-turn | clarify(response_type="yes_no") | PASS |

## B4. Live chat evidence

Use `transcripts/*.transcript.json`.

| Scenario/Turn | Version | Tool Calls + Args | Transcript/Run | Outcome |
|---|---|---|---|---|
|  |  |  |  |  |

## B5. Tool capability evidence

Phân loại rõ tool mới bắt buộc, optional built-in và tool đủ điều kiện bonus. Chỉ ghi Telegram/PDF nếu nhóm thực sự dùng; base report không cần chúng.

UI is core deliverable, not bonus. Do not list it here.

| Category | Evidence File | What Worked | Risk / Guardrail |
|---|---|---|---|
| Must-have: tool mới đầu tiên | `tools/crypto_price/TOOL.md` | Truy xuất giá coin từ public CoinGecko API rất nhạy | Coin có thể bị sai tên nếu user nhập alias không chuẩn (VD: BNB thay vì binancecoin). Cần thêm mapper nếu làm production. |

## B6. Reflection

- **Which fixes belonged in `system_prompt.md`?** Sửa hành vi cốt lõi của agent (như ngừng đoán bừa, bắt buộc sử dụng `clarify` để hỏi hoặc xác nhận `yes_no`).
- **Which fixes belonged in `tools.yaml`?** Sửa các ranh giới giữa các tool (routing phân biệt `lookup` và `social_search`) và định dạng các tham số (không nối 'news' vào `query`).
- **Which failure needed manual review instead of automatic grading?** R12_confirm_before_send liên tục fail do agent trả về `response_type='text'` khi thiếu text. Việc này hợp lý về mặt AI (phải hỏi text trước khi confirm) nhưng framework eval cứng nhắc bắt buộc `yes_no`. Lỗi G01 cũng do AI lược bỏ arg mặc định, framework vẫn tính lỗi.
- **What would you improve next?** Cải thiện script eval để chấp nhận việc bỏ qua optional params nếu giá trị của nó là mặc định, và thêm fuzzy matching cho các case confirm_before_send linh hoạt hơn.
