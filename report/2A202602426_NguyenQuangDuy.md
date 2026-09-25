# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Nguyễn Quang Duy |
| MSSV               | 2A202602426 |
| Khóa/Lớp         | K4 – L3 |
| Tên nhóm         | CT2D |
| Vai trò chính    | Observability & Reporting |
| Repository         | https://github.com/TuTune04/K4-L3A-Day10-CT2D |
| Ngày hoàn thành | 2026-09-25 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Quality Gate | `src/observability/quality.py` – `run_data_quality_checks` | DataFrame (sạch/corrupted/repaired) | `data/quality/<name>_quality_report.json`, `data/quality/gx/<name>_suite.json` | Hoàn thành |
| Freshness SLA | `src/observability/quality.py` – `build_freshness_report` | DataFrame có `age_days`, `published` | `data/quality/freshness_report*.json` | Hoàn thành |
| Reporting | `src/observability/reporting.py` – `generate_phase1_report`, `generate_corruption_report` | Metrics, quality, freshness, corruption log, answers | `data/reports/phase1_report.md`, `data/reports/corruption_report.md` | Hoàn thành |
| Bonus B1 – Dashboard + test | `src/observability/dashboard.py`, `script/build_dashboard.py`, `tests/test_observability.py` (10 test) | Artifact trong `data/` | `data/reports/dashboard.html` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Cung cấp kết quả Quality Gate + Freshness dạng dict có `success` để self-heal dùng làm tín hiệu `Healthy=True/False` | Tú (`pipelines/self_heal.py`) | Self-heal tự kích hoạt khi dữ liệu corrupted fail 4/8 expectation |
| Thống nhất danh sách cột bắt buộc của DataFrame sạch với phần cleaning để expectation không kiểm tra nhầm cột | Đức (`ingestion/cleaning.py`) | Baseline pass 8/8 ngay khi ghép |
| Đọc `*_answers.json` để liệt kê các câu bị giảm điểm trong báo cáo so sánh | Cường (evaluation) | `corruption_report.md` có breakdown theo question type |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| 8 expectation GX 1.x (API `get_context(mode="ephemeral")`, `data_sources.add_pandas`) | `src/observability/quality.py` | `baseline_quality_report.json` (pass), `corrupted_quality_report.json` (fail 4) | Lệnh kiểm tra bước 4 trong Guide |
| Freshness SLA: stale khi `age_days > 180`, fresh khi stale ratio ≤ 0.25 | `src/observability/quality.py` | `freshness_report*.json` | `is_fresh` của baseline/corrupted/repaired |
| Báo cáo 3 trạng thái, breakdown theo question type, danh sách câu bị giảm điểm | `src/observability/reporting.py` | `corruption_report.md` | `python script/run_corruption_flow.py` |

Nêu một output cụ thể mà phần việc của bạn tạo ra hoặc giúp xác minh:

`data/quality/corrupted_quality_report.json` ghi `success: false` với đúng 4 expectation thất bại: `unique[paper_id]` (do duplicate rows), `lengths[title]` (do truncate title), `lengths[summary]` (do blank summary) và `between[age_days]` (do stale date). Cùng lúc, freshness report của tập corrupted cho stale ratio 0.4545, vượt ngưỡng 0.25 nên `is_fresh = false`. Đây là tín hiệu giúp nhóm "nhìn thấy" lỗi dữ liệu trong khi agent vẫn trả lời bình thường. Dashboard `data/reports/dashboard.html` hiển thị các tín hiệu này cạnh metric RAG để so sánh 3 trạng thái trong một màn hình.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Khi dữ liệu hỏng, RAG không báo lỗi mà chỉ trả lời sai. Phần của tôi là tạo "trạm kiểm dịch" để phát hiện dữ liệu xấu trước khi nó vào ChromaDB, theo dõi độ tươi của cả tập dữ liệu, và biến các con số rời rạc (metric, kết quả kiểm định, log corruption) thành báo cáo mà người đọc hiểu được ngay chuyện gì đã xảy ra.

### Cách triển khai

