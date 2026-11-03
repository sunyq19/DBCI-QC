# EEG QC report requirements

Project specification · Version eeg-report/1.4 · 31 October 2026

[Scalp EEG specification](/en/standards) · [Check rules](/en/standards/eeg-checks) · [Scoring rules](/en/standards/eeg-scoring) · [Sources and basis](/en/standards/eeg-evidence) · [Back to workbench](/)

## 1 Scope and reporting principles

This document specifies content and traceability requirements for basic technical QC reports on human continuous scalp EEG. Reports shall describe checks actually executed in the run. They do not replace clinical diagnosis, authorization for a data use or external standards certification.

The main report should remain concise; detailed methods, parameters and evidence may be expandable or linked. Six parts shall be identifiable: recording overview, coverage and applicability, individual evidence, candidates and waveforms, methods and sources, and human review and limitations.

“Required” means recording an information item or its missing state, not inventing a non-empty value. “Conditionally required” means required when the relevant method executes or finding occurs. Not run, failed, insufficient conditions and completed with zero candidates shall remain distinct.

## 2 Recording overview

### 2.1 Required content

| Item | Requirement | Current structured location |
| --- | --- | --- |
| Recording and run identity | Distinguish the input recording, its revision and this run; retain a traceable plan identity | `plan_id` and `input_lineage` in `artifacts/plan.json`; job directory and frozen request |
| Provenance and files | Primary and necessary companion files, format and SHA-256; explicitly unknown source version or original/derived status | `source_sha256`, `source_files`, `input_provenance`, `input_data_usage`, `input_lineage` in `result.json`; `artifacts/M01_input.json` |
| Signal object and modality | Identify selected signal object and modality provenance; format does not establish modality | `input_modality`, `input_metadata` in `result.json`; NWB also has `source_signal` |
| Species and assessment scope | State whether provenance supports human scalp EEG scope; unknown shall not default to human | `eeg_assessment.population_confirmation` records that runtime does not capture complete scope confirmation; full semantics are in the field dictionary |
| Channels and sampling | Separate stored, selected and method-effective channels; sampling rate in Hz, actual sample count, units and calibration basis | `streams` in `artifacts/M01_input.json`; `recording`, `channels` in `artifacts/M02_selection.json`; method artifacts |
| Time and continuity | Native clock, actual boundaries, selected stream and continuous segment; distinguish input duration and analysis duration | `recording`, `qc_config.selection` in `result.json`; M01 `clock`, `streams`; M02 `selection`, `recording` |
| Reference and processing context | Known acquisition/current reference, comparison groups, filter and derivation history; restrictions where provenance is insufficient | Frozen `input_metadata`, `qc_config`; M02 `comparison_groups`, `processing_applied`; source documentation |

`processing_applied=[]` only states that no additional processing was applied during this read stage; it does not establish that the source file was never filtered, re-referenced or cleaned. `reference_channels` stores ECG/EOG/EMG auxiliary roles, not the EEG acquisition reference electrode.

### 2.2 Context

Where sources provide age, disease, medication, wake/sleep or task information, reports shall retain original values, provenance and scope. Unknown shall remain unknown. Age shall include units, reference origin and time context; interval states shall not be replaced by a whole-file label.

The [field dictionary](/en/standards/fields) defines complete semantics. Runtime still uses existing context fields such as `disease`, `age_group` and `task`; the new provenance and confirmation structure is not integrated in full. Existing tags do not establish verified species, age or clinical context. Missing context does not automatically block reliable technical measurements, but shall constrain relevant interpretation.

## 3 Coverage and applicability

### 3.1 Required content

Reports shall distinguish input extent, requested extent, actual analysis extent and displayed extent, including at least:

- Window or whole-record mode, selected stream, original channel identities, sample bounds, actual seconds and sampling rate.
- Checks actually executed, prerequisites, effective frequency bands and effective channel/time ranges.
- Not selected, insufficient, failed and partially assessed items with specific reasons.
- Source gaps, uncovered tails or windows and invalid-sample ranges that constrain interpretation.

