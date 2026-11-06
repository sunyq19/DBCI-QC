# 数据包清点与完整性（D01）

状态：首版实现，2026-11-06。用于数据接收时核对交付内容，独立于 M01–M09 单记录信号检查。它落实数据包完整性的第一步，不代表已实现医院 SOP 全部七个维度。

## 输入与输出

```text
事先约定的应有清单 + 本地数据目录
                  ↓
      清点文件 → 核对大小与指纹
                  ↓
         调用已有读取器查看结构
                  ↓
   应到/实到表 + 缺件定位 + 记录基本信息
```

输入目录不修改。清单需来自交付约定、独立发布索引或人工确认，不能运行后用“现有文件”反推“应有文件”。公开样例清单在下载前由固定版本索引生成。

输出：`report.html`、`result.json`、本次冻结的 `expectations.json`。报告包含范围、应到/实到矩阵、缺件/指纹异常、通道数/时长/采样率/文件内单位、读取提示和清单外文件。

| 状态 | 定义 |
| --- | --- |
| 齐备 | 指定文件已到；提供大小或指纹时也必须匹配 |
| 缺失 | 清单明确要求，但实际未找到 |
| 与清单不符 | 大小、指纹不符，或检查时文件发生变化 |
| 待确认 | 尚未确认该资料组应交什么；不算齐备 |
| 不适用 | 明确不属于此次交付范围，需说明原因 |
| 路径不可用 | 符号链接、非常规文件或无法访问；不跟随到目录外读取 |

“结构可读取”单独列出：单位未声明时仍可清点，但不能因此宣称可计算电压指标。读取器失败也不直接证明源数据损坏。清单外文件单列，不改变完整性分母；不按 `.bidsignore` 隐藏检查对象。仅排除本地管理目录 `.git`、`.qc`。

不生成 0–100 信号质量分，不据此给出医院最终 pass/conditional/block。D01 不检查表格内容；跨文件和数据集一致性现由 D02/D03 实现，见[数据集检查规则](dataset-checks.md)。BIDS 合规、匿名化和影像配准未实现。报告属于本地报告。

## 独立使用

在已安装的项目环境中：

```bash
.venv/bin/python -m ephys_qc package-inspect /path/to/package \
  --expectations /path/to/package/.qc/expectations.json \
  --output /path/to/new-report
```

输出目录须是新目录，且与输入目录分开。默认调用现有读取器；`--skip-readers` 只做清点与指纹，记录读取明确标为未评。命令返回 0 表示本次清点及被请求的读取均完成且无待处理项，1 表示报告已生成但有缺件、待确认、读取未评等，2 表示输入或运行错误。

Python：`from ephys_qc.toolkit import inspect_package, run_package_inventory`。实现位于 `src/ephys_qc/dataset_qc/`；不依赖网页服务。质控台新增“数据集”页，通过本机配置登记数据包目录；单文件上传仍走原 M01–M09。网页整包上传未实现。

## 清单示例

```json
{
  "schema_version": "package-expectations/1",
  "scope": "受试者 sub-01 的一个会话；不是全研究数据集",
  "files": [
    {"path": "sub-01/record.edf"},
    {"path": "sub-01/channels.tsv"}
  ],
  "items": [
    {"id": "s1-eeg", "subject": "sub-01", "category": "EEG",
     "requirement": "required", "files": ["sub-01/record.edf", "sub-01/channels.tsv"]},
    {"id": "s1-mri", "requirement": "not_applicable", "reason": "本次只交付头皮 EEG"},
    {"id": "s1-events", "requirement": "unknown", "reason": "事件表交付范围待确认"}
  ],
  "recordings": [{"path": "sub-01/record.edf"}]
}
```

文件项可增加 `size_bytes` 和 `digest: {"algorithm": "sha256", "value": "..."}`。MD5 只用于核对上游已有指纹；本地结果始终另存 SHA-256。没有上游指纹时，文件到齐不能证明与发布原件完全相同。NWB 多流记录可在 `recordings` 项明确 `stream_id`。

## 公开演示数据与复现

来自用户公开数据清单中的两个数据集，均声明 CC0；原作者、研究说明和引用保留在每个样例目录的原始 README 和 dataset_description.json 中。

