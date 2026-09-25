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
| Bonus B3 – test evaluation/retrieval | `tests/test_evaluation_retrieval.py` (13 test: test set, corruption, Chroma, QA, metrics) | DataFrame sạch | pytest pass | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Cung cấp `corruption_log.json` có danh sách `paper_id` bị ảnh hưởng theo từng loại lỗi | Duy (`observability/reporting.py`) | Báo cáo corruption liệt kê được câu nào giảm điểm do lỗi nào |
| Chuyển manifest của Chroma sang đường dẫn tương đối | Tú (tích hợp, chạy pipeline trên máy khác nhau) | Index chạy được sau khi clone repo sang máy khác |
| Dùng `refresh_derived_columns` của cleaning sau khi tiêm lỗi | Đức (`ingestion/cleaning.py`) | Dữ liệu corrupted giữ đúng schema 16 cột, index và Quality Gate chạy được |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Test set 5 dạng × 2 câu, có multi_hop liên ngành | `src/evaluation/testset.py` | `data/eval/test_set.json` | Lệnh kiểm tra CP2 bước 1 |
| `build_from_clean`, `semantic_search`, manifest đường dẫn tương đối, QA multi-hop | `src/retrieval/index.py`, `src/retrieval/qa.py` | 3 collection Chroma | Lệnh kiểm tra CP2 bước 2 |
| 6 kịch bản corruption seed 42 + log | `src/ingestion/corruption.py` | `corruption_log.json`, `papers_clean_corrupted.*` | Lệnh kiểm tra bước 7 trong Guide |

Nêu một output cụ thể mà phần việc của bạn tạo ra hoặc giúp xác minh:

`data/results/corruption_log.json` ghi lại 6 loại lỗi đã tiêm với seed 42, kèm danh sách `paper_id` bị ảnh hưởng ở mỗi loại. Kết quả là tập corrupted còn 22 dòng (24 − 5 bài mới nhất bị drop + 3 dòng nhân bản). Vì seed cố định, chạy lại luôn tiêm lỗi vào đúng các bài đó, nên có thể đối chiếu chính xác câu hỏi nào trong `test_set.json` bị ảnh hưởng bởi lỗi nào.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Muốn chứng minh dữ liệu xấu làm hỏng RAG, cần ba thứ: một bộ đề thi có đáp án và DOI chuẩn để đo; một vector index và QA agent để trả lời; và một cách tiêm lỗi có kiểm soát, tái lập được, để so sánh công bằng giữa baseline, corrupted và repaired. Ba phần này đều thuộc phạm vi của tôi.

### Cách triển khai

- **Test set:** sinh 10 câu từ DataFrame sạch, gồm 5 dạng × 2 câu: `summary`, `authors`, `date`, `categories` theo Guide, và thêm `multi_hop` ghép hai bài thuộc hai chuyên ngành khác nhau. Mỗi câu có `ground_truth` và `ground_truth_doc_ids`. `load_or_create_test_set` chỉ sinh test set một lần rồi dùng lại file, để cả 3 trạng thái dùng chung một bộ câu hỏi.
- **Retrieval:** `build_from_clean` nhúng `text_for_embedding` bằng MiniLM và nạp vào Chroma theo tên collection (`papers-baseline`, `papers-corrupted`, `papers-repaired`). `semantic_search` trả top-k tài liệu. Manifest lưu đường dẫn tương đối để repo chạy được trên máy khác.
- **QA:** lấy tiêu đề trong câu hỏi, tìm tài liệu liên quan, trích câu trả lời theo dạng câu hỏi. Câu multi-hop gom thông tin từ hai tài liệu.
- **Corruption:** 6 kịch bản dùng `random` với seed 42: drop 20% bài mới nhất, blank summary, inject noise, truncate title (< 8 ký tự), stale date (−365 ngày), duplicate rows. Sau đó gọi `refresh_derived_columns` để cột phái sinh khớp nội dung mới, và ghi log chi tiết.

