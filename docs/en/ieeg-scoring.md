# ECoG and sEEG scoring rules

Project draft · ieeg-score/0.1 · 2026-11-08 · Awaiting expert review

## 1 Presets

ECoG uses `ecog-basic-score/0.1`; sEEG uses `seeg-basic-score/0.1`. Both currently use numerical validity (30%) and signal stability (70%). These project weights are adjustable, not clinically calibrated or mandated by an external standard.

Numerical validity = 100 × (1 − NaN/Inf samples / all assessed channel samples).

Signal stability = minimum valid score among selected MNE contact/time candidates, calibrated file-limit plateaus, optional FieldTrip adjacent changes and optional within-group amplitude outliers.

Overall = sum(component × effective weight) / sum(effective weights).

## 2 Count related evidence once

MNE flatness is enabled by default. EDF/BDF file-limit checks need calibration. FieldTrip and group outliers remain optional; the latter requires explicit groups and comparable references. PSD, band power, RMS, peak-to-peak, events and visualizations remain descriptive.

A flat segment identified by two methods with scores of 80 yields stability 80, not 60. With numerical validity 100, the default total is 86. Related evidence cannot be positively weighted alongside the stability summary. APIs reject duplicate configurations.

This groups related evidence; it is not an exact sample-wise union or causal identification. Distinct non-overlapping problems are not added either, which can understate combined burden. Raw method scores and locations remain available under Stability evidence. Adding an optional method can change stability and must be recorded for comparison.

## 3 Coverage and missingness

Pool each method's native numerator and denominator across the recording first, then take the minimum method score. Do not average per-window minima. Contact candidates are duration-weighted by analysis block; time and sample fractions retain their native denominators.

Unavailable evidence is excluded, not filled with 100. With no valid stability evidence, its effective weight becomes zero and other valid components are renormalized. If every component is unavailable, or the planned recording scope is incomplete, no overall score is produced. Compare only matching configurations and assessed scopes.

## 4 Report and version

Results show the total, two components, effective shares and findings. Raw method scores remain expandable evidence and do not receive repeated weight. Preset, parameters and weights are frozen with each run; revisions create new reports. A score of 100 means selected checks found no candidates, not proven clinical quality.

See [intracranial check rules](/en/standards/ieeg-checks) for algorithms and sources. The grouped aggregation and weights are DBCI-QC project choices, not MNE, FieldTrip or BIDS standards.