Window evidence is in `artifacts/M02_selection.json`, `result.json.modules` and method artifacts. Whole-record evidence is in `artifacts/coverage.json`, `artifacts/window-results.json` and individual window results.

### 3.2 Interpreting coverage

Whole-record coverage shall use its declared denominator and distinguish available source samples, gaps, completed, partially assessed, failed and unexecuted ranges. A completed window may still contain method-level non-assessment; window status shall not establish that every check assessed every sample.

Coverage describes execution extent, not the proportion of acceptable data. Without validated deduplication across methods and windows, a report shall not produce an “all-artifact fraction” or unified bad duration. Original candidates, windows and overlaps shall be retained.

## 4 Individual evidence

### 4.1 Required structure for each check

| Content | Requirement |
| --- | --- |
| Stable identity | Check ID, title, catalogue version and mapped module |
| Applicability | Verifiable prerequisites, restrictions and missing-information actions |
| Execution | Actual module and method status; planned readiness shall not be treated as execution completion |
| Measurements | Original values, units, computational scope, windows, effective denominators and parameters |
| Decision criteria | Threshold value or computation, type, source and actual activation state |
| Evidence | Method artifact, field or entry location, original channel and time coordinates |
| Interpretation limits | Distinguish measurement, candidate and reviewed conclusion; identify unvalidated uses |

Mapping catalogue entries to module execution status does not establish acceptance for each entry. Different methods in a module may complete, be restricted or fail separately. Their statuses and evidence shall remain accessible.

### 4.2 Check entries and evidence files

Paths below are relative to a job's `artifacts/` directory. A file exists only when the relevant step produced it. Missing files shall be explained through status, not replaced by empty evidence that implies completion.

| Check | Module | Main method artifact | Essential content |
| --- | --- | --- | --- |
| EEG-001 Files, provenance and structure | M01 | `M01_input.json` | Source-member fingerprints, reader, streams, calibration and structure warnings |
| EEG-002 Information, reference and scope | M02 | `M02_selection.json`, `plan.json` | Actual selection, channel identities, comparison groups, native units and frozen configuration |
| EEG-003 Non-finite values, constants and endpoints | M03 | `M03_continuity.json` | Candidate type, duration and tolerance, original localization and endpoint prerequisites |
| EEG-004 Welch PSD | M04 | `M04_spectral.json` | Frequencies, power density, units, window function and actual estimation parameters |
| EEG-005 Narrow-band line-frequency indicators | M04 | `line_noise` in `M04_spectral.json` | Observed bands, windows, comparison statistics, candidates and non-assessment status |
| EEG-006 Spectral models and alpha descriptions | M04 | `parameterization` and related spectral descriptions in `M04_spectral.json` | Fit band, model and fit status; absent physiological peaks do not establish bad quality |
| EEG-007 Non-spatial bad-channel candidates | M05 | `M05_bad_channels.json` | Groups, effective channels, threshold activation, individual measurements and candidate reasons |
| EEG-008 Auxiliary event-locked indicators | M06 | `M06_auxiliary_events.json` | ECG/EOG auxiliary status, events and locked evidence; missing-channel or epoch reasons |
| EEG-009 High-frequency activity indicators | M06 | `M06_muscle.json` | Effective band, high-frequency candidates, EMG support and integrity protection |
| EEG-010 Annotation and time checks | M07 | `M07_annotations.json` | Annotation type, time mapping, bounds/coverage and whether labels are quality ground truth |
| EEG-011 Individual evidence and coverage | M08 | `M08_assessment.json`; whole-record also has `coverage.json` | Module statuses, non-assessment reasons, source consistency and uncalibrated score |
| EEG-012 Reporting, traceability and review | M09 | `report.html`, `waveform_selection.json`; job-root `result.json`, `reviews.json` | Run evidence, display scope, human decisions and separate versions |

