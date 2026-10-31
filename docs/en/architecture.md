# Platform architecture

Updated 2026-10-31. Current routes: scalp EEG, ECoG, sEEG and supported Neuropixels continuous voltage. Actual execution evidence is recorded separately in the [validation log](../runtime-validation.md).

[中文](../architecture.md)

The platform describes data first, selects applicable checks, and then explains the results. Disease and task labels provide context. Reader capabilities, measurable frequencies, referencing, auxiliary signals and event availability determine executable methods; a disease name does not determine quality.

## 1 Independent workflows

The **data workflow** reads a recording, freezes a plan, computes observations and produces a report for independent review.

The **method-validation workflow** registers independent reference labels, freezes data splits and parameters, executes methods, and measures performance and failure conditions. Successful report generation establishes execution, not detector accuracy. A detector's own labels cannot be its independent ground truth.

The toolkit exposes Python and CLI contracts. The local website consumes the same core and is not required to install or run algorithms. See the [toolkit interface](../toolkit.md).

## 2 Data objects

| Object | Responsibility |
| --- | --- |
| DatasetCard | Source, version, permissions, experiment, acquisition, preprocessing and annotation provenance |
| RecordingDescriptor | Source channels, declared types, units, sampling streams, clock origin and stored ranges |
| QCPlan | Selected group/range, method versions, parameters, dependencies and applicability decisions |
| QCResult | Measurements, candidate evidence, actual coverage, unassessed checks, failures and review links |

Dataset descriptions and recording headers are distinct evidence. Conflicting declarations are preserved. Unknown anatomy, diagnosis or referencing remains unknown.

## 3 Shared navigation and module responsibilities

The user-facing flow is **read → extract → confirm → recommend → execute → report/review**. No confirmed input means a neutral workflow view. File declarations may prefill a suggestion; reader defaults do not establish anatomy. A mixed recording requires a compatible analysis group. Browsing another modality's methods does not change the current data or plan.

The toolbox groups methods by purpose: data and metadata (M01/M02), integrity (M03), spectrum (M04), channel evidence (M05), artifacts (M06), events/time (M07) and reporting (M08/M09). Modality and activation conditions remain method properties.

`catalog(modality=...)` is an internal method-directory interface. Confirmed metadata selects the same modality through recommendations, planning and execution. Each plan/result also freezes `analysis_profile` so that the shared M03–M09 identifiers cannot silently select another implementation.

## 4 Current routes

| Route | Measurement layer | Important exclusions |
| --- | --- | --- |
| scalp-eeg/1 | Scalp EEG methods with their own prerequisites | No automatic extension to invasive or extracellular signals |
| ecog-basic/1 | Basic integrity, descriptive PSD and per-contact statistics | No spatial inference, artifact classifier or calibrated quality score |
| seeg-basic/1 | Separate sEEG entrypoints with descriptive kernels | No inferred shafts, bipolar pairs or pathological-artifact labels |
| neuropixels-voltage/2 | One supported SpikeGLX AP/LF stream or an NWB ElectricalSeries with explicit Neuropixels device evidence | No sorting, unit metrics, drift correction or cross-stream synchronization |

ECoG, sEEG and Neuropixels default to M03–M05 and add M07 for supported registered events. M01, M02, M08 and M09 provide shared infrastructure. ECoG/sEEG can explicitly enable FieldTrip difference candidates in M06; Neuropixels M06 remains unimplemented. Scalp-specific parameters are rejected rather than translated silently.

ECoG, sEEG and Neuropixels keep separate entrypoints in `modules/ecog/`, `modules/seeg/` and `modules/neuropixels/`, sharing descriptive mathematics from `modules/continuous/`. Shared numerical ideas do not imply shared clinical interpretation or threshold calibration. See the [integration design](../multimodal-extension.md), [sEEG specification](seeg/qc-standards.md) and [Neuropixels specification](neuropixels/qc-standards.md).

### 4.1 sEEG

Keep electrode, contact, recording channel and bipolar derivative identities separate. Names do not establish anatomy or adjacency. Preserve references and source bad labels without automatically excluding contacts. Pathological discharges and high-frequency activity can be research targets; they are not automatically artifacts.

### 4.2 Neuropixels

Neuropixels is a recording-system label; the internal modality is `extracellular`. AP/LF identify native voltage streams; supported NWB continuous voltage may also be processed LFP. A sorted unit is a different object. One plan uses one stream. Explicit gains convert analog neural channels to volts; digital sync words retain separate identities and cannot enter voltage statistics.

Default window length respects native sample rate, selected channel count and the 256 MiB input budget. No implicit downsampling is used to conceal an excessive window. Probe type 0 has real NP1 readback evidence. NP2 types 21/24 currently have synthetic decoding tests only; real NP2 validation is not claimed.

A future sorting layer must identify units, spike times, sorter versions, settings and source-recording/time mappings. Unit SNR, ISI violations, presence ratio and other unit metrics are not implemented. Raw RMS cannot substitute for unit SNR or an independently estimated noise floor.

## 5 Execution and state

M01 precedes M02. Measurement modules depend on the frozen M02 data. In the scalp route, M06 additionally depends on M03 candidate intervals; ECoG/sEEG can explicitly request FieldTrip M06 with its declared prerequisites; Neuropixels M06 is unavailable. M08 summarizes only actual results and unassessed states, and M09 writes reports. The workbench stores human decisions separately.

Each method declares inputs, outputs, prerequisites, parameters, source and implementation state. Planned methods are not runnable capabilities. Execution failure and missing prerequisites remain different states. Neither indicates that data are normal. Modifying data selection or parameters creates a new plan/run; existing evidence remains immutable.

All selected signals must belong to a single native sampling stream and a compatible continuous segment. Original sample origins are retained even when file-relative time starts at zero. A source clock declaration does not establish cross-device synchronization or absence of acquisition loss.

## 6 Evidence and limits

Results retain source fingerprints, software/method versions, units, denominators, actual sample ranges and missing/failed checks. Scores remain `null` until a comparison scope and calibration have been established. Execution completion is not quality.

Reading covers continuous EDF/EDF+, BDF, BrainVision, continuous EEGLAB, single-file FIF, NWB 2/HDF5 continuous ElectricalSeries and supported Neuropixels SpikeGLX AP/LF pairs. Physical conversion verifies the declared calibration numerically, not the original instrument's independent metrological accuracy.

Real observations, declared derivatives, format fixtures, synthetic tests and failed source-consistency examples are counted separately. The initial SpikeGLX examples are Pt03 AP and Noise4Sam LF. ACSF AP and truncated Noise4Sam AP remain rejected negative fixtures. The short 0.02-second check uses a window within the verified human AP excerpt and is not another observation. See the [integration data scope](../multimodal-extension.md) and [acceptance records](../runtime-validation.md).

### NWB integration in 1.0.0rc3.dev4

NWB is a container, not another anatomical modality. Multiple ElectricalSeries require explicit selection; object path, electrode-table mapping, units, clock and source fingerprints are frozen with the input revision and execution plan. Units remain separate objects and do not add continuous channels or imply unit QC. Other NWB voltage is confirmed as scalp EEG, ECoG or sEEG from source evidence; Neuropixels requires additional device evidence. No implicit joining, resampling or clock calibration is performed. Historical `neuropixels-raw/1` jobs retain their frozen interpretation; the current `neuropixels-voltage/2` profile does not rewrite them. See [NWB source and test scope](../nwb-testing.md).
