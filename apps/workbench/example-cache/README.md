# Published example reports

These are presentation snapshots of public electrophysiology data, not raw recordings or user uploads. The homepage embeds `manifest.json`; versioned report assets are served without NAS access or runtime analysis. All report links, content hashes and source-independent rendering are checked by `tests/test_example_cache.py`.

The four collections contain 13 recording reports. Source/version/license declarations are retained in the manifest and each dataset report:

- Scalp EEG: [OpenNeuro ds002034 v1.0.3](https://openneuro.org/datasets/ds002034/versions/1.0.3), CC0.
- ECoG: [OpenNeuro ds003029 v1.0.7](https://openneuro.org/datasets/ds003029/versions/1.0.7), CC0.
- sEEG: [MNE sample](https://mne.tools/stable/auto_tutorials/clinical/20_seeg.html), repository BSD-3-Clause; and [OpenNeuro ds004100](https://openneuro.org/datasets/ds004100), CC0. These are separate groups.
- Neuropixels: [Human Neuropixels recordings](https://zenodo.org/records/5899237), CC0-1.0. The AP/LF examples are short crops, not full source recordings.

[Example inventory and crop boundaries](../../../docs/example-datasets.md) · [Offline publication instructions](../README.md)

Publish explicitly using `scripts/publish_example_cache.py`. Do not edit snapshot HTML to change a scientific result. Original runtime evidence remains separate; changing weights for new analyses does not rewrite these published examples.
