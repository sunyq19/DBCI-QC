# Project scoring rules

Project trial · `project-weighted/1.1` · 7 November 2026 · Not expert-approved

## Definition and defaults

Component = `100 × (1 − candidate amount / assessed amount)`.
Project total = `sum(component × weight) / sum(weights)`.

Scalp EEG defaults to integrity, line interference and high-frequency bursts, with weight 1 each. Every optional component defaults to 0. ECoG, sEEG and Neuropixels have no default total and do not inherit scalp thresholds. Eligible FieldTrip or SpikeInterface results may be explicitly selected for project scoring.

Weights are finite values from 0 to 100. A positive weight requires the method and its parent module to be selected. All-zero weights disable the total. A missing positive-weight component or incomplete recording coverage prevents a total; weights are never silently redistributed. Missing values are neither zero nor perfect scores.

## Score outputs

| Method | Candidate amount / assessed amount |
| --- | --- |
| Integrity | Nonfinite or constant channel-samples / checked channel-samples |
| Thomson line noise | Flagged channel-windows, deduplicated across frequencies / assessed channel-windows |
| HF bursts | Candidate channel-seconds / valid channel-seconds |
| PREP nonspatial | Union of candidate channels / assessed channels |
| MNE amplitude | Two outputs: candidate channels / channels; union of global intervals / duration |
| MNE muscle | Flagged finite-score samples / finite-score samples |
| MNE bridges | Distinct channels involved in candidate pairs / channels |
| MNE LOF | Candidate channels / channels |
| AutoReject global | Flagged fixed epochs / evaluated epochs |
| Gnosis line length | Candidate channels / channels |
| Gnosis artifacts, low-band and high-band | Per-channel union of candidate intervals / actual channel-duration |
| Gnosis PSD deviation | Candidate channels / channels evaluated on retained spectral input |
| FASTER | Union of native candidate channels / channels |
| FieldTrip z-value | Union of candidate intervals / checked duration |
| SpikeInterface | Native noise-labelled channels / assessed channels |

Seventeen methods supply eighteen score outputs. Scoring capability does not imply that a particular recording satisfies a method's prerequisites. Each native detector and its parameters remain unchanged.

PSD, power, amplitude, spectrum fits, auxiliary event evidence, processing-change measurements and unvalidated population reference ranges are not directly converted to quality scores. Unimplemented methods, dataset checks and visualizations do not receive signal-quality scores.

## Whole-record pooling

Pool actual numerators and denominators for sample, epoch, window and interval outputs. For channel-only decisions, weight each analysis block by its actual analyzed duration; this produces channel-block-seconds, not exact artifact duration. Gnosis PSD uses the retained spectral-input duration. Unused tails and invalid filter edges are not counted as passes. A missing block leaves the method's whole-record score unavailable.

Methods can detect the same event, so optional components are not independent evidence. The total does not replace review of individual channels and times.

## Contract and reporting

`method-score/1` includes IDs, status, value, candidate and assessed amounts, unit, scope, reason, source artifacts and applicable parameters. Methods expose `can_output_score` and their output definitions in the catalog. M08 only aggregates.

Results save `method_scores`, `project_score` and `method-scores.json`; EEG reports also expose `report_view.score`. Weights are frozen in the plan. HTML and PDF use the same score data; extra components have dedicated PDF pages. Archived v1.0 and v0.2 reports retain their original definitions.

Only compare matched versions, methods, weights, parameters, channels, references, durations, bandwidth and processing histories. A perfect score means no candidates were detected by the selected checks, not that the recording is clinically suitable. Filtered-away frequency bands are not scored as clean. Threshold accuracy, project weights and acceptance limits remain subject to independent validation.
