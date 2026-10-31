# DBCI-QC

**A modular electrophysiology quality-control toolkit with an optional local workbench.**

[中文](README.md)

DBCI-QC connects file reading, metadata confirmation, method selection, module execution and independent review through a traceable workflow. Current routes cover **scalp EEG** and **basic descriptive checks for ECoG, sEEG and Neuropixels continuous voltage**. Users upload data first; confirmed metadata determines the analysis route.

Development version: **1.0.0rc3.dev8**. The previous tagged release candidate is **1.0.0rc2**. The main deliverable is an independently installable Python toolkit with Python and CLI interfaces. The website is optional. See the [toolkit contract](docs/toolkit.md), [change log](CHANGELOG.md), [versioned validation records](docs/runtime-validation.md) and [pending work (Chinese)](TODO.md).

Documentation: [general requirements](docs/en/workflow-standards.md) → [field dictionary](docs/en/metadata-fields.md) → [method applicability](docs/en/method-applicability.md); [current implementation](docs/en/implementation-status.md) separates implemented capability from the design.

## Workflow

```text
Read local files → Confirm channels and acquisition information → Confirm recommended plan
                                                                          ↓
Independent review ← Report, candidate locations and waveform evidence ← Run modules
```

Uploading and requesting recommendations do not start analysis. File-declared channel types can provide a suggestion; defaults, missing fields and conflicts require confirmation. Unknown information stays unknown. Disease and task labels provide context and currently do not select quality thresholds.

Original signals are not deleted, interpolated, re-referenced or overwritten. Reports preserve measurements, actual coverage, unsupported checks and failure reasons.

## Module organization

| Module | Shared responsibility |
| --- | --- |
| M01 | Read sources and check structure, units and file identity |
| M02 | Characterize data and freeze scope, methods and dependencies |
| M03 | Check signal integrity |
| M04 | Describe spectra and investigate measurable interference |
| M05 | Assess channel evidence using methods valid for the route |
| M06 | Evaluate applicable artifact indicators |
| M07 | Check registered state and event timing |
| M08 | Aggregate component evidence, coverage and limitations |
| M09 | Produce reports and support independent review |

The toolbox groups methods by their purpose. Modality and activation conditions are method attributes. Shared responsibilities do not imply shared thresholds: scalp EEG methods include available PREP-related, MNE and autoreject adaptations, while the descriptive routes below have distinct input gates and configurations.

| Route | Current scope | Limits |
| --- | --- | --- |
| scalp-eeg/1 | Confirmed scalp EEG | Each detector has separate prerequisites and validation limits |
| ecog-basic/1 | Confirmed surface-contact voltages | No inferred grid adjacency or automatic bad-contact classification |
| seeg-basic/1 | Confirmed depth-contact voltages | No inferred shaft/bipolar topology or pathological-artifact classification |
| neuropixels-voltage/2 | One SpikeGLX AP/LF stream or a continuous NWB ElectricalSeries with explicit Neuropixels device evidence | Sync words excluded from voltage analysis; no sorting or unit-quality assessment |

ECoG, sEEG and Neuropixels provide M03 integrity observations, M04 Welch/narrow-band descriptions and M05 per-contact statistics. Registered events can enable M07. ECoG/sEEG M06 can explicitly run FieldTrip difference-based interval indicators; Neuropixels M06 remains unimplemented. See [architecture](docs/en/architecture.md) and the [modality integration design](docs/multimodal-extension.md).

## File support

| Format | Upload | Current scope |
| --- | --- | --- |
| EDF / EDF+ | One `.edf` | Continuous waveforms |
| BDF | One `.bdf` | Continuous data with native sampling streams |
| BrainVision | `.vhdr`, `.vmrk` and `.eeg` together in a ZIP | Complete companion set |
| EEGLAB | Embedded `.set`, or `.set` and `.fdt` in a ZIP | Continuous data |
| FIF | One `.fif` | Single-file Raw data |
| SpikeGLX | One `.ap.bin` / `.ap.meta` or `.lf.bin` / `.lf.meta` pair in a ZIP | Supported Neuropixels raw stream, with neural and sync channels distinguished |
| NWB 2 / HDF5 | One `.nwb` file | Continuous ElectricalSeries; select and freeze one stream; Units are not continuous channels |

The upload and uncompressed ZIP limits are both **512 MiB**. One package represents one recording or one SpikeGLX stream. EDF+D/BDF+D, epoched EEGLAB, split FIF, NWB-Zarr, compressed `.cbin`, NIDQ and spike/unit inputs are outside the current workflow. File format alone does not determine modality; support depends on the actual channel declarations and reader constraints. See [format contracts](docs/file-formats.md).

Neuropixels reader contracts cover declared probe types 0, 21 and 24. **Real-data validation currently covers NP1 only; NP2 has synthetic decoding tests only.** Raw-recording descriptions do not establish sorting accuracy or unit quality.

NWB is a container, not an anatomical modality. Each ElectricalSeries retains its own electrode mapping, units and clock. The selected stream is frozen with the input revision and execution plan. Other NWB voltage is confirmed as scalp EEG, ECoG or sEEG from source evidence, rather than forced into the Neuropixels route. See [NWB examples and provenance](docs/nwb-testing.md) and the [manifest](datasets/nwb-examples.json) for the real human ECoG excerpt, legacy LFP and synthetic multistream/Units boundaries.

## Installation and local use

The tested scientific environment is Linux with Python 3.11. The workbench has no frontend build step. Node.js is used for development checks. Installing this package does not install external scientific backends automatically.

