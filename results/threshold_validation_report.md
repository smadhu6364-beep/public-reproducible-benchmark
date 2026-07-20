# Threshold & embedding-model validation report

- Embedding model: `all-MiniLM-L6-v2` (match.py's `EMBEDDING_MODEL`)
- Current default `MATCH_THRESHOLD` in match.py: **0.45** (was 0.5 before this validation; see match.py comment)
- Labeled pairs: 17 unambiguous (drive the recommendation) + 4 hard/borderline (reported only)
- Primary metric: cosine on **description+mitigation** (what match.py embeds). Description-only shown as a sensitivity.

> **Scope caveat (important):** the generated side of each pair is hand-written to emulate model output; no real model output exists yet (no API keys). This is a realistic labeled sample, not a harvested one. The recommendation below is therefore 'validated against a hand-built labeled set,' which is stronger than an unvalidated default but should be revisited once a real experiment run exists. See `analysis/threshold_validation_pairs.json` `_meta`.

## 1. Similarity distributions (unambiguous pairs, desc+mitigation)

- **Should-match** pairs (n=8): min=0.5227, mean=0.663, max=0.8118
- **Should-NOT-match** pairs (n=9): min=0.2014, mean=0.277, max=0.4206

The two classes are **cleanly separable** on this set: the highest should-not-match similarity (0.4206) is below the lowest should-match similarity (0.5227). Any threshold in that gap separates them perfectly; the gap midpoint is **0.4717**.

## 2. Threshold sweep (unambiguous pairs, desc+mitigation)

| threshold | TP | FN | FP | TN | sensitivity | specificity | precision | F1 | accuracy | Youden J |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.30 | 8 | 0 | 3 | 6 | 1.00 | 0.67 | 0.73 | 0.84 | 0.82 | 0.67 |
| 0.35 | 8 | 0 | 1 | 8 | 1.00 | 0.89 | 0.89 | 0.94 | 0.94 | 0.89 |
| 0.40 | 8 | 0 | 1 | 8 | 1.00 | 0.89 | 0.89 | 0.94 | 0.94 | 0.89 |
| 0.45 | 8 | 0 | 0 | 9 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| 0.50 | 8 | 0 | 0 | 9 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| 0.55 | 7 | 1 | 0 | 9 | 0.88 | 1.00 | 1.00 | 0.93 | 0.94 | 0.88 |
| 0.60 | 7 | 1 | 0 | 9 | 0.88 | 1.00 | 1.00 | 0.93 | 0.94 | 0.88 |
| 0.65 | 5 | 3 | 0 | 9 | 0.62 | 1.00 | 1.00 | 0.77 | 0.82 | 0.62 |
| 0.70 | 2 | 6 | 0 | 9 | 0.25 | 1.00 | 1.00 | 0.40 | 0.65 | 0.25 |

- Best by Youden's J: threshold **0.45** (J=1.0). Best by F1: threshold **0.45** (F1=1.0).

## 3. Sensitivity: description-only (mitigation dropped)

- Should-match (n=8): mean=0.5933, min=0.4481, max=0.7593
- Should-NOT-match (n=9): mean=0.2507, min=0.1457, max=0.3791
- Classes are **separable** on description-only; gap midpoint 0.4136. Best Youden threshold 0.40.

## 4. Hard / borderline cases (NOT used to pick the threshold)

These are genuine granularity-mismatch judgment calls. They show where realistic borderline pairs land relative to the recommended threshold.

| pair | register | human label | desc+mit sim | rationale |
|---|---|---|---|---|
| WB-HARD-01 | WB:P-STP-YouthEmployment (real pilot generation) | match (medium) | 0.4187 | Granularity mismatch: the specific 'long delivery chain / many partners' risk is arguably a facet of the broad 'institut |
| WB-HARD-02 | WB:P-STP-YouthEmployment (real pilot generation) | match (medium) | 0.4355 | Partial overlap: the pilot's payment-flow risk maps onto the ground-truth mitigation clause about 'the grants/stipends p |
| WB-HARD-03 | WB:P-STP-YouthEmployment (real pilot generation) | no-match (medium) | 0.3649 | Shared vocabulary (procurement, civil works, Príncipe center) but different risk framing: pilot frames it as SCHEDULE ri |
| XPROJ-HARD-01 | cross-project (UK HyNet vs UK Padeswood - legitimately similar) | match (high) | 0.5123 | Two DIFFERENT projects but a GENUINELY similar underlying risk (HMG cost/cross-chain exposure in the same HyNet CCUS clu |

## 5. Per-pair similarities (all pairs)

| pair | tier | expected | desc+mit | desc-only |
|---|---|---|---|---|
| WB-POS-01 | clear_positive | match | 0.7001 | 0.7385 |
| WB-POS-02 | clear_positive | match | 0.644 | 0.6274 |
| WB-POS-03 | clear_positive | match | 0.5227 | 0.4481 |
| WB-POS-04 | clear_positive | match | 0.8118 | 0.7593 |
| WB-NEG-01 | clear_negative | no-match | 0.2207 | 0.1891 |
| WB-NEG-02 | clear_negative | no-match | 0.3252 | 0.3155 |
| WB-NEG-03 | clear_negative | no-match | 0.2014 | 0.1758 |
| WB-NEG-04 | clear_negative | no-match | 0.2438 | 0.1457 |
| UK-POS-01 | clear_positive | match | 0.681 | 0.5631 |
| UK-POS-02 | clear_positive | match | 0.6635 | 0.5739 |
| UK-POS-03 | clear_positive | match | 0.6548 | 0.5273 |
| UK-POS-04 | clear_positive | match | 0.6263 | 0.5086 |
| UK-NEG-01 | clear_negative | no-match | 0.4206 | 0.3791 |
| UK-NEG-02 | clear_negative | no-match | 0.2285 | 0.2252 |
| UK-NEG-03 | clear_negative | no-match | 0.3348 | 0.3785 |
| XPROJ-NEG-01 | clear_negative | no-match | 0.2546 | 0.2903 |
| XPROJ-NEG-02 | clear_negative | no-match | 0.2634 | 0.1575 |
| WB-HARD-01 | hard_case | match | 0.4187 | 0.3834 |
| WB-HARD-02 | hard_case | match | 0.4355 | 0.2743 |
| WB-HARD-03 | hard_case | no-match | 0.3649 | 0.2959 |
| XPROJ-HARD-01 | hard_case | match | 0.5123 | 0.4527 |

## 6. End-to-end check: real match.py on the STP pilot generation

`match_project()` run on `scratch\pilot_STP_zeroshot.json` (6 generated risks) vs P-STP-YouthEmployment ground truth (4 risks), at each threshold:

| threshold | matches | of gen | of gt | matched pairs (gen->gt, sim) |
|---|---|---|---|---|
| 0.30 | 4 | 6 | 4 | R02->R03 (0.503); R06->R01 (0.499); R03->R04 (0.447); R05->R02 (0.373) |
| 0.35 | 4 | 6 | 4 | R02->R03 (0.503); R06->R01 (0.499); R03->R04 (0.447); R05->R02 (0.373) |
| 0.40 | 3 | 6 | 4 | R02->R03 (0.503); R06->R01 (0.499); R03->R04 (0.447) |
| 0.45 | 2 | 6 | 4 | R02->R03 (0.503); R06->R01 (0.499) |
| 0.50 | 1 | 6 | 4 | R02->R03 (0.503) |
| 0.55 | 0 | 6 | 4 | - |
| 0.60 | 0 | 6 | 4 | - |
| 0.65 | 0 | 6 | 4 | - |
| 0.70 | 0 | 6 | 4 | - |

This is the real granularity-mismatch signal in action: the pilot generated specific *implementation* risks while the ground truth lists broad *SORT* categories, so even a well-tuned threshold recovers only the pairs that genuinely correspond. Low match counts here are partly a real property of the task, not purely a threshold artifact - which is exactly why the recommendation is anchored on the hand-labeled clear pairs, not on this count.