| 固定版本 | 下载范围 | 来源文件 / 记录总数 | 首轮用途 |
| --- | --- | --- | --- |
| [ds003555 v1.0.1](https://openneuro.org/datasets/ds003555/versions/1.0.1) | sub-06、sub-19，全部已发布原始 EEG、派生片段和配套表 | 49 / 12 | 头皮 EEG、原始与派生记录分组、通道表和事件对应 |
| [ds003029 v1.0.7](https://openneuro.org/datasets/ds003029/versions/1.0.7) | sub-ummc003、sub-ummc006 的 6 份 ECoG；sub-umf004 的 1 份 sEEG；配套表 | 51 / 7 | 多次记录、BrainVision 多文件、跨文件不一致案例 |

总来源内容 1,654,303,613 字节，约 1.54 GiB。不含本地说明、清单和测试副本。所选受试者内容完整，但没有下载全队列；保留的 participants.tsv 是上游全表，不能用其总行数冒充本地人数。HFO 标记不是伪迹真值。

```bash
python3 scripts/public_examples/download_package_pilot.py --output /path/to/public-data
```

脚本需要 Git、网络和约 2 GiB 可用空间；目标样例目录必须不存在。下载前保存完整发布索引、固定提交与选择范围，S3 文件逐一匹配该提交中 annex 的大小/指纹；如果同一对象已变更会拒绝接受。不联网外传本机数据。

## D01 首轮实测记录

- 100/100 来源文件匹配预先冻结的清单；修正读取边界后，18/19 记录可解析结构，1 份被采样帧检查拒绝。没有执行这些记录的完整信号评分。
- ds003555 的原始记录为 23 通道、1024 Hz，分别 10800 秒和 7222 秒；10 份派生片段为 52 通道、2000 Hz、每份 300 秒。EDF 内物理单位为空，配套 channels.tsv 声明 uV，需要后续显式核验，不能静默补单位。
- ds003029 的 sEEG 载荷为 355472 字节，按文件头 129 通道、float32 解释后，有 688 个完整采样帧及 464 字节余数。初次后端静默舍去余数并返回 0.688 秒；现已增加读取前检查，明确拒绝此类输入。配套 JSON 的 RecordingDuration 为约 248.379 秒，事件在约 135 秒和 186 秒。文件与固定快照一致；时长/事件冲突为独立核对发现，**尚未由 D01 自动作跨文件判断**，作为下一步 D02 的真实回归案例。
- 另建一份人为缺件副本，仅移除一个通道表；D01 显示 50/51 文件、1 项缺失，原始样例未改动。单位测试覆盖完整记录缺失、指纹冲突、合法子集、未知/不适用、路径边界及读取失败。

首轮后续计划（现已完成 D02/D03 首版，见下方）：逐记录比较文件头与通道表/JSON 的单位、采样率、通道数和事件范围。原始与派生数据分别分组，合法重参考、重采样不当作跨人差异；采样率容差应结合文件头精度与转换说明确定。再接受试者/会话绑定与修正后复验。


## D01–D03 完整运行

```bash
.venv/bin/python scripts/public_examples/prepare_package_consistency.py /path/to/package \
  --output /path/to/package/.qc/consistency-plan.json
.venv/bin/python -m ephys_qc dataset-check /path/to/package \
  --expectations /path/to/package/.qc/consistency-plan.json \
  --output /path/to/new-dataset-report
```

首条辅助脚本只负责映射上述两个公开样例；新数据需按 schema 明确记录和比较组。核心 D01–D03 不使用数据集 ID 分支。返回 0 表示所有适用检查一致，1 表示报告已生成且存在冲突/复核/未评，2 表示运行或输入错误。Python 接口：`evaluate_dataset`、`run_dataset_qc`，均在 `ephys_qc.toolkit` 中导出。

## 在质控台登记本地目录

在 `.local/workbench.json` 中增加 `packages` 数组，保留其余设置；重启本地服务后打开 `/datasets`。每个目录须有独立应有清单和一致性配置。

```json
"packages": [
  {
    "id": "eeg-pilot",
    "label": "头皮 EEG · 两个体",
    "description": "固定公开子集，原始与派生分组",
    "root": "/absolute/path/to/package",
    "expectations": "/absolute/path/to/package/.qc/consistency-plan.json"
  }
]
```

网页只可选择已登记目录，不接受任意本机路径。运行前确认范围和比较组，清单变化后必须重新确认。任务在后台顺序计算；可离开页面并从“检查记录”返回。输出保存在配置的 `data_dir/package_jobs/<id>/`，不进入源码仓库。支持完整 HTML 报告和 JSON；本页没有单记录 EEG 的 PDF 评分报告。

## 一致性验收与异常演示

```bash
.venv/bin/python scripts/public_examples/validate_package_consistency.py \
  --public-root /path/to/public-data \
  --cases-root /path/to/new-controlled-cases \
  --reports-root /path/to/new-validation-reports
```

两个输出目录必须不存在。脚本保留两个公开原包，另建缺件、采样率冲突、恢复后复验三个明确标识的副本。检查恢复结果须与原包每项状态一致，而不是把上游问题全部变成通过。最后核验 100 个来源文件指纹不变。

实际执行：头皮 EEG 49/49 文件、2 人、12 记录；颅内包 51/51 文件、3 人、7 记录。原始/派生 EEG 分组后没有混报采样率差异；EDF 空单位保留复核。颅内包检出 6 份 ECoG 的文件头 nV/通道表 µV 冲突，以及 1 份 sEEG 结构问题。头皮 EEG 中部分 HFO 事件端点索引到 600002，超出 600000 样本的宽界，保留原始行号和起点约定待核对信息。

这些结果验证执行和可追溯性，不证明医院全部 SOP、检测准确性或正式验收分级已完成。

完整验收范围见[2026-11-06 数据集一致性验收](validation/dataset-consistency-20261106.md)。

## 从数据集进入记录信号检查

在数据集页的“个体与记录”选择个体，再点“打开记录”。服务根据已登记数据包和清单中的记录 ID 找到原文件，核对配套并冻结指纹；不重新上传或复制波形。确认模态、通道和参考后，继续使用 M01–M09 的现有检查流程。缺少单位等条件仍须解决，跨文件冲突不会被自动修正。

记录页面提供“返回数据集”，数据集列表关联每份记录的信号检查历史。重复打开相同来源和清单会复用确认记录；有信息修订时打开最新版本。原文件变化则创建新读取快照，旧结果保留，旧确认无法继续提交变更后的来源。

数据集检查与信号评分仍分别呈现；本次没有新增数据集总分，也没有将原始/派生记录混排。详见[记录关联验收](validation/dataset-record-links-20261106.md)。
