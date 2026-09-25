# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Khóa/Lớp         | K4 – L3                    |
| Tên nhóm         | CT2D                       |
| Repository         | `K4-L3A-Day10-CT2D`        |
| Ngày hoàn thành | 2026-09-25                 |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| --: | --- | --- | --- | --- |
| 1 | Đinh Công Tú | 2A202602479 | Trưởng nhóm / Pipeline Integrator | `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py`, artifacts `data/`, báo cáo nhóm |
| 2 | Vi Hùng Đức | 2A202602512 | Ingestion & Cleaning | `src/ingestion/crossref.py`, `src/ingestion/cleaning.py`, `data/raw/` |
| 3 | Lê Phan Việt Cường | 2A202602641 | Evaluation & Corruption | `src/evaluation/testset.py`, `src/ingestion/corruption.py`, `data/eval/test_set.json` |
| 4 | Nguyễn Quang Duy | 2A202602426 | Observability & Reporting | `src/observability/quality.py`, `src/observability/reporting.py`, `data/quality/`, `data/reports/` |

## 2. Tóm tắt kết quả

Nhóm đã hoàn thành đầy đủ 7 tầng của pipeline: ingestion Crossref (chế độ offline snapshot, có live mode với retry), cleaning, Quality Gate bằng Great Expectations 1.23.1, index ChromaDB với `all-MiniLM-L6-v2`, evaluation baseline, bộ 6 kịch bản corruption và idempotent repair. Baseline tạo đủ artifact: 2 file raw, `papers_clean.csv/json` (24 dòng), collection `papers-baseline`, `test_set.json` (10 câu), `baseline_metrics.json` và `phase1_report.md`. Trên dữ liệu sạch, Hit Rate và Token F1 đều đạt 1.0.

Sau khi tiêm lỗi, Hit Rate giảm từ 1.0 xuống 0.8, Token F1 từ 1.0 xuống 0.6979, LLM Judge Accuracy (gpt-4o-mini) từ 1.0 xuống 0.5, và Quality Gate fail 4/8 expectation. Lỗi nguy hiểm nhất là **stale date**: câu eval_008 vẫn truy xuất đúng bài (hit = true) nhưng trả lời sai năm (`2025-05-20` thay vì `2026-05-20`). Đây là silent failure điển hình, retrieval "đúng" mà câu trả lời vẫn sai. **Drop latest records** gây nhiều thiệt hại nhất: 4/10 câu bị giảm điểm (eval_001, eval_002 mất tài liệu đúng; 2 câu multi-hop mất bài thứ 2 trong cặp nên trả lời thừa lĩnh vực). RAG vẫn trả lời mọi câu mà không báo lỗi. Chỉ Quality Gate và Freshness SLA (stale ratio 0.4545 > 0.25) phát hiện ra vấn đề. Repair tái tạo dữ liệu từ raw snapshot và phục hồi 100% các chỉ số. Chạy repair 2 lần cho ra file giống hệt nhau từng byte.

Giới hạn còn lại: Ragas không được chạy (cần `RUN_RAGAS=1`), và dữ liệu là snapshot offline 24 bài.

## 3. Kiến trúc và luồng dữ liệu

### Luồng end-to-end

```text
Crossref API (REFRESH_SOURCE=1) hoặc snapshot data/raw/crossref_response.json
    -> parse -> data/raw/crossref_records.json                (crossref.py)
    -> cleaning -> data/clean/papers_clean.csv|json            (cleaning.py)
    -> Quality Gate GX 1.x + Freshness SLA (fail => dừng)      (quality.py)
    -> MiniLM embedding + ChromaDB `papers-baseline`           (retrieval/index.py)
    -> test_set.json -> evaluate -> baseline_metrics.json      (testset.py, metrics.py)
    -> phase1_report.md                                        (reporting.py)
    -> corruption 6 lỗi -> `papers-corrupted` -> evaluate      (corruption.py)
    -> repair: clean lại từ raw -> `papers-repaired` -> evaluate
    -> corruption_report.md (Baseline vs Corrupted vs Repaired)
```

### Trách nhiệm của từng khối

