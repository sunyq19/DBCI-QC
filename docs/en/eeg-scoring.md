# EEG basic QC scoring rules

Project trial · `eeg-basic-screen/0.2` · 31 October 2026

[EEG specification](/en/standards) · [Check terms](/en/standards/eeg-checks) · [Report requirements](/en/standards/eeg-report) · [M08](/en/standards/modules/M08)

## 1 Purpose and scope

This 0–100 index describes the burden and channel concentration of candidates detected by three specified checks in continuous scalp EEG. Higher scores mean less detected burden. It is not a percentage of usable data, clinical normality, downstream performance or external-standard compliance.

The scope is the selected channels and time of the selected signal stream. Other checks remain separately reported; omission from the score is not a pass.

## 2 Measurements

Detection determines candidates. Scoring aggregates that evidence without changing detector thresholds or fitting the current dataset's score distribution.

| Component | Candidate amount B per channel | Valid amount D per channel | Evidence |
| --- | --- | --- | --- |
| Integrity | Union of nonfinite and constant samples, computed as D minus finite nonconstant samples | Assessed samples | M03_continuity.json |
| Line noise | Windows flagged at any target frequency, deduplicated within channel and window | Computed windows | M04_spectral.json |
| High-frequency bursts | Duration of merged candidate intervals | Method-valid duration after exclusions and edges | M06_muscle.json |

Overlapping line windows are not artifact duration. High-frequency candidates are not confirmed muscle activity. Amplitude and other original measurements remain available; this index does not grade amplitude severity after a detector has already flagged a window.

## 3 Equations and interpretation

For component j and channel c, let `p[j,c] = B[j,c]/D[j,c]`, with `D > 0` and `0 ≤ B ≤ D`. Channel identity shall be unique and evidence complete. Missing evidence is not zero burden. The channel-level display is `100 × (1 − p[j,c])`.

For N equally weighted selected channels:

```text
R[j] = sqrt((p[j,1]^2 + ... + p[j,N]^2) / N)
S[j] = 100 × (1 − R[j])
Q = min(S[integrity], S[line_noise], S[hf_burst])
```

R is the RMS channel burden. At equal mean burden, concentration in fewer channels increases R. Exponent 2 and minimum-component aggregation are explicit project design choices, not externally mandated or expert-calibrated risk weights.

The total expresses the weakest of the three assessed dimensions. Perfect dimensions cannot compensate for a problem, and overlapping detections are not cumulatively deducted. Independent problems in separate dimensions are not added either; improving a nonlimiting dimension may leave the total unchanged. Keep all components visible.

| Score | Exact meaning |
| --- | --- |
| 100 | All required evidence is complete and no scored candidates were detected |
| 80 | The worst component has RMS channel burden 0.20 |
| 60 | The worst component has RMS channel burden 0.40 |
| 0 | At least one component flags all its valid amount in every selected channel |
| Unassessed | A complete, verifiable total cannot be computed; neither zero nor full marks |

No pass/fail or excellent/good grade is assigned. A score of 80 does not mean 80% usable data.

## 4 Whole-record pooling and missing evidence

`eeg-pooling/2` first sums native B and D across windows within each stable channel identity, then computes channel burdens, component RMS and the minimum component. Do not average window scores or RMS values. Short final windows use their true denominators.

All required components must be valid in every selected channel and window. Failed source verification, source gaps, unfinished windows, missing evidence or zero valid denominators withhold the total; completed component evidence and coverage remain visible. No missing-item weight redistribution is allowed.

Execution coverage differs from method-valid duration. Detector adaptation, multiple comparisons and edge exclusion depend on window boundaries; redetecting a signal after splitting it need not reproduce a single long-window result.

## 5 Fixed examples

Other dimensions are 100. These are arithmetic examples, not clinical labels.

| Line-window candidate distribution | Mean channel burden | Component and total |
| --- | --- | --- |
| Four channels, no candidates | 0% | 100 |
| Four channels, 25% each | 25% | 75 |
| One of four channels, 100% | 25% | 50 |
| One of 63 channels, 100% | About 1.59% | About 87.40 |
| All channels, all windows | 100% | 0 |

Channel count affects the relative burden of a local problem. Compare matching channel selections, references, methods, parameters, bandwidths and analysis scopes. Removing a problematic channel creates a new configuration, not a replacement for the original result.

## 6 Reporting and versioning

Retain score and aggregation versions, selection, effective ranges, detector settings and source fingerprints. Components retain native numerators and denominators, RMS and mean channel burden, pooled unflagged fraction, affected count and worst channel. The total identifies limiting components.

Implementation: `src/ephys_qc/scoring.py`; current score: `report_view.score`; channel details: `report_view.local_quality`. Generic legacy `score.value=null` still means that no calibrated cross-modality score is available.

Recomputed historical views shall identify previous and current versions through `score_revision`, without overwriting frozen artifacts. v0.1 arithmetic-mean scores and v0.2 scores shall not be ranked together. The original equation remains in `docs/archive/eeg-scoring-v0.1.md`.

## 7 Basis and validation

[PREP](https://www.frontiersin.org/journals/neuroinformatics/articles/10.3389/fninf.2015.00016/full), Detecting noisy or outlier channels, supports multiple channel-quality criteria. [HAPPE](https://www.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2018.00097/full), HAPPE processing report, supports separately reported channel and data-retention metrics. Neither prescribes this RMS/minimum formula; HAPPE post-cleaning metrics are not direct raw-data-quality scores. See [method evidence](/en/standards/eeg-evidence).

Tests shall cover clean/extreme cases, nonincreasing scores with increasing detected burden, concentration, order invariance, missingness, unequal windows, overlap and preservation of frozen evidence. Signal-injection checks shall be distinguished from arithmetic tests: monotonic scoring does not prove that adaptive detectors respond monotonically to raw noise amplitude.

Independent expert agreement, detection sensitivity/specificity and application relevance remain to be validated. This is a reproducible project trial index, not a calibrated universal EEG quality standard.
