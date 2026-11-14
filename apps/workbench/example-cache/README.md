# Published example reports

These are presentation snapshots of public electrophysiology data, not raw recordings or user uploads. The homepage embeds `manifest.json`; versioned report assets are served without NAS access or runtime analysis. All report links, content hashes and source-independent rendering are checked by `tests/test_example_cache.py`.

The current release contains eight public dataset examples, 21 recordings and 23 workflow reports (including the EEG workflow comparison). Source/version/license declarations are retained in the manifest and each dataset report. The inventory below lists the selected cohorts and exact crop boundaries; examples do not represent the complete upstream studies.

[Example inventory and crop boundaries](../../../docs/example-datasets.md) · [Offline publication instructions](../README.md)

Publish explicitly using `scripts/publish_example_cache.py`. Do not edit snapshot HTML to change a scientific result. Original runtime evidence remains separate; changing weights for new analyses does not rewrite these published examples.

Deploy the manifest and its release directory together. Report HTML/PDF and finding indexes are included; interactive waveforms require separately configured public source recordings and their companion files. Run `scripts/check_example_sources.py --config /data/workbench.json --checksums` on the target host or inside its QC container. See the [deployment guide](../../../docs/deployment/package.md).
