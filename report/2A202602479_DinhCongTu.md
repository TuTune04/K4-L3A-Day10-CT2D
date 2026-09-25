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
| Corruption & self-healing flow | `src/pipelines/corruption_flow.py` – `main()` | Baseline artifacts, raw records | `corrupted_*`, `repaired_*`, `corruption_report.md` | Hoàn thành |
| Artifacts & báo cáo nhóm | `data/`, `docs/TEAM.md`, `report/group_report.md` | Kết quả 2 pipeline | Artifact đã commit, báo cáo nhóm | Hoàn thành |
| Bonus B2 + CI (B3) | `src/pipelines/self_heal.py`, `.github/workflows/tests.yml`, `script/run_tests.sh`, `tests/test_pipelines.py` | Dataset + Quality/Freshness | `self_heal_log.json`, CI coverage gate 80% | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Thống nhất contract giữa các module (tên cột DataFrame, đường dẫn artifact trong `Paths`) để các phần ghép được với nhau | Đức (cleaning), Duy (quality), Cường (testset/index) | Hai pipeline chạy end-to-end, exit 0 |
| Đưa test của cả nhóm vào CI (GitHub Actions + `script/run_tests.sh`) với ngưỡng coverage 80% | Cả nhóm (`test_ingestion.py`, `test_evaluation_retrieval.py`, `test_observability.py`) | 58 passed, coverage 97.6% |
| Cấu hình LLM Judge `openai / gpt-4o-mini`, chạy lại pipeline và commit artifact cho cả nhóm | Duy (reporting), Cường (evaluation) | `data/results/*_metrics.json`, `*_answers.json` có `judge.reasoning` |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Ghép baseline end-to-end, Quality Gate chặn index khi fail | `src/pipelines/phase1.py` | `phase1_report.md`, `baseline_metrics.json` | `python script/run_phase1.py` (exit 0) |
| Ghép luồng corrupt → detect → evaluate → self-heal → so sánh 3 trạng thái | `src/pipelines/corruption_flow.py` | `corruption_report.md` | `python script/run_corruption_flow.py` (exit 0) |
| Cấu hình LLM Judge openai/gpt-4o-mini, chạy lại và commit artifact | `.env` (không commit), `data/` | `data/results/*_metrics.json` | `judge.reasoning` trong `*_answers.json` |

Nêu một output cụ thể mà phần việc của bạn tạo ra hoặc giúp xác minh:

`data/results/self_heal_log.json` cùng dòng console `Triggered=True | strategy=rollback_to_raw_snapshot | healthy after=True`. Output này chứng minh hệ thống tự phát hiện dữ liệu corrupted (Quality Gate fail 4/8, freshness stale 0.4545), tự chọn chiến lược rollback về raw snapshot, và sau khi phục hồi thì dữ liệu khỏe lại (8/8 pass, freshness 0.0417). Collection `papers-repaired` có đúng 24 bản ghi, bằng `papers-baseline`, và console xác nhận `identical to baseline content: True`.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Mỗi thành viên viết một module riêng (ingestion, cleaning, quality, testset, index, corruption, reporting). Nếu không có người ghép, các module có thể đúng khi chạy riêng nhưng sai khi nối với nhau: lệch tên cột, lệch đường dẫn file, hoặc dữ liệu xấu vẫn lọt vào vector store. Nhiệm vụ của tôi là:

1. Ghép tất cả thành hai luồng chạy được bằng một lệnh (Phase 1 và Corruption flow).
2. Đảm bảo dữ liệu fail Quality Gate không bao giờ được index.
3. Làm cho việc phục hồi tự động và idempotent: chạy lại bao nhiêu lần cũng ra cùng kết quả sạch, không cần sửa tay.

### Cách triển khai

- **Phase 1 (`phase1.py`):** fetch (live hoặc snapshot) → clean → chạy Quality Gate + Freshness. Nếu `success=False` thì dừng ngay, không build Chroma. Nếu pass thì index vào `papers-baseline` → sinh test set → trả lời và chấm điểm → ghi `baseline_metrics.json` và `phase1_report.md`.
- **Corruption flow (`corruption_flow.py`):** kiểm tra artifact baseline đã tồn tại (thiếu thì báo lỗi yêu cầu chạy Phase 1) → tiêm 6 lỗi → chạy Quality Gate/Freshness để phát hiện (`Healthy=False`) → index `papers-corrupted` và đánh giá trên cùng test set → gọi self-heal → index `papers-repaired` và đánh giá → sinh báo cáo 3 trạng thái.
- **Self-heal (`self_heal.py`), 3 nhánh:**
  1. Dữ liệu khỏe → không làm gì.
  2. Dữ liệu hỏng → rollback: rebuild từ `data/raw/crossref_records.json` qua đúng hàm cleaning của Phase 1, rồi kiểm tra lại.
  3. Rollback vẫn không khỏe → re-fetch từ Crossref. Nếu vẫn lỗi thì raise `RuntimeError` thay vì im lặng index dữ liệu xấu.

  Mọi quyết định đều ghi vào `self_heal_log.json`.
