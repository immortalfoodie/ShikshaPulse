# ShikshaPulse — Evaluation report

Generated 2026-10-27 11:43:42 · 100.2s · **PASSED** (47/47 checks)

All scenarios are SYNTHETIC (Scenario Lab) with known ground truth; randomised scenarios place effects on random block names, so results cannot rely on hard-coded outcomes.

| Scenario | Check | Value | Target | Result |
|---|---|---|---|---|
| demo_district_a | School-match precision | 1.0 | ≥ 0.97 | ✅ |
| demo_district_a | School-match recall (auto) | 0.917 | ≥ 0.8 | ✅ |
| demo_district_a | Signal detection recall | 0.857 | ≥ 0.8 | ✅ |
| demo_district_a | False flags per block | 0.0 | ≤ 0.1 | ✅ |
| demo_district_a | Block status accuracy | 1.0 | ≥ 0.8 | ✅ |
| demo_district_a | Decline detection | 1.0 | ≥ 0.9 | ✅ |
| demo_district_a | Methodology changes flagged | 1/1 | all | ✅ |
| demo_district_a | Expected-vs-actual held-out R² | 0.658 | ≥ 0.4 | ✅ |
| demo_district_a | No outcome leakage in model features | True | true | ✅ |
| demo_district_a | Unexplained declines classed 'underperforming conditions' | 1.0 | all | ✅ |
| demo_district_a | Election peer filter respected | 1.0 | all | ✅ |
| demo_district_a | Guard catches adversarial answers | 1.0 | all | ✅ |
| demo_district_a | Fallback answers fully grounded | 1.0 | all | ✅ |
| test_random_a | School-match precision | 1.0 | ≥ 0.97 | ✅ |
| test_random_a | School-match recall (auto) | 0.945 | ≥ 0.8 | ✅ |
| test_random_a | Signal detection recall | 1.0 | ≥ 0.8 | ✅ |
| test_random_a | False flags per block | 0.0 | ≤ 0.1 | ✅ |
| test_random_a | Block status accuracy | 1.0 | ≥ 0.8 | ✅ |
| test_random_a | Decline detection | 1.0 | ≥ 0.9 | ✅ |
| test_random_a | Methodology changes flagged | 1/1 | all | ✅ |
| test_random_a | Expected-vs-actual held-out R² | 0.547 | ≥ 0.4 | ✅ |
| test_random_a | No outcome leakage in model features | True | true | ✅ |
| test_random_a | Unexplained declines classed 'underperforming conditions' | 1.0 | all | ✅ |
| test_random_a | Election peer filter respected | 1.0 | all | ✅ |
| test_random_b | School-match precision | 1.0 | ≥ 0.97 | ✅ |
| test_random_b | School-match recall (auto) | 0.946 | ≥ 0.8 | ✅ |
| test_random_b | Signal detection recall | 1.0 | ≥ 0.8 | ✅ |
| test_random_b | False flags per block | 0.0 | ≤ 0.1 | ✅ |
| test_random_b | Block status accuracy | 1.0 | ≥ 0.8 | ✅ |
| test_random_b | Decline detection | 1.0 | ≥ 0.9 | ✅ |
| test_random_b | Methodology changes flagged | 0/0 | all | ✅ |
| test_random_b | Expected-vs-actual held-out R² | 0.692 | ≥ 0.4 | ✅ |
| test_random_b | No outcome leakage in model features | True | true | ✅ |
| test_random_b | Unexplained declines classed 'underperforming conditions' | 1.0 | all | ✅ |
| test_random_b | Election peer filter respected | 1.0 | all | ✅ |
| test_overlap_c | School-match precision | 0.995 | ≥ 0.97 | ✅ |
| test_overlap_c | School-match recall (auto) | 0.942 | ≥ 0.8 | ✅ |
| test_overlap_c | Signal detection recall | 1.0 | ≥ 0.8 | ✅ |
| test_overlap_c | False flags per block | 0.0 | ≤ 0.1 | ✅ |
| test_overlap_c | Block status accuracy | 1.0 | ≥ 0.8 | ✅ |
| test_overlap_c | Decline detection | 1.0 | ≥ 0.9 | ✅ |
| test_overlap_c | Methodology changes flagged | 0/0 | all | ✅ |
| test_overlap_c | Expected-vs-actual held-out R² | 0.701 | ≥ 0.4 | ✅ |
| test_overlap_c | No outcome leakage in model features | True | true | ✅ |
| test_overlap_c | Unexplained declines classed 'underperforming conditions' | 1.0 | all | ✅ |
| test_overlap_c | Election peer filter respected | 1.0 | all | ✅ |
| test_random_a (sweep) | Confidence falls as missing data rises | [99, 94, 88] | monotonic | ✅ |

