# Project scoring rules

Project trial rules · `project-weighted/1.1` · 7 November 2026 · Not expert-reviewed

[Technical specification](/en/standards) · [Check entries](/en/standards/eeg-checks) · [Report requirements](/en/standards/eeg-report) · [M08 Component assessment](/en/standards/modules/M08)

## 1 Scope

Scores summarize candidate fractions from the selected methods. They are not clinical acceptance decisions, industry standards or percentages of usable data. **Scalp EEG includes only signal integrity, line interference and high-frequency bursts by default, counted equally at approximately 33.3% of the total each.** Other methods may provide component scores but are excluded from the total until explicitly selected by the project.

ECoG, sEEG and Neuropixels do not inherit scalp EEG thresholds and have no default overall score. Integrated FieldTrip jump detection for ECoG/sEEG and SpikeInterface noisy-channel detection for Neuropixels may be selected for project scoring when their prerequisites are met. These scores describe the corresponding method's results, not comprehensive quality assessment of that modality.

## 2 Equations and configuration

```text
Component = 100 × (1 − candidate amount / assessed amount)
Total = Σ(component × share of total), with all shares summing to 100%
```

Internal weights are finite, nonnegative values from 0 to 100; they do not need to sum to 100. Results display percentages as a share of the total, with equal settings described as “N checks counted equally”. Raw relative weights remain in advanced settings and traceability data. Zero excludes a component; all-zero weights show component results without a total. A positive weight also requires the corresponding method and parent module to be enabled.

For component scores of 100, 60 and 95 with shares of 25%, 50% and 25%, the total is `100×25% + 60×50% + 95×25% = 78.75`. Internal relative weights are 1, 2 and 1; scaling all weights by the same factor changes neither the shares nor the total. Weights are saved with the plan, parameters and report. Changes require the plan to be checked again and do not automatically start computation.

**Uncomputed results, execution failures and missing valid denominators shall not become scores of 0 or 100.** A missing positive-weight result leaves the total null with a reason; its weight is neither lowered nor redistributed. Missing zero-weight results do not prevent scoring other checks. Missing checks, unassessed channels and incomplete time ranges remain visible in the report.

## 3 Score output catalogue

Each method declares `can_output_score`. A module may contain several methods, and one method may provide several outputs: MNE amplitude detection, for example, provides separate channel and interval components. M08 only aggregates and is not weighted again as another component.

| Module | Scoring method / output | Candidate amount / assessed amount | Included by default |
| --- | --- | --- | --- |
| M03 | Signal integrity | Union of nonfinite or constant channel-samples / all checked channel-samples | Approximately 33.3% |
| M04 | Line interference | Channel-windows flagged at one or more target frequencies / assessed channel-windows, deduplicated across frequencies | Approximately 33.3% |
| M06 | High-frequency bursts | Per-channel candidate interval duration / detector-valid channel-duration | Approximately 33.3% |
| M05 | PREP nonspatial candidates | Distinct channels flagged by any nonspatial component / assessed channels | No; optional |
| M03 | MNE amplitude channel candidates | Native bad-channel candidates / assessed channels | No; optional |
| M03 | MNE amplitude interval candidates | Union of global candidate intervals / assessed duration | No; optional |
| M06 | MNE high-frequency artifacts | Finite-score samples within candidate intervals / finite-score samples | No; optional |
| M05 | Channels involved in MNE bridges | Distinct channels in candidate pairs / assessed channels | No; optional |
| M05 | MNE LOF | Native candidate channels / assessed channels | No; optional |
| M03 | AutoReject global threshold | Fixed epochs exceeding the threshold / evaluated epochs | No; optional |
| M05 | Gnosis line length | Native candidate channels / assessed channels | No; optional |
| M06 | Gnosis artifact intervals | Per-channel duration after merging overlapping intervals / actual analyzed channel-duration | No; optional |
| M06 | Gnosis low-frequency anomalies | Same denominator rule, using the native low-frequency detector results | No; optional |
| M06 | Gnosis high-frequency anomalies | Same denominator rule, using the native high-frequency detector results | No; optional |
| M05 | Gnosis PSD deviation | Candidate channels / channels actually included in spectral comparison | No; optional |
| M05 | FASTER | Union of native component candidate channels / assessed channels | No; optional |
| M06 | FieldTrip jumps | Union of candidate intervals on the original timeline / assessed duration | No; optional |
| M05 | SpikeInterface noisy channels | Channels labelled `noise` by the native method / assessed channels | No; optional |

