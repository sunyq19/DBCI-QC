# Technical specification for scalp EEG data quality control

Project specification · Draft for comment · Version 0.7 · 31 October 2026

This document defines project requirements for basic technical QC of human continuous scalp EEG. It is not a published national, industry or association standard. Conformity to the project report format does not establish conformity to an external standard, detection accuracy or clinical validity.

| Level | Document | Purpose |
| --- | --- | --- |
| Shared requirements | [General requirements](/en/standards/overview) · [Field dictionary](/en/standards/fields) · [Method applicability](/en/standards/applicability) | Data description, missing information and applicability |
| EEG specification | This page | Assessment scope, requirements and validation principles |
| Check entries | [EEG check rules](/en/standards/eeg-checks) | Definitions, measurement conventions, threshold types and evidence locations for 12 checks |
| Reporting | [EEG QC report requirements](/en/standards/eeg-report) | Report structure, required and conditional fields, status and traceability |
| Evidence basis | [EEG sources and basis](/en/standards/eeg-evidence) | Locations in external sources, supported claims and limits of use |
| Implementation | [Current implementation](/en/standards/implementation) | Implemented capabilities, compatibility and validation scope |

Requirements and implementation shall be checked separately. The complete field-dictionary structure is not yet integrated into the runtime API. Missing information shall remain explicit; the presence of a field in a specification does not establish that software collects or confirms it.

## 1 Scope

This document covers basic technical assessment of human continuous scalp EEG with supporting provenance: files and calibration, signal integrity, spectral descriptions, narrow-band interference indicators, channel candidates, auxiliary-signal indicators, annotation checks and result traceability. Recordings may include wakefulness, sleep or disease context; context does not automatically change decision thresholds.

It does not cover clinical diagnosis, equipment electrical safety, invasive electrophysiology, animal electrophysiology or sorted neuronal-unit quality criteria. Reliable technical measurements may be retained outside this scope, without claiming completion of an assessment within this specification. Unknown species or recording location shall leave scope unconfirmed.

Technical quality and suitability for a particular application shall be assessed separately. A technical candidate does not by itself require data rejection. Suitability for disease identification, movement decoding or negative-example research requires a separate application protocol and validation.

## 2 Normative references

External normative references: none. Informative references are listed in Appendix A and [sources and basis](/en/standards/eeg-evidence). They inform data management, acquisition context or method definitions; requirements intended for other purposes shall not be converted directly into universal project acceptance limits.

Detailed checks are specified in [check rules](/en/standards/eeg-checks), with reporting requirements in [EEG QC reports](/en/standards/eeg-report). Their versions and the check-catalogue version shall be recorded together. Internal module identifiers do not replace check definitions.

## 3 Terms

| Term | Definition |
| --- | --- |
| Basic technical quality | Properties concerning data structure, calibration, continuity and interpretable signal evidence, excluding guarantees of application performance |
| Check entry | An assessment item with a stable identifier, applicability conditions, measurement conventions, outputs and supporting basis; one module may implement several entries |
| Measurement | A value or description computed over a declared scope and parameters, not necessarily a quality decision |
| Quality candidate | A channel, interval, channel pair or segment flagged under a declared rule and pending review |
| Confirmed finding | A quality conclusion established through a specified review procedure, retaining its scope and review basis |
| Check coverage | Channels, time and frequencies actually assessed in a run, distinct from input extent and waveform display extent |
| Assessment configuration | Methods, parameters, thresholds, applicability conditions, aggregation rules and their versions |
| Threshold type | Classification as an external requirement, method definition, adaptive statistical limit or provisional project parameter, retaining its specific source |
| Not assessed | No valid assessment because a check was not selected, conditions were insufficient or execution failed; not equivalent to no detected anomaly |
| Reference | The electrical reference used during acquisition or voltage calculation; ECG, EOG and EMG auxiliary channels do not thereby become EEG reference electrodes |

“Shall” denotes a requirement, “should” a recommendation, and “may” permission.

## 4 General requirements

### 4.1 Data identity and provenance

A unique identifier, source, version, file checksum, original or derived status and companion-file relationships shall be recorded. Unknown information shall remain explicitly unknown and shall not be inferred to fill gaps. Source labels, manual additions and program-derived information shall be distinguished.

Reports shall not contain unnecessary personal identifying information. Matching file fingerprints establish byte identity, not the accuracy of annotations or acquisition declarations.

### 4.2 Metadata and channels

Species, recording location, signal object, format, channel count, sampling rate, length, units, calibration and time axis shall be checked. Stored channels, selected analysis channels and effective channels for each method shall be distinguished. Original channel indices and names shall be retained; duplicate names shall not be merged. File format shall not establish modality or disease.

