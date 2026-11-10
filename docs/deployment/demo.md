# 部署共享演示版

版本：`1.0.0rc3.dev40`。使用现有质控台；访客无需账号，所有上传与报告进入共享的“我的数据”。管理员通过服务器维护服务，不另设管理后台。

## 准备

Linux、Python **3.11**（含 venv）、Git、[Caddy 2.10+](https://caddyserver.com/docs/install)。先按 **4 核 CPU、16 GiB 内存、100 GiB 持久磁盘**安排小规模展示；这是部署起点，不是所有 2 GiB 文件的性能保证，无须 GPU。算法任务按现有队列执行。

需一个 SSH 管理员、一个网站地址。没有域名可先用 `http://服务器IP`；有域名时使用 `https://域名`，解析到服务器并开放 80/443，Caddy 管理 HTTPS。Python 服务只监听 `127.0.0.1`，不开放 8769 公网端口。

## 安装与启动

以下使用专用低权限运行用户 `dbciqc`；SSH 管理员负责安装、更新及日志查看。修改示例域名为实际访问地址，不要带末尾 `/`。

```bash
sudo useradd --system --create-home --home-dir /srv/dbciqc --shell /usr/sbin/nologin dbciqc
sudo install -d -o dbciqc -g dbciqc /srv/dbciqc/app /srv/dbciqc/runtime
sudo -u dbciqc git clone https://github.com/sunyq19/DBCI-QC.git /srv/dbciqc/app
cd /srv/dbciqc/app
sudo -u dbciqc python3.11 scripts/setup_local.py --data-dir /srv/dbciqc/runtime
sudo -u dbciqc .venv/bin/python scripts/prepare_demo.py \
  --origin https://qc.example.org --data-dir /srv/dbciqc/runtime
```

配置生成于 `.local/demo/`，不会覆盖本地版配置；再次生成请使用新的 `--output` 目录。示例报告随源码提供，服务器初始“我的数据”为空。

```bash
sudo cp .local/demo/dbci-qc.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now dbci-qc
sudo caddy validate --config /srv/dbciqc/app/.local/demo/Caddyfile --adapter caddyfile
```

新建专用服务器可将生成的 Caddyfile 安装为 `/etc/caddy/Caddyfile`，然后启用 Caddy：

```bash
sudo install -m 644 .local/demo/Caddyfile /etc/caddy/Caddyfile
sudo systemctl enable --now caddy
sudo systemctl reload caddy
```

已有网站的服务器应把生成的网站段合并进原 Caddy 配置，先核对现有站点，不覆盖原文件。其他反向代理也可使用：保留原始 Host/Origin、上传请求体允许 2 GiB、流式转发、响应等待至少 1 小时。访问地址必须与 `workbench.json` 的 `deployment.public_origin` 一致；服务不会信任访客提交的转发头来放行未知地址。

## 示例与实际上传

- 首页直接显示 EEG、ECoG、sEEG、Neuropixels **缓存数据集报告**，查看无需重新计算；快照没有附带原始信号，不作为可重跑记录。
- EEG 示例同时保存完整检查位置，使用与实际报告相同的筛选、彩色标记和通道对照界面。要展开交互波形，在服务配置 `workbench.json` 的 `example_review_sources` 中登记“原始文件 SHA-256 → 服务端绝对路径”，然后重启服务。所需指纹在缓存清单 `review_snapshots` 中；只登记对应的公开示例文件。读取时会核对内容指纹，不能用相似数据替换。无需搬入原来的运行目录或重新执行算法。
- 未配置原始示例文件时仍可查看报告、图表和检查位置；波形区明确提示未配置，不显示其他位置的旧图冒充当前波形。
- 在操作浏览器的电脑上下载一个真实公开 EEG：

```bash
python3 scripts/demo_sample.py --output ./demo-sample
```

将 `demo-sample/S001R03.edf` 上传到网页，确认“头皮 EEG”和 64 个信号通道，其余未知字段可保留未知，使用推荐方案、整份检查。配套 `SOURCE.json` 记录出处、许可、实验说明和校验值。

上传副本保留 **7 天**，报告与计算证据保留；运行中的记录延后清理。所有访客可见文件说明及报告，只上传公开或已脱敏材料。缓存示例是展示快照，不能据此推断服务器已安装所有可选上游算法；Gnosis 等可选环境仍按[方法说明](../toolkit.md)单独配置，未安装会明确标示。

单文件、单份记录及配套文件合计 **2 GiB**；数据集 **10 GiB / 100 记录 / 5,000 文件**。网页先接收单份记录或其配套 ZIP，整库由管理员预置和登记，不能把 10 GiB 数据集当作单记录上传。登记格式见[数据包检查](../dataset-inventory.md)与[数据集示例](../example-datasets.md)。

## 验收与维护

在安装环境运行独立验收，不触及线上数据：

```bash
.venv/bin/python scripts/validate_demo.py --output /tmp/dbci-demo-check
# 有真实文件时增加：--edf /path/to/S001R03.edf
```

它核验四类缓存及其图表/PDF，实际上传、读取、推荐、计算、网页报告、PDF、波形、两客户端共享记录和重启保留；结果写入输出目录。输出目录须尚不存在。浏览器排版、真实公网链路和大文件耗时须在目标服务器另行验收。

```bash
sudo systemctl status dbci-qc
sudo journalctl -u dbci-qc -n 100
sudo systemctl restart dbci-qc
df -h /srv/dbciqc/runtime
```

管理员只需管理一个服务。日志不通过演示网页开放；清理仅处理有平台所有权记录且已到期的上传副本，不删除报告。默认保留 10 GiB 磁盘余量，空间不足拒绝新上传；一次接收一个文件，忙时返回稍后重试。网页上传等待上限为 1 小时。

备份 `.local/demo/workbench.json` 和整个 `/srv/dbciqc/runtime/`；运行目录与源码分开。更新代码前备份并记录当前提交号，等待任务结束后停服务、更新、重新运行安装脚本安装依赖，再启动。不要运行覆盖数据目录的同步或清理命令。服务重启不丢已完成报告；未完成任务标为中断，可重新提交。

反向代理配置依据：[Caddy 请求体限额](https://caddyserver.com/docs/caddyfile/directives/request_body)、[反向代理](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)。
