# Corruption Report - Baseline vs Corrupted vs Repaired

_Generated at 2026-09-25T08:36:24.407375+00:00 by `script/run_corruption_flow.py`. All three states are evaluated on the same test set._

## 1. RAG Metrics (3 states)

| Metric | Baseline | Corrupted | Repaired | Delta corrupted | Delta repaired |
| --- | --- | --- | --- | --- | --- |
| Retrieval Hit Rate | 1.0000 | 0.8000 | 1.0000 | -0.2000 | +0.0000 |
| Mean Token F1 | 1.0000 | 0.6979 | 1.0000 | -0.3021 | +0.0000 |
| LLM Judge Accuracy | 1.0000 | 0.6000 | 1.0000 | -0.4000 | +0.0000 |
| Mean Judge Score (1-5) | 5 | 3.7000 | 5 | -1.3000 | +0.0000 |

## 2. Observability Signals

| Signal | Baseline | Corrupted | Repaired |
| --- | --- | --- | --- |
| Row count | 24 | 22 | 24 |
| Quality Gate (GX) | PASS | FAIL | PASS |
| Failed expectations | 0 | 4 | 0 |
| Latest published | 2026-07-22 | 2026-06-12 | 2026-07-22 |
| Stale ratio | 0.0417 | 0.4545 | 0.0417 |
| Freshness is_fresh | PASS | FAIL | PASS |

## 3. Injected Corruptions

Seed `42` - rows 24 -> 22.

| Corruption | Rows | Description |
| --- | --- | --- |
| drop_latest_records | 5 | Dropped the 5 most recently published papers (20%). |
| blank_summary | 3 | Summary replaced with an empty string. |
| inject_noise | 3 | Garbage tokens and shuffled characters injected into the summary (propagates to text_for_embedding). |
| truncate_title | 3 | Title truncated to 7 characters. |
| stale_date | 7 | Published date shifted back 5 years (35% of rows). |
| duplicate_rows | 3 | Rows appended a second time (duplicate paper_id). |

## 4. Impact by Question Type (Hit Rate / Token F1)

| Question type | baseline | corrupted | repaired |
| --- | --- | --- | --- |
| authors | 1.00 / 1.00 | 0.50 / 0.50 | 1.00 / 1.00 |
| categories | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 |
| date | 1.00 / 1.00 | 1.00 / 0.50 | 1.00 / 1.00 |
| multi_hop | 1.00 / 1.00 | 1.00 / 0.62 | 1.00 / 1.00 |
| summary | 1.00 / 1.00 | 0.50 / 0.87 | 1.00 / 1.00 |

### Questions that regressed on corrupted data

| ID | Type | Baseline F1 | Corrupted F1 | Corrupted hit | Corrupted answer (truncated) |
| --- | --- | --- | --- | --- | --- |
| eval_001 | summary | 1.0000 | 0.7407 | FAIL | An extended empirical study on tatic benchmarks fail to capture domain drift in  |
| eval_002 | authors | 1.0000 | 0.0000 | FAIL | Anh Tran, Quoc Pham |
| eval_005 | multi_hop | 1.0000 | 0.6667 | PASS | Multi-Agent Systems, Artificial Intelligence |
| eval_008 | date | 1.0000 | 0.0000 | PASS | 2021-05-20 |
| eval_010 | multi_hop | 1.0000 | 0.5714 | PASS | Natural Language Processing, Evaluation Methodology |

## 5. Analysis

- **Retrieval Hit Rate**: baseline 1.0000 -> corrupted 0.8000 (-0.2000) -> repaired 1.0000; fully recovered.
- **Mean Token F1**: baseline 1.0000 -> corrupted 0.6979 (-0.3021) -> repaired 1.0000; fully recovered.
- **LLM Judge Accuracy**: baseline 1.0000 -> corrupted 0.6000 (-0.4000) -> repaired 1.0000; fully recovered.
- **Mean Judge Score (1-5)**: baseline 5.0000 -> corrupted 3.7000 (-1.3000) -> repaired 5.0000; fully recovered.
- **Quality Gate** on corrupted data: FAIL (4 failed: expect_column_values_to_be_unique[paper_id], expect_column_value_lengths_to_be_between[title], expect_column_value_lengths_to_be_between[summary], expect_column_values_to_be_between[age_days]). After repair: PASS.
- **Freshness SLA**: corrupted stale ratio 0.4545 (is_fresh=False, latest=2026-06-12) vs repaired 0.0417 (is_fresh=True, latest=2026-07-22).
- **Silent failure**: the RAG layer raised no error on the corrupted index and still answered every question; only the Quality Gate and freshness monitor surfaced the problem. In production the gate must block indexing (Phase 1 does this) - here it runs in audit mode so the degradation can be measured.

## 6. Repair Strategy

Repair does not patch the corrupted table. It re-runs the deterministic cleaning step from the preserved raw snapshot (`data/raw/crossref_records.json`) and rebuilds a fresh Chroma collection (`papers-repaired`). Because the input and transformation are both deterministic, running repair any number of times yields the same clean dataset (idempotent), with no manual edits.
