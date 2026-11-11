# 部署演示版

更新：2026-11-11。一台 Linux 服务器、一个网址，同时提供质控台和模块协作。012 已按此结构运行；云端尚待部署。

| 访问路径 | 用途 | 后台与持久数据 |
| --- | --- | --- |
| `/` | 上传、选模块、运行检查、查看报告 | Python 服务；公开数据持久保存，上传临时处理 |
| `/flow/` | 模块批注、方案草稿、附件、固定版本 | Node.js 服务；SQLite 数据库与附件 |

查看无需账号；模块协作使用团队密码编辑。“我的数据”只展示管理员核实来源的公开数据。用户上传及报告仅在当前浏览器临时查看，不进入公共目录。管理员通过服务器维护服务，不另建管理后台。

## 1. 准备

需要 Linux、Python **3.11**（含 venv）、Node.js **24**（含 npm）、Git、[Caddy 2.10+](https://caddyserver.com/docs/install)。小规模展示可从 **4 核 CPU、16 GiB 内存、100 GiB 持久磁盘**起步，无须 GPU；这不是所有 2 GiB 文件的性能保证。

准备 SSH 管理方式和网站地址。有域名使用 `https://域名`，配置解析并开放 80/443；没有域名可先用 `http://服务器IP:端口`。两个后台均只监听本机地址，由 Caddy 统一提供访问。

## 2. 安装

下列命令用于新建专用服务器；已有 `dbciqc` 用户或安装目录时复用，不重复创建。

```bash
sudo useradd --system --create-home --home-dir /srv/dbciqc --shell /usr/sbin/nologin dbciqc
sudo install -d -o dbciqc -g dbciqc /srv/dbciqc/app /srv/dbciqc/runtime /srv/dbciqc/runtime/flow
sudo -u dbciqc git clone https://github.com/sunyq19/DBCI-QC.git /srv/dbciqc/app
cd /srv/dbciqc/app
sudo -u dbciqc python3.11 scripts/setup_local.py --data-dir /srv/dbciqc/runtime
sudo -u dbciqc npm ci --prefix apps/flow-editor
cd apps/flow-editor
sudo -u dbciqc node scripts/build-self-host.mjs
cd ../..
```

生成配置，将示例域名替换为实际地址，不带末尾 `/`：

```bash
sudo -u dbciqc .venv/bin/python scripts/prepare_demo.py \
  --origin https://qc.example.org \
  --data-dir /srv/dbciqc/runtime --port 18769 \
  --with-flow --node "$(command -v node)"
sudo -u dbciqc .venv/bin/python scripts/set_flow_password.py .local/demo/flow-password.verifier
```

密码在服务器终端隐藏输入；文件只保存校验值，权限为 600，不进入 Git。若迁移 012，沿用已有校验文件和协作数据库，不创建新的空协作库。配置输出 `.local/demo/` 已存在时不会覆盖；重新生成须指定新的 `--output`。

只部署质控台时可省略协作构建、`--with-flow`、`--node` 和密码步骤；此时 `/flow/` 不可用。

## 3. 启动统一入口

```bash
sudo cp .local/demo/dbci-qc.service .local/demo/dbci-flow.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now dbci-qc dbci-flow
sudo caddy validate --config /srv/dbciqc/app/.local/demo/Caddyfile --adapter caddyfile
```

专用新服务器可安装生成的 Caddyfile：

```bash
sudo install -m 644 .local/demo/Caddyfile /etc/caddy/Caddyfile
sudo systemctl enable --now caddy
sudo systemctl reload caddy
```

已有网站时，将生成的网站段合并进现有配置，不覆盖其他站点。后台端口 18769/18770 不对公网开放。网页互相跳转使用当前网址，不需要修改源码中的服务器 IP。

其他反向代理须保留原始 Host、Origin，向协作服务设置可信的 `X-Real-IP`，允许 2 GiB 请求体及至少 1 小时的质控响应等待。质控配置 `deployment.public_origin` 与协作服务 `FLOW_PUBLIC_ORIGIN` 必须为同一个实际访问地址；服务不通过客户端转发头猜测来源。

## 4. 示例与上传

首页直接提供 EEG、ECoG、sEEG、Neuropixels 缓存数据集报告，查看不重新运行算法。新安装的“我的数据”初始为空；既有记录须核实公开来源并登记后才会显示。

EEG 示例已保存完整检查位置，支持筛选、彩色标记和通道对照。交互波形还需配置对应公开原始文件：在 `workbench.json` 的 `example_review_sources` 登记“SHA-256 → 服务端绝对路径”，指纹见缓存清单 `review_snapshots`。读取前核对文件内容。未配置时仍可查看报告、图表和位置列表，波形区会提示缺少源文件；缓存快照不是可重新计算的数据。

在操作浏览器的电脑上下载一份真实公开 EEG，再上传演示：

```bash
python3 scripts/demo_sample.py --output ./demo-sample
```

上传 `demo-sample/S001R03.edf`，确认头皮 EEG、64 个信号通道，使用推荐方案、整份检查；`SOURCE.json` 保存来源和许可。Gnosis、FieldTrip 等可选环境仍按[方法说明](../toolkit.md)安装，缓存报告不代表新服务器已安装这些方法。

- 单文件及单份记录配套文件合计 **2 GiB**，ZIP 按展开后大小核算。
- 数据集 **10 GiB / 100 记录 / 5,000 文件**，由管理员预置并登记，见[数据集配置](../dataset-inventory.md)。网页暂不支持整库上传。
- 上传文件、报告、图表和运行记录在完成后 **1 小时**清理，可提前“结束并清理”；未运行的上传闲置 **30 分钟**清理，最长 **6 小时**。见[数据保存规则](../data-storage.md)。
- 默认保留 10 GiB 磁盘余量，空间不足拒绝新上传；一次接收一个文件，算法按现有队列执行。

## 5. 验收

```bash
.venv/bin/python scripts/validate_demo.py --output /tmp/dbci-demo-check
cd apps/flow-editor
node --test tests/self-host.test.mjs
```

第一项在隔离目录核验示例、实际上传、推荐、计算、报告、PDF、波形及跨浏览器隔离、结束清理、异常重启清理；第二项核验协作的本地/HTTPS 代理来源、编辑、附件、固定版本与重启保留。两者不修改线上数据。目标服务器还应实际打开网页，检查两页跳转、示例波形、上传运行和协作保存，并记录耗时与峰值内存。

## 6. 更新和从 012 迁移

```bash
sudo systemctl status dbci-qc dbci-flow
sudo journalctl -u dbci-qc -n 100
sudo journalctl -u dbci-flow -n 100
```

更新前等待计算结束，暂停两个服务，备份配置、密码校验文件与已确认公开的运行记录；排除 `.temporary/`、上传缓存和来源未确认的旧记录。更新代码、安装变更依赖、重建协作包，再启动；不覆盖持久数据。公开数据的历史报告保留。临时上传在重启后清理，不迁移、不备份；停止服务前通知正在检查的用户下载报告。

从 012 搬到云端，需迁移：

| 012 的内容 | 云端目标 |
| --- | --- |
| `/mnt/sdb/DBCI-QC/runtime/` | 仅迁移已确认公开的记录和报告，排除 `.temporary/` |
| `/mnt/sdb/DBCI-QC/flow/data/` | 新质控持久目录下的 `flow/`，保留 SQLite 和全部附件 |
| `/mnt/sdb/DBCI-QC/flow/config/password.verifier` | 新配置目录的 `flow-password.verifier`，保持私密权限 |
| 公开样本及现有工作台配置 | 迁移原文件并调整输入路径、示例指纹映射和访问地址 |

停协作服务后复制整个数据目录；在线备份应使用 SQLite backup API 并同时保存附件，不单独复制正在写入的数据库主文件。不要把已有团队数据、密码校验文件或用户上传材料推到 GitHub。云端反向代理不缓存上传响应、不记录请求体、文件名头或 Cookie；磁盘快照也应排除临时目录所在卷，不能将“应用已删除”表述为“历史快照已擦除”。

模块目录随代码构建更新；同步保留团队文字、批注、布局、附件及固定版本。**协作草稿不会直接改动质控算法或评分**，确定方案后仍需修改、验证并发布实际代码。
