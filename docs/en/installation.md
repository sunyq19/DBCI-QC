# Installation and configuration

[README](../../README.en.md) · [中文](../installation.md)

## First installation

Use Linux, Python 3.11 and Git. Follow the [quick start](../../README.en.md#quick-start). Setup needs no administrator access and does not modify system Python.

| Location | Purpose |
| --- | --- |
| `.venv/` | Isolated Python environment and dependencies |
| `.local/workbench.json` | Local configuration, excluded from Git |
| `.local/runtime/` | Default upload copies, jobs, reports and reviews |

Computation runs locally without a Claude or OpenAI API. Initial installation requires GitHub and Python package access. Raw datasets are not included.

## Custom storage or port

For a new configuration:

```bash
python3.11 scripts/setup_local.py --port 8770 --data-dir /path/to/DBCI-QC-data
```

Existing `.local/workbench.json` is preserved, including when these arguments are supplied. Stop the service before editing it manually:

| Field | Meaning |
| --- | --- |
| `port` | Local port, default `8769` |
| `python` | Absolute path to the installed `.venv/bin/python` |
| `data_dir` | Absolute path for upload copies and results |
| `inputs` / `profiles` | Optional registered data and profiles; empty by default |

Changing `data_dir` does not move old data. See the [minimal configuration](../../apps/workbench/workbench.minimal.json).

## Update

Let active jobs finish and stop the server with `Ctrl+C`. From the repository:

```bash
git pull --ff-only
python3.11 scripts/setup_local.py
.venv/bin/python apps/workbench/server.py --config .local/workbench.json
```

Refresh the browser. Setup preserves configuration and data. If Git refuses to update because of local edits, save and reconcile them rather than forcing a reset.

If an older configuration uses another Python, setup prints a notice. Point its `python` field to the new `.venv/bin/python`, keeping `data_dir`, `inputs` and `profiles`; alternatively maintain the dependencies in the original environment. Historical evidence and scores are retained; revised views identify the scoring rules used.

## Troubleshooting

| Problem | Action |
| --- | --- |
| `python3.11` not found | Install Python 3.11, or activate a Conda Python 3.11 environment and run `python scripts/setup_local.py` |
| Missing `venv` / `ensurepip` | Install your system's Python 3.11 venv support or use Conda Python 3.11 |
| Download fails | Check GitHub/package access and rerun setup |
| Port already used | Stop the other service or change `port` and open the matching URL |
| Missing dependency / PDF fails | Rerun setup and ensure the configured Python is the installed environment |
| No example data listed | Upload your own file or use the README's synthetic example or [public examples](../public-examples.md) |

`requirements/workbench.txt` pins top-level dependencies and a BrainElecQC commit; it is not a full transitive lock. [Research extensions](../optional-methods-runtime.md) require separate setup. Windows and macOS are not verified environments.

## Background launcher (Linux, optional)

```bash
.venv/bin/python scripts/run_local.py --open
.venv/bin/python scripts/run_local.py --status
.venv/bin/python scripts/run_local.py --stop
```

These start, inspect and stop the service managed by this launcher. Avoid launching a foreground server on the same port. Logs are at `data_dir/server.log`.

## Headless toolkit

```bash
.venv/bin/dbci-qc catalog
.venv/bin/dbci-qc inspect /path/to/record.edf
```

See the [toolkit API](../toolkit.md) and [workbench API](../../apps/workbench/README.md).

## Upload retention and personal library

New upload copies expire **7 days** after receipt. While running, the service checks expiry every minute and defers deletion for queued/running jobs. Reports, saved evidence, fingerprints and confirmation records remain. Linked originals, registered dataset folders and legacy files without an ownership receipt are never automatically removed.

My uploads starts empty; development entries, examples and legacy drafts no longer populate it. Their files and reports are preserved. An administrator can explicitly mark a configured `inputs` or `packages` entry with `library_origin: user_registered` to show it as personal data; this does not authorize deleting the linked source. Re-upload expired copies to rerun QC. Cloud user isolation and object-storage lifecycle remain planned.
