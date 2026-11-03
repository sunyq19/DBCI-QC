# EEG check terms and modules

Project implementation procedure · Version eeg-basic/1.1 · Specification 0.8

[EEG specification](/standards) · [Evidence sources](/standards/eeg-evidence) · [Report requirements](/standards/eeg-report) · [Field dictionary](/standards/fields)

## 1 Catalog and interpretation

This catalog specifies terms, measurements and evidence for basic technical QC of human continuous scalp EEG. Twelve terms map to the existing nine modules, not twelve additional algorithms. Core checks require an execution account; conditional checks require their prerequisites; descriptive checks have no quality cutoff. Project requirements are separate from informative external sources. Verify defaults against effective runtime parameters.

Mapping is not certification. Human/scalp scope requires source confirmation, not yet fully captured by runtime fields. Read algorithm candidates, human decisions and execution states separately. Integrity issues can prevent spectral/event methods; failure does not imply zero noise or normality.

| Term | Purpose | Type | Module |
| --- | --- | --- | --- |
| [EEG-001](#eeg-001) | Files, provenance and calibration | Core check | [M01](/standards/modules/M01) |
| [EEG-002](#eeg-002) | Context, reference and assessment scope | Core check | [M02](/standards/modules/M02) |
| [EEG-003](#eeg-003) | Nonfinite values, constant runs and endpoint plateaus | Core check | [M03](/standards/modules/M03) |
| [EEG-004](#eeg-004) | Power spectral density | Core check | [M04](/standards/modules/M04) |
| [EEG-005](#eeg-005) | Line-frequency narrow-band indicators | Core check | [M04](/standards/modules/M04) |
| [EEG-006](#eeg-006) | Aperiodic spectrum, peaks and alpha power | Descriptive check | [M04](/standards/modules/M04) |
| [EEG-007](#eeg-007) | Channel quality candidates | Conditional check | [M05](/standards/modules/M05) |
| [EEG-008](#eeg-008) | ECG/EOG time-locked indicators | Conditional check | [M06](/standards/modules/M06) |
| [EEG-009](#eeg-009) | High-frequency bursts and EMG support | Conditional check | [M06](/standards/modules/M06) |
| [EEG-010](#eeg-010) | Annotation and timing checks | Conditional check | [M07](/standards/modules/M07) |
| [EEG-011](#eeg-011) | Domain summary and comparability | Core check | [M08](/standards/modules/M08) |
| [EEG-012](#eeg-012) | Report, evidence and human review | Core check | [M09](/standards/modules/M09) |

## EEG-001

**Files, provenance and calibration**

### Applicability and measurement

All inputs; the primary file and required companions must be available.

Check format structure, SHA-256, streams, channel roles, units and digital-to-physical calibration. Keep header signal count distinct from numeric signal count.

### Decision basis and reporting

Missing files, fingerprint conflicts or unreliable calibration block the affected input. Readability is not signal acceptance; these are project engineering requirements.

Source/version, format, reader version, companion fingerprints, clock, units and structural warnings.

### Implementation and evidence

[M01](/standards/modules/M01) · SRC-1833, SRC-BIDS, SRC-PROJECT · [Source locations](/standards/eeg-evidence)

Artifacts: `M01_input.json`.

Evidence fields: `source_sha256`, `source_files`, `header`, `streams`, `clock`, `reader_id`, `reader_version`, `annotations`.

Engineering behavior and public-file execution are documented; general accuracy against independent expert labels and industry acceptance cutoffs are not established.

## EEG-002

**Context, reference and assessment scope**

### Applicability and measurement

Select calibrated scalp EEG channels and a continuous range; species/site require source confirmation.

Retain source indices/names, sampling rate, half-open sample interval, auxiliary roles, reference and comparison groups. Unknown reference remains unconfirmed; disease and age tags do not directly tune thresholds.

### Decision basis and reporting

A missing prerequisite restricts the dependent method. Runtime does not yet capture the full species/age contract; scope confirmation is not inferred.

Selected channels, time/sample limits, reference declaration, missing context, input tags and frozen plan.

### Implementation and evidence

[M02](/standards/modules/M02) · SRC-BIDS, SRC-CAAE, SRC-IFCN, SRC-PROJECT · [Source locations](/standards/eeg-evidence)

Artifacts: `M02_selection.json`.

Evidence fields: `selection`, `recording`, `channels`, `reference_channels`, `comparison_groups`, `processing_applied`.

Engineering behavior and public-file execution are documented; general accuracy against independent expert labels and industry acceptance cutoffs are not established.

## EEG-003

**Nonfinite values, constant runs and endpoint plateaus**

### Applicability and measurement

Calibrated voltage; endpoint classification additionally requires ADC calibration.

Locate all nonfinite samples. Classify runs of strictly equal successive finite raw samples (difference tolerance 0), default minimum max(2,ceil(0.1×fs)) samples. Near-zero tolerance max(1e-7 V, half a quantization step with rounding allowance) is only a constant-run classifier; endpoint tolerance is 0.25 LSB with floating-point allowance. Source intervals are half-open.

### Decision basis and reporting

These are BrainElecQC implementation settings. near_zero_flatline is not physiological low amplitude; endpoint plateaus do not establish hardware saturation. General repeated-block detection is not implemented.

Per-channel nonfinite count, candidate type/position/value, calibration availability, effective tolerances and non-assessment reasons. Candidate count is not duration.

### Implementation and evidence

[M03](/standards/modules/M03) · SRC-BRAINELECQC, SRC-PROJECT · [Source locations](/standards/eeg-evidence)

Artifacts: `M03_continuity.json`.

Evidence fields: `parameters`, `input_range`, `measurements`, `candidates`, `interval_convention`.

Engineering behavior and public-file execution are documented; general accuracy against independent expert labels and industry acceptance cutoffs are not established.

## EEG-004

**Power spectral density**

### Applicability and measurement

The current core implementation requires finite selected input and at least a two-sample window.

Welch one-sided PSD in V²/Hz; default 4 s Hann windows, 50% overlap, per-window mean removal, arithmetic mean, nfft=nperseg. nperseg=min(N,max(2,round(4fs))); bin spacing Δf=fs/nperseg (artifact field frequency_resolution_hz); resolving ability also depends on the window.

### Decision basis and reporting

PSD is descriptive with no universal acceptance threshold. Compare reference, filtering history, resolution and actual coverage before comparing power.

Frequencies, per-channel PSD, valid window count, window/tail coverage, units and effective parameters.

### Implementation and evidence

[M04](/standards/modules/M04) · SRC-SCIPY, SRC-PROJECT · [Source locations](/standards/eeg-evidence)

Artifacts: `M04_spectral.json`.

Evidence fields: `input`, `config`, `psd`, `software`.

Engineering behavior and public-file execution are documented; general accuracy against independent expert labels and industry acceptance cutoffs are not established.

## EEG-005

**Line-frequency narrow-band indicators**

### Applicability and measurement

At least one complete 4 s window; center plus scan half-width must be strictly below Nyquist.

BrainElecQC Thomson-type DPSS F test: default 4 s windows/1 s steps, full bandwidth 2 Hz; scan ±2 Hz around measurable 50/60 Hz harmonics. Bonferroni correction spans channels, complete windows and unique bins; sinusoid amplitude is peak 2|A|, not RMS.

### Decision basis and reporting

Adjusted p<0.01 is a statistical screening setting, not an industry cutoff; a significant narrow band does not itself confirm technical contamination.

Measurable bands, F/p/peak amplitude and flagged windows; flagged_union_seconds is a union per channel and target frequency, and flagged_union_fraction_of_input uses input duration. Durations across targets are not additive total line-noise time, nor prevalence over assessed time.

### Implementation and evidence

[M04](/standards/modules/M04) · SRC-BRAINELECQC, SRC-PREP, SRC-PROJECT · [Source locations](/standards/eeg-evidence)

Artifacts: `M04_spectral.json`.

Evidence fields: `config`, `methods.line_noise`, `line_noise.status`, `line_noise.channel_summary`, `line_noise.observations`, `line_noise.windows`.

Engineering behavior and public-file execution are documented; general accuracy against independent expert labels and industry acceptance cutoffs are not established.

## EEG-006

**Aperiodic spectrum, peaks and alpha power**

### Applicability and measurement

Default spectral fit requires at least 10 s, four periodograms, coverage of 2–40 Hz, positive power and compatible peak width/resolution; outputs are checked separately.

FOOOF fixed background model, default 2–40 Hz, fit full selection and 30 s local windows separately. Alpha power uses trapezoidal PSD integration with interpolated boundaries, 8–13 Hz absolute and default 2–40 Hz relative denominator.

### Decision basis and reporting

Descriptive only; no acceptance criterion. Alpha energy includes background and is not peak height. Age, state and pathology affect spectra.

Per-fit status, exponent/peak parameters/R²/error, absolute alpha µV² and relative percent, bands and non-assessment reasons.

### Implementation and evidence

[M04](/standards/modules/M04) · SRC-FOOOF, SRC-SCIPY, SRC-PROJECT · [Source locations](/standards/eeg-evidence)

Artifacts: `M04_spectral.json`.

Evidence fields: `config`, `parameterization`, `alpha_power`.

Engineering behavior and public-file execution are documented; general accuracy against independent expert labels and industry acceptance cutoffs are not established.

## EEG-007

**Channel quality candidates**

### Applicability and measurement

Explicit reference/comparison groups; group thresholds need at least four usable channels. Mixed reference or bipolar derivations are not automatically grouped.

Nonspatial PREP components: robust amplitude 0.7413×IQR and group z-score, relative high-frequency MAD ratio, 98th Hazen percentile of absolute correlation in 1 s windows, and dropout fraction. Retain filtering, group scale and assessed-window denominators.

### Decision basis and reporting

Default |amplitude z|>5, HF z>5; fraction of assessed windows with correlation<0.4 or dropout>0.01. These are screening rules, not universal bad-channel definitions; absent group prerequisites/zero scales do not create z-scores.

Channel identity, metrics/criteria, active group thresholds, candidate reasons, window denominators and unassessed tail; source bad-channel labels stay separate from detection.

### Implementation and evidence

[M05](/standards/modules/M05) · SRC-BRAINELECQC, SRC-PREP, SRC-PROJECT · [Source locations](/standards/eeg-evidence)

Artifacts: `M05_bad_channels.json`.

Evidence fields: `parameters`, `preprocessing`, `input_range`, `groups`, `channels`, `window_metrics`, `unwindowed_tail`, `candidates`.

Engineering behavior and public-file execution are documented; general accuracy against independent expert labels and industry acceptance cutoffs are not established.

## EEG-008

**ECG/EOG time-locked indicators**

### Applicability and measurement

Confirmed ECG/EOG auxiliary channels on the same native clock, finite nonconstant input and complete event windows.

Detect auxiliary events then compute EEG time-locked statistics. Auxiliary event count and EEG contamination are different quantities. Retain detector thresholds, filters, event window, event subsampling and consistency-statistic settings.

### Decision basis and reporting

Missing auxiliaries/incomplete event windows are unassessed, not zero contamination; event presence does not itself establish EEG artifact.

Per-kind auxiliary status, detected/included event counts, source-clock positions, time-locked statistics, effective parameters and limitations.

### Implementation and evidence

[M06](/standards/modules/M06) · SRC-BRAINELECQC, SRC-MNE, SRC-PROJECT · [Source locations](/standards/eeg-evidence)

Artifacts: `M06_auxiliary_events.json`.

Evidence fields: `config`, `start_sample`, `stop_sample`, `by_kind`.

Engineering behavior and public-file execution are documented; general accuracy against independent expert labels and industry acceptance cutoffs are not established.

## EEG-009

**High-frequency bursts and EMG support**

### Applicability and measurement

Band, Nyquist and filter-length conditions must hold; use M03 integrity guards. EMG support additionally needs usable synchronous EMG.

Analyze high-frequency power/envelope bursts on a copy, preserving band, window, threshold and exclusions; unsupported bursts remain high-frequency indicators.

### Decision basis and reporting

Current implementation settings are not clinical EMG criteria; high-frequency neural/pathological activity is not automatically removed.

Candidate intervals, EMG support, integrity guards, effective band/threshold and non-assessment reasons.

### Implementation and evidence

[M06](/standards/modules/M06) · SRC-BRAINELECQC, SRC-MNE, SRC-PROJECT · [Source locations](/standards/eeg-evidence)

Artifacts: `M06_muscle.json`.

Evidence fields: `parameters`, `status`, `reference`, `channels`, `candidates`.

Engineering behavior and public-file execution are documented; general accuracy against independent expert labels and industry acceptance cutoffs are not established.

## EEG-010

**Annotation and timing checks**

### Applicability and measurement

Annotations must have known provenance and a supported format/mapping; unextracted does not mean absent.

Check units, source clock, bounds/overlap, selected events and coverage; preserve source categories without converting task, sleep or seizure labels into QC truth.

### Decision basis and reporting

Missing annotations mean non-assessment; event consistency does not replace hardware synchronization measurement.

Annotation provenance/format, original/mapped times, selected events, coverage and issues; separate quality_ground_truth declaration.

### Implementation and evidence

[M07](/standards/modules/M07) · SRC-BIDS, SRC-1833, SRC-PROJECT · [Source locations](/standards/eeg-evidence)

Artifacts: `M07_annotations.json`.

Evidence fields: `format`, `label_scope`, `selected_count`, `covered_seconds`, `issues`, `quality_ground_truth`.

Engineering behavior and public-file execution are documented; general accuracy against independent expert labels and industry acceptance cutoffs are not established.

## EEG-011

**Domain summary and comparability**

### Applicability and measurement

Summarize completed, partial, skipped and failed modules with scope/configuration.

Retain domain measurements and provenance; execution coverage uses actual assessed scope. Compare data only under compatible species, reference, bandwidth, state, processing and configuration.

### Decision basis and reporting

Generic uncalibrated score.value remains null. The separate EEG project trial index eeg-basic-screen/0.2 is in report_view.score: components use one minus RMS channel burden, scaled to 100; the total is the minimum. Missing evidence withholds totals; no industry acceptance cutoff.

Domain states, missing/failure reasons, source-integrity verification, score status and comparison conditions. Separately retain EEG trial score version, components, native counts and historical recalculation markers.

### Implementation and evidence

[M08](/standards/modules/M08) · SRC-1833, SRC-PROJECT · [Source locations](/standards/eeg-evidence)

Artifacts: `M08_assessment.json`.

Evidence fields: `score`, `source_unchanged`, `module_assessments`, `missing_capabilities`.

Engineering behavior and public-file execution are documented; general accuracy against independent expert labels and industry acceptance cutoffs are not established.

## EEG-012

**Report, evidence and human review**

### Applicability and measurement

All outputs; retain traceable results even with partial failure.

Report identity, scope, domains, candidates, parameters and evidence; a rule snapshot links actual artifact fingerprints. Human reviews are independently appended/versioned; historical reports are not rewritten.

### Decision basis and reporting

Reports are not clinical diagnoses or compliance certificates; retain pending until human review. Rule mapping does not automatically prove conformance.

Method/environment versions, source hashes, display scope, rule version, evidence index and separate review access.

### Implementation and evidence

[M09](/standards/modules/M09) · SRC-1833, SRC-CAAE-QC, SRC-PROJECT · [Source locations](/standards/eeg-evidence)

Artifacts: `environment.json`、`waveform_selection.json`.

Evidence fields: `implementation`, `packages`, `actual_executed_sources`, `channel_names`, `start_seconds`, `duration_seconds`.

Engineering behavior and public-file execution are documented; general accuracy against independent expert labels and industry acceptance cutoffs are not established.

## 2 Optional methods and terms

Optional methods add evidence to existing terms; they do not add score points or create ground truth by voting. Dependencies, effective parameters and failures remain in extension artifacts. Unexported measurements remain unavailable rather than reconstructed from candidate names.

| Term | Integrated method | Interpretation limit |
| --- | --- | --- |
| EEG-003 | MNE amplitude; global AutoReject | Successive differences differ from peak-to-peak amplitude; global threshold is exploratory in-sample estimation, not task-trial validation |
| EEG-007 | MNE bridging, LOF; mne-faster | Pairs are not bad-channel counts; actual bridge cutoff and FASTER raw features/z-scores are not exported; FASTER is a Python implementation |
| EEG-009 | MNE high-frequency envelope; FieldTrip differential z-value | Generic high-frequency/difference candidates do not confirm EMG; FieldTrip runs through Octave compatibility |
| Processing-effect evaluation | ASR, CleanLine, Zapline-plus | Explicit selection, temporary copy, no cleaned signal export; power changes do not prove quality improvement |

PyPREP RANSAC, local AutoReject and ICLabel are not integrated. Execution gates differ from published validation coverage; low-channel-count FASTER needs independent validation. See evidence sources.

## 3 Versions and review

Generated from src/ephys_qc/specifications/eeg-basic.v1.json. New EEG reports preserve exact eeg-rules.json bytes/SHA-256, the eeg-assessment.json evidence index, method artifacts and effective parameters. Version catalog changes and regenerate both languages; do not backfill historical reports. Whole-record output retains window reports; durations from different frequencies/channels or overlapping windows are not additive total contamination.
