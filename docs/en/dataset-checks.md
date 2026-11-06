# Dataset completeness and consistency checks

Rule version: dataset-consistency/0.1. Updated: 2026-11-06. Trial project rules, pending review.

## 1 Scope

Check an explicitly scoped local package against expected files, record bindings and declared comparison groups. The completeness and consistency requirements originate from the Huashan SOP; the executable rules below are this project's implementation, not hospital acceptance criteria or a published standard.

Original files are preserved. These checks do not establish personal identity, signal quality, image registration, de-identification or full BIDS compliance. Individual consistency means consistency within the declared subject's records.

## 2 Modules

| Module | Checks | Outputs |
| --- | --- | --- |
| D01 Completeness | Expected files, sizes, fingerprints, readable structure | Missing files, mismatches and structural failures |
| D02 Individual consistency | Subject/session bindings, header-to-table channels, units, sampling rates, duration, events; repeated records within a subject/session/group | Record-specific evidence and within-subject differences |
| D03 Dataset consistency | Declared group configuration, table schema, duplicate signal files | Group differences and duplicate-content leads |

These modules complement M01–M09 single-record signal checks. Complete files need not contain consistent metadata, and consistent metadata does not establish signal quality.

## 3 Inputs and groups

Expected files must come from an independent delivery agreement or published index, not be inferred from whatever files are currently present. Record plans explicitly bind paths to subject, session, modality, raw/derived status, comparison group and accompanying tables. JSON inheritance order must be explicit; raw-record metadata is not automatically inherited by derivatives.

Each group declares four policies: same_channels, same_rates, same_units, same_reference. Mixing raw/derived records or modalities stops comparison. Scalp EEG pilots compare fixed layouts separately for raw and derived records. Intracranial cohorts allow different subjects' channel counts and names; repeated records from the same subject, session and group still require a consistent layout. Different implantation periods must be grouped separately.

## 4 Rule definitions

| Check | Rule | Missing or conflicting evidence |
| --- | --- | --- |
| Identifiers | Names and declared subject/session/task/acquisition/run must agree; selected index rows must be unique | Missing or repeated selected IDs conflict; absent tables are unassessed; unselected cohort rows are not missing files |
| Channels | Unique nonempty names plus type/units columns; name sets agree with file header | Set differences conflict; order-only differences require review; comparison pairs channels by name |
| Units | Compare original source units with tables; normalize µV/μV/uV | nV versus uV is a label discrepancy (internal status `conflict`) requiring calibration/export review; unknown units require review, without silent correction; non-voltage auxiliary channels may have n/a |
| Sampling rates | Compare header, channels table and declared JSON | General tolerance: relative 1e-7 or absolute 1e-6 Hz; BrainVision additionally allows half a microsecond of sampling-interval rounding |
| Duration | Compare represented sample counts if both clocks are known, allowing about one sample | Missing declarations or unreadable files remain unassessed |
| Events | Required columns, finite times, nonnegative durations, bounds, valid channel names for index events | Overlap allowed; negative onset requires review; n/a remains unassessed; out-of-range events conflict |
| Within-subject configuration | Compare channels, rates, units and reference within subject/session/group | Singletons and missing evidence are unassessed; mixed raw/derived groups stop |
| Cohort configuration | Apply the group's four explicit policies | Permitted variation is not a failure; majority values are not automatically correct |
| Table schema | Compare channels-table column sets | Optional-column differences require review; unavailable tables are unassessed |
| Duplicate content | Compare signal-file SHA-256 | Identical content is a review lead, not identity or fraud evidence |

For sample-index events with unknown zero/one origin, the initial rule checks a broad range from 0 to N+1, where N is the sample count. This does not resolve the source convention. Original out-of-bounds rows are retained, never clipped.

## 5 Reports and reruns

Reports preserve scope, counts, subjects, groups, each check's status, affected records, relative paths, observed evidence, rule version and frozen expectations. Statuses are consistent, conflict, review, unassessed and not applicable. No 0–100 signal-quality score or hospital acceptance grade is produced. Execution completion is separate from findings. `conflict` is not a signal-quality grade: it includes different structural or metadata discrepancies. Unit labels alone do not prove incorrect amplitudes; calibration factors and source records must be checked. The UI describes each specific issue and next step instead of exposing only a status code.

Each run is stored independently. Interrupted jobs are marked on service restart. Corrected copies produce new reports; D04 records local decisions and automatic revision comparisons. Authenticated signatures remain future work. Reports retain relative filenames and public subject codes; de-identification is not implemented. Navigation and check labels are bilingual; detailed rule messages and source group descriptions currently retain Chinese text.

## 6 Sources and validation

Huashan SOP-05 v0.2 is a local requirements document and is not redistributed. The following BIDS resources inform input semantics; custom event tables are mapped explicitly and do not become BIDS tables by being readable.

- [BIDS EEG](https://bids-specification.readthedocs.io/en/stable/modality-specific-files/electroencephalography.html).
- [BIDS events](https://bids-specification.readthedocs.io/en/stable/modality-agnostic-files/events.html).

Execution is exercised on fixed subsets of ds003555 v1.0.1 (2 subjects, 12 records) and ds003029 v1.0.7 (3 subjects, 7 records). Findings may include real conflicts. This establishes engineering behavior on these cases, not expert validation or universal format coverage.


## D04: review and retest (dataset-review/1)

After D01–D03 complete, record an evidence-bound decision for mismatches, review findings and unassessed checks: correction required, restricted use, follow-up, or explained difference. A reason and impact are required; corrections, restrictions and follow-up also require an action and owner. Machine statuses and EEG scores are never overwritten.

An outcome requires explicit confirmation. Outstanding corrections produce “correction and retest required”; otherwise all pending items require a decision before confirming restricted use or reviewed within scope. These are local project decisions, not hospital acceptance or authenticated signatures.

Each save appends a revision. Editing clears the final outcome. Retests freeze the baseline job and its review revision. A finding is resolved only when the same check passes under identical rules and scope. Omitted checks and scope changes are not resolutions. Unchanged evidence may retain a decision; final approval is never inherited. HTML and PDF contain the outcome, action register, retest changes and traceability. Retests currently rerun the complete dataset-information check.