Optional extensions also produce `Mxx_<extension_id>.json` and shall record actual backend and method versions. Python reimplementations, upstream source calls and Octave compatibility execution shall be distinguished, not collectively described as validated equivalents. Extension candidates do not redefine the basic check entries.

### 4.3 Values and statuses

Zero candidates only means that declared rules produced no candidates within the assessed scope. Uncomputed or non-finite values, absent effective denominators and unestablished scores shall be null with status or reason. Unknown booleans shall not become false; unavailable annotations shall not become confirmed absence of events.

`completed`, `partial`, `skipped` and `failed` are execution statuses, not quality grades. Method-level states such as `computed`, `no_events` and missing conditions shall be retained, not overwritten by module summaries. Counts shall distinguish channels, channel pairs, events, intervals and fixed windows.

## 5 Candidates and waveforms

### Project trial score

The current version is `eeg-basic-screen/0.2`; definitions, equations, missing-data rules and examples are maintained in [EEG scoring rules](/en/standards/eeg-scoring).

For each channel calculate invalid/constant sample burden, flagged line-window burden and high-frequency candidate-time burden. Each component is `100 × (1 − RMS of channel burdens)`; the total is the minimum of the three components. All selected channels and required components must be assessed. Missing evidence receives no credit or replacement weights.

Retain component numerators, denominators, RMS and mean channel burdens, worst channel and assessed count. Keep the raw pooled unflagged fraction distinct from the score. Additional checks such as ADC limits, reference-group comparisons and auxiliary timing remain separately reported. No industry acceptance threshold or application success probability is assigned.

The score is stored in `report_view.score`, separately from legacy generic `score.value=null`. New runs freeze the current score. A revised view of a historical run shall identify the old score and recalculation version without rewriting evidence. Do not rank different versions together.

### Candidate display

When candidates exist, conditionally required fields are: stable candidate identity, originating check and method, category, reason, original channel identity, localization granularity, evidence reference and review status. Localized intervals shall also retain original sample or second coordinates and endpoint convention.

Whole-window or channel-level outputs shall explicitly state that abnormal onset and offset were not localized. Channel-pair candidates shall retain both members without arbitrarily choosing one as the bad channel. Source seizures, task events and sleep stages shall not directly become artifact candidates.

Waveform and spectrum figures shall label channels, time, units, gain or display processing. The current static waveform shows at most the first 6 selected channels and first 15 seconds, with parameters in `waveform_selection.json`; it does not represent the entire analysis extent. The raw-waveform API's extrema envelope is a bounded preview, not every native sample or a diagnostic viewer. Unavailable images shall retain explanations and available structured evidence, without invented substitute waveforms.

## 6 Methods, parameters and sources

### 6.1 Frozen configuration and method identity

Actual parameters shall be retained, not only links to software defaults. `artifacts/plan.json` retains the plan, `result.json.qc_config` the runtime configuration, and `artifacts/environment.json` software/dependency versions and executed-source fingerprints. Optional extension parameters and execution details shall also be checked against their own artifacts.

Evidence sources shall have stable identifiers linked to [sources and basis](/en/standards/eeg-evidence). Reports shall distinguish source-supported method definitions, external acquisition recommendations and provisional project criteria. A reference citation alone does not establish validated thresholds.

### 6.2 Project-rule snapshot

New EEG runs save a rule mapping in `result.json.eeg_assessment` and `artifacts/eeg-assessment.json`; `artifacts/eeg-rules.json` saves the corresponding catalogue. This supports traceability, not automated conformity assessment.