- **Quality Gate:** dùng đúng API GX 1.x: `gx.get_context(mode="ephemeral")` → `context.data_sources.add_pandas(...)` → `add_dataframe_asset` → `add_batch_definition_whole_dataframe` → `get_batch(batch_parameters={"dataframe": df})`. Gồm 8 expectation: 4 expectation bắt buộc của Guide (row count 5–5000, not null cho `paper_id`/`title`/`text_for_embedding`, unique `paper_id`, độ dài summary ≥ 30) và các expectation bổ sung về độ dài title và khoảng `age_days`. Kết quả chuẩn hóa thành dict `{success, statistics, failed_expectations, results}`, đồng thời xuất suite ra `data/quality/gx/` để truy vết.
- **Freshness:** đếm tỉ lệ bản ghi có `age_days > 180`; tỉ lệ ≤ 0.25 thì `is_fresh = True`.
- **Reporting:** hai hàm sinh Markdown. Báo cáo Phase 1 tóm tắt baseline; báo cáo corruption đặt 3 trạng thái cạnh nhau, tách theo question type và liệt kê các câu bị giảm điểm.
- **Dashboard (B1):** sinh một file HTML tĩnh từ artifact trong `data/`, có cảnh báo drift khi metric lệch baseline. Màu biểu đồ đã được kiểm tra với người mù màu, và có bảng số liệu đi kèm để không phụ thuộc vào màu.

### Input, output và contract

| Thành phần                   | Mô tả |
| ------------------------------ | ----- |
| Input                          | DataFrame có `paper_id, title, summary, text_for_embedding, age_days, published`; dict metrics/quality/freshness |
| Output                         | Dict kết quả `{success, statistics, failed_expectations, results}`; payload freshness; 2 file Markdown |
| Module phụ thuộc             | `great_expectations` 1.x, `core/utils.py` |
| Module sử dụng output        | `pipelines/phase1.py` (gate), `pipelines/self_heal.py` (phát hiện lỗi để kích hoạt repair), `pipelines/corruption_flow.py` |
| Điều kiện lỗi cần xử lý | Cột list không hash được khi kiểm tra unique (chỉ đưa cột scalar vào GX); DataFrame rỗng; metric thiếu |

### Cách xác minh

```bash
pytest tests/test_observability.py
python script/build_dashboard.py
python -c "from core.config import load_settings; from observability.quality import run_data_quality_checks; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); res=run_data_quality_checks(df, s, 'test'); print(f'Quality check status = {res[\"success\"]}')"
```

- **Kết quả mong đợi:** `Quality check status = True` trên dữ liệu sạch; fail trên dữ liệu corrupted.
- **Kết quả thực tế:** `tests/test_observability.py` 10 passed; dashboard sinh ra `data/reports/dashboard.html`; Baseline 8/8 pass; corrupted fail 4 (`unique[paper_id]`, `lengths[title]`, `lengths[summary]`, `between[age_days]`); freshness 0.0417 → 0.4545 → 0.0417.
- **Artifact/log:** `data/quality/`, `data/reports/corruption_report.md`, `data/reports/dashboard.html`

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** GX 1.x cho phép tạo context kiểu lưu file (tạo thư mục `gx/` với config, checkpoint, data docs) hoặc kiểu ephemeral chạy trên RAM. Quality Gate được gọi nhiều lần trong một lần chạy (baseline, corrupted, repaired, và trong self-heal).
- **Các phương án đã cân nhắc:**
  1. File context: GX tự quản lý suite, checkpoint và data docs HTML.
  2. Ephemeral context, tự xuất kết quả và suite ra JSON.
