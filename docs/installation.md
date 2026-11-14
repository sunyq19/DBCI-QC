# 安装与配置

新安装启用 `public-only/1`：公开数据经管理员登记后保存，上传及报告临时处理，详见[数据保存规则](data-storage.md)。旧配置不会自动切换，须核对来源后迁移。

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

等待当前任务结束，用 `python3 scripts/run_local.py --stop` 停止后台服务（前台启动则按 `Ctrl+C`），然后在仓库目录运行：

```bash
git pull --ff-only
python3.11 scripts/setup_local.py
python3 scripts/run_local.py
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

## 固定环境启动（Linux）

```bash
python3 scripts/run_local.py --open
python3 scripts/run_local.py --status
python3 scripts/run_local.py --stop
```

这三个命令分别用于启动、查看状态、停止本启动器管理的服务。不要和前台启动方式同时占用一个端口。后台日志保存在配置的 `data_dir/server.log`。

启动器固定使用仓库 `.venv/bin/python`，无需先激活 Conda；不会因终端换环境而改用系统 Python。启动前同时检查网页服务和计算进程的 Python 3.11、主要依赖版本及实际导入。缺依赖时拒绝启动，错误写入上述日志。也可单独检查：

```bash
.venv/bin/python src/ephys_qc/runtime_environment.py --config .local/workbench.json
```

配置中的 `python` 必须保留 `.venv/bin/python` 路径，不要将符号链接转换为底层系统 Python。移动整个仓库后须重新创建环境并调整配置路径，不能直接复制其他机器的 `.venv`。本机启动器不安装开机自启；重启电脑后运行启动命令即可。需要自动恢复的服务器按[一站部署](deployment/demo.md)使用 systemd 或 Docker。

## 模块协作入口

本地 Python 启动器提供质控台，不会自动部署协作数据库。团队已有协作网站时，在 `.local/workbench.json` 增加以下字段，将按钮指向同一份草稿和版本：

```json
"collaboration": {
  "enabled": true,
  "url": "http://团队服务器地址:8769/flow/"
}
```

将地址替换为团队的实际地址；配置后在临时任务结束时重启工作台。以后重启保留此配置，不需要再次修改按钮。版本链接中的参数会保留，不建立第二套协作库。单机独立部署两页请使用[一站部署](deployment/demo.md)或[Docker 部署包](deployment/package.md)；同址部署无需此跳转配置。

## 模块独立调用

```bash
.venv/bin/dbci-qc catalog
.venv/bin/dbci-qc inspect /path/to/record.edf
```

实际计算、Python API 与模块交接见[模块工具包](toolkit.md)。工作台接口见[API 文档](../apps/workbench/README.md)。

## 数据目录与上传清理

新安装使用 `data_policy: public-only/1`。示例与“我的数据”只保存管理员核实来源的公开数据；上传及报告仅当前浏览器临时访问，不进入公共目录。

报告完成后 1 小时清理，未运行的上传闲置 30 分钟清理，会话最长 6 小时。可提前点击“结束并清理”，请先下载报告。服务重启清理遗留临时工作区。公开数据来源登记、旧配置迁移及备份要求见[数据保存规则](data-storage.md)。

旧配置不会自动迁移；启用新规则前核对原有来源。未登记的旧资料停止对外访问，历史文件须由管理员核对后清理。

### 公开方法扩展

工作台依赖已包含 PyPREP、local AutoReject、MNE-ICALabel、NWB Inspector 和 BIDS Validator。ICLabel使用CPU ONNX推理；BIDS校验使用安装包内置规则，检查时不联网。

标准依赖同时包含DREDge LF的CPU后端。已有环境单独补装时运行：

```bash
.venv/bin/python -m pip install -r requirements/drift-cpu.txt
```

自定义精简环境未安装时，只有该可选项显示缺少依赖，不影响其他检查。方法位置、输入条件和计分边界见[公开方法扩展接口](design/public-methods-v1.md)。
