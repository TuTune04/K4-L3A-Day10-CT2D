# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Lê Phan Việt Cường |
| MSSV               | 2A202602641 |
| Khóa/Lớp         | K4 – L3 |
| Tên nhóm         | CT2D |
| Vai trò chính    | Evaluation, Retrieval & Corruption |
| Repository         | https://github.com/TuTune04/K4-L3A-Day10-CT2D |
| Ngày hoàn thành | 2026-09-25 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Test set | `src/evaluation/testset.py` – `build_test_set`, `load_or_create_test_set` | DataFrame sạch | `data/eval/test_set.json` (10 câu, 5 dạng) | Hoàn thành |
| Retrieval smoke test & multi-hop QA | `src/retrieval/index.py` – `build_from_clean`, `semantic_search`; `src/retrieval/qa.py` | `papers_clean.json`, câu hỏi | Chroma collection, `AnswerResult` | Hoàn thành |
| Corruption | `src/ingestion/corruption.py` – `corrupt_clean_dataframe` | DataFrame sạch | DataFrame corrupted, `data/results/corruption_log.json` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| _(Tự viết bằng lời của bạn.)_ |  |  |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Test set 5 dạng × 2 câu, có multi_hop liên ngành | `src/evaluation/testset.py` | `data/eval/test_set.json` | Lệnh kiểm tra CP2 bước 1 |
| `build_from_clean`, `semantic_search`, manifest đường dẫn tương đối, QA multi-hop | `src/retrieval/index.py`, `src/retrieval/qa.py` | 3 collection Chroma | Lệnh kiểm tra CP2 bước 2 |
| 6 kịch bản corruption seed 42 + log | `src/ingestion/corruption.py` | `corruption_log.json`, `papers_clean_corrupted.*` | Lệnh kiểm tra bước 7 trong Guide |

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
| Input                          | DataFrame sạch (schema của cleaning); câu hỏi dạng `'<title>'` |
| Output                         | `test_set.json` (`id, type, question_type, question, ground_truth, ground_truth_doc_ids`); DataFrame corrupted + log |
| Module phụ thuộc             | `ingestion/cleaning.py` (`refresh_derived_columns`), `core/` |
| Module sử dụng output        | `evaluation/metrics.py`, `pipelines/phase1.py`, `pipelines/corruption_flow.py` |
| Điều kiện lỗi cần xử lý | Ít hơn 10 tài liệu; title chứa dấu `'`; không tìm được bài ghép multi_hop; collection chưa tồn tại |

### Cách xác minh

```bash
python -c "from core.config import load_settings; from evaluation.testset import load_or_create_test_set; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); ts=load_or_create_test_set(df, s.paths.test_set_json); print(f'Test set gồm {len(ts.samples)} câu hỏi')"
python -c "from core.config import load_settings; from retrieval.index import LocalEmbeddingIndex; s=load_settings(); idx=LocalEmbeddingIndex(s, collection_name='papers-baseline'); idx.build_from_clean(); res=idx.semantic_search('machine learning', top_k=2); print(f'Tìm thấy {len(res)} tài liệu liên quan')"
python -c "from core.config import load_settings; from ingestion.corruption import corrupt_clean_dataframe; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); c=corrupt_clean_dataframe(df, s.paths.corruption_log); print(f'Corrupted {len(c)} dòng')"
```

- **Kết quả mong đợi:** 10 câu hỏi; 2 tài liệu; log ghi đủ 6 loại lỗi.
- **Kết quả thực tế:** `Test set gồm 10 câu hỏi`, `Tìm thấy 2 tài liệu liên quan`, `Corrupted 22 dòng` (24 − 5 dropped + 3 duplicate).
- **Artifact/log:** `data/eval/test_set.json`, `data/results/corruption_log.json`

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

**Họ và tên:** Lê Phan Việt Cường
**Ngày xác nhận:**
