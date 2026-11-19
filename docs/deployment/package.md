# 1.1.7 打包部署

一个仓库，两种安装形式：本页通过 Docker 自动安装并启动；[源码部署](demo.md)使用已有 Python/Node 环境。算法、报告和协作功能共用代码。

## 云端交接要点

| 要更新或保留的内容 | 操作要求 |
| --- | --- |
| 版本 | 使用同一个发布包；核对 `RELEASE.json` 的版本与提交，升级后重新构建质控和协作服务。GitHub 更新不会自动更新已有云主机。 |
| 页面与示例 | 代码、`example-cache/manifest.json` 及它指向的完整缓存目录一起更新。当前为 8 组数据集、21 份记录及 2 份额外方案报告。 |
| 可拖动的示例波形 | 原始公开文件不在 GitHub；另行复制并只读挂载，更新 `example_review_sources`，运行下方文件校验。只有报告缓存时不能完整演示波形交互。 |
| 扩展算法 | 灵犀云独立环境、FieldTrip 等须单独配置。能看缓存报告不代表服务器能重新执行其中的所有方法。 |
| 协作与上传 | 保留协作数据库、附件、密码校验文件及公开源文件配置。不要迁移用户临时上传，不向新访客展示旧的个人运行目录。 |
| 对外入口 | `/` 与 `/flow/` 使用同一域名/IP；`PUBLIC_ORIGIN` 必须匹配浏览器地址。最终核对报告、波形、上传运行、PDF及协作保存。 |

1.1.4 起将公开署名统一为项目名。协作历史在展示时采用同一规则，数据库原件保留；旧部署不会自动隐名，须部署新版。旧 Git 标签、历史提交与旧发布包仍是当时的存档，不等同于当前发布版本。

## 1. 准备

