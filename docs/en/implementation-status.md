# Current implementation and validation scope

Informative document · Version implementation/1 · 2026-10-31 · Software baseline 1.0.0rc3.dev8

[General requirements](/standards/overview) · [Field dictionary](/standards/fields) · [Method applicability](/standards/applicability)

This document maps requirements to current software without establishing acceptance thresholds. Successful execution, numerical equivalence, independent label validation and clinical validity are different evidence levels.

## 1 Data description and readers

| Item | Current capability | Boundary |
| --- | --- | --- |
| metadata-fields/1 | 35 definitions; both languages generated from one catalog | Design contract, not a completed intake, storage or runtime API migration |
| Technical metadata | Reader-dependent channels, sampling, duration, units, structure and annotations | Unextracted information is not evidence of absence |
| Context | Existing disease, age-group and task options | Complete species, numeric age/unit/time context and state-interval models are not implemented; human age groups must not be applied to animals |
| File entry points | EDF, BDF, BrainVision, EEGLAB SET, FIF, SpikeGLX and NWB 2/HDF5 | Companion files, calibration, timing and supported object requirements apply; not all content in these containers is supported |
| NWB | Supported continuous ElectricalSeries and LFP/FilteredEphys objects | Units are not continuous voltages; readable generic LFP does not imply a complete QC route; NWB-Zarr is unsupported |

The catalog is not a runtime request schema. Existing jobs retain their frozen inputs and configurations. Three real-source mapping exercises are stored under examples/metadata with a separate validation record; they do not establish a deployed metadata importer.

## 2 Modules and routes

| Route | Implemented checks | Interpretation boundary |
| --- | --- | --- |
| [Scalp EEG](/standards) | Integrity, spectrum, channel candidates, conditional artifact methods and event checks | Method-specific prerequisites; no universal clinical cutoff or cross-species validity claim |
| [ECoG](/standards/ecog) | Descriptive M03–M05; M07 for registered events; explicitly optional FieldTrip difference candidates in M06 | Pathological activity is not automatically an artifact; contact thresholds and scores remain uncalibrated |
| [sEEG](/standards/seeg) | Separate route/parameters; descriptive M03–M05, event checks and optional FieldTrip difference candidates | Electrode-shaft relations, pathology and anatomical suitability are incomplete |
| [Neuropixels voltage](/standards/neuropixels) | Single-stream M03–M05, conditional M07 and optional SpikeInterface AP channel candidates | No M06, sorted-unit QC, drift or cross-stream synchronization; other extracellular systems are not automatically Neuropixels |

Each job uses one supported modality/compatible channel group or independent continuous stream. Streams are not silently concatenated. Shared M01–M09 identifiers do not establish shared algorithms, parameters or validation scope.

## 3 Optional research extensions

| Method | Actual implementation | Current boundary |
| --- | --- | --- |
| FASTER channel statistics | mne-faster Python implementation | Not the original MATLAB FASTER; equivalence is unproven |
| FieldTrip difference intervals | Upstream method via Octave compatibility backend | Difference z-value candidates, not the entire FieldTrip artifact pipeline; MATLAB equivalence unproven |
| SpikeInterface AP channels | Upstream std/MAD methods, per source shank | Supported AP conditions only; not full LF/IBL methods or unit quality |
| ASR impact assessment | Upstream implementation via Octave | Explicit calibration interval required; whole-record automatic window recalibration rejected |
| CleanLine impact assessment | Upstream implementation via Octave | Metrics and before/after PSD; MATLAB equivalence unproven |
| Zapline-plus impact assessment | Upstream implementation via Octave | An overprocessing example retains a warning; processing is not presumed beneficial |

These extensions do not enable default cleaning. Temporary copies support impact assessment; complete cleaned-waveform export, whole-record cleaning and paired review are not implemented. PyPREP RANSAC, local AutoReject and ICLabel remain planned.

## 4 Reports and evidence

Reports preserve method/configuration identity, metrics, candidates, coverage, unassessed reasons and separate human decisions. The total score remains uncalibrated: score.value is null. Execution coverage is not a quality score.

Optional extensions have actual public-file runs across four routes plus synthetic and rejection-path tests, documented in repository docs/research-adapter-validation-20261031.md and docs/optional-methods-runtime.md. This evidence establishes bounded engineering behavior, not sensitivity, specificity or signal preservation across species, diseases and tasks.

The metadata exercise uses human EEG, monkey ECoG and mouse LFP sources, preserving missing age, age at experiment start and age in months respectively. The mouse source uses a Neuronexus probe and does not qualify for the Neuropixels route. See repository docs/metadata-validation-20261031.md.

Development tasks remain in repository TODO.md and are neither normative requirements nor implementation evidence. Update this document with implementation changes; existing reports retain their original versions.