### Input, output và contract

| Thành phần                   | Mô tả |
| ------------------------------ | ----- |
| Input                          | DataFrame sạch (schema của cleaning); câu hỏi dạng `'<title>'` |
| Output                         | `test_set.json` (`id, type, question_type, question, ground_truth, ground_truth_doc_ids`); DataFrame corrupted + log |
| Module phụ thuộc             | `ingestion/cleaning.py` (`refresh_derived_columns`), `core/` |
| Module sử dụng output        | `evaluation/metrics.py`, `pipelines/phase1.py`, `pipelines/corruption_flow.py`, `retrieval/agent.py` |
| Điều kiện lỗi cần xử lý | Ít hơn 10 tài liệu; title chứa dấu `'`; không tìm được bài ghép multi_hop; collection chưa tồn tại |

### Cách xác minh

```bash
pytest tests/test_evaluation_retrieval.py
python -c "from core.config import load_settings; from evaluation.testset import load_or_create_test_set; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); ts=load_or_create_test_set(df, s.paths.test_set_json); print(f'Test set gồm {len(ts.samples)} câu hỏi')"
python -c "from core.config import load_settings; from retrieval.index import LocalEmbeddingIndex; s=load_settings(); idx=LocalEmbeddingIndex(s, collection_name='papers-baseline'); idx.build_from_clean(); res=idx.semantic_search('machine learning', top_k=2); print(f'Tìm thấy {len(res)} tài liệu liên quan')"
python -c "from core.config import load_settings; from ingestion.corruption import corrupt_clean_dataframe; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); c=corrupt_clean_dataframe(df, s.paths.corruption_log); print(f'Corrupted {len(c)} dòng')"
```

- **Kết quả mong đợi:** 10 câu hỏi; 2 tài liệu; log ghi đủ 6 loại lỗi.
- **Kết quả thực tế:** `tests/test_evaluation_retrieval.py` 13 passed; `Test set gồm 10 câu hỏi`, `Tìm thấy 2 tài liệu liên quan`, `Corrupted 22 dòng` (24 − 5 dropped + 3 duplicate).
- **Artifact/log:** `data/eval/test_set.json`, `data/results/corruption_log.json`

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Corruption cần ngẫu nhiên để giống lỗi thực tế, nhưng báo cáo phải so sánh 3 trạng thái và giải thích được câu nào giảm điểm vì lỗi nào.
- **Các phương án đã cân nhắc:**
  1. Ngẫu nhiên hoàn toàn: mỗi lần chạy tiêm lỗi vào các bài khác nhau.
  2. Chọn tay cố định một danh sách `paper_id` để tiêm lỗi.
  3. Ngẫu nhiên với seed cố định (42), ghi log `paper_id` bị ảnh hưởng.
- **Phương án đã chọn:** Phương án 3, seed 42 kèm `corruption_log.json` chi tiết.
- **Lý do:**
  - Phương án 1 làm metric corrupted thay đổi mỗi lần chạy, không tái lập được kết quả trong báo cáo và demo.
  - Phương án 2 gắn chặt với snapshot hiện tại, đổi dữ liệu là hỏng, và dễ vô tình chọn đúng những bài có trong test set.
  - Seed cố định giữ được tính ngẫu nhiên trong cách chọn nhưng cho kết quả tái lập. Log giúp truy vết từ lỗi đến câu hỏi bị ảnh hưởng.
