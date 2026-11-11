# Installation and configuration

New installations use `public-only/1`: only administrator-verified public data persists. Uploads and reports are temporary; see [storage policy](../data-storage.md). Existing configurations require an explicit, source-audited migration.

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
| Example reports missing | The repository ships four cached modality examples; check that `apps/workbench/example-cache/` was downloaded completely. Upload your own data or use the synthetic EDF to run a new check. |

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

## Public library and temporary uploads

New installations use `data_policy: public-only/1`. Only administrator-verified public datasets and reports persist. Uploaded files and reports are private to the submitting browser and never enter the public library.

Results expire 1 hour after completion; unstarted uploads expire after 30 idle minutes, with a 6-hour maximum session. Users may finish and clear earlier after downloading reports. Restart clears abandoned temporary work. See [storage rules](../data-storage.md) for source registration, backup exclusions and explicit migration of existing configurations. Unapproved legacy data becomes inaccessible; its physical cleanup requires an administrator’s inventory review.
