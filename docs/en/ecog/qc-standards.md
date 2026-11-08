# ECoG basic quality-check specification

Project technical specification · Version ecog-basic/1 · 2026-10-31 · Document revision 3 · Research use

Shared requirements: [general requirements](/standards/overview), [field dictionary](/standards/fields), [method applicability](/standards/applicability). Actual capabilities are listed separately under [implementation scope](/standards/implementation). Species and age retain source, units and time context; human age categories must not be applied to animals. These metadata requirements do not change existing analysis-profile versions or establish new cross-species thresholds.

## 1 Scope

This specification covers continuous voltage recordings explicitly confirmed as cortical surface ECoG. It provides descriptive measurements and traceable evidence, not clinical bad-contact thresholds, sEEG checks or extracellular unit QC.

## 2 Inputs

Confirm modality, source channel indices, voltage units, native clock and analysis range. Unknown reference, filtering or electrode locations remain unknown. A BrainVision default EEG type is not anatomical evidence. Explicitly declared incompatible FIF types must be rejected.

## 3 Configuration

Use `method_config.ecog`: `psd_window_seconds=4` and `line_frequencies_hz=[50,60]`. PSD uses a Hann window, 50% overlap and per-segment mean removal; short selections report their actual segment length. Narrow-band half-width is max(1 Hz, frequency resolution). Only measurable bands are described, without rejection thresholds. These are project measurement settings, not industry quality standards.


### Basic recommended scheme v0.3 (2026-11-08)

Read and confirm modality, contacts, units and reference → numerical integrity, sustained flatness and file-range plateaus → PSD, line-frequency neighborhoods and contact statistics → report. Add M07 only for verified, registered event tables.

M03 recommends the original MNE `annotate_amplitude` with `flat=0 V`, `peak=None`, `min_duration=0.05 s`, `bad_percent=5`. The 50 ms setting follows MNE-BIDS `inspect_dataset`. The 5% value routes findings to channel candidates or temporal annotations; it is not a clinical cutoff. Explicit custom parameters are preserved in each run.

Flatness is evaluated within each analysis window. Channel-only candidates do not imply exact abnormal intervals; merged temporal annotations do not identify a contact. Brief runs split across window boundaries may be missed. Empty candidates do not establish overall quality.

EDF/BDF additionally checks runs at verified file encoding limits. Within-group amplitude outliers require explicit groups and confirmed comparable references. Original FieldTrip adjacent-change screening remains opt-in; it is not an automatic diagnosis of artifacts. See [intracranial check rules](/en/standards/ieeg-checks) for exact conditions and formulas.

The default score uses numerical validity (30%) and signal stability (70%), with adjustable weights. Related evidence contributes once; see [intracranial scoring](/en/standards/ieeg-scoring). MNE contact-candidate and merged-interval fractions expose optional score outputs with default weight 0; they cannot be summed as contaminated duration. PSD, narrowband power and RMS remain descriptive measurements.

Reports include scope, itemized check results, candidate locations, contact measurements, window-specific charts and provenance. Pooled RMS is weighted by finite sample count. The peak-to-peak summary is the maximum window value, not whole-record peak-to-peak.

Sources: [MNE annotate_amplitude](https://mne.tools/stable/generated/mne.preprocessing.annotate_amplitude.html), [MNE-BIDS inspect_dataset](https://mne.tools/mne-bids/stable/generated/mne_bids.inspect_dataset.html). This is an executable project draft, without expert approval or bad-contact ground-truth validation.

## 4 Execution and results

Recommend M03, M04 and M05, adding M07 when events are registered. M01, M02, M08 and M09 are required; M06 supports explicitly selected FieldTrip difference-interval evidence. Windows are at most 120 seconds. Whole-record execution retains per-window coverage and short tails. No cleaning, deletion or rereferencing is applied. Nonempty scalp-only parameters are rejected rather than silently replaced. The default produces two component scores and a weighted total; unavailable components are excluded explicitly.

## 5 Module requirements

### 5.1 M01 Data intake and structure checks

Use registered readers and freeze source hashes, native streams and continuous segments. A default EEG reader type in BrainVision does not establish scalp placement. ECoG requires explicit source or user confirmation.

[Module details](/standards/ecog/modules/M01)

### 5.2 M02 Data characterization and check plan

Read the selected native samples without resampling or rereferencing; preserve channel identity. The legacy eeg_indices field denotes ECoG analysis contacts in this route.

[Module details](/standards/ecog/modules/M02)

### 5.3 M03 Basic signal integrity

Locate nonfinite samples and runs of at least two exactly equal consecutive samples. Exact equality is a technical observation, not a validated artifact decision. No scalp amplitude or rejection-duration threshold is applied.

Detailed candidate locations are limited to 10,000 per window; all samples and per-contact counts remain covered. Truncation must retain total and omitted counts and mark the result partial. Unstored locations do not imply normality.

[Module details](/standards/ecog/modules/M03)

### 5.4 M04 Spectrum and line-frequency observations

Estimate Welch PSD with SciPy and describe power and peak location near configured frequencies. No FOOOF, alpha score, Thomson decision or muscle threshold is applied. A peak does not establish interference origin.

[Module details](/standards/ecog/modules/M04)

### 5.5 M05 Per-contact statistics

Calculate finite-sample count, mean, standard deviation, RMS and peak-to-peak range per contact. No PREP, LOF or bridging detection. Amplitude or contact names do not establish bad contacts or spatial adjacency.

[Module details](/standards/ecog/modules/M05)

### 5.6 M06 Artifact method scope

Only an explicit fieldtrip_zvalue selection enables this module. Difference-z candidates require review; pathological activity may trigger them. No scalp physiological-artifact fallback or rejection.

[Module details](/standards/ecog/modules/M06)

### 5.7 M07 Source event checks

Map source events onto the original clock and current selection. Point events remain points. Do not infer clinical intervals or artifact labels from unverified markers.

[Module details](/standards/ecog/modules/M07)

### 5.8 M08 Evidence summary and aggregation

Aggregate execution coverage, observations, failures and unavailable reasons. Completion is not quality. Different references, windows or processing histories are not directly comparable.

[Module details](/standards/ecog/modules/M08)

### 5.9 M09 Reporting and review

Generate HTML and JSON evidence; save workbench review decisions separately. Review does not overwrite algorithm evidence. The report is not a clinical diagnosis.

[Module details](/standards/ecog/modules/M09)

## 6 Validation and data

Public examples use the MNE epilepsy_ecog record originating from OpenNeuro ds003029. BrainVision and derived FIF are one observation, not independent participants. BIDS declares 89 ECoG and 9 MISC channels; MISC names do not establish auxiliary physiological roles. Source bad-channel labels are not detector inputs. Reader agreement, execution and scientific accuracy are separate checks. Preserve the header nV declaration and missing sidecar units; numerical agreement does not independently validate acquisition calibration.

[OpenNeuro ds003029](https://openneuro.org/datasets/ds003029) · [MNE epilepsy_ecog](https://mne.tools/stable/generated/mne.datasets.epilepsy_ecog.data_path.html)