EEG, ECG, EOG, EMG and other roles shall be distinguished. Acquisition reference and current reference shall be recorded separately. Comparison groups, positions, filter history and context shall have provenance. Missing information shall restrict relevant methods or interpretation without requiring guessed values.

Age shall retain value or range, units, reference origin and associated acquisition time. Unknown disease is not healthy, and unknown species is not human. Context fields shall not drive automatic penalties without independent validation.

### 4.3 Data preservation

Original files shall not be overwritten. Filtering, re-referencing, resampling and segmentation parameters shall be recorded. Excluded or repaired data shall be saved separately with correspondence to the originals. Processing of temporary evaluation copies shall be distinguished from delivery of cleaned data. A decrease in a measurement alone does not establish improved quality after cleaning.

### 4.4 Execution plan

Technical information shall be extracted before confirming modality, channels and context and generating applicable recommendations. Check entries, methods, dependencies, parameters and non-assessment reasons shall be recorded and configuration frozen before execution. Window or whole-record scope shall be declared. Whole-record chunking shall retain original window coordinates, execution coverage, source gaps and non-assessment reasons. Thresholds shall not vary by disease or task without validation.

Methods shall be selected according to each check's prerequisites. Missing auxiliary channels, positions or annotations shall restrict the checks that depend on them, without invalidating other completed technical measurements or omitting unassessed items.

### 4.5 Coordinates and statistics

Results shall identify original channels and time or sample coordinates, and declare interval endpoints, denominators and uncovered ranges. Overlapping intervals shall be combined for duration statistics according to a declared rule. Without a defined combination rule, reports shall retain observation counts and windows without producing a total abnormal duration.

Channel, channel-pair, event and segment counts shall not be conflated. Unassessed data shall not be counted as normal. Ratios shall have explicit numerators, denominators and deduplication rules. Differences between computational and display units shall state the conversion. Unavailable or non-finite measurements shall be stored as null with status or reason, not replaced with zero.

### 4.6 Status and interpretation

Not selected, insufficient conditions, execution failure, completed checks and pending review shall be distinguished. Module status, method status, candidate status and human decisions shall be recorded separately. Completed computation does not imply acceptable quality; no detected candidate does not establish the absence of quality problems.

Physiological variation, pathological activity and task responses shall not automatically be classified as technical artifacts. Automated candidates shall retain reasons and evidence. Human confirmation shall follow a recordable review procedure without overwriting the initial algorithm outputs.

### 4.7 Language consistency

Chinese and English shall be presented separately. Switching language shall not change original names, stable identifiers, numbers, units, configuration or conclusions.

## 5 Module requirements

This chapter retains the responsibilities and links of implementation modules M01–M09. Checks are defined by assessment purpose; modules map those checks to implementations. Replacing an algorithm or software package shall preserve check semantics, outputs and validation requirements. Detailed measurement conventions are given in [check rules](/en/standards/eeg-checks) and the frozen run configuration.

### 5.1 M01 Data intake and structure checks

Maps to EEG-001: file, provenance and structure checks.

- Format adapters shall check file structure, recording length, channels, clocks, calibration and fingerprints of the primary file and required companions.
- Technical headers, conversion evidence and structural issues shall be reported. Readability shall not substitute for a signal quality conclusion. Missing hardware-calibration information shall be identified per format, without borrowing another format's capability claims.

[Module guide](/en/standards/modules/M01)

### 5.2 M02 Data characterization and check plan

Maps to EEG-002: information, reference and assessment scope.

- Applicability shall be checked using M01 results and the confirmed selection. Streams, original channels, reference, comparison groups, dependencies, parameters and configuration identity shall be recorded.
- The data profile, execution set and non-assessment reasons shall be reported. Context tags shall not independently incur quality penalties. Actual selection boundaries and native sample counts shall be retained; requested duration shall not substitute for actual loaded extent.

[Module guide](/en/standards/modules/M02)

### 5.3 M03 Signal integrity

Maps to EEG-003: non-finite values, constant runs and endpoint indicators.

- Non-finite, constant-run and endpoint candidates shall be defined separately, with windows, tolerances, minimum durations and protection ranges recorded.
- Candidate types, channels, intervals and measurements shall be reported. Low-amplitude activity shall not be equated with a constant run, nor an endpoint plateau with proven hardware saturation. Hardware endpoint checking shall not be claimed without valid analogue-to-digital endpoint calibration.

[Module guide](/en/standards/modules/M03)

### 5.4 M04 Spectrum and narrow-band interference

Maps to EEG-004: Welch power spectral density; EEG-005: narrow-band line-frequency indicators; EEG-006: spectral models and alpha descriptions.