| Khối             | Input          | Xử lý chính             | Output/artifact          | Owner          |
| ----------------- | -------------- | -------------------------- | ------------------------ | -------------- |
| Ingestion         | Crossref `/works` hoặc snapshot | Retry 429/5xx, parse, bỏ record thiếu DOI/title/abstract | `data/raw/*.json` | Vi Hùng Đức |
| Cleaning          | `PaperRecord` list | Strip JATS, normalize, `age_days`, dedup, `text_for_embedding` | `data/clean/papers_clean.*` | Vi Hùng Đức |
| Embedding/index   | Clean DataFrame | MiniLM + Chroma cosine, 3 collection tách biệt | `data/chroma/`, `data/embeddings/` | Code starter, Lê Phan Việt Cường kiểm thử |
| Evaluation        | Clean DataFrame | 10 câu × 4 dạng, Hit Rate / Token F1 / Judge | `data/eval/`, `data/results/` | Lê Phan Việt Cường |
| Observability     | Clean/corrupted DataFrame | 8 expectation GX 1.x, Freshness SLA | `data/quality/` | Nguyễn Quang Duy |
| Corruption/repair | Clean DataFrame / raw records | 6 lỗi seed 42; repair từ raw | `data/results/corruption_log.json`, `papers_clean_repaired.*` | Lê Phan Việt Cường / Đinh Công Tú |
| Orchestration     | Tất cả module | Thứ tự chạy, gate, so sánh | `data/reports/*.md` | Đinh Công Tú |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình             | Giá trị sử dụng |
| ---------------------------- | ------------------- |
| `LLM_PROVIDER`             | `openai`          |
| `LLM_MODEL`                | `gpt-4o-mini` (LLM Judge) |
| Embedding model              | `sentence-transformers/all-MiniLM-L6-v2` |
| Số lượng Crossref records | 24                |
| Retrieval `top_k`          | 4                 |
| Freshness threshold          | 180 ngày, tối đa 25% bài stale |
| Random seed, nếu có        | 42 (corruption)   |

### Lệnh cài đặt

```bash
python -m pip install -e .
```

### Lệnh chạy

```bash
cp .env.example .env   # điền LLM_PROVIDER=openai, LLM_MODEL=gpt-4o-mini, OPENAI_API_KEY=<key>
python script/run_phase1.py
python script/run_corruption_flow.py
```

Không có API key thì đặt `LLM_PROVIDER=mock`. Khi đó pipeline vẫn chạy, nhưng Judge chuyển sang heuristic theo Token F1.

### Kết quả tái hiện

| Lệnh             | Trạng thái | Thời điểm chạy gần nhất | Bằng chứng |
| ----------------- | ---------- | ----------------------------- | ---------- |
| Baseline pipeline | Thành công (exit 0) | 2026-09-25 08:22 UTC | `data/reports/phase1_report.md`, `data/results/baseline_metrics.json` |
| Corruption flow   | Thành công (exit 0) | 2026-09-25 08:23 UTC | `data/reports/corruption_report.md`, `data/results/*_metrics.json` |

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính                | Giá trị                             |
| --------------------------- | ------------------------------------- |
| Source                      | Crossref REST API `https://api.crossref.org/works` (chạy từ snapshot offline `data/raw/crossref_response.json`) |
| Query/filter                | `agentic retrieval augmented generation large language model`; `from-pub-date:<run_date − 180d>,has-abstract:true` |
| Thời điểm lấy dữ liệu | Snapshot có sẵn; run date 2026-09-25 |
| Số record nhận được    | 24 items → 24 records hợp lệ |
| Cơ chế retry/backoff      | 4 lần, retry với 429/500/502/503/504 và lỗi mạng, chờ theo `Retry-After` hoặc 2^n giây; hết lượt thì fallback về snapshot |

### Raw và clean schema

| Trường        | Kiểu dữ liệu | Bắt buộc?  | Ý nghĩa   | Xử lý khi thiếu/sai |
| --------------- | --------------- | ------------ | ----------- | ---------------------- |
| `paper_id` | str (DOI, lowercase) | Có | Khóa định danh | Loại record; dedup giữ bản `updated` mới nhất |
| `title` | str | Có | Tiêu đề | Loại record nếu rỗng |
| `summary` | str | Có | Abstract đã bỏ tag JATS | Loại record nếu rỗng |
| `authors` / `authors_joined` | list[str] / str | Không | Tác giả | Danh sách rỗng |
| `categories` / `categories_joined` / `primary_category` | list[str] / str | Không | Crossref `subject` | `primary_category = "Uncategorized"` |
| `published` / `updated` | str `YYYY-MM-DD` | Có / Không | Ngày xuất bản / cập nhật | Fallback `published-print` → `published-online` → `created`; loại record nếu không parse được |
| `age_days` | int | Có | Số ngày tính từ `published` đến run date | Tính lại mỗi lần chạy |
| `text_for_embedding` | str | Có | Ngữ cảnh 5 phần đưa vào embedding | Sinh lại từ các cột gốc |

