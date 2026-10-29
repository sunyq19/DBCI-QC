# Technical specification for scalp EEG data quality control

Project specification · Draft for comment · Version 0.5 · 29 October 2026

## 1 Scope

This document specifies requirements for scalp EEG intake, checks, assessment, reporting and validation.

It does not cover clinical diagnosis, electrical safety testing of equipment or invasive electrophysiology quality criteria. Implementations shall declare their supported scope and reject or mark out-of-scope data as not assessed.

Technical quality and suitability for a particular application shall be assessed separately.

## 2 Normative references

None. Informative references are listed in Appendix A.

## 3 Terms

| Term | Definition |
| --- | --- |
| Quality candidate | A channel, interval, channel pair or segment flagged under a declared rule |
| Confirmed finding | A quality conclusion established through a specified review procedure |
| Check coverage | The channels, time and frequency ranges actually assessed in a run |
| Assessment configuration | Methods, parameters, thresholds, applicability conditions, aggregation rules and their versions |

“Shall” denotes a requirement, “should” a recommendation, and “may” permission.

## 4 General requirements

### 4.1 Data identity and provenance

A unique identifier, source, version, file checksum, original or derived status and companion-file relationships shall be recorded. Unknown information shall remain explicitly unknown and shall not be inferred to fill gaps.

Reports shall not contain unnecessary personal identifying information.

### 4.2 Metadata and channels

Modality, format, channel count, sampling rate, length, units, calibration and time axis shall be checked. Original channel indices and names shall be retained; duplicate names shall not be merged. File format shall not establish modality or disease.

EEG, ECG, EOG, EMG and other roles shall be distinguished, with acquisition reference recorded separately. Reference, comparison groups, positions, filter history and context shall have provenance; missing information shall restrict the relevant methods.

### 4.3 Data preservation

Original files shall not be overwritten. Filtering, re-referencing, resampling and segmentation parameters shall be recorded. Excluded or repaired data shall be saved separately with correspondence to the originals.

### 4.4 Execution plan

Technical information shall be extracted before confirming modality, channels and context and generating applicable recommendations. Methods, dependencies, parameters and reasons for non-assessment shall be recorded and configuration frozen before execution. Window or whole-record scope shall be declared. Whole-record chunking shall retain original window coordinates, execution coverage, source gaps and reasons for non-assessment. Thresholds shall not vary by disease or task without validation.

### 4.5 Coordinates and statistics

Results shall identify original channels and time or sample coordinates, and declare interval endpoints, denominators and uncovered ranges. Overlapping intervals shall be combined for duration statistics according to a declared rule.

Channel, channel-pair, event and segment counts shall not be conflated. Unassessed data shall not be counted as normal.

### 4.6 Status and interpretation

Not selected, insufficient conditions, execution failure, completed checks and pending review shall be distinguished. Completed computation does not imply acceptable quality; no detected candidate does not establish the absence of quality problems.

Physiological variation, pathological activity and task responses shall not automatically be classified as technical artifacts.

### 4.7 Language consistency

Chinese and English shall be presented separately. Switching language shall not change original names, stable identifiers, numbers, units, configuration or conclusions.

## 5 Module requirements

### 5.1 M01 Data intake and structure checks

- Format adapters shall check file structure, recording length, channels, clocks, calibration and checksums of the primary file and required companions.
- Technical headers, conversion evidence and structural issues shall be reported. Readability shall not substitute for a signal quality conclusion.

[Module guide](/en/standards/modules/M01)

### 5.2 M02 Data characterization and check plan

- Applicability shall be checked using M01 results and the confirmed selection; dependencies, parameters and configuration identity shall be recorded.
- The data profile, execution set and non-assessment reasons shall be reported. Context tags shall not independently incur quality penalties.

[Module guide](/en/standards/modules/M02)

### 5.3 M03 Signal integrity

- Non-finite values, constant runs and declared endpoint or amplitude anomalies shall be checked, recording windows and tolerances.
- Candidate types, channels, intervals and measurements shall be reported. Low-amplitude activity shall not be equated with a constant run, nor an endpoint plateau with proven hardware saturation.

[Module guide](/en/standards/modules/M03)

### 5.4 M04 Spectrum and narrow-band interference

- Spectral windows, resolution, power units and statistical methods shall be recorded. Narrow-band checks shall remain within measurable frequencies; insufficient conditions shall be marked not assessed.
- Peaks, aperiodic spectra, band power and interference evidence shall be reported separately, without direct conversion to a universal quality score.

[Module guide](/en/standards/modules/M04)

### 5.5 M05 Channel quality candidates

- Reference, comparison groups and method-specific position requirements shall be checked. Computation shall use comparable channel sets.
- Channel identities, measurements, thresholds, coverage and candidate reasons shall be reported. Whole-window candidates shall not be assigned invented intervals, nor channel pairs equated with confirmed bad channels.

[Module guide](/en/standards/modules/M05)

### 5.6 M06 Physiological artifact indicators

- Auxiliary signals, sampling clocks and integrity protection ranges shall be checked. Event-locked and high-frequency analyses shall be recorded separately.
- Events, measurements and auxiliary support shall be reported. A physiological event shall not directly imply contamination; high-frequency activity without sufficient evidence shall not be confirmed as muscle artifact.

