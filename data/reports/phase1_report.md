# Phase 1 Report - Baseline Pipeline

_Generated at 2026-09-25T08:22:55.936902+00:00 by `script/run_phase1.py`._

## 1. Source & Lineage

| Field | Value |
| --- | --- |
| source_api | Crossref REST API |
| mode | offline snapshot |
| query | agentic retrieval augmented generation large language model |
| filter | from-pub-date:2026-03-29,has-abstract:true |
| raw_records | 24 |
| clean_rows | 24 |
| run_date | 2026-09-25 |
| embedding_model | sentence-transformers/all-MiniLM-L6-v2 |
| collection | papers-baseline |
| llm_provider | openai |
| top_k | 4 |

## 2. Retrieval & Answer Quality (Baseline)

| Metric | Value |
| --- | --- |
| Retrieval Hit Rate | 1.0000 |
| Mean Token F1 | 1.0000 |
| LLM Judge Accuracy | 1.0000 |
| Mean Judge Score (1-5) | 5 |
| Samples | 10 |

### Breakdown by question type

| Question type | Hit Rate | Mean Token F1 |
| --- | --- | --- |
| authors | 1.0000 | 1.0000 |
| categories | 1.0000 | 1.0000 |
| date | 1.0000 | 1.0000 |
| multi_hop | 1.0000 | 1.0000 |
| summary | 1.0000 | 1.0000 |

## 3. Data Quality Gate (Great Expectations 1.x)

Overall: **PASS** - 8/8 expectations passed (great_expectations 1.23.1).

| Expectation | Column | Observed | Result |
| --- | --- | --- | --- |
| expect_table_row_count_to_be_between | (table) | 24 | PASS |
| expect_column_values_to_not_be_null | paper_id | 0 unexpected / 24 | PASS |
| expect_column_values_to_be_unique | paper_id | 0 unexpected / 24 | PASS |
| expect_column_values_to_not_be_null | title | 0 unexpected / 24 | PASS |
| expect_column_value_lengths_to_be_between | title | 0 unexpected / 24 | PASS |
| expect_column_values_to_not_be_null | text_for_embedding | 0 unexpected / 24 | PASS |
| expect_column_value_lengths_to_be_between | summary | 0 unexpected / 24 | PASS |
| expect_column_values_to_be_between | age_days | 1 unexpected / 24 | PASS |

## 4. Freshness SLA

Rule: stale = `age_days > 180`; the dataset is fresh when stale ratio <= 0.25.

| Field | Value |
| --- | --- |
| total_rows | 24 |
| latest_published | 2026-07-22 |
| oldest_published | 2026-03-28 |
| stale_rows | 1 |
| stale_ratio | 0.0417 |
| threshold_days | 180 |
| is_fresh | PASS |
