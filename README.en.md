# DBCI-QC

**A modular electrophysiology quality-control toolkit with a local workbench.**

[中文](README.md) · [Toolkit API](docs/toolkit.md) · [Draft specification](docs/en/qc-standards.md) · [Changes](CHANGELOG.md)

Source baseline: **2026-11-08 / 1.0.0rc3.dev40**. The local workbench is available. The [shared-demo deployment setup](docs/deployment/demo.md) reuses the same interface, with no visitor accounts and one administrator. All uploaded recordings and reports share one data library. See the [deployment checklist](docs/deployment/cloud-readiness.md). The shared flow website documents modules; it does not execute QC on uploaded recordings.

Upload a local file, confirm its modality and channels, run the recommended checks, and review the report. Modules also run through Python or the CLI without the website.

Development version: **1.0.0rc3.dev40**. Current routes cover scalp EEG and basic descriptions of ECoG, sEEG and Neuropixels continuous voltage. EEG reports include trial scores, component results, candidate locations and PDF export. ECoG/sEEG and Neuropixels have adjustable grouped scoring presets.

The [Neuropixels specification](docs/en/neuropixels/qc-standards.md) defines nine continuous-voltage checks. AP conditionally receives original SpikeInterface outlier screening; LF/LFP retains separate descriptive checks. Sorted-unit QC, drift and cross-stream synchronization are not implemented.

Neuropixels AP outlier screening requires the optional SpikeInterface research dependency. If unavailable, that check remains unassessed while the basic measurements are retained. See [research-runtime setup](docs/optional-methods-runtime.md).

## Quick start

Tested on **Linux with Python 3.11 and Git**. Initial installation needs internet access. No Node.js, frontend build or login is required. Windows and macOS have not undergone equivalent validation.

### 1. Download and install

```bash
git clone https://github.com/sunyq19/DBCI-QC.git
cd DBCI-QC
python3.11 scripts/setup_local.py
```

Setup creates `.venv`, installs scientific and PDF dependencies, and generates `.local/workbench.json` with local paths. Existing configuration is preserved. With Conda, activate a Python 3.11 environment and use `python scripts/setup_local.py`.

### 2. Start

```bash
.venv/bin/python apps/workbench/server.py --config .local/workbench.json
```

### 3. Open

