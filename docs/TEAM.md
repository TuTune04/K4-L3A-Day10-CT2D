# Danh Sách Thành Viên & Báo Cáo Phân Công Nhóm

- **Tên Nhóm:** `CT2D`
- **Mã Nhóm / Lớp:** `K4-L3-DAY10`
- **Tên Repository Nộp Bài:** `K4-L3A-Day10-CT2D`

---

## # Thành viên

| STT | Họ và tên | MSSV | Email | Vai trò & Phân công công việc | Báo cáo cá nhân |
|---:|---|---|---|---|---|
| 1 | Đinh Công Tú | 2A202602479 | baygiolamaygio04@gmail.com | Trưởng nhóm / Pipeline Integrator (`core/config.py`, `pipelines/phase1.py`, `pipelines/corruption_flow.py`, idempotent repair, artifacts, báo cáo nhóm) | `report/2A202602479_DinhCongTu.md` |
| 2 | Vi Hùng Đức | 2A202602512 | viduc173hb@gmail.com | Ingestion & Cleaning (`ingestion/crossref.py`, `ingestion/cleaning.py`, raw data lineage) | `report/2A202602512_ViHungDuc.md` |
| 3 | Lê Phan Việt Cường | 2A202602641 | cuongthenao@gmail.com | Evaluation, Retrieval & Corruption (`evaluation/testset.py`, `retrieval/index.py`, `retrieval/qa.py`, `ingestion/corruption.py`) | `report/2A202602641_LePhanVietCuong.md` |
| 4 | Nguyễn Quang Duy | 2A202602426 | Quangduy230905@gmail.com | Observability & Reporting (`observability/quality.py` GX 1.x + Freshness SLA, `observability/reporting.py`) | `report/2A202602426_NguyenQuangDuy.md` |

### Phân công theo Checkpoint

| Checkpoint | Đinh Công Tú | Vi Hùng Đức | Lê Phan Việt Cường | Nguyễn Quang Duy |
|---|---|---|---|---|
| CP0 – Setup & Raw Ingestion | Fork repo, mời collaborator, cấu hình môi trường | `fetch_source_records`, `parse_crossref_payload`, `load_raw_records` | Kiểm tra môi trường, smoke test ChromaDB/MiniLM | Kiểm tra môi trường GX 1.x |
| CP1 – Cleaning & Quality Gate | Chốt data contract (schema cột) | `build_clean_dataframe`, `age_days`, `text_for_embedding` | – | `run_data_quality_checks` (GX 1.x), `build_freshness_report` |
| CP2 – Test Set & Index | Tích hợp index vào pipeline, `paths.test_set_json` | – | `load_or_create_test_set` (10 câu, 5 dạng gồm multi_hop), `build_from_clean` / `semantic_search`, multi-hop QA | – |
| CP3 – Baseline End-to-End | `phase1.py`, chạy baseline | Hỗ trợ debug dữ liệu | Kiểm tra Hit Rate / Token F1 | `generate_phase1_report` |
| CP4 – Corruption | `corruption_flow.py` | – | `corrupt_clean_dataframe` (6 lỗi) | Kiểm tra Quality Gate bắt lỗi |
| CP5 – Repair & Report | Idempotent repair, chạy lại toàn bộ | Xác nhận repair tái tạo từ raw | Phân tích suy giảm theo question type | `generate_corruption_report` (3 trạng thái) |
| Bonus B1/B2/B3 | Self-healing `pipelines/self_heal.py`, CI GitHub Actions, `tests/test_pipelines.py` | `tests/test_ingestion.py` | `tests/test_evaluation_retrieval.py` | Dashboard `observability/dashboard.py`, `tests/test_observability.py` |
| CP6 – Demo & Nộp bài | Demo, TEAM.md, `group_report.md` | Báo cáo cá nhân + nộp LMS | Báo cáo cá nhân + nộp LMS | Báo cáo cá nhân + nộp LMS |

---

## # Cá nhân

### ## DinhCongTu-2A202602479
- **Vai trò:** Trưởng nhóm & Điều phối Pipeline.
- **Công việc chi tiết đã hoàn thành:**
  - Xây dựng baseline pipeline end-to-end trong `src/pipelines/phase1.py`: ingest → clean → Quality Gate (chặn index nếu fail) → ChromaDB → test set → evaluate → report.
  - Xây dựng `src/pipelines/corruption_flow.py`: corrupt → audit quality/freshness → re-index & evaluate → idempotent repair từ `data/raw/crossref_records.json` → so sánh 3 trạng thái trên cùng test set.
  - Cấu hình LLM Judge `openai / gpt-4o-mini`, chạy lại toàn bộ pipeline, commit artifacts trong `data/`, viết `report/group_report.md`.
- **Điều học được / Đóng góp chính:**
  - _(Tự điền)_

### ## ViHungDuc-2A202602512
- **Vai trò:** Phụ trách Ingestion & Làm sạch dữ liệu.
- **Công việc chi tiết đã hoàn thành:**
  - `src/ingestion/crossref.py`: parse Crossref payload (DOI, title, abstract JATS, authors, subject, dates, URL), gọi API có retry/backoff cho 429/5xx, fallback snapshot offline, lưu 2 raw artifacts.
  - `src/ingestion/cleaning.py`: bỏ tag JATS/HTML, chuẩn hóa khoảng trắng, tính `age_days`, khử trùng theo `paper_id`, sinh `text_for_embedding` 5 phần.
- **Điều học được / Đóng góp chính:**
  - _(Tự điền)_

### ## LePhanVietCuong-2A202602641
- **Vai trò:** Phụ trách Evaluation Set & Data Corruption.
- **Công việc chi tiết đã hoàn thành:**
  - `src/evaluation/testset.py`: bộ 10 câu hỏi, 5 dạng (summary, authors, date, categories, multi_hop) × 2, chọn trải đều theo thời gian xuất bản; `load_or_create_test_set` giữ test set cố định.
  - `src/retrieval/index.py`: `build_from_clean()` và `semantic_search()` cho smoke test ChromaDB; `src/retrieval/qa.py`: trả lời câu multi-hop bằng cách tra cứu 2 bài và lấy giao lĩnh vực.
  - `src/ingestion/corruption.py`: 6 kịch bản lỗi có seed cố định (drop latest 20%, blank summary, inject noise, truncate title, stale date lùi 5 năm, duplicate rows) và `corruption_log.json`.
- **Điều học được / Đóng góp chính:**
  - _(Tự điền)_

### ## NguyenQuangDuy-2A202602426
- **Vai trò:** Phụ trách Data Observability & Reporting.
- **Công việc chi tiết đã hoàn thành:**
  - `src/observability/quality.py`: Quality Gate bằng Great Expectations 1.x (row count, not null, unique `paper_id`, độ dài `summary`, độ dài `title`, freshness `age_days`) và Freshness SLA (`age_days > 180`, ngưỡng 25%).
  - `src/observability/reporting.py`: `phase1_report.md` và `corruption_report.md` đối chiếu Baseline / Corrupted / Repaired, phân tích theo question type.
- **Điều học được / Đóng góp chính:**
  - _(Tự điền)_
