# Neuropixels continuous-voltage quality-control specification

Project technical specification · Version neuropixels-qc/0.1 · 2026-11-08 · Consultation draft; expert review pending

## 1 Scope and assessment object

This project draft defines checks, routing and reporting for verified SpikeGLX AP/LF streams and NWB continuous ElectricalSeries with explicit Neuropixels device evidence. Execution configuration remains `neuropixels-voltage/2`; the recommendation recipe is `neuropixels-basic-recipe/0.1`. It is not a published industry standard or accuracy-calibrated classifier.

AP and LF/LFP share intake, timing, integrity, spectrum and contact statistics. AP additionally receives conditional channel-outlier screening. Sorted units are a separate object and are not yet supported. High-frequency AP activity is not scalp muscle artifact; one recording channel is not one neuron. Source-processed LFP remains labelled as processed.

[IBL raw-data QC](https://docs.internationalbrainlab.org/_autosummary/ibllib.ephys.ephysqc.html) separately exposes raw RMS/spectral measurements and sorting metrics. This distinction informs the project scope; the full IBL pipeline is not implemented here.

## 2 Required information

Confirm format, selected continuous stream, AP/LF/LFP or unknown band, device model, neural versus digital channel roles, native rate, voltage calibration, source identity, duration and original clock. NWB selection includes the ElectricalSeries path and electrode mapping. Shank/site/geometry enable conditional methods; missing geometry must not be inferred. Preserve reference, processing history, species, age units and experiment context; unknown fields remain unknown.

SpikeGLX frame length, saved words, rate and duration must agree. Digital synchronization words are excluded from voltage statistics; firstSample preserves the original sample origin. See [SpikeGLX metadata](https://billkarsh.github.io/SpikeGLX/Sgl_help/Metadata_Help.html).

## 3 Default routing

Read one stream → confirm channels and clock → integrity, spectrum and contact statistics → conditional AP outlier screening → registered-event checks → report.

M03–M05 are the base modules. M07 is selected when a supported event table is registered. Recommend AP screening only if at least one actual processing window meets the method conditions; an explicit user method list takes precedence. Recheck every window, including short tails. Long recordings retain exact native-sample coverage, gaps and failures. Full-record scanning is distinct from internal random-chunk sampling. Intake limits remain 2 GiB per file and 10 GiB per dataset.

## 4 Interpretation and scoring

Invalid structure or essential calibration blocks intake. Non-finite values, fully constant windows and AP outliers are findings for review. Missing prerequisites, failed methods and unimplemented checks are unassessed, not normal.

The implemented AP outlier component is `100 × (1 − unique candidate channels / assessed channels)`. Across windows, pool channel counts weighted by window duration. std and MAD are alternative settings, not separate penalties. This component does not measure drift, synchronization, neural-unit quality or precise contaminated time. The default report shows the component without declaring a universal Neuropixels total. Explicit project scoring must disclose selected checks, actual weights and exclusions. LF/LFP does not inherit AP scoring. A zero-valued recording is not healthy merely because it has no NaN.

See [Neuropixels check rules](/en/standards/neuropixels-checks).

## 5 Module requirements

### 5.1 M01 Data intake and structure checks

Validate companion files, declared sizes/checksums, frames, gain and signal identity. The current reader recognizes probe types 0, 21 and 24. Real examples cover NP1; NP2 has synthetic contract tests only. Arbitrary bare binaries, cbin, NIDQ and NWB-Zarr are outside the supported input scope.

[Module details](/en/standards/neuropixels/modules/M01)

### 5.2 M02 Data characterization and check plan

Freeze one stream, source channel indices, native clock, selected range, methods and parameters. AP and LF from one experiment are not independent biological samples or automatically synchronized streams. Preserve grouping and processing provenance.

[Module details](/en/standards/neuropixels/modules/M02)

### 5.3 M03 Basic signal integrity

Count NaN/Inf and exactly equal consecutive runs. Record the longest run within each processing window and flag channels constant throughout that window for review. Adjacent quantized equality is not proof of dropped samples. Detail-storage limits never reduce measured counts; runs across computation boundaries are not silently merged.

[Module details](/en/standards/neuropixels/modules/M03)

### 5.4 M04 Within-stream spectrum observations

Welch PSD uses a Hann window, 50% overlap and constant detrending. Default windows are 0.1 s for AP and 1 s for LF/LFP. Report actual frequency resolution and known source filtering. Power around 50/60 Hz is descriptive, not automatic power-line contamination evidence.

[Module details](/en/standards/neuropixels/modules/M04)

### 5.5 M05 Per-channel statistics

Report finite count, mean, standard deviation, RMS and peak-to-peak. RMS includes neural activity and is not a noise-floor estimate.

For AP with source shank mapping, at least eight selected neural channels per shank and an eligible processing window, recommend original SpikeInterface MAD screening. Defaults: 300 Hz high-pass, 20 random 0.3 s chunks, seed 0 and a threshold of five times the within-shank median channel MAD. These are project settings, not acceptance thresholds. Only good/noise labels are implemented; good means below this threshold. IBL coherence+psd and dead/out labels are not implemented. See [SpikeInterface preprocessing](https://spikeinterface.readthedocs.io/en/stable/modules/preprocessing.html#detect-bad-channels-interpolate-bad-channels).

[Module details](/en/standards/neuropixels/modules/M05)

### 5.6 M06 Artifact method scope

No default destriping, rereferencing, motion correction or spike sorting. Future processing modules remain separate; modification fractions are not quality scores.

[Module details](/en/standards/neuropixels/modules/M06)

### 5.7 M07 Source event checks

Validate registered event fields, ranges and sample mapping. Digital error-bit decoding and cross-stream/probe clock alignment are not implemented. A sync channel does not prove synchronization.

[Module details](/en/standards/neuropixels/modules/M07)

### 5.8 M08 Evidence summary and aggregation

Aggregate actual assessed denominators, coverage and missing checks. Distinguish scanning from method-level sampling. Do not convert counts of equal quantized samples into a bad-channel rate.

[Module details](/en/standards/neuropixels/modules/M08)

### 5.9 M09 Reporting and review

Use four sections: Results, Review locations, Chart analysis and Report details. Show band, channels, actual coverage and principal findings first. Preserve source channels and processing windows; channel-only candidates do not acquire invented event onset/offset times.

[Module details](/en/standards/neuropixels/modules/M09)

## 6 Future sorted-unit requirements

Require unit identity, spike times and clock, source recording, sorter version and settings; waveforms, amplitudes and positions depend on the requested metric. Candidate dimensions include firing rate, presence ratio, refractory/ISI violations, amplitude cutoff, isolation and drift. Missing inputs mean unassessed metrics.

Do not simply average these metrics. [Allen unit-metric documentation](https://allensdk.readthedocs.io/en/latest/_static/examples/nb/ecephys_quality_metrics.html) discusses metric biases and cautions against relying on peak-channel SNR alone. No dataset-specific filtering threshold is promoted to a universal project cutoff.

## 7 Validation and versioning

Validate real AP, real LF and explicitly labelled boundary cases separately. Technical annotations, simulated artifacts and physiological events are different evidence types. Version changes to detectors, thresholds, sampling, windows and scores; preserve past runs.

Current NP1 examples include public Pt03 AP 2 s, Pt02 AP 4 s and Pt01 LF 20 s extracts. Completing these local files does not cover the source experiment or validate long-term drift. Noise4Sam and previously identified all-zero NWB extracts are boundary fixtures, not healthy physiological references. Preserve source ranges and derivation records. [Public data source](https://zenodo.org/records/5899237).

Shared requirements: [General](/en/standards/overview), [Fields](/en/standards/fields), [Applicability](/en/standards/applicability). Engineering execution is not independent accuracy validation.