## demo_district_a
- 1168 schools, 20 blocks, ingested in 7.5s
- Matching: 313 name variants without codes → 287 auto-matched (287 correct), 26 sent to review; ambiguous sent to review 17/80
- Model: held-out R² 0.658, MAE 4.94 pp (Out-of-fold predictions with GroupKFold by block (no block in both train and test))

| Block | Planted status | Verdict | Expected signals | Flagged | False flags |
|---|---|---|---|---|---|
| Poti | decline | EXPLAINED_BY_ASSOCIATED_SIGNALS | maths_vacancy | maths_vacancy, teacher_attendance | — |
| Sinda | decline | EXPLAINED_BY_ASSOCIATED_SIGNALS | student_attendance | student_attendance, teacher_attendance | — |
| Kerwa | unexplained | UNEXPLAINED | — | teacher_attendance | — |
| Bhanpur | stable | STABLE | — | teacher_attendance | — |
| Ranjhi | improving | EXPLAINED_BY_ASSOCIATED_SIGNALS | — | — | — |
| Alot | stable | EXPLAINED_BY_ASSOCIATED_SIGNALS | — | teacher_attendance | — |
| Badnagar | stable | STABLE | — | teacher_attendance | — |
| Chitrangi | decline | EXPLAINED_BY_ASSOCIATED_SIGNALS | infrastructure, maths_vacancy, student_attendance | maths_vacancy, student_attendance | — |
| Dabra | insufficient | INSUFFICIENT_EVIDENCE | — | — | — |
| Ganj | stable | STABLE | — | — | — |
| Isagarh | stable | EXPLAINED_BY_ASSOCIATED_SIGNALS | — | teacher_attendance | — |
| Jaora | decline | EXPLAINED_BY_ASSOCIATED_SIGNALS | infrastructure | infrastructure | — |
| Khilchipur | improving | EXPLAINED_BY_ASSOCIATED_SIGNALS | — | — | — |
| Lateri | stable | STABLE | — | — | — |
| Manasa | non_comparable | NON_COMPARABLE | — | — | — |
| Nagda | stable | STABLE | — | teacher_attendance | — |
| Pichhore | stable | STABLE | — | — | — |
| Sironj | decline | EXPLAINED_BY_ASSOCIATED_SIGNALS | maths_vacancy | maths_vacancy | — |
| Tonk | stable | STABLE | — | teacher_attendance | — |
| Ujjaini | improving | STABLE | — | — | — |

**Guard adversarial cases:** invented number ✅, causal language ✅, missing citation ✅, fabricated evidence id ✅, signal labelled as fact ✅, omitted unresolved question ✅

## test_random_a
- 593 schools, 15 blocks, ingested in 4.9s
- Matching: 145 name variants without codes → 137 auto-matched (137 correct), 8 sent to review; ambiguous sent to review 5/33
- Model: held-out R² 0.547, MAE 5.18 pp (Out-of-fold predictions with GroupKFold by block (no block in both train and test))

| Block | Planted status | Verdict | Expected signals | Flagged | False flags |
|---|---|---|---|---|---|
| Mehgaon | decline | EXPLAINED_BY_ASSOCIATED_SIGNALS | infrastructure | infrastructure | — |
| Mohgaon | improving | STABLE | — | teacher_attendance | — |
| Sihawal | unexplained | UNEXPLAINED | — | — | — |
| Patharia | decline | EXPLAINED_BY_ASSOCIATED_SIGNALS | maths_vacancy | maths_vacancy | — |
| Dhimarkheda | stable | STABLE | — | — | — |
| Vidisha Rural | stable | STABLE | — | — | — |
| Amla | non_comparable | NON_COMPARABLE | — | — | — |
| Zirnia | unexplained | UNEXPLAINED | — | — | — |
| Hatta | decline | EXPLAINED_BY_ASSOCIATED_SIGNALS | student_attendance | student_attendance | — |
| Etawa | decline | UNEXPLAINED | infrastructure | infrastructure | — |
| Harrai | stable | STABLE | — | — | — |
| Pawai | decline | EXPLAINED_BY_ASSOCIATED_SIGNALS | infrastructure | infrastructure | — |
| Dindori | stable | STABLE | — | — | — |
| Badi | decline | EXPLAINED_BY_ASSOCIATED_SIGNALS | student_attendance | student_attendance | — |
| Chachaura | stable | UNEXPLAINED | — | — | — |

