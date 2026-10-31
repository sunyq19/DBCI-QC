# Neuropixels voltage quality-check specification

Project technical specification · Version neuropixels-voltage/2 · 2026-10-31 · Document revision 2 · Research use

Shared requirements: [general requirements](/standards/overview), [field dictionary](/standards/fields), [method applicability](/standards/applicability). Actual capabilities are listed separately under [implementation scope](/standards/implementation). Species and age retain source, units and time context; human age categories must not be applied to animals. These metadata requirements do not change existing analysis-profile versions or establish new cross-species thresholds.

## 1 Scope

For supported Neuropixels SpikeGLX raw AP/LF streams or continuous NWB 2/HDF5 ElectricalSeries with explicit Neuropixels device evidence. NWB voltage may be source-processed LFP; retain processing declarations instead of calling all input raw AP/LF. Internal modality: extracellular; recording system: Neuropixels. No sorting/unit input, spike sorting, drift correction or neuron-quality assessment is implemented. Reader contracts cover explicit probe types 0, 21 and 24. Real-data validation currently covers NP1; NP2 has synthetic decoding tests only.

## 2 Input

For SpikeGLX, upload the .bin and same-stem .meta for one complete stream, optionally in a ZIP. For NWB, upload one file and explicitly select one continuous ElectricalSeries. Require device evidence, rate, mapping, calibration and time origin. Keep SpikeGLX analog channels separate from digital sync words. Read NWB electrode-table rows and conversion fields explicitly. Missing calibration or device identity must not be guessed; Units are not continuous voltage.

## 3 Configuration

analysis_profile is neuropixels-voltage/2 and the configuration key is method_config.neuropixels. Default Welch windows are 0.1 seconds for AP and 1 second for LF/LFP or other confirmed Neuropixels voltage; line_frequencies_hz=[50,60]. Preserve effective frequency resolution; these are not universal noise thresholds.

## 4 Execution and results

Use the shared upload, confirmation, planning, execution and reporting flow. Default M03–M05; M07 can check registered events. M06 is unimplemented. One stream per plan with its native sample rate; no automatic stream joining or cleaning. score.value remains null.

## 5 Module requirements

### 5.1 M01 Data intake and structure checks

For SpikeGLX, check binary length, rate, saved-channel count, mapping, gains and firstSample; preserve sync-word identity. For NWB, check continuous ElectricalSeries, device evidence, electrode mapping, unit conversion and each stream clock. Units do not add continuous channels.

An arbitrary bare .bin is not Neuropixels input. Supported probe types are constrained by the reader. NIDQ, compressed .cbin, NWB-Zarr and other unsupported acquisition formats are outside this version.

[Module details](/en/standards/neuropixels/modules/M01)

### 5.2 M02 Data characterization and check plan

Select one SpikeGLX AP/LF stream or one NWB continuous ElectricalSeries per plan. Compute voltage metrics only on analog neural channels; retain but exclude sync words. Freeze NWB object path, electrode mapping and clock; changing streams requires a new plan. Freeze neuropixels-voltage/2 parameters and sources.

The internal modality is extracellular; Neuropixels is a recording-system label. Do not join AP/LF or different NWB series into one sampling clock. Probe geometry does not establish verified tissue location. Ordinary NWB voltage or LFP is not automatically Neuropixels input.

[Module details](/en/standards/neuropixels/modules/M02)

### 5.3 M03 Basic signal integrity

Scan nonfinite values and exactly equal adjacent runs; locate all evidence in source sample coordinates.

ADC quantization causes equal adjacent samples. Equality does not establish packet loss or bad channels. No fault diagnosis or automatic repair is inferred from these counts.

[Module details](/en/standards/neuropixels/modules/M03)

### 5.4 M04 Within-stream spectrum observations

Use Welch with a Hann window, 50% overlap and per-segment mean removal. Defaults: 0.1-second AP windows, 1-second LF/LFP or other confirmed Neuropixels voltage windows. Record actual resolution.

Short AP windows may not resolve nearby peaks. Acquisition filtering limits interpretation. Line-frequency observations are not noise verdicts; neural high-frequency activity is not a muscle-artifact deduction.

[Module details](/en/standards/neuropixels/modules/M04)

### 5.5 M05 Per-channel statistics

Compute finite count, mean, standard deviation, RMS and peak-to-peak. Never interpret digital sync words as voltages.

RMS includes neural signal and is not an independent noise floor. Optional SpikeInterface AP std/MAD candidates require supported AP input and source shank groups; candidates are not confirmed bad channels. No unit SNR, ISI violations or drift is computed. A source channel is not a sorted unit.