- **Bằng chứng quyết định phù hợp:** Chạy lại nhiều lần đều ra 22 dòng và cùng metric corrupted tất định (hit rate 0.8, token F1 0.6979); riêng judge accuracy dao động 0.5–0.6 do LLM judge, không do corruption; test trong `tests/test_evaluation_retrieval.py` kiểm tra hai lần gọi với cùng seed cho cùng kết quả.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Yêu cầu checkpoint của nhóm ghi kịch bản stale date là "Đổi ngày xuất bản về 5 năm trước", nhưng `corruption_log.json` ghi `"Published date shifted back 365 days (35% of rows)."`. Câu eval_008 trả lời `2025-05-20`, tức chỉ lùi 1 năm.
- **Lệnh hoặc bước tái hiện:** `python script/run_corruption_flow.py`, sau đó đọc mục `stale_date` trong `data/results/corruption_log.json`.
- **Nguyên nhân gốc:** Hai tài liệu lệch nhau: `docs/Guide.md` (bước 7) ghi lùi 365 ngày, còn yêu cầu checkpoint ghi 5 năm. Tôi làm theo Guide trước (`STALE_SHIFT_DAYS = 365`) mà không đối chiếu với yêu cầu checkpoint.
- **Cách xử lý:** Đổi thành `STALE_SHIFT_YEARS = 5` và dùng `pd.DateOffset(years=5)` thay cho số ngày cố định. `age_days` được cộng thêm đúng số ngày chênh lệch thực tế `(original - shifted).dt.days`, vì 5 năm có thể chứa năm nhuận. Chạy lại corruption flow và cập nhật báo cáo.
- **Cách xác minh sau khi sửa:** Log ghi `shifted back 5 years`; eval_008 giờ trả lời `2021-05-20`; freshness corrupted vẫn stale (0.4545); test `test_corruption_effects` kiểm tra mọi dòng stale có `age_days > 5 * 365`.
- **Điều học được:** Khi có nhiều nguồn yêu cầu, phải đối chiếu chúng trước khi code và chốt một nguồn chuẩn. Tham số của kịch bản corruption nên đặt thành hằng số có tên, để đổi yêu cầu chỉ cần sửa một chỗ.

## 7. Hiểu biết về luồng end-to-end

1. Dữ liệu đi từ Crossref đến vector index như thế nào?
2. Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?
3. Quality checks khác freshness monitoring ở điểm nào trong bài lab?
4. Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?
5. Repair được xem là thành công dựa trên artifact và metric nào?

**Câu trả lời:**