```bash
git clone https://github.com/sunyq19/DBCI-QC.git
cd DBCI-QC
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m pip install "brainelecqc[qc,readers,figures] @ git+https://github.com/Jlei61/BrainElecQC.git@f007d829712d1b824cda79409d181a3313d6a78f"
python -m pip install "mne==1.13.2" "autoreject==0.5.1" "h5io==0.2.5" "pymatreader==1.3.2"
python -m pip install "pynwb==3.1.3" "hdmf==4.3.1" "h5py==3.16.0"
```

BrainElecQC is installed separately and is not redistributed in this repository. The [tested environment record](profiles/tested-environment.json) is not a complete dependency lock. See [third-party notices](THIRD_PARTY_NOTICES.md).

Use the toolkit without starting the website:

```bash
dbci-qc catalog
dbci-qc inspect /path/to/record.edf
python examples/headless_qc.py --output /path/to/new-demo
```

For the local workbench, copy the minimal configuration and set its `python` and `data_dir` fields to absolute local paths. Keep runtime data outside the repository. Preserve any existing configuration.

```bash
mkdir -p .local
cp -n apps/workbench/workbench.minimal.json .local/workbench.json
python apps/workbench/server.py --config .local/workbench.json
```

Open [http://127.0.0.1:8769/](http://127.0.0.1:8769/). The service listens locally and requires no login. Uploaded copies remain in the configured local runtime directory. On Linux, `python scripts/run_local.py` also supports background startup, `--status` and `--stop`. See the [workbench API documentation](apps/workbench/README.md).

## Public examples and reproducibility

```bash
python scripts/public_examples/prepare_ecog_example.py --output /path/to/ecog-examples
python scripts/public_examples/prepare_seeg_example.py --output /path/to/seeg-examples
python scripts/prepare_neuropixels_samples.py --destination /path/to/neuropixels-examples
```

These scripts keep sources, provenance, upload samples and registration drafts outside the repository. They do not register records in the workbench or start QC tasks.

- ECoG: original BrainVision and a lossless FIF representation of one public observation; not two independent participants.
- sEEG: a byte-identical public FIF excerpt, with 119 contacts and 32 task annotations. Original nonzero sample origin is retained.
- Neuropixels: a declared two-second excerpt from human Pt03 raw AP data, plus a Noise4Sam LF format fixture. The remote full AP file checksum was not verified because only a specified byte range was downloaded.
- ACSF AP and truncated Noise4Sam AP are retained as rejected source-consistency examples, not runnable registrations. The 0.02-second boundary check selects a window from the verified human AP excerpt.

The earlier scalp EEG coverage set contains seven public datasets and 26 records. Format fixtures, derivative representations, biological observations and quality ground truth are counted separately. Task, sleep and seizure annotations are not artifact ground truth. See [public examples](docs/public-examples.md), [modality-specific scope](docs/multimodal-extension.md) and [validation records](docs/runtime-validation.md).

Each run retains source hashes, input/configuration versions, chosen methods, actual windows, software environment and outputs. Human decisions are separately versioned. Short-window and whole-record checks retain evaluated, failed and unexecuted coverage; windowed execution is not equivalent to fitting a method once to the complete recording.

## Validation and limitations

```bash
python scripts/check_release.py
```

Automated checks cover readers, plans, module isolation, revisions, review conflicts, window coverage and UI state. Tests requiring local data may skip in a fresh environment. Real-file acceptance and browser review are separate from unit tests.

**Overall quality scores remain `null` because no unified score has been calibrated.** Independent expert-labelled accuracy has not been established. Current sEEG and Neuropixels routes are descriptive. Spike sorting, unit SNR/ISI metrics, probe drift, cross-stream synchronization, disease-specific classification and Linxi host integration are not implemented. Project specifications are technical drafts, not published industry standards.

## Documentation

| Topic | Entry |
| --- | --- |
| Toolkit handoff | [Python, CLI and package contract](docs/toolkit.md) |
| Architecture | [English](docs/en/architecture.md) · [中文](docs/architecture.md) · [Modality integration design](docs/multimodal-extension.md) |
| General workflow | [English specification](docs/en/workflow-standards.md) |
| Route specifications | [Scalp EEG](docs/en/qc-standards.md) · [ECoG](docs/en/ecog/qc-standards.md) · [sEEG](docs/en/seeg/qc-standards.md) · [Neuropixels](docs/en/neuropixels/qc-standards.md) |
| Evidence | [Data validation](docs/data-validation.md) · [Runtime acceptance](docs/runtime-validation.md) · [Method sources](docs/toolkit-sources.md) |
| Research candidates | [Six source-reviewed methods, not executable (Chinese)](docs/qc-methods-review-20261031.md) |
| Version control | [Versioning](docs/versioning.md) · [Change log](CHANGELOG.md) |

The workbench serves these versioned specification sources and links each module to its detailed page. Core modules live in `src/ephys_qc/modules/`; sEEG and Neuropixels use distinct entrypoints over shared descriptive kernels in `modules/continuous/`. Source readers, recommendations and plans are independent of `apps/workbench/`.

## Sources and licensing

[BrainElecQC](https://github.com/Jlei61/BrainElecQC) provides the initial scalp EEG backend. DBCI-QC supplies the common contracts, routing, scheduling, evidence reports and review workflow, with additional MNE and autoreject methods. Neuropixels voltage uses SpikeGLX or a supported NWB reader with device evidence; voltage measurements do not invoke spike sorting.

This repository has not yet designated a project license. Third-party code and data retain their own terms. Raw recordings, private annotations, runtime reports, machine configuration and installed third-party packages are excluded from version control.
