# QC method applicability

Project technical specification · Version applicability/1 · 2026-10-31 · Research use

## 1 Purpose and basis

This document defines the transition from data descriptions to plans. See the [field dictionary](/standards/fields) and [implementation inventory](/standards/implementation). These are project requirements, not universal cross-species quality thresholds.

## 2 Decision order

### 2.1 Signal object

Verify signal object, recording site and acquisition technology first. Continuous voltage, sorted units and derived power/envelopes require their own validated methods. Readable files, voltage unit strings or an EEG name alone do not establish a route.

### 2.2 Technical prerequisites

Each method declares required fields, ranges, dependencies and missing actions. Use the selected stream, channels and interval, not conditions borrowed from another recording in the dataset.

| Condition | Checks that may remain | Restricted operations |
| --- | --- | --- |
| Unverified units/calibration | Reliably interpretable numeric structure | Absolute-voltage criteria and calibration-dependent methods |
| Unknown positions/frame | Non-spatial methods | Spatial prediction/interpolation |
| Unknown reference/comparison groups | Some per-channel descriptions | Same-reference or comparable-channel methods |
| Clock/rate conflict | Structural diagnosis of identifiable objects | Frequency, duration and alignment; reject a stream when needed |
| Missing auxiliary signals | Other applicable methods | Methods requiring EOG/ECG support |
| Insufficient channels/time | Eligible basic metrics | Unsupported estimators; do not return successful empty candidates |
| Unknown species/age | Technical checks within validated scope | Species-/age-specific interpretation and thresholds |
| Unknown processing history | Limited current-signal descriptions | Claims about raw noise or cleaning effectiveness |

### 2.3 Context and validation scope

Task, species, age, disease, animal model and state support interpretation and validation strata. They do not independently establish bad channels, scores or cleaning actions. Specialized thresholds require applicable data, independent validation and a rule version.

Animal ECoG may reuse applicable numeric computation, but does not inherit human clinical or scalp thresholds from a modality label. Computational feasibility and valid scientific decisions are separate claims.

## 3 Method declarations and plans

Each method retains a stable ID, module, upstream project/entry point, version, engine, prerequisites, dependencies, output, parameter provenance and validation evidence. Record Python/MATLAB/Octave execution, compatibility layers, third-party reimplementations and original-author implementations distinctly.

Separate unselected, insufficient conditions, confirmation needed, pending execution, failed and completed states. Existing API codes may remain, but their meaning must be explicit. partial is not a fixed percentage or quality grade.

Request additional information only for selected methods requiring it. Unknown may remain unknown; guessed values must not make a method appear executable.

## 4 Optional processing

Processing requires explicit selection and method prerequisites. Line-noise removal, channel rejection, interpolation, interval rejection and ASR reconstruction are distinct actions, not an undefined repair switch.

ASR calibration retains scope, source, filtering and rank; an automatically selected segment is not confirmed clean. Whole-record processing validates state transfer and edges. Per-window recalibration is not equivalent to one whole-record calibration.

Retain derived copies, processing records and before/after comparisons. Disclose strong changes, upstream overcleaning warnings and unprocessed tails. Metric improvement does not authorize overwriting sources or automatically accepting results.

## 5 Assessment and comparison

Retain original metrics, units, scope and denominators. Overall scores need a separately validated assessment configuration. Unassessed data are not normal; method count, completion and change fractions are not quality scores.

Compare raw records using raw reports and consistent conditions. Compare processed records separately with their processing recipes, without presenting different processing outputs as raw-data quality.