- Linux x86_64 服务器，Docker Engine 与 Compose v2.20 或更新版本。
- 建议至少 4 核、16 GiB 内存、100 GiB 可用磁盘。实际计算量取决于记录大小与方法；默认每次运行一项质检任务。
- 首次构建需要联网下载 Python、Node、Caddy 和算法依赖；无需在宿主机安装 Python、Node 或 Git。
- 下载 [v1.1.7 发布文件](https://github.com/sunyq19/DBCI-QC/releases/tag/v1.1.7)中的 `DBCI-QC-1.1.7-deploy.tar.gz` 与 `SHA256SUMS`。

```bash
sha256sum -c SHA256SUMS
tar -xzf DBCI-QC-1.1.7-deploy.tar.gz
cd DBCI-QC-1.1.7
sh deploy.sh
```

首次构建较慢；以后启动复用已有镜像。默认仅本机访问 **http://localhost:8769/**，模块协作在 **http://localhost:8769/flow/**。打开首页即可查看 EEG、ECoG、sEEG、Neuropixels 的公开缓存示例，也可上传文件检查、查看报告及下载 PDF。

## 2. 供其他电脑访问

首次启动前复制配置文件，然后填写实际地址；已经启动时直接修改生成的 `.env`。

```bash
cp deploy/demo.env.example .env
```

例如服务器 IP 为 `192.0.2.10`，在 `.env` 修改：

```dotenv
PUBLIC_ORIGIN=http://192.0.2.10:8769
BIND_ADDRESS=0.0.0.0
HTTP_PORT=8769
HTTPS_PORT=8443
CADDY_SITE=:80
RESERVE_GIB=10
```

再运行 `sh deploy.sh`，浏览器访问配置的 `PUBLIC_ORIGIN`。安全组/防火墙放行访问端口。质控台与模块协作共用同一入口，无需分别配置网址；只有网关开放端口。

公网有域名时，建议使用 HTTPS。域名解析到服务器后，配置如下并开放 80、443 端口，Caddy 自动申请证书：

```dotenv
PUBLIC_ORIGIN=https://qc.example.org
BIND_ADDRESS=0.0.0.0
HTTP_PORT=80
HTTPS_PORT=443
CADDY_SITE=https://qc.example.org
RESERVE_GIB=10
```

`PUBLIC_ORIGIN` 须为浏览器实际使用的完整来源，不带末尾 `/`。不要直接把上面的示例 IP 或域名作为生产地址。

## 3. 开启协作编辑

初始可查看模块，编辑尚未开启。在服务器交互终端运行：

```bash
sh deploy.sh password
```

按提示输入两次密码，输入内容不会显示。系统仅存校验值；设置完成后自动重启协作服务。已有密码不会被此命令覆盖。查看无需登录，编辑、保存草稿、固定版本及删除自己创建的草稿/版本按现有协作规则执行；删除仍需再次输入密码。

## 4. 维护

```bash
sh deploy.sh status   # 查看三个服务
sh deploy.sh logs     # 查看最近的服务日志
sh deploy.sh stop     # 停止服务，保留持久数据
sh deploy.sh          # 启动或重新构建
```

数据独立于代码目录，存放在 Docker 命名卷中：

| 卷 | 内容 |
| --- | --- |
| `dbci-qc_qc-data` | 质控运行目录；用户上传及报告仍按临时会话清理 |
| `dbci-qc_flow-data` | 团队草稿、讨论、附件和固定版本 |
| `dbci-qc_flow-config` | 编辑密码校验值 |
| `dbci-qc_gateway-data` / `dbci-qc_gateway-config` | HTTPS 证书及网关状态 |

升级前确认临时上传已处理完，再停止服务。备份需要保留的公共目录配置、协作数据和 `.env`，不要备份用户临时上传。解压新包后复制原 `.env`，如配置过公开源文件挂载，还须复制原 `compose.override.yaml`，然后运行 `sh deploy.sh` 重建并启动。Compose 项目名固定为 `dbci-qc`，更换代码目录不会自动建立另一套数据。不要删除持久卷；恢复协作数据时须连同数据库和附件一起恢复。

从 1.1.5 或更早版本升级时，协作服务会在启动时将 SQLite 从 WAL 切换到 DELETE 日志模式。请保留原协作持久卷，让 SQLite 在启动时处理旧日志文件。升级后打开首页和一份报告，核对首页响应的 `X-Frame-Options: SAMEORIGIN`、报告内嵌图表的加载和协作历史的读取。

发布包中的 `RELEASE.json` 记录精确版本和 Git 提交。下载后先核对 `SHA256SUMS`，不要把旧包的页面文件覆盖进新包。已有 `/data/public-catalog.json`、公开源文件及其挂载路径应保留；它们不随代码包自动下载。

管理员登记公开数据时，可在 `qc-data` 卷内放置 `/data/public-catalog.json`，只填写 `inputs`、`profiles`、`packages`、`public_records`、`public_packages`、`example_review_sources`。路径使用容器内路径；通过 `compose.override.yaml` 将公开源文件只读挂载到质控容器。重启后读取目录，上传隔离规则不可由此文件关闭。

### 示例报告与交互波形

GitHub 提供报告、图像和检查位置；不包含原始脑电文件。仅更新代码可以看到报告，但拖动波形、对照通道还需要以下配置：

1. 将公开示例源文件放到服务器单独目录，例如 `/srv/dbci-qc/public-sources`。保留配套文件和原文件名：BrainVision 的 `.vhdr/.eeg/.vmrk`、EEGLAB 的 `.set/.fdt`、SpikeGLX 的 `.bin/.meta` 必须一起复制。
2. 在 `compose.override.yaml` 中，将该目录只读挂载到 `qc` 服务的 `/data/public-sources`。
3. 在 `/data/public-catalog.json` 的 `example_review_sources` 中登记文件指纹与**容器内**主文件绝对路径的对应关系。指纹取当前 `apps/workbench/example-cache/manifest.json` 的 `review_snapshots`；不要使用本地电脑或 012 的路径。只需演示波形时，无须把这些文件加入“我的数据”。
4. 重建镜像并启动后执行：

```bash
docker compose exec qc python scripts/check_example_sources.py --config /data/workbench.json --checksums
```

检查应无缺件或内容不符，再实际打开示例，拖动波形、切换通道并下载 PDF。该检查只校验文件，不重新运行算法。

更新示例时，`manifest.json` 和对应的版本目录必须成套部署；不要把旧版数据集总览与新版单份报告混用。历史评分原件保留，新发布页面的总分、权重明细与 PDF 应一致。“我的数据”不配置 `demo_library_reports`，新浏览器初始为空；用户临时上传和报告不得打包、备份或推送至 GitHub。

如需在同一机器运行多个独立演示，设置不同的 `COMPOSE_PROJECT_NAME`、对外端口和 `PUBLIC_ORIGIN`；其持久卷也会分别建立。

构建时执行依赖一致性检查与实际导入测试，服务启动时再次检查 Python 和基础依赖；失败的服务不会被网关判为就绪。升级须重新构建镜像，不能只在旧容器里替换代码。独立检查运行环境：

```bash
docker compose exec qc python /app/src/ephys_qc/runtime_environment.py --config /data/workbench.json
```

GitHub 的部署测试会从镜像构建开始，实际验证公开 EDF 上传、检查、报告、PDF 和协作入口。灵犀云的独立 Python 3.12、Octave/FieldTrip 等扩展仍需额外配置，不会被基础依赖检查误报为已安装。

### 上传协议更新

上传界面与服务端须成套更新。升级后刷新浏览器，上传前查看 `/privacy` 并勾选同意；默认不选中，公开示例无需勾选。当前协议展示生效日期 2026-11-17、运营主体临港国家实验室，联系邮箱为 `qc.bci@lglab.ac.cn`。协议更新时须同步正文和服务端版本并重启服务。

Caddy 配置也需同步：上传前通过 `GET /api/v1/upload-policy/check` 预检同意及版本，避免大文件被后台提前拒绝时网关返回 502。该接口只检查请求头，不读取上传正文、不创建临时会话；真正接收上传时仍再次校验。Docker 包和源码部署模板都包含此设置，机制见 [Caddy forward_auth 文档](https://caddyserver.com/docs/caddyfile/directives/forward_auth)。

API 客户端先读取 `GET /api/v1/upload-policy`，向用户展示协议并取得本次确认，再在上传请求中发送 `X-QC-Privacy-Consent: agree` 和 `X-QC-Privacy-Version: <返回的 version>`。没有确认或版本过期返回 403 `privacy_consent_required`，服务端不保存该请求的上传内容。测试脚本中的同意仅用于明确的公开/合成验收文件，不能照搬为产品自动勾选。

修改 `apps/workbench/web/privacy.html` 后重启服务；协议版本由内容校验值生成。收件元数据中的版本和同意时间与临时文件一起清理。

## 5. 包含范围

- 单记录及配套文件合计最多 **2 GiB**；已登记数据集总量最多 **10 GiB**。网页整库上传尚未提供。
- 随包提供公开报告快照和可视化示例；不包含原始电生理数据。缓存报告可立即查看；拖动原始波形需要相应公开源文件。新上传文件在本次会话中可交互查看。
- “我的数据”初始为空。公开源文件和目录由管理员配置，迁移方式见[一站部署](demo.md)和[数据保存规则](../data-storage.md)。访客上传不进入公共目录。
- 上传完成后的报告保留 1 小时供查看、下载；未运行的上传闲置 30 分钟清理，临时会话最长 6 小时。可提前“清理本次上传”，服务重启也会清理遗留临时会话。
- 默认安装依赖与源码安装一致。灵犀云、FieldTrip 等可选运行环境须另行配置，见[扩展方法](../optional-methods-runtime.md)；缓存报告不代表扩展已在新机器安装。
- 不包含 012 上的团队数据库、附件、编辑密码和用户上传。要保留团队协作历史，管理员需另行备份迁移。
- 发布的是源码与构建配方，首次安装需联网，**不是离线预装镜像**。上游依赖从原仓库下载，许可说明见[第三方说明](../../THIRD_PARTY_NOTICES.md)。

## 发布包复现

开发者从固定提交生成同一版本的文件集合：

```bash
python3 scripts/build_deploy_bundle.py --ref v1.1.7 --output /path/to/releases
```

包内 `RELEASE.json` 记录版本和 Git 提交，外部 `SHA256SUMS` 校验下载文件。源码目录中的个人配置、运行库和未提交文件不会混入包内。

部署结构参考 [Docker Compose 单机部署](https://docs.docker.com/compose/how-tos/production/)及 [Caddy 反向代理](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)。