- **CI:** `script/run_tests.sh` chạy toàn bộ `tests/` với coverage gate 80%; GitHub Actions chạy script này mỗi lần push.

### Input, output và contract

| Thành phần                   | Mô tả |
| ------------------------------ | ----- |
| Input                          | Settings từ `.env`; raw snapshot `data/raw/`; các hàm của ingestion/observability/evaluation/retrieval |
| Output                         | Toàn bộ artifact trong `data/` + 2 báo cáo Markdown |
| Module phụ thuộc             | Mọi module trong `src/` |
| Module sử dụng output        | Báo cáo nhóm, demo CP6 |
| Điều kiện lỗi cần xử lý | Quality Gate fail ở baseline → dừng trước khi index; thiếu artifact baseline khi chạy corruption flow → báo lỗi yêu cầu chạy Phase 1; self-heal không phục hồi được (rollback và re-fetch đều lỗi) → `RuntimeError` |

### Cách xác minh

```bash
python script/run_phase1.py
python script/run_corruption_flow.py
./script/run_tests.sh
```

- **Kết quả mong đợi:** Cả 2 lệnh exit 0; self-heal tự kích hoạt trên dữ liệu corrupted; repaired giống baseline; 3 collection Chroma.
- **Kết quả thực tế:** Exit 0. Console in `Healthy=False -> self-healing will be triggered` và `Triggered=True | strategy=rollback_to_raw_snapshot | healthy after=True`; Chroma có `papers-baseline` (24), `papers-corrupted` (22), `papers-repaired` (24); `./script/run_tests.sh`: 58 passed, coverage 97.6%.
- **Artifact/log:** `data/reports/phase1_report.md`, `data/reports/corruption_report.md`, `data/results/self_heal_log.json`

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Khi dữ liệu bị corrupt, cần chọn cách đưa nó về trạng thái sạch. Yêu cầu của lab là repair phải idempotent và không sửa tay.
- **Các phương án đã cân nhắc:**
  1. Sửa trực tiếp trên DataFrame corrupted: xóa dòng trùng, điền lại summary rỗng, lùi ngày về giá trị cũ…
  2. Luôn re-fetch từ Crossref API.
  3. Rollback: rebuild từ raw snapshot đã lưu ở bước ingestion, chỉ re-fetch khi rollback thất bại.
- **Phương án đã chọn:** Phương án 3, rollback về `data/raw/crossref_records.json` làm chiến lược chính, re-fetch làm dự phòng, và `RuntimeError` khi cả hai đều thất bại.
- **Lý do:**
  - Phương án 1 phải viết một hàm sửa riêng cho từng loại lỗi. Nó không sửa được lỗi mất dữ liệu (5 bài bị drop), và kết quả phụ thuộc vào trạng thái hiện tại nên khó idempotent.
  - Phương án 2 phụ thuộc mạng, có thể gặp `429`, và API có thể trả dữ liệu khác lần trước, nên không so sánh công bằng với baseline được.
  - Raw snapshot được giữ nguyên từ đầu (raw preservation), nên rebuild từ đó qua đúng hàm cleaning luôn cho ra cùng một kết quả.
