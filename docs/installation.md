# 安装与配置

[返回 README](../README.md) · [English](en/installation.md)

## 首次使用

准备 Linux、Python 3.11 和 Git，按 [README](../README.md#快速开始) 执行安装与启动命令即可。安装脚本不需要管理员权限，不修改系统 Python。

| 位置 | 用途 |
| --- | --- |
| `.venv/` | 本项目的 Python 与依赖 |
| `.local/workbench.json` | 本机配置，不上传 GitHub |
| `.local/runtime/` | 默认上传副本、任务、报告与复核记录 |

计算发生在本机，无需 Claude 或 OpenAI API。首次安装需要访问 GitHub 和 Python 包源。原始记录不随仓库分发。

## 自定义目录或端口

首次安装时可以指定：

```bash
python3.11 scripts/setup_local.py --port 8770 --data-dir /path/to/DBCI-QC-data
```

已有 `.local/workbench.json` 时，脚本保留原配置，参数不会覆盖它。需要修改时，先停止服务，再编辑配置：

| 字段 | 含义 |
| --- | --- |
| `port` | 本机端口，默认 `8769` |
| `python` | 安装好依赖的 `.venv/bin/python` 的绝对路径 |
| `data_dir` | 上传副本与运行结果目录的绝对路径 |
| `inputs` / `profiles` | 可选的预登记数据和方案；新安装为空 |

修改 `data_dir` 不会自动迁移旧数据，旧记录仍保留在原目录。配置示例见 [workbench.minimal.json](../apps/workbench/workbench.minimal.json)。

## 更新已有安装

等待当前任务结束，按 `Ctrl+C` 停止服务，然后在仓库目录运行：

```bash
git pull --ff-only
python3.11 scripts/setup_local.py
.venv/bin/python apps/workbench/server.py --config .local/workbench.json
```

刷新网页。安装脚本保留配置、数据和历史结果；如有本地代码修改导致 Git 拒绝更新，先保存并整理自己的修改，不要强制重置。

旧配置若使用另一套 Python，脚本会显示提示。可将配置中的 `python` 改为新 `.venv/bin/python` 的绝对路径，保留 `data_dir`、`inputs` 和 `profiles`。也可以继续维护原计算环境，安装所需依赖。历史评分和原始证据保留，新版显示会注明重算规则。

## 常见问题

| 情况 | 处理 |
| --- | --- |
| 找不到 `python3.11` | 先安装 Python 3.11；使用 Conda 时，在 Python 3.11 环境中执行 `python scripts/setup_local.py` |
| 缺少 `venv` / `ensurepip` | 安装当前系统提供的 Python 3.11 venv 支持，或使用 Conda 的 Python 3.11 |
| 下载失败 | 确认能访问 GitHub 和 Python 包源，再重跑同一安装命令 |
| 端口被占用 | 停止旧服务，或修改配置的 `port`，按新端口打开网页 |
| 缺少依赖 / PDF 无法生成 | 重跑安装脚本，并确认配置使用其生成的 Python 环境 |
| 网页里没有示例报告 | 当前仓库附带四类缓存示例；确认完整下载了 `apps/workbench/example-cache/`。自己的原始数据仍需上传，也可使用 README 的合成示例 |

`requirements/workbench.txt` 固定主要依赖和 BrainElecQC 提交，不是所有间接依赖的完整锁文件。研究扩展单独安装，见[扩展方法](optional-methods-runtime.md)。Windows、macOS 暂不作为已验证环境。

## 后台启动（Linux，可选）

```bash
.venv/bin/python scripts/run_local.py --open
.venv/bin/python scripts/run_local.py --status
.venv/bin/python scripts/run_local.py --stop
```

这三个命令分别用于启动、查看状态、停止本启动器管理的服务。不要和前台启动方式同时占用一个端口。后台日志保存在配置的 `data_dir/server.log`。

## 模块独立调用

```bash
.venv/bin/dbci-qc catalog
.venv/bin/dbci-qc inspect /path/to/record.edf
```

实际计算、Python API 与模块交接见[模块工具包](toolkit.md)。工作台接口见[API 文档](../apps/workbench/README.md)。

## 上传副本与个人目录

新上传副本自接收起保留 **7 天**。服务运行期间每分钟检查到期记录；正在排队或计算的记录等待任务结束再清理。报告、保存的证据、来源指纹和确认记录保留。本机原文件、就地关联的数据集和没有新保留策略的旧资料不自动删除。

“我的数据”只展示本次更新后的用户上传。旧开发输入、示例及旧草稿不自动恢复到个人入口，原数据和报告没有因此删除。管理员要将一个既有 `inputs` 或 `packages` 条目作为个人资料显示，可明确设置 `library_origin: user_registered`；这个标记不会授权删除关联原件。

到期后可以查看已有报告，重新计算须再次上传。当前是本机单用户目录；云端账号隔离、对象存储生命周期与审计尚待实现。