- **Phương án đã chọn:** Ephemeral context (`mode="ephemeral"`). Mỗi lần kiểm định tự xuất `<name>_quality_report.json` và `<name>_suite.json`.
- **Lý do:** Ephemeral không để lại trạng thái giữa các lần chạy, nên kết quả chỉ phụ thuộc vào DataFrame đầu vào. Điều này quan trọng vì repair phải idempotent và test phải chạy độc lập. Cách này cũng không sinh thư mục rác vào repo và chạy nhanh hơn. Việc tự xuất JSON vẫn giữ được khả năng truy vết mà file context mang lại.
- **Bằng chứng quyết định phù hợp:** Chạy Quality Gate nhiều lần trên cùng dữ liệu cho cùng kết quả (baseline và repaired đều 8/8); 10 test trong `tests/test_observability.py` chạy độc lập, không phụ thuộc thứ tự; `data/quality/gx/` có suite của từng trạng thái để đối chiếu.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Bản đầu của báo cáo nhóm ghi 2 câu multi_hop (eval_005, eval_010) giảm điểm do **truncate title** làm hỏng tra cứu chính xác bài thứ 2. Khi đối chiếu lại thì nhận định này sai.
- **Lệnh hoặc bước tái hiện:** So `paper_ids` của từng loại lỗi trong `data/results/corruption_log.json` với `ground_truth_doc_ids` trong `data/eval/test_set.json`.
- **Nguyên nhân gốc:** Nhận định được suy ra từ cơ chế ("title bị cắt thì lookup hỏng") thay vì truy từ log. Thực tế `truncate_title` không trúng bài nào trong test set. Bài thứ 2 của eval_005 (`…1804`) và của eval_010 (`…1812`) nằm trong `drop_latest_records`.
- **Cách xử lý:** Sửa báo cáo nhóm: 4/10 câu giảm điểm do drop latest records, 1 câu do stale date. Ghi rõ inject noise và truncate title không làm metric thay đổi, vì không trúng bài nào có câu hỏi summary/title. Bảng "Questions that regressed" trong `corruption_report.md` được dùng làm điểm xuất phát để truy từng câu về log.
- **Cách xác minh sau khi sửa:** Ghép `paper_ids` trong log với test set ra đúng: drop_latest → eval_001, eval_002, eval_005, eval_010; stale_date → eval_008. Khớp 5 câu bị giảm F1 trong `corrupted_answers.json`.
- **Điều học được:** Mọi kết luận nhân quả trong báo cáo phải truy được về artifact (log + answers), không suy luận từ cơ chế. Việc đối chiếu này còn phát hiện thêm một giới hạn: test set 10 câu không phủ hết các loại lỗi, nên Quality Gate vẫn cần thiết.

## 7. Hiểu biết về luồng end-to-end

1. Dữ liệu đi từ Crossref đến vector index như thế nào?
2. Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?
3. Quality checks khác freshness monitoring ở điểm nào trong bài lab?
4. Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?
5. Repair được xem là thành công dựa trên artifact và metric nào?

**Câu trả lời:**

