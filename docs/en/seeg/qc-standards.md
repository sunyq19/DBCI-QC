# sEEG basic quality-check specification

Project technical specification · Version seeg-basic/1 · 2026-10-31 · Document revision 2 · Research use

Shared requirements: [general requirements](/standards/overview), [field dictionary](/standards/fields), [method applicability](/standards/applicability). Actual capabilities are listed separately under [implementation scope](/standards/implementation). Species and age retain source, units and time context; human age categories must not be applied to animals. These metadata requirements do not change existing analysis-profile versions or establish new cross-species thresholds.

## 1 Scope

For explicitly confirmed continuous sEEG voltages and one compatible analysis group. Integrity, spectrum and statistics share mathematical kernels, while modality, parameters and interpretation remain distinct. This is a project specification, not a clinical or industry quality threshold.

## 2 Input

Confirm source channels, voltage units, rate and range. Preserve evidence or unknown states for referencing, filters, implantation and shafts. Mixed neural recordings require selection of a compatible analysis group.

## 3 Configuration

analysis_profile is seeg-basic/1. method_config.seeg uses psd_window_seconds=4 and line_frequencies_hz=[50,60]. These are calculation settings, not healthy ranges. Scalp-specific thresholds are not substitutes.

## 4 Execution and results

Default modules are M03, M04 and M05; add M07 for registered events. M01, M02, M08 and M09 are required. M06 supports explicitly selected FieldTrip difference-interval evidence. Preserve source data, references and bad labels. No automatic cleaning, re-reference or exclusion. Total score is null.

## 5 Module requirements

### 5.1 M01 Data intake and structure checks

Check fingerprints, channel identity, native sampling streams, continuous segments and units. Distinguish file declarations, companion evidence and user confirmation.

A file extension or a default EEG reader type does not establish electrode anatomy. Unknown units cannot be treated as calibrated voltage.

[Module details](/en/standards/seeg/modules/M01)

### 5.2 M02 Data characterization and check plan

Freeze the analysis group, native sample range and seeg-basic/1 settings; retain the reference state stored in the source.

The legacy eeg_indices field denotes sEEG contacts here. Shaft, tissue and bipolar pairing remain unknown without evidence. Do not infer them from names or automatically re-reference.

[Module details](/en/standards/seeg/modules/M02)

### 5.3 M03 Basic signal integrity

Scan nonfinite values and consecutive runs of at least two exactly equal samples; retain full counts and a bounded detailed list.

Quantization can produce equal samples; this is not a bad-contact verdict. A file can start at a nonzero acquisition sample. An omitted location is not evidence of normality.

[Module details](/en/standards/seeg/modules/M03)

### 5.4 M04 Spectrum and line-frequency observations

Use SciPy Welch with a Hann window, 50% overlap and per-segment mean removal. Default window: 4 seconds. Describe measurable bands around 50/60 Hz.

Band half-width is max(1 Hz, frequency resolution). No alpha scoring or scalp muscle threshold. High-frequency or pathological activity is not automatically an artifact, and a peak does not establish its cause.

[Module details](/en/standards/seeg/modules/M04)

### 5.5 M05 Per-contact statistics

Compute finite count, mean, standard deviation, RMS and peak-to-peak. Retain source identity and do not automatically exclude source bad labels.

RMS is not an independent noise floor. No scalp PREP, LOF, bridging or inferred cross-shaft adjacency. Different references and anatomical locations are not directly ranked against one baseline.

[Module details](/en/standards/seeg/modules/M05)

### 5.6 M06 Artifact method scope

Explicitly selected fieldtrip_zvalue provides review intervals; it is not selected by default and does not substitute scalp artifact thresholds.

Not assessed does not mean artifact-free. Stimulation, motion, cable effects and pathological activity require separate evidence and validation; no confirmed artifact diagnosis or automatic repair is claimed.

[Module details](/en/standards/seeg/modules/M06)

### 5.7 M07 Source event checks

Check fields, valid times and overlap; map events to the selected range and original samples while preserving source categories and durations.

Task and seizure events are not artifact ground truth. Point events are not joined into intervals. Clock mapping does not establish hardware synchronization; unlabelled does not mean normal.

[Module details](/en/standards/seeg/modules/M07)

### 5.8 M08 Evidence summary and aggregation

Summarize actual scope and itemized evidence; distinguish completed, partial, skipped and failed.

Completion is not quality. No unified score across patients, references or anatomy has been calibrated. Epilepsy-related activity is not itself a deduction.

[Module details](/en/standards/seeg/modules/M08)

### 5.9 M09 Reporting and review

Write HTML/JSON and evidence artifacts. Store workbench review decisions independently with versions.

Human review does not overwrite automatic evidence. This technical report does not replace clinical diagnosis or anatomical verification.

[Module details](/en/standards/seeg/modules/M09)

## 6 Validation and sources

The test sample is a byte-identical copy of public sample_seeg_ieeg.fif: 119 channels, 59,966 samples, 999.412109375 Hz and 32 task events. Original first_samp is 1,310,640; file-relative and acquisition time differ. Independent FIFF payload decoding agrees on all 7,135,954 values with the adapter. This establishes engineering read consistency only. Full processing history, acquisition reference, original physical calibration, anatomy and quality ground truth remain unverified; diagnosis is unknown.

[MNE sEEG tutorial](https://mne.tools/stable/auto_tutorials/clinical/20_seeg.html) · [BIDS iEEG](https://bids-specification.readthedocs.io/en/stable/modality-specific-files/intracranial-electroencephalography.html)
