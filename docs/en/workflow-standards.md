# Electrophysiology data QC specification

Project technical specification · Version workflow/3 · 2026-10-31 · Research use

## 1 Scope and document structure

This specification defines description, applicability, execution, assessment and traceability requirements for declared supported electrophysiology records. It is a project specification, not a published national, industry or association standard, clinical diagnosis or device certification.

“Shall” denotes a project requirement, “should” a recommendation and “may” permission. Requirements do not establish implemented capabilities; a separate implementation and validation record declares current support.

| Level | Document | Purpose |
| --- | --- | --- |
| General requirements | This page | Shared workflow, information boundaries and reporting |
| Data description | [Field dictionary v1](/standards/fields) | Five groups, types, units, scope, provenance and missing actions |
| Method selection | [Method applicability](/standards/applicability) | Technical prerequisites, context, missing data and execution states |
| Modality requirements | [Scalp EEG](/standards) · [ECoG](/standards/ecog) · [sEEG](/standards/seeg) · [Neuropixels voltage](/standards/neuropixels) | Route-specific checks and interpretation |
| Implementation | [Current implementation and validation](/standards/implementation) | Integrated capabilities, compatibility layers and evidence limits |

Each modality provides M01–M09 guides with actual entry points, parameters, dependencies and sources. Development plans, discussion and experiment logs are not specification clauses.

## 2 Data description

### 2.1 Five field groups

Organize subject, signal/files, channels/acquisition, experiment/state, and processing/provenance separately. Species, format, recording site, signal object and acquisition technology are independent. Neuropixels is not a species; NWB is not a modality.

Preserve original values, units, scope, provenance and confirmation. Distinguish known, unknown, not applicable and conflicting information. Do not invent facts from defaults. Aggregate counts retain their source collections; derived age groups retain their rules.

### 2.2 Subject and time context

Age retains value or range, unit, reference event and time context. Age at experiment start shall not become exact age at each later session. Unknown species is not automatically human; unknown disease is not healthy.

Wake, sleep, anesthesia and stimulation states use clocked intervals or events. Coarse session declarations retain their original granularity without invented staging.

### 2.3 Channels, contacts and clocks

Channels, electrode contacts and sorted units are distinct entities. Preserve source indices, stable identities, names, roles and mappings. Duplicate names do not merge channels, and digital sync is excluded from neural voltage statistics.

Each stream has an independent clock and calibration. Distinguish source sample origin, file-relative time and session time. Candidate intervals declare closed or half-open endpoints. Streams are not automatically concatenated or resampled.

## 3 Intake and confirmation

### 3.1 Reading

Select a reader from file structure, verify companions and extract actual channels, sampling, length, units and annotation status. Unreliable reading produces a specific reason, without silent repairs.

Multiple NWB ElectricalSeries require explicit selection. Units-only files are not continuous voltage. Preserve source processing and electrode maps with the selected stream. Unextracted annotations shall not be reported as absent.

### 3.2 Confirmation

Reliable declarations may prefill suggestions. Reader defaults, filenames and waveform appearance do not establish species, disease, reference or implant location. Resolve missing or conflicting information before dependent methods run.

Show extracted facts and necessary confirmations first. Optional context must not force guessed values; only dependent operations or interpretation are restricted.

## 4 Method selection and execution

### 4.1 Shared workflow

Read → Confirm → Recommend → Freeze plan → Execute → Report and review.

| Stage | Modules | Shared responsibility |
| --- | --- | --- |
| Intake and description | M01, M02 | Source verification, fields, selection and method plan |
| Technical checks | M03, M04, M05 | Integrity, spectrum/interference and channel evidence |
| Conditional checks | M06, M07 | Applicable artifact indicators and event/state checks |
| Summary and review | M08, M09 | Metrics, coverage, limits, evidence and human decisions |

Shared IDs do not imply identical algorithms or thresholds across modalities or species. Methods declare accepted objects, prerequisites, parameters and validation scope. Recommendations retain reasons for inclusion and exclusion.

### 4.2 Technical prerequisites and context

Assess units, rate, reference, comparable channels, coordinates, auxiliary signals and history per method. Species, age, disease and task primarily support interpretation and validation strata. Threshold changes require independent evidence and versioned rules.

A missing prerequisite for one method does not make the entire record unassessable. Reliably readable portions may undergo applicable checks; remaining scope is unassessed.

### 4.3 Execution scope

Freeze input revision, digests, stream, channels, time range, methods, parameters and dependencies. Distinguish windows, samples of a record and whole-record checks. Execution coverage is not a quality acceptance rate.

Chunking preserves segment boundaries, short tails, gaps, unassessed scope and failures. Define edge handling, calibration state and candidate merging; inconsistent local processing must not be described as globally equivalent execution.

## 5 Checks and processing

Checks produce metrics, candidates and evidence. Filtering, rejection, interpolation and ASR change data and require a derived version linked to its parent, without overwriting the source.

Retain separate before/after reports with methods, parameters, affected scope and time/channel mappings. Improvement in one metric does not establish signal preservation. See [current implementation](/standards/implementation) for cleaning availability.

## 6 Assessment, reporting and validation

### 6.1 Result semantics

Separate execution states, applicability limits, observations, candidates and human decisions. Completion is not acceptable quality; empty candidates do not prove absence of problems; unknown/unassessed data are not normal.

Distinguish physiology, pathology, task responses and technical artifacts. Software defaults, statistical significance and project experimental settings are not industry acceptance thresholds.

### 6.2 Reporting and comparison

Reports retain identity, metadata provenance/conflicts, selection, methods, parameters, metric units/denominators, coverage, localization, unassessed reasons and review. Comparisons account for species, reference, bandwidth, processing, state and execution scope.

Overall scores require a defined purpose, normalization, weights, missing-data rules and independent validation. Otherwise they remain null; execution success is not a substitute.

### 6.3 Validation and traceability

Validate reading, execution, detection accuracy, signal preservation and application utility separately. Synthetic faults do not replace natural labels; public-file execution does not establish cross-species or cross-disease validity.

Historical records, plans and reports retain their field/rule versions. Confirmation and review append revisions. Language switching preserves original values, units and decisions.

## 7 References

Metadata organization references [BIDS 1.11.2](https://bids-specification.readthedocs.io/en/v1.11.2/) and [NWB 2.11.0](https://github.com/NeurodataWithoutBorders/nwb-schema/blob/2.11.0/core/nwb.file.yaml). Project fields, states and routing do not establish complete BIDS/NWB compliance.

Scope, source clauses and verification dates for industry standards and clinical guidance are maintained separately in docs/standard-basis.md and docs/sources/. Catalog entries do not replace full texts, and human clinical requirements do not automatically define animal-data quality boundaries.
