# 共享演示版部署验收

日期：2026-11-08。程序：`1.0.0rc3.dev40`。状态：本地部署准备和接口流程通过；目标服务器尚未提供，未宣称已上线。

## 环境

新建 Python 3.11 虚拟环境，按 `scripts/setup_local.py` 安装当前仓库与 `requirements/workbench.txt`；`pip check` 通过。独立运行目录，不读取或修改开发者原有数据。真实数据验收使用 Caddy 2.10.2 反向代理，Host 与 Origin 按演示配置校验；systemd 服务文件通过语法检查。

## 已验证

| 项目 | 结果 |
| --- | --- |
| 四类缓存示例 | EEG、ECoG、sEEG、Neuropixels；全部 256 个缓存文件通过 HTTP 获取并核对 SHA-256，包含报告、图表、脚本和 PDF |
| 初始目录 | 新运行目录的“我的数据”为空；示例独立显示 |
| 真实上传 | PhysioNet EEGMMIDB 1.0.0，S001R03，64 通道、160 Hz、125 秒；原文件指纹不变 |
| 完整操作 | 上传→读取→确认→推荐→计划→排队→整份计算→报告；125 秒全部计算，分为 3 段 |
| 结果访问 | 网页报告、PDF、嵌入图表、指定通道/时段波形接口均成功 |
| 共享与重启 | 两个独立 HTTP 客户端看到同一上传与报告；重启服务后状态、目录及报告仍在 |
| 合成验证 | 2 通道、10 秒合成 EDF 同样走完整 HTTP 流程，三项默认评分均有数值 |
| 请求与容量 | 错误 Host、外站 Origin、跨站请求拒绝；超 2 GiB、磁盘不足、并发上传及锁释放有专项测试 |
| 自动回归 | 772 项 Python 测试通过，8 项因可选环境缺失跳过；153 项前端状态检查及本地化、导航、布局、报告、波形等既有检查通过 |

真实样本综合分 **99.77**；完整性 **99.60**、工频 **99.95**。末尾短段使高频项缺少完整有效证据，该项不计分，剩余有效项重新归一化。这是现有规则在该文件上的结果，未修改算法或补成满分；不作为检测准确率证明。

真实样本来源：[PhysioNet EEGMMIDB 1.0.0](https://physionet.org/content/eegmmidb/1.0.0/)。下载器固定来源、SHA-256、许可和引用，见 `scripts/demo_sample.py`。

## 复现

```bash
python3.11 scripts/setup_local.py
python3 scripts/demo_sample.py --output /tmp/dbci-public-sample
.venv/bin/python scripts/validate_demo.py \
  --edf /tmp/dbci-public-sample/S001R03.edf --output /tmp/dbci-real-check
# 可增加 --caddy /path/to/caddy，一并验证实际反向代理
```

输出目录须尚不存在。保留 `acceptance.json`、`result-summary.json`、`report.html`、`report.pdf`、服务器日志和独立运行目录。完整验收脚本也已接入 GitHub Actions，自动化使用合成 EDF，不在 CI 下载真实研究数据。

## 尚未验收

- 浏览器视觉和真实双浏览器操作：浏览器工具受已保存的网站权限阻止，HTTP 客户端测试不等于浏览器测试。
- 目标服务器安装、实际域名 / HTTPS、开机启动、互联网带宽及稳定性。
- 2 GiB 大文件的实际上传耗时、峰值内存及多人访问容量。当前验证的是边界规则和小型数据完整流程。
- 未把缓存报告视为所有可选算法都已安装；未验证新的算法准确率或重新审定评分标准。
