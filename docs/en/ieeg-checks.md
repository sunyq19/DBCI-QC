# ECoG and sEEG basic check rules

Project technical specification · ieeg-basic-recipe/0.3 · 2026-11-08 · Awaiting expert review

## 1 Scope

Confirmed ECoG or sEEG continuous voltage. The pipeline identifies technical candidates for review; it does not determine whether pathological activity should be removed.

Read and confirm → integrity, flatness and range → spectra, contact comparisons and transients → report and review.

## 2 Modules and conditions

| Module | Check | Condition | Output |
| --- | --- | --- | --- |
| M01 | Format, calibration and clock | Supported native reader | Source identity and technical metadata |
| M02 | Modality, contacts, reference and scope | Confirmed selection | Frozen configuration |
| M03 | NaN/Inf and repeated samples | Continuous voltage | Counts and source positions |
| M03 | Sustained flatness | Finite data | Original MNE channel or merged-time candidates |
| M03 | Encoding-limit plateaus | EDF/BDF calibration present | Contact intervals and sample counts |
| M04 | Welch PSD and line-frequency neighborhoods | Adequate sampling bandwidth | Descriptive spectra and power |
| M05 | Contact statistics | Continuous voltage | RMS and window peak-to-peak measurements |
| M05 | Group amplitude outliers | Explicit groups and comparable references | Optional project candidates |
| M06 | Adjacent changes | Original FieldTrip installed; window at least 10 s | Merged time candidates |
| M07 | Event timing | Supported registered annotations | Source-clock event observations |
| M08/M09 | Aggregate and report | Saved evidence | Coverage, candidates, methods and review locations |

## 3 Rules

### 3.1 Flatness

Original MNE `annotate_amplitude`: flat=0, peak=None, minimum duration=50 ms, bad_percent=5. The duration follows MNE-BIDS inspection; the percentage routes findings to contact or interval outputs. Neither is a universal clinical cutoff. Merged intervals do not establish which contact was affected.

### 3.2 Encoding-limit plateaus

`ieeg_range_plateau`: at least three consecutive samples within one quarter of a quantization step of a file calibration endpoint. Use actual reader calibration, never observed signal extrema. EDF encoding limits need not equal hardware ADC limits; a hit suggests possible clipping, not proven saturation. The three-sample minimum is a project parameter.

### 3.3 Within-group amplitude outliers

`ieeg_group_outliers` is opt-in. Map every selected source contact to an explicit group using `comparison_groups`; confirm comparability with `reference_confirmed=true`. Groups must reflect acquisition and research context, not guessed name prefixes.

Subtract each contact's median, compute RMS, then take log10. Compute z=(log10 RMS − group median)/normal-scaled MAD using the original SciPy MAD function. Default absolute z>4 proposes a candidate, with at least four contacts per group. These are uncalibrated project parameters. With unconfirmed references, insufficient contacts, nonfinite/constant signals or near-zero MAD, retain measurements without assigning a pass. This is an independent project rule, not an IEEG_Pipelines or ABCD implementation.

### 3.4 Adjacent changes

Original FieldTrip `ft_artifact_zvalue`, absdiff=yes, cumulative=no, no band-pass or padding; project default z=4. Preserve merged interval evidence and maximum channel z values. Seizures or stimulation may also trigger candidates. This method is opt-in, never automatically enabled; the trusted optional runtime must be installed. No code is downloaded during a job.

## 4 Reporting and optional scores

The default total uses numerical validity (30%) and signal stability (70%). Related raw outputs use 100 × (1 − candidate amount / assessed amount) and contribute through one stability score, not repeated weights. See [scoring rules](/en/standards/ieeg-scoring). MNE preserves separate contact/time denominators. Encoding-limit plateaus use finite calibrated channel samples; group outliers use assessed contacts; FieldTrip uses assessed time. Invalid groups do not count as passes. Different denominators do not describe one additive artifact fraction.

Save source positions, parameters, effective denominators, windows and version. PSD/RMS are descriptive, not direct scores. Short patterns crossing processing windows may be missed; report window scope.

## 5 Dataset evidence and validation

BIDS records channel/electrode metadata and source status labels; it does not prescribe a universal bad-contact threshold. Preserve source labels separately from detected candidates. The local MNE and OpenNeuro examples validate execution and source clocks, not clinical accuracy. Some source references are n/a and groups are absent; do not invent them to enable thresholds.

Before standard adoption, freeze the rules and measure false positives and misses against independently reviewed contacts and intervals, stratified by reference, preprocessing and ictal/interictal context.

## 6 Sources

- [MNE amplitude annotations](https://mne.tools/stable/generated/mne.preprocessing.annotate_amplitude.html)
- [MNE-BIDS inspection](https://mne.tools/mne-bids/stable/generated/mne_bids.inspect_dataset.html)
- [EDF specification](https://www.edfplus.info/specs/edf.html)
- [FieldTrip artifact detection](https://www.fieldtriptoolbox.org/tutorial/preproc/automatic_artifact_rejection/)
- [SciPy MAD](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.median_abs_deviation.html)
- [BIDS intracranial specification](https://bids-specification.readthedocs.io/en/stable/modality-specific-files/intracranial-electroencephalography.html)
- [OpenNeuro ds004100 v1.1.3](https://openneuro.org/datasets/ds004100/versions/1.1.3)

[ECoG scheme](/standards/ecog) · [sEEG scheme](/standards/seeg)

## Workbench configuration

Select the within-group outlier method under Advanced settings, expand Contact comparison groups, assign every selected contact a group from acquisition records, and confirm comparable reference and acquisition conditions. A group edit revokes that confirmation. Unconfirmed groups provide measurements only.