[Module guide](/en/standards/modules/M06)

### 5.7 M07 State and event checks

- Annotation provenance, definitions, time units, ordering, bounds, overlaps and coverage shall be checked, retaining original times and their mappings.
- Sleep, task, clinical events and quality labels shall be distinguished. Missing labels shall not imply normality; time mapping shall not substitute for hardware synchronization measurement.

[Module guide](/en/standards/modules/M07)

### 5.8 M08 Evidence summary and aggregation

- Actual results, coverage and non-assessment reasons shall be aggregated, retaining individual measurements and assessment configuration.
- Numeric overall scores or universal acceptance grades shall not be issued without calibration. Unassessed items shall not receive full credit.

[Module guide](/en/standards/modules/M08)

### 5.9 M09 Reporting and review

- Reports, figures and structured results shall agree in channels, time, units and status. Unreviewed results shall be identified.
- Human review shall be appended separately from algorithm artifacts, recording candidate identity, decision, reason, reviewer identifier, time and version, with protection against concurrent overwrites. A quality report shall not replace clinical diagnosis.

[Module guide](/en/standards/modules/M09)

## 6 Assessment and reporting

### 6.1 Measurements and thresholds

Methods, units, parameters, statistical scope and applicability shall accompany measurements. Thresholds shall record their source and validation basis; adaptive thresholds shall also record the estimation data and method.

Software defaults and statistical significance levels shall not be described as industry acceptance limits.

### 6.2 Comparison and overall scores

Comparisons shall check reference, sampling, bandwidth, processing history, state, coverage and configuration version.

An overall score shall have a predefined purpose, normalization, weights, missing-item treatment and critical-issue handling, and be evaluated on independent data. Otherwise it shall be marked not established or uncalibrated.

### 6.3 Report contents

| Category | Required content |
| --- | --- |
| Identity and acquisition | Recording provenance, version, checksum, channel and acquisition metadata, missing information |
| Check scope | Original coordinates, actual channels and frequencies, sampled or complete examination, uncovered ranges |
| Method configuration | Methods, dependencies, parameters, applicability, configuration and software versions |
| Measurements and candidates | Values, units, threshold sources, denominators, locations, reasons and evidence |
| Assessment and review | Individual findings, overall-score status, non-assessment or failure reasons, review and modification records |

### 6.4 Result consistency

Figures shall state their displayed ranges and display processing. Envelope previews shall preserve the temporal order of bucket extrema and shall not be presented as every native sample. Whole-window or channel-pair candidates shall not receive invented precise abnormal intervals. Structured results shall retain parameters, coordinates and evidence references needed for recomputation. Report generation shall not establish detection accuracy or completed review.

## 7 Validation

### 7.1 Validation plan

Methods shall declare scope, validation objectives, inputs, expected behavior and acceptance criteria. Engineering correctness, detection performance and application utility shall be recorded separately.

### 7.2 Engineering validation

Reading and calibration, channel identity, time mapping, applicability, dependencies, errors and cancellation, data preservation and report consistency shall be checked. Handling of both supported and unsupported inputs shall be validated.

### 7.3 Detection performance

Known fault injection should check locations, units and boundaries; independent real labels should evaluate false positives and missed findings. Injection results shall not replace natural-artifact evaluation.

Labels shall record categories, granularity, evidence and disagreement handling. Physiological, pathological, technical-fault and uncertain examples shall remain distinguishable.

### 7.4 Data separation and evidence

Development and final evaluation shall be separated by participant, session or actual dependence. Final evaluation labels shall not enter detectors or parameter tuning.

Validation records shall state data quantities, devices, references, states, anomaly types and unvalidated conditions. Disagreements and negative results shall be retained.

## 8 Change management

Specifications, methods, configurations and software shall have separate version identities. Changes shall record their basis, effective scope and relevant validation results. Historical configurations and conclusions shall not be overwritten. Revisions to input fields and annotation mappings shall create new versions and retain original labels, correspondences and supporting evidence.

Implementation documentation shall match actual capability and disclose unmet requirements.

## Appendix A References

This appendix is informative. English descriptions of Chinese reference titles are explanatory translations.

- [YY/T 1833.2—2022: Artificial intelligence medical devices—Quality requirements and evaluation—Part 2: General requirements for datasets](https://app.nidc.org.cn/jianybz/bz_file_pdf/wwgk/ylqxtjxhybz/2022/20220720/YYT183322022.pdf)
- [YY/T 2029—2026: Brain–computer interface medical devices—Quality requirements and evaluation methods for EEG datasets used by AI algorithms](https://app.nidc.org.cn/jianybz/bz_file_pdf/wwgk/ylqxtjxhybz/2026/2026-10/2c9048cca08f981001a12512f7a54d97.pdf) (effective 1 September 2027)
- [CAAE 2022: Clinical EEG technical operating guide](https://www.caae.org.cn/Public/Uploads/20220118/video/61e6242d78ca7.pdf)
- [IFCN/ILAE 2023: Routine and sleep EEG: Minimum recording standards](https://doi.org/10.1016/j.clinph.2023.01.002)
- [BIDS EEG specification 1.11.2](https://bids-specification.readthedocs.io/en/v1.11.2/modality-specific-files/electroencephalography.html)
