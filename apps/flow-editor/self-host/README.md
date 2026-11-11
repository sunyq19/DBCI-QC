# 同址部署

模块协作页与质控台共用入口：`http://10.100.21.50:8769/flow/`。
查看不需要登录；编辑沿用已有密码。页面、版本、批注、附件均由 012 提供，不依赖 Sites 跨站接口。

云端与内网使用同一套结构，完整安装命令见[一站部署](../../../docs/deployment/demo.md)。一个地址提供质控台 `/` 和模块协作 `/flow/`。

## 构建与运行

需要 Node.js 24。在 `apps/flow-editor` 目录安装构建依赖后：

```sh
node scripts/build-self-host.mjs
```

将 `dist-self-host` 复制到服务器，运行 `node server.mjs`。运行环境仅需 Node 24，无需安装 npm 依赖。

- `FLOW_DATA_DIR`：独立于发布目录的持久化目录，包含 SQLite 数据库和附件。
- `FLOW_PASSWORD_FILE`：权限为 600 的密码校验文件；沿用原 PBKDF2 格式。不要写入仓库。
- `FLOW_PUBLIC_ORIGIN`：明确的外部网址，如 `https://qc.example.org`，无尾斜杠；代理部署必须设置，保留 Host/Origin。
- `FLOW_BIND`、`FLOW_PORT`：默认 `127.0.0.1:18770`，由反向代理提供访问。

反向代理将 `/flow`、`/flow/*`、`/api/flow`、`/api/access`、`/api/attachments` 转发至此服务，并保留 Host、Origin。其他路径仍由质控台处理。

模块目录随构建发布；升级后沿用原来的合并逻辑更新草稿，保留团队说明和固定版本。GitHub Pages 与旧在线服务不再是内网部署的必需依赖。

## 数据与维护

012 发布目录：`/mnt/sdb/DBCI-QC/flow/releases/`；当前版本由 `current` 指向。
持久化目录：`/mnt/sdb/DBCI-QC/flow/data/`；密码校验文件在同级 `config/`。
服务示例见 `dbci-flow.service`。更新发布目录时不要覆盖 `data`、`config`。

仅从旧 Sites 服务导入时运行 `scripts/import-site-snapshot.mjs`；导入逐条校验文档散列并拒绝覆盖已有数据库。备份运行中的数据库应使用 SQLite backup API，同时复制附件目录，避免仅复制正在写入的数据库主文件。

012 现有入口用于内网演示；云端由反向代理提供 HTTPS，密码编辑与匿名查看规则不变。原始质控数据不存入协作数据库。