- **Bằng chứng quyết định phù hợp:** `papers-repaired` có 24 bản ghi và `identical to baseline content: True`; mọi metric của repaired bằng baseline (hit rate 1.0, token F1 1.0, judge accuracy 1.0); Quality 8/8 pass; freshness 0.0417. Có test end-to-end chạy repair nhiều lần và kiểm tra kết quả không đổi. Cả 3 nhánh của self-heal đều có test.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Lần chạy đầu với `LLM_PROVIDER=mock`, `baseline_metrics.json` vẫn có `judge_accuracy` 1.0, và ở trạng thái corrupted là 0.7 (score 3.6), trông như có một LLM judge đang chấm thật. Mở `data/results/baseline_answers.json` thì mọi câu đều có `"reasoning": "Fallback heuristic judge used because the LLM evaluator was unavailable."`.
- **Lệnh hoặc bước tái hiện:** `LLM_PROVIDER=mock python script/run_phase1.py`, sau đó đọc trường `judge.reasoning` trong `baseline_answers.json`.
- **Nguyên nhân gốc:** Mô hình mock (`FakeListChatModel`) không hỗ trợ `with_structured_output`. `_judge_answer` trong `evaluation/metrics.py` bắt exception này và âm thầm chuyển sang heuristic theo Token F1 (F1 ≥ 0.95 → 5 điểm, ≥ 0.5 → 3 điểm, còn lại 1 điểm). Vì vậy "judge" chỉ là Token F1 viết lại dưới dạng khác. Đây cũng là một silent failure ngay trong phần đánh giá.
- **Cách xử lý:** Cấu hình `LLM_PROVIDER=openai`, `LLM_MODEL=gpt-4o-mini` và API key trong `.env` (file này đã gitignore, không commit), rồi chạy lại cả 2 pipeline. Báo cáo nhóm ghi rõ judge nào được dùng.
- **Cách xác minh sau khi sửa:** `judge.reasoning` trong `*_answers.json` giờ là nhận xét do LLM viết. Judge accuracy trên dữ liệu corrupted đổi từ 0.7 (heuristic) sang 0.5–0.6 (gpt-4o-mini). Ví dụ eval_008 trả lời sai năm bị gpt-4o-mini chấm 1/5.
- **Điều học được:** Một metric có giá trị chưa chắc đã được tính đúng cách. Cần kiểm tra metric được sinh ra như thế nào, không chỉ nhìn con số. Code có fallback âm thầm thì phải có tín hiệu để nhận ra khi fallback được dùng.

## 7. Hiểu biết về luồng end-to-end

1. Dữ liệu đi từ Crossref đến vector index như thế nào?
2. Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?
3. Quality checks khác freshness monitoring ở điểm nào trong bài lab?
4. Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?
5. Repair được xem là thành công dựa trên artifact và metric nào?

**Câu trả lời:**

