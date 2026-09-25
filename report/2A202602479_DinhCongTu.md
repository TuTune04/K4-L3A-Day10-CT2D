# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Đinh Công Tú |
| MSSV               | 2A202602479 |
| Khóa/Lớp         | K4 – L3 |
| Tên nhóm         | CT2D |
| Vai trò chính    | Trưởng nhóm / Pipeline Integrator |
| Repository         | https://github.com/TuTune04/K4-L3A-Day10-CT2D |
| Ngày hoàn thành | 2026-09-25 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Cấu hình | `src/core/config.py` (`paths.test_set_json`) | Biến môi trường `.env` | `Settings`, `Paths` | Hoàn thành |
| Baseline pipeline | `src/pipelines/phase1.py` – `main()` | Raw snapshot, settings | `papers_clean.*`, `papers-baseline`, `baseline_metrics.json`, `phase1_report.md` | Hoàn thành |
| Corruption & repair flow | `src/pipelines/corruption_flow.py` – `main()` | Baseline artifacts, raw records | `corrupted_*`, `repaired_*`, `corruption_report.md` | Hoàn thành |
| Artifacts & báo cáo nhóm | `data/`, `docs/TEAM.md`, `report/group_report.md` | Kết quả 2 pipeline | Artifact đã commit, báo cáo nhóm | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| _(Tự viết bằng lời của bạn.)_ |  |  |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Ghép baseline end-to-end, Quality Gate chặn index khi fail | `src/pipelines/phase1.py` | `phase1_report.md`, `baseline_metrics.json` | `python script/run_phase1.py` (exit 0) |
| Ghép luồng corrupt → evaluate → repair → so sánh 3 trạng thái | `src/pipelines/corruption_flow.py` | `corruption_report.md` | `python script/run_corruption_flow.py` (exit 0) |
| Cấu hình LLM Judge openai/gpt-4o-mini, chạy lại và commit artifact | `.env` (không commit), `data/` | `data/results/*_metrics.json` | `judge.reasoning` trong `*_answers.json` |

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
| Input                          | Settings từ `.env`; raw snapshot `data/raw/`; các hàm của ingestion/observability/evaluation/retrieval |
| Output                         | Toàn bộ artifact trong `data/` + 2 báo cáo Markdown |
| Module phụ thuộc             | Mọi module trong `src/` |
| Module sử dụng output        | Báo cáo nhóm, demo CP6 |
| Điều kiện lỗi cần xử lý | Quality Gate fail ở baseline → dừng trước khi index; thiếu artifact baseline khi chạy corruption flow → báo lỗi yêu cầu chạy Phase 1 |

### Cách xác minh

```bash
python script/run_phase1.py
python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** Cả 2 lệnh exit 0; repaired giống baseline; 3 collection Chroma.
- **Kết quả thực tế:** Exit 0. Console in `Repaired rows: 24 | identical to baseline content: True`; Chroma có `papers-baseline` (24), `papers-corrupted` (22), `papers-repaired` (24).
- **Artifact/log:** `data/reports/phase1_report.md`, `data/reports/corruption_report.md`

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

**Họ và tên:** Đinh Công Tú
**Ngày xác nhận:**