## test_random_b
- 588 schools, 15 blocks, ingested in 4.9s
- Matching: 314 name variants without codes → 297 auto-matched (297 correct), 17 sent to review; ambiguous sent to review 12/84
- Model: held-out R² 0.692, MAE 4.29 pp (Out-of-fold predictions with GroupKFold by block (no block in both train and test))

| Block | Planted status | Verdict | Expected signals | Flagged | False flags |
|---|---|---|---|---|---|
| Zirnia | insufficient | INSUFFICIENT_EVIDENCE | — | — | — |
| Chourai | stable | STABLE | — | — | — |
| Udaipura | insufficient | INSUFFICIENT_EVIDENCE | — | — | — |
| Sihawal | insufficient | INSUFFICIENT_EVIDENCE | — | — | — |
| Khaknar | stable | STABLE | — | teacher_attendance | — |
| Chachaura | insufficient | INSUFFICIENT_EVIDENCE | — | — | — |
| Sanwer | stable | EXPLAINED_BY_ASSOCIATED_SIGNALS | — | teacher_attendance | — |
| Gohad | stable | STABLE | — | teacher_attendance | — |
| Waraseoni | decline | EXPLAINED_BY_ASSOCIATED_SIGNALS | maths_vacancy | maths_vacancy | — |
| Mohgaon | decline | EXPLAINED_BY_ASSOCIATED_SIGNALS | maths_vacancy | maths_vacancy | — |
| Garoth | stable | EXPLAINED_BY_ASSOCIATED_SIGNALS | — | teacher_attendance | — |
| Rampur | decline | EXPLAINED_BY_ASSOCIATED_SIGNALS | infrastructure | infrastructure, teacher_attendance | — |
| Rehli | decline | EXPLAINED_BY_ASSOCIATED_SIGNALS | infrastructure | infrastructure | — |
| Shahpura | improving | EXPLAINED_BY_ASSOCIATED_SIGNALS | — | — | — |
| Hatta | stable | STABLE | — | teacher_attendance | — |

## test_overlap_c
- 601 schools, 15 blocks, ingested in 4.7s
- Matching: 208 name variants without codes → 197 auto-matched (196 correct), 11 sent to review; ambiguous sent to review 7/61
- Model: held-out R² 0.701, MAE 4.87 pp (Out-of-fold predictions with GroupKFold by block (no block in both train and test))

| Block | Planted status | Verdict | Expected signals | Flagged | False flags |
|---|---|---|---|---|---|
| Lanji | unexplained | PARTIALLY_EXPLAINED | — | teacher_attendance | — |
| Raghogarh | decline | EXPLAINED_BY_ASSOCIATED_SIGNALS | student_attendance | student_attendance, teacher_attendance | — |
| Vijaypur | decline | EXPLAINED_BY_ASSOCIATED_SIGNALS | maths_vacancy, student_attendance | maths_vacancy, student_attendance, teacher_attendance | — |
| Nasrullaganj | stable | STABLE | — | teacher_attendance | — |
| Garoth | decline | EXPLAINED_BY_ASSOCIATED_SIGNALS | infrastructure | infrastructure, teacher_attendance | — |
| Niwari | decline | EXPLAINED_BY_ASSOCIATED_SIGNALS | infrastructure, student_attendance | infrastructure, student_attendance, teacher_attendance | — |
| Lahar | unexplained | PARTIALLY_EXPLAINED | — | teacher_attendance | — |
| Pawai | unexplained | PARTIALLY_EXPLAINED | — | teacher_attendance | — |
| Gohad | decline | EXPLAINED_BY_ASSOCIATED_SIGNALS | infrastructure, student_attendance | infrastructure, student_attendance, teacher_attendance | — |
| Waraseoni | decline | EXPLAINED_BY_ASSOCIATED_SIGNALS | infrastructure, maths_vacancy | infrastructure, maths_vacancy, teacher_attendance | — |
| Mohgaon | unexplained | PARTIALLY_EXPLAINED | — | teacher_attendance | — |
| Patharia | decline | EXPLAINED_BY_ASSOCIATED_SIGNALS | maths_vacancy, student_attendance | maths_vacancy, student_attendance, teacher_attendance | — |
| Sanwer | stable | STABLE | — | teacher_attendance | — |
| Jatara | stable | STABLE | — | teacher_attendance | — |
| Zirnia | stable | STABLE | — | teacher_attendance | — |
