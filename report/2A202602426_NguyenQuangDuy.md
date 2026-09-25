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
| _(Tự viết bằng lời của bạn.)_ |  |  |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| 8 expectation GX 1.x (API `get_context(mode="ephemeral")`, `data_sources.add_pandas`) | `src/observability/quality.py` | `baseline_quality_report.json` (pass), `corrupted_quality_report.json` (fail 4) | Lệnh kiểm tra bước 4 trong Guide |
| Freshness SLA: stale khi `age_days > 180`, fresh khi stale ratio ≤ 0.25 | `src/observability/quality.py` | `freshness_report*.json` | `is_fresh` của baseline/corrupted/repaired |
| Báo cáo 3 trạng thái, breakdown theo question type, danh sách câu bị giảm điểm | `src/observability/reporting.py` | `corruption_report.md` | `python script/run_corruption_flow.py` |

Nêu một output cụ thể mà phần việc của bạn tạo ra hoặc giúp xác minh:

_(Tự viết bằng lời của bạn.)_

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

_(Tự viết bằng lời của bạn.)_

### Cách triển khai

_(Tự viết bằng lời của bạn.)_

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

- **Bối cảnh:** _(Tự viết bằng lời của bạn.)_
- **Các phương án đã cân nhắc:**
- **Phương án đã chọn:**
- **Lý do:**
- **Bằng chứng quyết định phù hợp:**

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** _(Tự viết bằng lời của bạn.)_
- **Lệnh hoặc bước tái hiện:**
- **Nguyên nhân gốc:**
- **Cách xử lý:**
- **Cách xác minh sau khi sửa:**
- **Điều học được:**

## 7. Hiểu biết về luồng end-to-end

1. Dữ liệu đi từ Crossref đến vector index như thế nào?
2. Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?
3. Quality checks khác freshness monitoring ở điểm nào trong bài lab?
4. Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?
5. Repair được xem là thành công dựa trên artifact và metric nào?

**Câu trả lời:**

_(Tự viết bằng lời của bạn.)_

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` | 1.0000 | 0.8000 | 1.0000 | |
| `mean_token_f1`      | 1.0000 | 0.6979 | 1.0000 | |
| `judge_accuracy`     | 1.0000 | 0.6000 | 1.0000 | |
| `mean_judge_score`   | 5.0000 | 3.7000 | 5.0000 | |
| Quality checks         | 8/8 Pass | 4/8 Fail | 8/8 Pass | |
| Freshness status       | Fresh (0.0417) | Stale (0.4545) | Fresh (0.0417) | |

_Nguồn: `data/results/*_metrics.json`, `data/quality/`, LLM Judge `openai / gpt-4o-mini`._

### Kết luận từ số liệu

1. _(Tự viết bằng lời của bạn.)_
2.

Corruption nào ảnh hưởng rõ nhất và vì sao?

_(Tự viết bằng lời của bạn.)_

Kết quả nào khác với kỳ vọng ban đầu?

_(Tự viết bằng lời của bạn.)_

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. _(Tự viết bằng lời của bạn.)_
2.
3.

### Nếu có thêm thời gian

_(Tự viết bằng lời của bạn.)_

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
