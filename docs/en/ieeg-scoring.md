# ECoG and sEEG scoring rules

Project draft · ieeg-score/0.2 · 2026-11-09 · Awaiting expert review

## 1 Two levels of weights

ECoG uses `ecog-basic-score/0.2`; sEEG uses `seeg-basic-score/0.2`.

| Component | Default share | Calculation |
| --- | ---: | --- |
| Numerical validity | 30% | 100 × (1 − NaN/Inf samples / assessed channel samples) |
| Signal stability | 70% | Weighted mean of valid child scores |

Stability = sum(valid child score × child weight) / sum(valid child weights).

Overall = sum(valid component score × component weight) / sum(valid component weights).

Both levels are adjustable in Advanced settings → Scoring. Child checks have equal default weights. Zero excludes a check from that level without discarding measurements. These are project settings, not clinically calibrated or mandated by an external standard.

## 2 Stability checks

Default checks are MNE flat-channel and flat-interval candidates, plus file-range endpoint plateaus where valid EDF/BDF calibration exists. FieldTrip jump intervals and grouped contact outliers are optional; grouped checks require explicit comparable references. Each child score is 100 × (1 − its candidate fraction), retaining its native denominator.

Only selected, valid checks with positive weights participate. Preset child weights do not enable optional algorithms. Example: scores 80 and 100 with shares 75% and 25% yield stability 85. With validity 100 and top-level shares 30%/70%, the total is 89.5.

## 3 Avoid repeated weight

Stability receives one top-level share; its children cannot also receive separate top-level weights. Two scores of 80 average to 80, rather than subtracting 20 twice. This is a weighted index, not an interval union or usable-time fraction. Correlated methods may flag the same finding; changing the method set changes the effective shares. Compare matching methods, parameters, weights and scopes. PSD, band power, RMS, peak-to-peak, events and visualizations remain descriptive.

## 4 Coverage and missingness

Pool each method's native numerators and denominators across the recording first, then apply child and parent weights. Channel fractions use block-duration weighting; sample and time fractions keep their native denominators. Do not simply average per-block scores.

Unavailable children receive zero effective weight; valid children are renormalized. Missing results are never filled with 100. With no positive valid children, stability is excluded from the overall mean. No overall score is produced when all components are unavailable/disabled or the planned scope is incomplete.

## 5 Report and version

Expandable results show child scores, effective shares, deductions and measurements. Configuration and effective weights at both levels, missingness, parameters and scope are saved with each run. A score of 100 means no deductions from the valid checks performed, not proven clinical quality.

Version 0.2 replaces the minimum child rule with a weighted mean. Version 0.1 runs retain their original formula and results; selecting the new preset creates a new run.

See [intracranial check rules](/en/standards/ieeg-checks). Formulas and weights are DBCI-QC project choices, not MNE, FieldTrip or BIDS standards.