### Quy tắc cleaning

| Quy tắc                                 | Quality dimension liên quan | Số record bị tác động | Cách xác minh      |
| ---------------------------------------- | ---------------------------- | -------------------------: | -------------------- |
| Bỏ tag JATS/HTML trong abstract (`<jats:p>`) | Validity | 24 | So sánh `crossref_response.json` và `papers_clean.json` |
| Loại record thiếu DOI/title/abstract/ngày | Completeness | 0 | 24 raw → 24 clean |
| Dedup theo `paper_id` | Uniqueness | 0 | GX `expect_column_values_to_be_unique` pass |
| Chuẩn hóa khoảng trắng, bỏ author/subject trùng | Consistency | 24 (áp dụng cho mọi record) | `papers_clean.csv` |

`text_for_embedding` gồm 5 dòng `Title / Authors / Published / Categories / Summary`, để câu hỏi về tác giả, ngày và lĩnh vực đều khớp được ngữ nghĩa. Document ID trong Chroma có dạng `<paper_id>::<row_index>`, nhờ đó các dòng trùng lặp ở trạng thái corrupted vẫn index được và thể hiện đúng tác động của duplicate. `age_days = run_date − published` (tính theo ngày UTC).

## 6. Evaluation setup

| Thành phần                             | Cấu hình thực tế          |
| ---------------------------------------- | ----------------------------- |
| Số câu hỏi                            | 10                            |
| Các `question_type`                   | summary, authors, date, categories, multi_hop (2 câu mỗi dạng) |
| Ground-truth document ID                 | DOI của bài được chọn (multi_hop: 2 DOI); paper chọn trải đều theo `published`, từ mới nhất đến cũ nhất |
| Embedding model                          | `all-MiniLM-L6-v2` (normalized) |
| Vector store/collection                  | ChromaDB cosine: `papers-baseline`, `papers-corrupted`, `papers-repaired` |
| Retrieval `top_k`                      | 4                             |
| LLM provider/model                       | `openai` / `gpt-4o-mini` (LLM Judge, structured output) |
| Test set dùng chung cho ba trạng thái | `data/eval/test_set.json` (sha256 `1bdf16b34997a8d2…`) |

Test set được sinh 1 lần từ dữ liệu sạch và giữ cố định; chỉ sinh lại khi đặt `REFRESH_TEST_SET=1`. Nhờ đó, mọi thay đổi metric giữa 3 trạng thái chỉ đến từ dữ liệu, không phải do câu hỏi khác. Vì test set chọn cả những bài mới nhất, lỗi drop latest records sẽ lộ ra trong metric.

Câu **multi_hop** hỏi lĩnh vực chung của 2 bài thuộc 2 chủ đề khác nhau (ví dụ *Multi-Agent Consensus* và *Freshness SLAs* có chung *Artificial Intelligence*). Để trả lời, `qa.py` tra cứu chính xác cả 2 title rồi lấy giao 2 tập categories. Chỉ cần thiếu 1 bài là câu trả lời sai.

## 7. Kết quả baseline

### Artifact checklist

| Artifact                 | Đường dẫn thực tế                | Trạng thái | Ghi chú   |
| ------------------------ | -------------------------------------- | ------------ | ---------- |
| Raw response/records     | `data/raw/`                          | Có | 24 items |
| Cleaned dataset          | `data/clean/`                        | Có | CSV + JSON, 24 dòng |
| Embedding manifest/index | `data/embeddings/`, `data/chroma/`   | Có | 3 collection |
| Evaluation set           | `data/eval/test_set.json`            | Có | 10 câu |
| Baseline metrics         | `data/results/baseline_metrics.json` | Có | |
| Quality/freshness        | `data/quality/`                      | Có | kèm GX suite trong `data/quality/gx/` |
| Baseline report          | `data/reports/phase1_report.md`      | Có | |

### Baseline metrics

| Metric                 |       Giá trị | Diễn giải                             |
| ---------------------- | --------------: | --------------------------------------- |
| `retrieval_hit_rate` | 1.0000 | Cả 10 câu đều có DOI đúng trong top-4 |
| `mean_token_f1`      | 1.0000 | QA trích xuất đúng trường metadata tương ứng với ground truth |
| `judge_accuracy`     | 1.0000 | gpt-4o-mini chấm 10/10 câu đúng |
| `mean_judge_score`   | 5.0000 | Cả 10 câu đạt 5/5 |
| Ragas, nếu có        | N/A | Bỏ qua (cần `RUN_RAGAS=1`, chạy chậm) |