Seventeen integrated methods provide eighteen score outputs. Scoring capability does not mean that the current input meets a method's execution requirements. The planner still checks sampling rate, duration, reference groups, segments and runtime dependencies. All PREP comparison-group thresholds must be available; otherwise, an absence of candidates cannot be treated as all channels being normal.

Gnosis source: [GnosisNeuroDynamicSE](https://github.com/Gnosis-Neurodynamics/GnosisNeuroDynamicSE). Its methods preprocess a declared analysis copy and call the upstream functions to generate candidates. Scores are standardized outputs added by this project's adapter, not an official Gnosis overall score. When PSD comparison uses retained segments after artifact rejection, reports retain the actual selected segments and effective duration. Insufficient data for spectral estimation produce no score.

## 4 Outputs not scored directly

Welch PSD, spectral fits, band power and amplitude are not themselves quality measures. The population applicability of Gnosis reference distributions is unconfirmed; values outside a reference range do not automatically establish poor quality. Before/after changes from ASR, CleanLine or Zapline+ are not the original data's contamination fraction.

Auxiliary event-locked evidence, event checks, reading and planning, dataset consistency and visualizations continue to provide evidence. They declare `can_output_score=false` when no independent quality definition and valid denominator exist. Unimplemented methods cannot be scored. Dataset structure results are not added to signal scores.

## 5 Whole-record aggregation

1. For sample, epoch, channel-window and interval-duration outputs, pool candidate and assessed amounts across analysis blocks before scoring. Do not directly average window scores or convert overlapping line-noise windows into contaminated duration.
2. For methods returning only channel candidates, compute each block's candidate-channel fraction and weight blocks by their actual analyzed duration. The stored unit is `channel_block_seconds`. It describes channel-candidate burden across blocks, **not exact abnormal duration**.
3. PSD methods use only retained spectral-input duration as the weight. AutoReject does not count unused final samples as passes; MNE high-frequency detection does not count invalid filter edges as passes.
4. If a method lacks a valid result in any scheduled block, its whole-record component is unavailable. Source gaps, unexecuted windows or failed source verification withhold the whole-record total. Method-effective scope and whole-record execution coverage are recorded separately.

Different detectors may flag the same problem; a weighted mean does not add independent evidence. Optional methods are excluded by default, and projects should state their selected methods and reasons for the weights. Overall scores shall not hide local abnormalities: candidate channels, times and original measurements remain in the report.

## 6 Interface and traceability

Each scoring output uses `method-score/1` and includes at least:

- `id`, `method_id`, `module_id` and `contract_version`;
- `status`, `value`, `candidate_amount`, `assessed_amount` and `unit`;
- `scope`, `reason`, `source_artifacts`, and applicable parameter and preprocessing information.

New runs save outputs in method artifacts, `result.method_scores` and `method-scores.json`. `result.project_score` stores the run's weights and weighted result; EEG reports also expose `report_view.score`. Missing positive-weight outputs remain explicit. HTML, the workbench and PDF use the same rules, display checks actually included in the total first, and list other available component results separately. PDF tables paginate automatically without compressing or omitting components.

`project-weighted/1.0` and the earlier `eeg-basic-screen/0.2` retain their original definitions; historical records are not silently converted. The v1.0 archive is `docs/archive/project-scoring-v1.0.md`. An explicit revision to a new version shall retain the original report and revision explanation.

## 7 Comparability and calibration

Compare scores only when rule versions, scoring components, weights, detection parameters, selected channels, references, durations, frequency bands and processing states are comparable. The same EEG modality or disease label alone does not establish comparability.

Previously cleaned data may produce no candidates and receive high scores. A score of 100 only means that the selected methods found no candidates; it does not establish interference-free original acquisition. A target frequency band removed by filtering shall not receive a perfect “no line noise” score. No acceptance threshold is set, and severity after detection is not scored. Detector accuracy and agreement between scores and expert judgments still require independent validation.