Visit **[http://127.0.0.1:8769/](http://127.0.0.1:8769/)**.

```text
Upload → Confirm metadata → Review recommendation → Run → View report / Download PDF
```

Keep the terminal open; stop with `Ctrl+C`. Subsequent launches only need step 2. Upload copies, jobs and reports default to `.local/runtime/`, excluded from Git. Original files remain unchanged. The server binds to localhost only.

For custom directories, ports and upgrades, see the [installation guide](docs/en/installation.md).

## Supported files

| Format | Upload |
| --- | --- |
| EDF / EDF+, BDF | One `.edf` or `.bdf` |
| BrainVision | `.vhdr`, `.vmrk`, `.eeg` together in a ZIP |
| EEGLAB | Embedded `.set`, or `.set` + `.fdt` in a ZIP |
| FIF | One Raw `.fif` |
| NWB 2 / HDF5 | One `.nwb`; select a continuous ElectricalSeries after reading |
| SpikeGLX | One AP or LF `.bin` + `.meta` pair in a ZIP |

Limits are **2 GiB per file and 10 GiB per dataset**. A recording and its companion files must total no more than 2 GiB; recording ZIPs are measured after extraction. Continuous recordings only: EDF+D/BDF+D, epoched SET, split FIF, NWB-Zarr, `.cbin` and sorted units are outside the current scope. Format does not establish modality. See [reader contracts](docs/file-formats.md).

To try a generated engineering example:

```bash
.venv/bin/python examples/headless_qc.py --output .local/demo
```

This generates `.local/demo/synthetic.edf` and runs an integrity check. You can upload that EDF to the workbench. It verifies the workflow, not accuracy on natural artifacts. The output directory must not already exist. See [public examples](docs/public-examples.md) for real data. Configured examples open directly from **Example datasets**, following dataset → recordings → report. See the [example dataset guide](docs/example-datasets.md) for the four-modality local demonstration; recordings and generated reports are not bundled with a new clone.

## Modules and reports

| Stage | Modules |
| --- | --- |
| Read and confirm | M01 File/structure checks; M02 Metadata and execution plan |
| Check quality | M03 Integrity; M04 Spectra/interference; M05 Channels; M06 Artifact indicators; M07 Events/timing |
| Summarize and review | M08 Component assessment; M09 Reporting and manual review |

Implementations are separate files in [`src/ephys_qc/modules/`](src/ephys_qc/modules/). Python and CLI usage is documented in the [toolkit guide](docs/toolkit.md).

When configuring a recording, click M03–M07 in the workflow to expand its methods. Each method shows recommendation, applicability and scoring capability. Core checks follow their parent module; optional methods can be selected individually. Recommendations are independent of the last-run selections. Score components and percentage weights appear directly below stage 02 and update with method selections.

EEG reports show an overview, integrity/line-interference/high-frequency-burst components, channel and time results, candidate waveforms and scoring rules. Whole-record processing runs in background chunks and retains coverage and unassessed conditions.

**Score project-weighted/1.2 is a project trial metric, not an expert-calibrated standard.** A full score means no candidate was detected by the scored checks, not that all aspects of the data are satisfactory. Missing checks are not assigned full marks. ECoG/sEEG and Neuropixels use separate project presets. See [scoring rules](docs/en/eeg-scoring.md) and [report requirements](docs/en/eeg-report.md).

## Methods and extensions

Default setup installs BrainElecQC, MNE-Python, autoreject, PyNWB and PDF dependencies. BrainElecQC provides the initial EEG backend; DBCI-QC provides common reading, applicability rules, orchestration and reporting.

Research extensions such as FASTER, SpikeInterface, FieldTrip, ASR, CleanLine and Zapline-plus need separate dependencies or configuration. They do not all run by default. See [optional methods](docs/optional-methods-runtime.md) and [method sources](docs/toolkit-sources.md).

From a registered dataset, open a subject/session recording directly for signal QC without re-uploading; dataset membership, source fingerprints and run history are retained.

## Documentation and development

- [Install, configure and update](docs/en/installation.md)
- [Toolkit API](docs/toolkit.md) · [Workbench API](apps/workbench/README.md)
- [General requirements](docs/en/workflow-standards.md) · [EEG specification](docs/en/qc-standards.md) · [Check terms](docs/en/eeg-checks.md) · [Evidence](docs/en/eeg-evidence.md)
- [Implementation scope](docs/en/implementation-status.md) · [Installation verification](docs/validation/local-install-20261103.md) · [Pending work](TODO.md)

Development checks additionally require Node.js:

```bash
.venv/bin/python scripts/check_release.py
```

Specifications are unreviewed project drafts, not published industry standards. Outputs support research screening and human review, not clinical diagnosis. Full metadata-dictionary integration, cross-record score comparison and Linxi host integration remain pending.

## Sources and licensing

[DBCI-QC](https://github.com/sunyq19/DBCI-QC) · [Jiaxin Lei / BrainElecQC](https://github.com/Jlei61/BrainElecQC)

BrainElecQC is installed at a fixed commit, not vendored. Raw data, local configuration and reports are not distributed with the repository. This project has not yet selected a license; third-party software and data retain their own licenses. See [third-party notices](THIRD_PARTY_NOTICES.md).

## Dataset checks

Datasets share the same data entry. Open a dataset from **Example datasets** or **Imported data**: D01 file completeness → D02 individual consistency → D03 cohort consistency. Register local package roots and explicit expectations in the local configuration, confirm scope, then run checks in the background. Reports include subjects, groups, conflicts and evidence; no signal-quality score is assigned. Whole-package browser upload is not implemented. Core functions are independent of the UI. See [rules](docs/en/dataset-checks.md) and [configuration](docs/dataset-inventory.md).

Confirmed dataset recordings can be queued as a reviewed sequential batch, cancelled and traced to their reports. EEG results offer overview, candidate review with native-window PSD, and selectable visualizations. Report comparisons group matching configurations; unknown history and excluded frequency bands never become clean scores.

New uploads are retained for **7 days**; reports and saved evidence remain available. Linked originals and legacy development data are excluded from automatic expiry. See [storage and configuration](docs/en/installation.md).

Configure weights in **Advanced settings → Scoring and weights**. Scalp EEG currently supports integrity, line-interference and high-frequency-burst scores. Components use candidate fractions; the total is a weighted mean. Neuropixels uses numerical validity 30% and deduplicated channel status 70%; unavailable components are excluded. Other measurements remain unscored. See the [scoring specification](docs/en/eeg-scoring.md).

Published example reports for four modalities are included in `apps/workbench/example-cache`. The homepage renders them without reading raw data or waiting for the personal library. Scalp EEG defaults to three equally weighted components; eligible optional methods support explicit weights under Advanced settings. See [scoring rules](docs/en/eeg-scoring.md).

See [Neuropixels scoring rules](docs/en/neuropixels-scoring.md) for included checks, deduplication and effective weights.