1. Dữ liệu được lấy từ Crossref API (hoặc snapshot khi lỗi mạng) và lưu nguyên bản ở `data/raw/`. Sau đó cleaning chuẩn hóa thành DataFrame, thêm `age_days` và `text_for_embedding`. DataFrame phải qua trạm của tôi, gồm Quality Gate và Freshness. Chỉ khi pass, dữ liệu mới được nhúng bằng MiniLM và nạp vào ChromaDB. Nếu fail, Phase 1 dừng trước bước index.
2. Mỗi câu hỏi mang theo đáp án chuẩn và DOI của bài chứa đáp án. Hit rate kiểm tra DOI đó có nằm trong các tài liệu retrieval trả về không. Token F1 và LLM Judge so câu trả lời với đáp án chuẩn. Nhờ có DOI, có thể tách lỗi "không tìm được bài" khỏi lỗi "tìm đúng bài nhưng trả lời sai".
3. Quality checks trả lời câu hỏi "từng bản ghi có hợp lệ không": trùng khóa, thiếu trường, quá ngắn. Freshness trả lời câu hỏi "cả kho dữ liệu còn cập nhật không": tỉ lệ bài cũ hơn 180 ngày. Hai tín hiệu bổ sung cho nhau. Ví dụ, drop latest records không làm bản ghi nào sai định dạng nhưng làm kho bị cũ đi, và chỉ freshness phát hiện được.
4. Test set cố định giống một thước đo. Nếu thước đo thay đổi giữa các lần đo thì không thể nói điểm giảm là do dữ liệu. Giữ nguyên test set thì chênh lệch metric phản ánh đúng tác động của corruption và repair.
5. Repair thành công khi `repaired_quality_report.json` quay lại 8/8, freshness về 0.0417, `repaired_metrics.json` bằng baseline ở mọi chỉ số, và collection `papers-repaired` có đủ 24 bản ghi. Dashboard hiển thị cả ba trạng thái để thấy repaired trùng khớp baseline.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` | 1.0000 | 0.8000 | 1.0000 | Giảm 20%: có câu hỏi mà bài đúng không còn trong index |
| `mean_token_f1`      | 1.0000 | 0.6979 | 1.0000 | Giảm khoảng 30%, nhiều hơn hit rate, nên có câu tìm đúng bài nhưng nội dung đã hỏng |
| `judge_accuracy`     | 1.0000 | 0.6000 | 1.0000 | 4/10 câu bị chấm sai |
| `mean_judge_score`   | 5.0000 | 3.7000 | 5.0000 | Điểm trung bình vẫn khá cao, nên nếu chỉ nhìn tổng thì dễ bỏ sót vấn đề |
| Quality checks         | 8/8 Pass | 4/8 Fail | 8/8 Pass | Bắt được 4/6 loại lỗi; không bắt được inject noise |
| Freshness status       | Fresh (0.0417) | Stale (0.4545) | Fresh (0.0417) | 1/24 bài cũ tăng lên 10/22 bài cũ |

_Nguồn: `data/results/*_metrics.json`, `data/quality/`, LLM Judge `openai / gpt-4o-mini`._

### Kết luận từ số liệu

1. Tín hiệu observability (Quality Gate fail, freshness stale) xuất hiện ngay trên dữ liệu, trước cả khi chạy đánh giá RAG. Trong thực tế không có ground truth để đo hit rate, nên phát hiện lỗi ở tầng dữ liệu là cách duy nhất để cảnh báo sớm.
2. Các tín hiệu của tôi khớp chiều với metric RAG: khi quality fail và freshness stale thì mọi metric đều giảm; khi quality và freshness quay lại bình thường thì metric cũng về đúng baseline. Điều này cho thấy các expectation đã chọn có liên quan thật tới chất lượng câu trả lời.

Corruption nào ảnh hưởng rõ nhất và vì sao?

Drop latest records. Mất bài thì retrieval không thể tìm thấy, nên đây là nguồn chính khiến hit rate còn 0.8. Nó cũng làm tỉ lệ bài cũ tăng vọt (kết hợp với stale date). Đặc biệt, drop records không làm bản ghi còn lại sai định dạng, nên chỉ freshness phát hiện được. Nếu chỉ có Quality Gate thì lỗi này lọt qua.

Kết quả nào khác với kỳ vọng ban đầu?

Tôi kỳ vọng Quality Gate bắt được cả 6 loại lỗi, nhưng inject noise lọt qua: summary bị chèn ký tự rác vẫn đủ dài, không null, không trùng, nên không vi phạm expectation nào. Hiện tại Quality Gate chỉ kiểm tra hình thức, chưa kiểm tra nội dung. Ngoài ra, báo cáo tự sinh đang viết bằng tiếng Anh trong khi báo cáo nhóm viết tiếng Việt, nên đọc chung chưa thống nhất.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Một bộ expectation pass không có nghĩa dữ liệu đúng. Nó chỉ nghĩa là dữ liệu không vi phạm những gì mình đã nghĩ tới trước. Cần biết rõ expectation của mình không bắt được gì.
2. Kiểm tra cấp bản ghi (quality) và cấp tập dữ liệu (freshness) phải đi cùng nhau, vì có loại lỗi chỉ lộ ra ở một trong hai cấp.
3. Báo cáo và dashboard là một phần của observability. Con số đúng nhưng trình bày khó đọc thì người vận hành vẫn bỏ sót cảnh báo.

### Nếu có thêm thời gian

- Thêm expectation kiểm tra nội dung, ví dụ `ExpectColumnValuesToMatchRegex` giới hạn tỉ lệ ký tự không phải chữ trong summary, để bắt inject noise.
- Chuyển báo cáo tự sinh và dashboard sang tiếng Việt (hoặc cho chọn ngôn ngữ) cho thống nhất với báo cáo nhóm.
- Lưu lịch sử kết quả kiểm định qua nhiều lần chạy để dashboard vẽ xu hướng theo thời gian, thay vì chỉ so sánh 3 trạng thái.

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [ ] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ ] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [ ] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [ ] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [ ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Quang Duy
**Ngày xác nhận:**