- Spectral windows, window function, overlap, detrending, resolution, power units and statistical methods shall be recorded. Narrow-band checks shall remain within measurable frequencies; insufficient conditions shall be marked not assessed.
- Line-frequency candidates shall retain centre frequency, scan band, background-estimation or comparison method, observation windows and decision rules. Boundaries shall also be recorded when a separate comparison band is used. A spectral peak alone does not establish power-line interference.
- Peaks, aperiodic spectra, band power and model-fit status shall be reported separately. Alpha or aperiodic descriptions shall not be converted directly into a universal quality score; absent alpha shall not by itself invalidate a recording.

[Module guide](/en/standards/modules/M04)

### 5.5 M05 Channel quality candidates

Maps to EEG-007: non-spatial bad-channel candidates.

- Reference, comparison groups and method-specific position requirements shall be checked. Computation shall use comparable channel sets. Within-group statistics shall state effective channels, exclusion rules and whether thresholds were actually active.
- Channel identities, individual measurements, thresholds, coverage and candidate reasons shall be reported. Whole-window candidates shall not receive invented intervals, nor channel pairs be equated with confirmed bad channels. Source bad-channel labels shall remain separate from algorithm outputs; agreement between methods does not substitute for independently labelled validation.

[Module guide](/en/standards/modules/M05)

### 5.6 M06 Physiological artifact indicators

Maps to EEG-008: auxiliary-signal event-locked indicators; EEG-009: high-frequency activity indicators.

- Auxiliary roles, sampling clocks and integrity protection ranges shall be checked. Event-locked and high-frequency analyses shall be recorded separately. Successful auxiliary event detection does not establish concurrent EEG contamination.
- Events, measurements and auxiliary support shall be reported. A physiological event shall not directly imply contamination; high-frequency activity without sufficient evidence shall not be confirmed as muscle artifact. Missing or constant auxiliary channels and insufficient epochs shall be distinguished.

[Module guide](/en/standards/modules/M06)

### 5.7 M07 State and event checks

Maps to EEG-010: annotation and time checks.

- Annotation provenance, definitions, time units, ordering, bounds, overlaps and coverage shall be checked, retaining original times and their mappings.
- Sleep, task, clinical events and quality labels shall be distinguished. Missing labels shall not imply normality, and unextracted annotations shall not be described as confirmed absent. Time mapping shall not substitute for hardware synchronization measurement.

[Module guide](/en/standards/modules/M07)

### 5.8 M08 Evidence summary and aggregation

Maps to EEG-011: individual evidence and check coverage.

- Actual results, coverage and non-assessment reasons shall be aggregated, retaining individual measurements and assessment configuration. Each finding shall be traceable to a check entry, executed method and artifact.
- Numeric overall scores or universal acceptance grades shall not be issued without calibration. Unassessed items shall not receive full credit. Execution coverage, candidate counts and numbers of catalogue entries completed shall not become quality or standards-conformity percentages.

[Module guide](/en/standards/modules/M08)

### 5.9 M09 Reporting and review

Maps to EEG-012: reporting, traceability and human review.

- Reports, figures and structured results shall agree in channels, time, units and status. Unreviewed results shall be identified. Report sections and fields shall follow [report requirements](/en/standards/eeg-report).
- Human review shall be appended separately from algorithm artifacts, recording candidate identity, decision, reason, reviewer identifier, time and version, with protection against concurrent overwrites. A quality report shall not replace clinical diagnosis.

[Module guide](/en/standards/modules/M09)

## 6 Assessment and reporting

### 6.1 Measurements and thresholds

Methods, units, parameters, statistical scope, effective sample or channel counts and applicability shall accompany measurements. Thresholds shall record source, type, scope and validation basis. Adaptive thresholds shall also record estimation data, estimation method and activation state.

Software defaults, statistical significance levels and provisional project parameters shall not be described as industry acceptance limits. Criteria without independent validation may support explicitly labelled candidate screening, not universal acceptable/unacceptable conclusions. Original sources, project-derived requirements and algorithm implementations shall be separately accessible.

### 6.2 Comparison and overall scores

Comparisons shall check reference, sampling, bandwidth, processing history, state, coverage and configuration version. Shared disease or format does not establish comparability; identically named measurements with different definitions shall not be combined directly.

An overall score shall have a predefined purpose, normalization, weights, missing-item treatment and critical-issue handling, and be evaluated on independent data. Otherwise it shall be marked not established or uncalibrated and stored as null. Reports may present individual measurements, candidates and limitations without a universal score.

### 6.3 Report contents