1. Crossref trả JSON, được lưu nguyên ở `data/raw/`. Ingestion parse thành `PaperRecord`, cleaning tạo DataFrame có `text_for_embedding`. Sau khi qua Quality Gate và Freshness, phần của tôi (`build_from_clean`) nhúng cột đó bằng MiniLM và lưu vector cùng metadata (DOI, title…) vào ChromaDB. Mỗi trạng thái dữ liệu có collection riêng để so sánh.
2. `ground_truth_doc_ids` cho phép chấm retrieval độc lập với câu trả lời: nếu DOI đúng nằm trong top-k thì là hit. `ground_truth` dùng để chấm câu trả lời bằng Token F1 (độ trùng từ) và LLM Judge (đúng về nghĩa). Kết hợp hai tầng này mới biết lỗi xảy ra ở bước tìm kiếm hay bước trả lời.
3. Quality checks kiểm tra tính hợp lệ của dữ liệu ở cấp bản ghi và cột. Freshness đo độ mới của toàn bộ kho. Trong 6 lỗi tôi tiêm, duplicate, truncate title, blank summary và stale date bị Quality Gate bắt; drop latest records và stale date làm freshness chuyển sang stale.
4. Test set là biến kiểm soát. Tôi dùng `load_or_create_test_set` để sinh một lần và tái sử dụng file, đảm bảo 3 lần đánh giá dùng đúng 10 câu hỏi. Nếu sinh lại từ DataFrame corrupted thì câu hỏi sẽ tự khớp với dữ liệu hỏng, và sự suy giảm sẽ bị che mất.
5. Repair thành công khi `papers-repaired` có 24 tài liệu như baseline, `repaired_metrics.json` bằng baseline ở mọi chỉ số, và các câu từng bị giảm điểm trong `corrupted_answers.json` được trả lời đúng lại.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` | 1.0000 | 0.8000 | 1.0000 | 2/10 câu mất tài liệu nguồn trong index |
| `mean_token_f1`      | 1.0000 | 0.6979 | 1.0000 | Ngoài câu miss, câu dạng summary bị ảnh hưởng bởi blank summary |
| `judge_accuracy`     | 1.0000 | 0.6000 | 1.0000 | 4 câu sai, trong đó có câu retrieval vẫn đúng |
| `mean_judge_score`   | 5.0000 | 3.7000 | 5.0000 | Giảm nhưng không về 0, vì 6/10 câu không bị ảnh hưởng |
| Quality checks         | 8/8 Pass | 4/8 Fail | 8/8 Pass | Khớp với 4/6 kịch bản tôi tiêm |
| Freshness status       | Fresh (0.0417) | Stale (0.4545) | Fresh (0.0417) | Do drop bài mới và stale date |

_Nguồn: `data/results/*_metrics.json`, `data/quality/`, LLM Judge `openai / gpt-4o-mini`._

### Kết luận từ số liệu

1. Mức giảm của metric phụ thuộc vào việc lỗi có trúng tài liệu trong test set hay không. Không phải cứ tiêm lỗi là điểm giảm, nên cần đối chiếu `corruption_log.json` với `ground_truth_doc_ids` để giải thích đúng.
2. Judge accuracy (0.6) giảm nhiều hơn hit rate (0.8), cho thấy corruption gây hai loại hỏng: mất tài liệu (retrieval miss) và còn tài liệu nhưng nội dung hỏng (trả lời sai dù tìm đúng).

Corruption nào ảnh hưởng rõ nhất và vì sao?

Drop latest records có ảnh hưởng rõ nhất, vì nó xóa hẳn tài liệu nguồn. Câu hỏi về bài bị drop không thể đạt hit, kéo hit rate xuống 0.8. Blank summary xếp sau: tài liệu vẫn được tìm thấy nhưng không còn nội dung để trả lời câu dạng summary. Đây là lý do judge accuracy thấp hơn hit rate.

Kết quả nào khác với kỳ vọng ban đầu?

- Baseline đạt 1.0 ở mọi chỉ số. Nguyên nhân là câu hỏi sinh theo template từ chính dữ liệu, và QA trích xuất theo luật nên luôn khớp đáp án. Kết quả này chứng minh pipeline hoạt động đúng, nhưng chưa phản ánh chất lượng RAG với câu hỏi tự nhiên.
- Inject noise và truncate title không làm giảm điểm câu nào, vì các bài bị tiêm hai lỗi này (theo seed 42) không nằm trong `ground_truth_doc_ids` của test set. Hai lỗi này có tồn tại (truncate title bị Quality Gate bắt) nhưng test set chưa đủ rộng để đo tác động của chúng.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Một bộ đánh giá chỉ đo được những gì nó bao phủ. Test set 10 câu không trúng bài bị tiêm noise thì không thể kết luận noise vô hại.
2. Tính tái lập (seed cố định, test set dùng lại, log chi tiết) quan trọng ngang tính đúng. Không tái lập được thì không so sánh và không giải thích được kết quả.
3. Cần tách đánh giá retrieval và đánh giá câu trả lời để biết pipeline hỏng ở tầng nào.

### Nếu có thêm thời gian

- Thiết kế corruption có chủ đích, đảm bảo mỗi loại lỗi trúng ít nhất một bài trong test set, để đo được tác động của cả 6 loại.
- Thêm câu hỏi diễn đạt tự nhiên (không chứa nguyên tiêu đề) và dùng LLM để trả lời thay vì trích xuất theo luật, để baseline phản ánh chất lượng RAG thật.
- Tăng test set lên nhiều hơn 10 câu và báo cáo khoảng dao động, vì với 10 câu, mỗi câu sai làm metric lệch tới 10%.

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