1. **Từ Crossref đến vector index.** `crossref.py` gọi `/works` (có retry khi gặp 429/5xx, lỗi thì fallback về snapshot). Response gốc được lưu nguyên vào `crossref_response.json`, sau đó parse thành `PaperRecord` và lưu `crossref_records.json`. `cleaning.py` bỏ thẻ JATS, chuẩn hóa khoảng trắng, tính `age_days`, khử trùng theo `paper_id`, ghép `text_for_embedding` gồm 5 phần. Quality Gate + Freshness kiểm tra DataFrame, và chỉ khi pass thì `index.py` mới nhúng bằng MiniLM và nạp vào ChromaDB.
2. **Test set và ground-truth IDs.** Mỗi câu hỏi trong `test_set.json` có `ground_truth` (đáp án chuẩn) và `ground_truth_doc_ids` (DOI của bài chứa đáp án). Retrieval hit rate đo xem top-k tài liệu lấy ra có chứa DOI đúng không. Token F1 so câu trả lời với `ground_truth` ở mức từ. LLM Judge (gpt-4o-mini) chấm điểm 1–5 và đúng/sai theo nghĩa.
3. **Quality checks và freshness.** Quality checks (GX 1.x) kiểm tra tính hợp lệ về cấu trúc của từng bản ghi: không null, `paper_id` duy nhất, độ dài title/summary, khoảng `age_days`, số dòng. Freshness đo độ tươi của cả tập dữ liệu: tỉ lệ bài có `age_days > 180` phải ≤ 25%. Một tập có thể pass hết quality checks nhưng vẫn "ôi" vì toàn bài cũ, và ngược lại.
4. **Cùng một test set cho 3 trạng thái.** Nếu đổi câu hỏi thì không biết điểm thay đổi do dữ liệu hay do đề thi. Giữ nguyên test set thì dữ liệu là biến duy nhất thay đổi, nên chênh lệch metric phản ánh đúng tác động của corruption và repair.
5. **Tiêu chí repair thành công.** `papers-repaired` có 24 bản ghi, nội dung giống baseline (`identical to baseline content: True`); `repaired_metrics.json` bằng `baseline_metrics.json` ở mọi chỉ số; `repaired_quality_report.json` 8/8 pass; freshness quay về 0.0417; `self_heal_log.json` ghi `healthy after=True`; và chạy lại repair vẫn cho cùng kết quả.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` | 1.0000 | 0.8000 | 1.0000 | 2/10 câu không lấy được bài đúng, phù hợp với việc 5 bài mới nhất bị drop khỏi index |
| `mean_token_f1`      | 1.0000 | 0.6979 | 1.0000 | Giảm mạnh nhất; ngoài bài bị mất còn do summary bị xóa trắng |
| `judge_accuracy`     | 1.0000 | 0.6000 | 1.0000 | 4/10 câu sai, nhiều hơn số câu miss retrieval, nên có câu tìm đúng bài nhưng nội dung đã hỏng |
| `mean_judge_score`   | 5.0000 | 3.7000 | 5.0000 | Agent vẫn trả lời, không báo lỗi; đây đúng là silent failure |
| Quality checks         | 8/8 Pass | 4/8 Fail | 8/8 Pass | Bắt được duplicate, title bị cắt, summary rỗng, ngày bị làm cũ |
| Freshness status       | Fresh (0.0417) | Stale (0.4545) | Fresh (0.0417) | Drop bài mới + làm cũ ngày đẩy tỉ lệ bài cũ từ 1/24 lên 10/22 |

_Nguồn: `data/results/*_metrics.json`, `data/quality/`, LLM Judge `openai / gpt-4o-mini`._

### Kết luận từ số liệu

1. Corruption làm chất lượng RAG giảm rõ rệt (judge accuracy 1.0 → 0.6, token F1 1.0 → 0.70), nhưng hệ thống không hề báo lỗi. Chỉ Quality Gate (4/8 fail) và Freshness (stale 0.4545) phát hiện ra vấn đề. Điều này cho thấy observability ở tầng dữ liệu là cần thiết, vì không thể trông vào việc agent tự báo sai.
2. Repair bằng rollback về raw snapshot đưa mọi chỉ số về đúng mức baseline, chứng minh việc giữ bản raw và rebuild qua cùng một hàm cleaning đủ để phục hồi hoàn toàn mà không cần sửa tay.

Corruption nào ảnh hưởng rõ nhất và vì sao?

Drop latest records ảnh hưởng rõ nhất. Mất 5 bài thì mọi câu hỏi có `ground_truth_doc_ids` trỏ tới các bài đó đều miss retrieval, không có cách nào trả lời đúng. Đây cũng là nguyên nhân chính kéo freshness sang stale. Blank summary đứng thứ hai: bài vẫn được tìm thấy nhưng không còn nội dung để trả lời câu hỏi dạng summary, nên judge accuracy (0.6) giảm nhiều hơn hit rate (0.8). Nhận định câu nào hỏng do lỗi nào tôi đối chiếu qua `corrupted_answers.json` và `corruption_log.json` (danh sách `paper_id` bị ảnh hưởng).

Kết quả nào khác với kỳ vọng ban đầu?

- Baseline đạt tuyệt đối 1.0 ở mọi chỉ số. Ban đầu tôi nghĩ đây là dấu hiệu pipeline tốt, nhưng thực ra câu hỏi được sinh theo template từ chính dữ liệu và QA trích xuất theo luật, nên baseline gần như chắc chắn đạt điểm tối đa. Con số này chứng minh pipeline đúng, chưa chứng minh chất lượng RAG trên câu hỏi thật.
- Inject noise và truncate title không làm giảm điểm câu nào, vì không trúng bài nào trong test set. Inject noise cũng không bị Quality Gate bắt, do summary chèn rác vẫn đủ dài và không null. Vậy nên 4/8 expectation fail chưa phản ánh đủ cả 6 loại lỗi.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Lỗi dữ liệu là silent failure.** Agent vẫn trả lời trôi chảy trên dữ liệu hỏng, nên phải có gate chặn trước khi index và có metric so sánh với baseline, không thể chờ hệ thống tự báo lỗi.
2. **Raw preservation là nền tảng của repair idempotent.** Giữ nguyên bản raw và mọi bước sau đều là hàm tất định từ raw thì phục hồi chỉ là chạy lại, không cần sửa tay từng lỗi.
3. **Phải kiểm chứng cách một metric được tính, không chỉ đọc con số.** Judge chạy heuristic khi dùng mock nhưng vẫn cho số trông hợp lý. Nếu không đọc `reasoning` thì nhóm đã báo cáo sai bản chất của metric.

### Nếu có thêm thời gian

- Viết thêm câu hỏi test không theo template (diễn đạt khác, hỏi gián tiếp) để baseline phản ánh chất lượng RAG thật, và đảm bảo mỗi loại corruption đều trúng ít nhất một câu hỏi.
- Thêm expectation phát hiện nhiễu (ví dụ regex kiểm tra tỉ lệ ký tự không phải chữ trong summary) để Quality Gate bắt được inject noise.
- Cập nhật `uv.lock` bằng `uv lock` (hiện lockfile chưa có `pytest-cov` được thêm cho CI, nên `uv sync` sẽ thiếu gói này) và cho CI cài bằng `uv sync --locked` để lockfile lệch là fail ngay.
- Chạy thử live mode với Crossref API thật để kiểm chứng cleaning trên dữ liệu không được chuẩn bị sẵn.

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