| Section | Required content |
| --- | --- |
| Recording overview | Provenance, version, checksum, species and recording-location status, channel and acquisition information, missing fields |
| Coverage and applicability | Input and actual analysis extent, channels and frequency ranges, window or whole-record scope, uncovered parts, method restrictions |
| Individual evidence | Check entries, execution status, measurements, units, denominators, threshold types and evidence locations |
| Candidates and waveforms | Candidate types, original coordinates, reasons, displayed ranges and display processing; unavailable localization explicitly identified |
| Methods and sources | Rule versions, implementations, dependency environment, actual parameters, sources and frozen plan |
| Review and limitations | Review status, decisions and versions, non-assessment or failure reasons, uncalibrated score and interpretation limits |

Detailed fields, conditional requirements and current artifact locations are specified in [EEG QC reports](/en/standards/eeg-report). Unknown values shall be reported as unknown rather than inferred to complete a table.

### 6.4 Result consistency

Figures shall state displayed ranges and display processing. Envelope previews shall preserve the temporal order of bucket extrema and shall not be presented as every native sample. Whole-window or channel-pair candidates shall not receive invented precise abnormal intervals. Structured results shall retain parameters, coordinates and evidence references needed for recomputation. Report generation shall not establish detection accuracy or completed review.

A project-rule snapshot shall retain catalogue version, checksum, check identifiers, execution statuses and evidence references. The snapshot records how a report maps to project rules; it is not an automated conformity certification. Failed, skipped, partially assessed and evidence-missing entries shall remain visible.

## 7 Validation

### 7.1 Validation plan

Methods shall declare scope, validation objectives, inputs, expected behavior and acceptance criteria. Engineering correctness, detection performance and application utility shall be recorded separately. Each check shall map to validation records and known limits; having tests does not establish every validation layer.

### 7.2 Engineering validation

Reading and calibration, channel identity, time mapping, applicability, dependencies, errors and cancellation, data preservation and report consistency shall be checked. Handling of both supported and unsupported inputs shall be validated. Numerical measurements shall retain reference values or independent recomputation methods, tolerances and boundary conditions.

### 7.3 Detection performance

Known fault injection should check locations, units and boundaries; independent real labels should evaluate false positives and missed findings. Injection results shall not replace natural-artifact evaluation. A few successfully processed examples shall not be described as overall accuracy.

Labels shall record categories, granularity, evidence, review procedures and disagreement handling. Physiological, pathological, technical-fault and uncertain examples shall remain distinguishable. Detection evaluation shall declare its unit—channel, event, interval or sample—matching tolerance, effective denominator and treatment of uncertain labels.

### 7.4 Data separation and evidence

Development and final evaluation shall be separated by participant, session or actual dependence. Final evaluation labels shall not enter detectors or parameter tuning.

Validation records shall state data quantities, devices, references, states, anomaly types and unvalidated conditions. Disagreements and negative results shall be retained. Lack of independent expert validation shall be disclosed; report completeness, dataset count and method count shall not substitute for it.

## 8 Change management

Specifications, check entries, methods, configurations and software shall have separate version identities. Changes shall record their basis, effective scope and relevant validation results. Historical configurations and conclusions shall not be overwritten. Revisions to input fields and annotation mappings shall create new versions and retain original labels, correspondences and supporting evidence.

Implementation documentation shall match actual capability and disclose unmet requirements. New rule snapshots shall not be backfilled as though old runs used them. A retrospective mapping shall state its creation time, original runtime version and mapping-rule version.

## Appendix A References

This appendix is informative. Entry-specific evidence, source locations and limits are in [EEG sources and basis](/en/standards/eeg-evidence). References do not establish external standards conformity or clinical validity certification. English descriptions of Chinese reference titles are explanatory translations.

- [YY/T 1833.2—2022: Artificial intelligence medical devices—Quality requirements and evaluation—Part 2: General requirements for datasets](https://app.nidc.org.cn/jianybz/bz_file_pdf/wwgk/ylqxtjxhybz/2022/20220720/YYT183322022.pdf)
- [YY/T 2029—2026: Brain–computer interface medical devices—Quality requirements and evaluation methods for EEG datasets used by AI algorithms](https://app.nidc.org.cn/jianybz/bz_file_pdf/wwgk/ylqxtjxhybz/2026/2026-10/2c9048cca08f981001a12512f7a54d97.pdf)
- [CAAE 2022: Clinical EEG technical operating guide](https://www.caae.org.cn/Public/Uploads/20220118/video/61e6242d78ca7.pdf)
- [IFCN/ILAE 2023: Routine and sleep EEG: Minimum recording standards](https://doi.org/10.1016/j.clinph.2023.01.002)
- [BIDS EEG specification 1.11.2](https://bids-specification.readthedocs.io/en/v1.11.2/modality-specific-files/electroencephalography.html)
