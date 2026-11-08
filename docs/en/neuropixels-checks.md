# Neuropixels check rules

Project technical specification · Version neuropixels-checks/0.1 · 2026-11-08 · Expert review pending

## 1 Implemented checks

| ID | Module | Applies when | Output and interpretation |
| --- | --- | --- | --- |
| NP01 Structure/calibration | M01 | All continuous streams | Companion files, frames, scaling and channel identities; invalid required calibration blocks intake |
| NP02 Stream/time | M02 | All continuous streams | AP/LF/LFP, native clock, origin and gaps; no assumed cross-stream synchronization |
| NP03 Non-finite values | M03 | All selected neural samples | Per-channel NaN/Inf counts and intervals; zero non-finite values alone do not establish quality |
| NP04 Constant runs | M03 | All selected neural samples | Exact-run counts, window-local maximum duration and fully constant channels; quantized equality alone is not a bad channel |
| NP05 Spectrum | M04 | Enough samples for the actual Welch window | PSD, resolution and line-frequency neighborhood power; descriptive, not a bad-channel score |
| NP06 Channel statistics | M05 | At least one finite sample | Mean, standard deviation, RMS and peak-to-peak with finite denominators; no universal amplitude cutoff |
| NP07 AP dispersion | M05 | AP, source shanks, at least eight channels per shank and eligible windows | Original SpikeInterface std/MAD candidates and method score; good does not exclude dead/out |
| NP08 Events | M07 | Registered events with known clock/format | Field/range/sample mapping; not hardware synchronization |
| NP09 Coverage/report | M08–M09 | Every run | Assessed/failed/missing ranges, findings, parameters and versions; extracts do not represent whole experiments |

## 2 Fixed AP method contract

The execution environment requires the SpikeInterface research dependency; when absent, this check is unassessed and descriptive outputs are retained. The adapter calls SpikeInterface 0.104.2 detect_bad_channels, default method MAD. Per-shank defaults: 300 Hz high-pass, 20 random chunks of 0.3 s, seed 0 and five times the median channel MAD. std is an alternative parameter, not an independent penalty.

Processing windows require 1–120 s, at most 256 MiB of float input, a rate supporting the high-pass and at least two chunk durations. Each tail window is checked independently. Random chunks may overlap; 20 × 0.3 s does not establish six independent seconds. Internal detection filtering does not replace the source recording.

Non-finite input, a zero median across the input-channel standard deviations within a shank or upstream failure makes the method unassessed. Fully constant windows remain separate NP04 review findings. AP score = 100 × (1 − unique candidate channels / assessed channels). Across windows, pool candidate-channel × duration and assessed-channel × duration; this is not exact contaminated time. Missing window evidence prevents a whole-record method score. Repeated candidate identities are not counted twice.

## 3 Not yet implemented

| Check | Required evidence |
| --- | --- |
| IBL coherence+psd / dead/out | Verified physical geometry, depth order and separate probe/shank AP input |
| Error-bit or dropped-sample decoding | Original status words and supported device/version bit definitions |
| Cross-stream synchronization | At least two streams with synchronization events and separate clocks |
| Clipping/saturation | Verified hardware or encoding bounds and gains; EDF limits are not transferred |
| Drift | Located/detected spikes or suitable motion input, time and geometry |
| Sorted-unit QC | Sorting, unit IDs, spike times and metric-specific waveform/amplitude inputs |

## 4 Evidence and project choices

[SpikeGLX metadata](https://billkarsh.github.io/SpikeGLX/Sgl_help/Metadata_Help.html) supports structure and clock checks. [SpikeInterface](https://spikeinterface.readthedocs.io/en/stable/modules/preprocessing.html#detect-bad-channels-interpolate-bad-channels) distinguishes std/MAD from coherence+psd, which alone supplies dead/out. [IBL](https://docs.internationalbrainlab.org/_autosummary/ibllib.ephys.ephysqc.html) motivates raw RMS/spectral review. [Allen](https://allensdk.readthedocs.io/en/latest/_static/examples/nb/ecephys_quality_metrics.html) informs future unit dimensions and their limitations.

The eight-channel minimum, one-second execution floor, 256 MiB limit, five-times default and component score are project adapter/configuration choices, not universal acceptance limits. See the [Neuropixels specification](/en/standards/neuropixels).
