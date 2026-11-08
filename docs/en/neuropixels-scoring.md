# Neuropixels scoring rules

Project technical specification · neuropixels-score/0.1 · 2026-11-08 · Expert review pending

## 1 Scope

This score assesses the selected continuous-voltage checks. AP and LF/LFP are separate; it is not a sorted-unit score. Preset: neuropixels-voltage-score/0.1; recipe: neuropixels-basic-recipe/0.2; aggregation: project-weighted/1.2. The 30/70 weights are initial project choices, not established consensus or expert-calibrated thresholds. Detector parameters are unchanged.

## 2 Default components

| Component | Weight | Evidence |
| --- | ---: | --- |
| Numerical validity | 30% | M03 NaN/Inf samples divided by all assessed channel-samples |
| Channel status | 70% | Union of fully constant channels and eligible AP SpikeInterface outliers within each window |

LF/LFP uses fully constant windows only. AP method inclusion must be explicit in the report. PSD, line-neighborhood power, RMS, peak-to-peak, events, execution coverage and unimplemented unit/drift/synchronization metrics do not contribute.

Weights are editable in Advanced settings → Scoring and weights. Zero means deliberately excluded. Underlying constant/AP scores remain available but carry no separate default weight. Both configuration and aggregation reject simultaneous weights for the grouped component and its evidence, or two separately weighted members of the same family.

## 3 Formulas and deduplication

Numerical validity = 100 × (1 − non-finite samples / all assessed channel-samples). Require complete unique channel identities and consistent finite/non-finite counts. Finite constants are not penalized here. Pool sample counts across windows before scoring.

A fully constant channel has the same finite value throughout an analysis window. Short quantization repeats do not qualify. This check requires all selected samples to be finite and the constant summary to be complete; otherwise it is unassessed, and numerical validity records the non-finite evidence separately.

AP outliers are the original SpikeInterface MAD or std candidates under the [check rules](/en/standards/neuropixels-checks). They are alternative detector settings, not two scoring components.

Within each window, union candidate source-channel IDs from valid constant and AP checks. Channel status = 100 × (1 − Σ(unique candidate channels × window duration) / Σ(assessed channels × window duration)). Verify identical source identities, channel sets and time ranges before combining. Overlap counts once; different candidates remain included. The minimum of method scores cannot replace the actual union.

The denominator is channel-window time, not exact contaminated time. Fully constant detection depends on window boundaries; shorter constant fragments are measurements only. Comparisons require the same window policy.

## 4 Missing evidence and overall score

A source method enters the whole-record union only when every processing window has valid scores and identities. If AP fails or is restricted in one window, exclude it from the whole-record union, retaining all saved candidates for review. A fully valid constant check can still support channel status; label that reduced scope explicitly.

Overall score = Σ(valid component × configured weight) / Σ(valid configured weights). An unavailable component has effective weight zero; normalize the other effective shares. Never impute zero or 100. A measured zero is valid and remains weighted. If all components are unavailable, all weights are zero, coverage is incomplete or source verification fails, no overall score is produced.

## 5 Example

For 100 channels, ten constant candidates and twenty AP candidates with five shared identities yield 25 unique candidates and channel status 75. Numerical validity 100 gives 100 × 30% + 75 × 70% = 82.5. Do not count thirty candidate channels.

If numerical validity is 98 and channel status is unavailable, effective shares become 100%/0% and the total is 98, explicitly limited to numerical validity. Both unavailable means no total.

## 6 Reporting and versions

Results show total, two components, effective shares and findings; underlying method scores are expandable. Record parameters, actual included/excluded methods, windows and source evidence. Old runs are not retroactively assigned these scores. A score of 100 only means no candidates under the valid selected checks.

Compare only matching bands, processing history, selected channels, methods, available evidence, weights and windows. Same-file workflow comparisons assess configuration changes, not independent biological samples. Detector sources remain in the [specification](/en/standards/neuropixels) and [check rules](/en/standards/neuropixels-checks); these aggregation rules are project-defined.