## 8. Data quality và freshness

### Quality checks

| Check        | Quality dimension | Ngưỡng/kỳ vọng | Kết quả baseline      | Bằng chứng |
| ------------ | ----------------- | ------------------ | ----------------------- | ------------ |
| `ExpectTableRowCountToBeBetween` | Volume | 5–5000 dòng | Pass (24) | `data/quality/baseline_quality_report.json` |
| `ExpectColumnValuesToNotBeNull` × 3 | Completeness | `paper_id`, `title`, `text_for_embedding` | Pass (0 null) | như trên |
| `ExpectColumnValuesToBeUnique` | Uniqueness | `paper_id` | Pass (0 trùng) | như trên |
| `ExpectColumnValueLengthsToBeBetween` | Completeness | `summary` ≥ 30 ký tự | Pass | như trên |
| `ExpectColumnValueLengthsToBeBetween` | Validity | `title` ≥ 8 ký tự | Pass | như trên |
| `ExpectColumnValuesToBeBetween` | Timeliness | `age_days` ∈ [0, 180], mostly 0.75 | Pass (1/24 ngoài ngưỡng) | như trên |

### Freshness

| Thuộc tính               | Giá trị                           |
| -------------------------- | ----------------------------------- |
| Freshness được đo tại | Clean dataset (`age_days`) |
| Timestamp mới nhất       | 2026-07-22 (cũ nhất 2026-03-28) |
| Ngưỡng freshness         | `age_days > 180` là stale; fresh khi stale ratio ≤ 0.25 |
| Trạng thái baseline      | Fresh |
| Lý do                     | 1/24 bài stale (0.0417); bài `10.1145/3637528.3671805` có age 181 ngày |

## 9. Corruption scenarios và repair

| Corruption         | Cách tạo | Record bị tác động | Quality signal kỳ vọng | Tác động thực tế | Cách repair   |
| ------------------ | ---------- | ---------------------: | ------------------------ | --------------------- | -------------- |
| drop_latest_records | Xóa 20% bài mới nhất | 5 | Freshness: latest lùi về | Latest 2026-07-22 → 2026-06-12; eval_001, eval_002 hit fail; eval_005, eval_010 (multi_hop) mất 1/2 bài | Clean lại từ raw |
| blank_summary | `summary = ""` | 3 | Độ dài summary fail | GX summary fail (4 dòng tính cả duplicate); trúng bài của eval_008 (câu hỏi date) | Clean lại từ raw |
| inject_noise | Chèn token rác, xáo ký tự | 3 | Khó bắt bằng rule | GX không bắt trực tiếp. Trúng bài của eval_005/eval_009 nhưng 2 câu này hỏi categories nên metric không đổi | Clean lại từ raw |
| truncate_title | Cắt title còn 7 ký tự | 3 | Độ dài title fail | GX title fail (4 dòng, tính cả 1 dòng duplicate); không trúng bài nào trong test set | Clean lại từ raw |
| stale_date | `published` − 365 ngày | 7 | Freshness fail | stale ratio 0.4545, GX `age_days` fail; eval_008 hit đúng nhưng trả lời `2025-05-20` (F1 0) | Clean lại từ raw |
| duplicate_rows | Nhân đôi dòng | 3 | Unique fail | GX unique `paper_id` fail (6 dòng) | Dedup trong cleaning |

Corruption log:

- Đường dẫn: `data/results/corruption_log.json`
- Trạng thái: Có
- Nhận xét: log ghi seed 42, số dòng trước/sau (24 → 22), loại lỗi, số dòng và danh sách `paper_id` bị ảnh hưởng cho từng loại.

Repair không sửa trên bảng đã hỏng. Nó đọc lại `data/raw/crossref_records.json`, là bản raw được giữ nguyên, rồi chạy lại đúng hàm cleaning có tính xác định (deterministic), sau đó index vào collection mới `papers-repaired`. Dữ liệu vì vậy được khôi phục từ nguồn tin cậy chứ không phải che lỗi. Kết quả đã được xác minh: `papers_clean_repaired.json` giống hệt baseline về `paper_id` và `text_for_embedding`, và 2 lần chạy repair cho ra file giống nhau từng byte.

## 10. So sánh baseline, corrupted và repaired