[Module details](/en/standards/neuropixels/modules/M05)

### 5.6 M06 Artifact method scope

Not implemented in this version; do not substitute EEG/ECoG artifact methods. No destriping, common-reference transformation or motion correction.

Drift requires suitable spatial/temporal evidence and a validated method. Integrity statistics do not establish drift or spike-sorting accuracy.

[Module details](/en/standards/neuropixels/modules/M06)

### 5.7 M07 Source event checks

Check fields, time range and source sample mapping for registered or explicitly mapped events. NWB events must use the selected stream origin, not another series clock.

No automatic sync-edge extraction or cross-probe/AP/LF clock calibration. Similar timestamps or the presence of a sync channel do not establish alignment.

[Module details](/en/standards/neuropixels/modules/M07)

### 5.8 M08 Evidence summary and aggregation

Summarize observations, not-assessed states, failures and sources; retain stream-specific scope.

No sorting-quality score, unit yield or usable-neuron conclusion. AP and LF streams are not two independent biological samples.

[Module details](/en/standards/neuropixels/modules/M08)

### 5.9 M09 Reporting and review

Produce a continuous-voltage report with independent review, the selected stream, source processing and unassessed scope. Source-processed LFP must not be presented as unprocessed acquisition data.

The report does not imply spike sorting or unit QC. Future unit reports must reference sorter version, settings, raw data, clock mapping and independent metric evidence.

[Module details](/en/standards/neuropixels/modules/M09)

## 6 Layers and validation limits

The continuous-voltage layer describes voltage and sampling integrity, distinguishing native acquisition from source-processed LFP. A future sorting layer requires unit identity, spike times, sorter versions and source-recording links. Firing rate, presence ratio, ISI violations and SNR require their own inputs and assumptions. Preserve dependencies, clocks and missing values; toolkit defaults are not universal standards. Only the continuous-voltage layer is connected here. Keep real-example acceptance separate from synthetic boundary tests; neither establishes clinical or sorting accuracy.

[SpikeGLX metadata](https://billkarsh.github.io/SpikeGLX/Sgl_help/Metadata_Help.html) · [SpikeInterface recording and sorting](https://spikeinterface.readthedocs.io/en/latest/modules/core.html) · [Neuropixels analysis example](https://spikeinterface.readthedocs.io/en/stable/how_to/analyze_neuropixels.html)

## 7 Example scope

Acceptance examples have distinct purposes. Format fixtures are not neural-quality ground truth.

| Example | Data range | Validation purpose | Status |
| --- | --- | --- | --- |
| Human Pt03 AP | Original binary frames from recording seconds 60–62; companion header records the derived excerpt | Biological signal reading, source time mapping and basic module execution | Independent readback passed; execution is recorded in versioned acceptance |
| Noise4Sam LF | 5.2652 seconds from a public format fixture | LF calibration, stream identity and basic execution | Independent readback passed; not a physiological benchmark |
| Human AP short window | A 0.02-second selection within the verified Pt03 excerpt | Short windows and partial reports when frequency resolution is insufficient | Boundary case, not another observation |
| ACSF AP | Public fixture with a binary SHA1 inconsistent with its declaration | Rejection of inconsistent source identity | Negative fixture, not registered or analyzed |
| Truncated Noise4Sam AP | Public shortened file with inconsistent original length and hash declarations | Rejection of inconsistent companions | Negative fixture, not registered or analyzed |

Only a specified byte range of Pt03 was downloaded. Do not claim verification of the complete original file MD5. Preserve the source URL, range, original header, derivative metadata changes and excerpt hash. Actual coverage and execution status belong in versioned acceptance records.

[Pt03 public source](https://zenodo.org/records/5899237) · [Neo public format fixtures](https://gin.g-node.org/NeuralEnsemble/ephy_testing_data)

### 7.1 NWB extension in 1.0.0rc3.dev4

The current profile is `neuropixels-voltage/2`; historical `neuropixels-raw/1` jobs keep their frozen interpretation. The Allen probeD NWB LFP retains explicit timestamps and device-extension declarations. Distant sampled windows contain zeros, making this an abnormal-signal boundary, not a normal physiological benchmark. Its electrode-group rate conflicts with the timestamps and should be disclosed. Other real ECoG or ordinary LFP examples do not become Neuropixels inputs. See [NWB examples and provenance](../../nwb-testing.md) for source and derivative details; execution status remains in the versioned acceptance record.