| Field | Meaning |
| --- | --- |
| `schema_version` | Snapshot schema `eeg-assessment/1` |
| `catalog_version`, `specification_version` | Check catalogue `eeg-basic/1.1` and specification `0.8` |
| `catalog_sha256` | SHA-256 of the corresponding catalogue, distinguishing rule changes from this run |
| `claim` | `project_rule_traceability_only`: project-rule traceability only |
| `conformance` | null: no conformity score, certification or item acceptance conclusion |
| `population_confirmation` | `not_captured_by_runtime`: runtime does not capture complete population-scope confirmation |
| `checks[]` | Per-entry `id`, `title`, `module_id`, `module_status`, `module_reason`, `source_ids`, `parameters`, `measurement_summary` and `evidence` |
| `checks[].evidence[]` | Relative `artifact` path, file `sha256` and locatable `fields`; verify against actual artifacts |
| `child_artifact_maps[]` | Whole-record only: explicit mapping from each child's original artifact name to its exported name in the parent job; resolve child snapshot filenames through this map while preserving original JSON bytes |

Module-status mapping does not establish completion of every method within the module. Summaries do not replace detailed method evidence. Whole-record results shall retain per-window snapshots and mappings without inventing a unified cross-window detection conclusion. Old reports shall not be backfilled as though they used new rules.

## 7 Human review and limitations

### 7.1 Review records

Unreviewed automated candidates shall be marked pending. Human review shall separately retain candidate identity, accepted/rejected/uncertain decision, reason, declared reviewer, time, version and history. Current `reviews.json` is appended in the job root. Current review progress shall be read from review records, not only the frozen report's initial `review_status=pending`.

Review shall not overwrite `result.json` or method artifacts, automatically edit data, or convert `score.value=null` to a percentage. A user-entered reviewer name is not an authenticated electronic signature.

### 7.2 Required limitations

Reports shall distinguish the versioned project trial index above from a calibrated universal quality score, and identify actual missing information, non-assessment, failures, descriptive-only results and unvalidated capabilities. Lack of independent expert-labelled validation shall be disclosed. Successfully processed public records or limited visual review do not establish detection accuracy or validity across diseases.

Current snapshots map check definitions to execution evidence. Complete species and age fields are not migrated into runtime, and independent expert validation is not established. Reports shall not claim full field-specification compliance or universal EEG quality acceptance.

## 8 Report retention and consistency checks

The report package shall retain `result.json`, a readable report, frozen plan, environment, rule snapshot and method evidence actually generated. Human review shall be retained as separately appended versions. Whole-record reports shall provide access to corresponding window evidence. Exported child artifacts use a window ID followed by `--`, preventing identically named files from different windows from overwriting each other.

Before release or handoff, checks shall cover consistent source fingerprints and selection, units and coordinates, correspondence between checks and actual methods, visible skipped/failed items, accurate display ranges, valid evidence links, null values not replaced by zero and traceable rule versions. These are report and engineering consistency checks, not detection-performance validation.

## PDF export and result table

Scalp EEG window and whole-record reports support a two-page PDF using the same score and evidence as the page. Page 1 contains scope, scores, deductions and measurements; page 2 contains candidate locations, original waveform excerpts and a reviewer section. Export does not modify frozen results. Each deduction equals 100 minus the component score. Missing measurements remain unassessed.

The first two high-frequency candidates are illustrated, or line-noise candidates if none exist. Waveform access re-verifies the frozen source. Unavailable sources omit the figure with an explanation. Install `pip install -e ".[reports]"`; `DBCI_QC_PDF_FONT` can specify a Chinese-capable TrueType font.

## Whole-record background execution

New inputs default to full duration of the selected signal stream. Native, non-overlapping windows are processed in the background while the local service runs; closing the page does not cancel the job. Quick precheck remains available.

`eeg-pooling/2` first sums native numerators and denominators within each channel, then computes channel burdens, component RMS and the minimum component. Window scores are not averaged. Detector thresholds remain unchanged. Missing windows, source gaps, incomplete source verification or unassessable tail components withhold the whole-record total, while measurements and coverage remain visible.

Channel components, the lowest component and per-window scores expose local findings without arbitrary extra penalties. Window boundaries and method-specific exclusions remain documented. Compare only matching configurations; this is not a multi-file population score.