| Metric/signal            | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi | Nhận xét   |
| ------------------------ | -------: | --------: | -------: | -----------------------: | --------------: | ------------ |
| `retrieval_hit_rate`   | 1.0000 | 0.8000 | 1.0000 | −0.2000 | 100% | 2 câu mất tài liệu đúng (eval_001 summary, eval_002 authors) |
| `mean_token_f1`        | 1.0000 | 0.6979 | 1.0000 | −0.3021 | 100% | 5/10 câu bị giảm: 4 do drop latest, 1 do stale date |
| `judge_accuracy`       | 1.0000 | 0.5000 | 1.0000 | −0.5000 | 100% | gpt-4o-mini đánh sai 5/10 câu |
| `mean_judge_score`     | 5.0000 | 3.8000 | 5.0000 | −1.2000 | 100% | |
| Quality checks pass/fail | 8/8 Pass | 4/8 Fail | 8/8 Pass | −4 | 100% | Fail: unique, title, summary, age_days |
| Freshness status         | Fresh (0.0417) | Stale (0.4545) | Fresh (0.0417) | +0.4128 stale ratio | 100% | |

1. **Stale date** → stale ratio tăng 0.0417 → 0.4545 (`is_fresh=False`, GX `age_days` fail) → eval_008 vẫn truy xuất đúng bài (hit = true) nhưng trả lời sai năm, F1 1.0 → 0.0, judge 2/5. Hit Rate không bắt được loại lỗi này, chỉ freshness monitor bắt được.
2. **Drop latest records** → latest lùi về 2026-06-12 (freshness) → eval_001, eval_002 mất tài liệu đúng (hit fail); 2 câu multi_hop chỉ tra cứu được 1/2 bài nên trả lời bằng toàn bộ categories của bài còn lại (F1 0.67 / 0.57). **Repair từ raw** → 8/8 expectation pass, freshness về 0.0417 → mọi metric về lại 1.0.

Inject noise và truncate title có trong dữ liệu corrupted, nhưng không làm thay đổi metric: các bài bị trúng lỗi không có câu hỏi summary/title trong test set. Tức là **test set 10 câu không đủ phủ mọi loại lỗi**, và Quality Gate vẫn là tín hiệu cần thiết. Inject noise còn không bị GX bắt trực tiếp (summary sau khi chèn nhiễu vẫn ≥ 30 ký tự).

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** lần chạy đầu với `LLM_PROVIDER=mock`, `judge_accuracy` và `mean_judge_score` vẫn có giá trị và biến động theo trạng thái, trông như có một LLM judge đang chấm thật.
- **Nguyên nhân:** mô hình mock (`FakeListChatModel`) không hỗ trợ `with_structured_output`. `_judge_answer` bắt exception và chuyển sang heuristic theo Token F1. Mọi câu trả lời đều có `reasoning = "Fallback heuristic judge used..."`.
- **Cách xử lý:** cấu hình `LLM_PROVIDER=openai`, `LLM_MODEL=gpt-4o-mini` trong `.env` (không commit) rồi chạy lại cả 2 pipeline.
- **Cách xác minh:** trường `judge.reasoning` trong `data/results/*_answers.json` giờ là nhận xét do LLM viết. Với dữ liệu corrupted, judge đánh sai 5/10 câu, trong khi heuristic trước đó chỉ đánh sai 3/10.

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng   | Hướng cải thiện có thể kiểm chứng |
| --------------------- | -------------- | ----------------------------------------- |
| Chưa chạy Ragas | Thiếu faithfulness / context precision | Chạy `RUN_RAGAS=1`, so sánh 4 metric Ragas giữa 3 trạng thái |
| Quality Gate không bắt được inject noise; test set không phủ bài bị noise/truncate | Nhiễu văn bản lọt vào index | Thêm expectation tỉ lệ ký tự non-alphanumeric / regex token rác, kiểm tra fail trên `papers_clean_corrupted` |
| Dữ liệu là snapshot 24 bài | Kết quả chưa phản ánh dữ liệu live | Chạy `REFRESH_SOURCE=1` và so sánh freshness report |

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm và repository chính xác.
- [x] Phân công khớp với module, artifact và kết quả thực tế.
- [x] Lệnh tái hiện đã được chạy lại trên phiên bản dùng để nộp.
- [x] Baseline, corrupted và repaired dùng cùng evaluation set.
- [x] Bảng metrics khớp với các file trong `data/results/`.
- [x] Quality/freshness conclusions khớp với `data/quality/`.
- [x] Các đường dẫn báo cáo và artifact truy cập được.
- [ ] Mỗi thành viên đã hoàn thành báo cáo vai trò riêng.
- [x] Không có `.env`, API key, token hoặc secret trong source, report, log hay ảnh.
