# 公开 EEG 示例与复现

截至 2026-10-29，代表性覆盖集包含7个公开数据集、26份记录；固定案例见[coverage-cases.json](../datasets/coverage-cases.json)，批量执行规则见[数据覆盖验收规范](data-validation.md)。以下先保留原有11份登记模板，再说明本轮新增15份。它们用于验证读取、适用条件、标注语义和报告追溯，不是已完成独立裁决的准确率基准。相同参与者的多次运行不能当作独立参与者。

## 记录与默认窗口

本轮新增数据包含真实连续SET，本文中较早的EDF选区说明仍只对应原有11份模板。上传任意文件不会自动导入其原目录中的背景或外部标签。

### 本机直接上传样例

已有本地验收环境的样例目录以`/path/to/edf-upload-examples`表示；这是目录占位，克隆仓库不会附带样例文件。该环境保存15份波形EDF实际副本，共339,803,296字节。另有`README.txt`、`manifest.json`和`SHA256SUMS.txt`记录来源、许可、原件位置和副本指纹。先试`01_先试_睁眼静息_S001R01.edf`，再试含ECG/EOG/EMG的HMC、多采样率Sleep-EDF、注意任务和临床双极记录。没有将注释专用EDF放入波形样例中，没有修改数据或额外下载。

这15份文件用于用户自行选择本机文件上传，和以下11份预登记示例配置分开。上传入口按技术头提出选道建议，确认后默认分析文件开头至多120秒，不根据文件名导入疾病、任务、参考、外部标注或原目录中的特殊时段。两份睡眠文件开头不保证处于睡眠，CHB-MIT开头120秒不覆盖2996–3036秒的已知发作。全部副本经过真实通用接入、确认和推荐核验，来源不变；多次运行不代表独立参与者。

### 预登记记录

时间均相对原始 EDF 开始，窗口采用左闭右开区间；界面可调整起点和时长，单次最多 120 秒。表中通道数指明确选作 EEG 的导联，不含辅助导联。

| 数据与输入 ID | 默认窗口（秒） | EEG / 采样率 | 典型用途 | 已知标注及边界 |
|---|---|---|---|---|
| EEGMMIDB S001R01 · `eegmmidb-s001r01` | 0–61 | 64 / 160 Hz | 睁眼静息，与同一人的闭眼/运动记录对照 | 官方实验条件；无独立伪迹真值 |
| HMC SN062 · `hmc-sn062` | 100–200 | 4 / 256 Hz | 睡眠 EEG 与同钟 ECG/EOG/EMG 辅助导联 | 人工分期，窗口含 N1/N2；睡眠分期不是质量标签 |
| OpenNeuro sub-01 · `ds002034-sub01` | 60–120 | 62 / 512 Hz | 注意任务、同参考通道比较和事件核对 | 任务事件、来源记录级 good/bad 通道标签；整段标签不能直接评价每个短窗口 |
| OpenNeuro sub-02 · `ds002034-sub02` | 60–120 | 62 / 512 Hz | 同上；与 sub-01 分开保留 | 同上；来源坏道标签不输入检测器 |
| EEGMMIDB S001R02 · `eegmmidb-s001r02` | 0–61 | 64 / 160 Hz | 闭眼静息及睁闭眼状态对照 | 闭眼条件来自官方运行协议；无人工坏道/伪迹区间 |
| EEGMMIDB S001R03 · `eegmmidb-s001r03` | 0–120 | 64 / 160 Hz | 真实左右握拳任务及事件时间轴 | EDF+ 的 T0/T1/T2 事件；任务时段不等于运动伪迹 |
| Sleep-EDF SC4001E0 · `sleep-edfx-sc4001` | 30600–30720 | 2 / 100 Hz | 少导联双极睡眠记录、多采样率来源的选道边界 | 人工 R&K 1968 分期；窗口含 W 30 秒、stage 1 90 秒，不是伪迹真值 |
| CHB-MIT chb01_03 · `chbmit-chb01-03` | 2990–3090 | 23 / 256 Hz | 临床发作背景下的质量描述 | 官方发作区间 2996–3036 秒；发作不是伪迹，区间外也不保证无伪迹 |
| EEGMMIDB S002R01 · `eegmmidb-s002r01` | 0–61 | 64 / 160 Hz | 另一参与者的睁眼基线 | 官方实验条件；年龄、疾病和具体参考未核实，无人工质量标签 |
| EEGMMIDB S002R04 · `eegmmidb-s002r04` | 0–120 | 64 / 160 Hz | 左右握拳想象，补充真实运动场景 | 原记录123秒；T1/T2分别是左/右握拳想象提示，不是实际动作或伪迹标签 |
| Sleep-EDF SC4011E0 · `sleep-edfx-sc4011` | 28710–28830 | 2 / 100 Hz | 另一参与者的REM睡眠 | 人工R&K分期覆盖REM 120秒；分期不是质量真值 |

OpenNeuro 两份记录均为 `ses-01/task-offline/run-01`。工作台登记模板包含全部十一份输入的选道、窗口、来源和 SHA256，见 [workbench.example.json](../apps/workbench/workbench.example.json)。模板中的路径须替换成本机实际路径。

## 一手来源与许可

| 数据集 | 固定版本与官方来源 | 来源声明的许可 |
|---|---|---|
| EEG Motor Movement/Imagery Dataset | [PhysioNet 1.0.0](https://physionet.org/content/eegmmidb/1.0.0/)；[运行编号说明](https://archive.physionet.org/physiobank/database/eegmmidb/) | Open Data Commons Attribution License v1.0 |
| HMC Sleep Staging Database | [PhysioNet 1.1](https://physionet.org/content/hmc-sleep-staging/1.1/) | CC-BY-4.0 |
| ds002034 | [OpenNeuro 1.0.3](https://openneuro.org/datasets/ds002034/versions/1.0.3) | CC0 |
| Sleep-EDF Database Expanded | [PhysioNet 1.0.0](https://physionet.org/content/sleep-edfx/1.0.0/)；[原始 Hypnogram](https://physionet.org/files/sleep-edfx/1.0.0/sleep-cassette/SC4001EC-Hypnogram.edf) | Open Data Commons Attribution License v1.0 |
| CHB-MIT Scalp EEG Database | [PhysioNet 1.0.0](https://physionet.org/content/chbmit/1.0.0/)；[导联和发作时间说明](https://physionet.org/files/chbmit/1.0.0/chb01/chb01-summary.txt) | Open Data Commons Attribution License v1.0 |

数据许可与算法代码许可分别记录。下载目录保留官方说明、许可页、校验和及派生说明；引用或再分发时应保留对应数据集和作者署名、许可链接与修改说明。

## 影响质控解释的事实

EEGMMIDB 的 R03 是真实左右握拳，R04 才是对应想象任务。R03 原文件共 125 秒，默认分析前 120 秒；完整 EDF+ 的 30 个任务区间均保留。`bids_events_tsv` 是平台已有表适配器的名称，不表示转写后已成为完整 BIDS 数据集。新增 R02/R03 的采集参考细节未核实，比较组保持未设置，不把 64 道直接当作已确认同参考队列。

S002R04 根据[官方运行协议](https://archive.physionet.org/physiobank/database/eegmmidb/)单独解码为握拳想象，背景使用 `task=motor_imagery`；没有把想象提示当成真实动作。S002两份记录的比较组同样保持未设置。SC4011的默认窗口取配套分期中第一个长度不少于120秒的REM区间，未根据信号是否“干净”挑选；它与SC4001属于不同参与者，不是同一文件的克隆窗口。个体年龄未另行核实，保持未知。

HMC 的 EEG 参考分为 3+1 组，不满足当前每组至少四道的组内阈值条件。Sleep-EDF 使用 Fpz-Cz、Pz-Oz 两条双极 EEG 和水平 EOG（源索引 0、1、2），均为 100 Hz。其 1 Hz 呼吸、温度、marker 和经过处理的 EMG 包络没有被上采样后冒充同钟原始辅助导联；EMG 包络也不能用于原始肌电相关性验证。未完整核实的采集/预处理滤波史保持未知。

CHB-MIT 是双极导联，不能直接拼成公共参考比较组。源索引 14 和 22 均名为 `T8-P8`，索引 2 和 18 是反向 `T7-P7` / `P7-T7`；保留各自索引身份，不合并重复名称或自动改参考。疾病和年龄只作为来源背景，不能改变检测阈值或据此判定病理波形是伪迹。

这些新增记录没有人工逐通道伪迹/坏道真值。计划中的“不适用”和实际输出的“部分完成”应保留理由，不能为增加执行数量而取消参考、频带或导联数量门槛。开源方法的候选只供复核；时间区间、通道、通道对和固定分析段是不同计数单位，不能相加成“总坏道数”。

## 准备新增四份示例

[准备入口](../scripts/public_examples/prepare_public_examples.py) 准备 R02、R03、Sleep-EDF 和 CHB-MIT 四份记录。它不会重新取得此前的 R01、HMC 或 OpenNeuro 示例，也不会自动登记到工作台、创建任务或清洗原始信号。

在仓库根目录、已安装 BrainElecQC/MNE 等依赖的科学 Python 环境中运行。`python` 应指向该环境；[已测环境](../profiles/tested-environment.json) 可作版本参考。

```bash
python scripts/public_examples/prepare_public_examples.py --help

python scripts/public_examples/prepare_public_examples.py \
  --repo-root "$PWD" \
  --data-root "$HOME/ephys-qc-data/public-eeg" \
  --evidence-dir "$HOME/ephys-qc-data/public-eeg-preparation"
```

两处输出目录均位于仓库外。若已有原始 `S001R02.edf`，在同一命令后增加 `--existing-r02 /absolute/path/to/S001R02.edf`：脚本校验后引用该文件，不再复制。省略该参数则从官方来源下载 R02。

入口依次下载、检查技术头、转写标注、生成登记草稿并做 0.1 秒读取探针与规划/标注核验。已有原始文件会被复用并核验；波形和可核对官方清单的源文件 SHA256 不符即失败，不覆盖原始 EDF。派生表和证据文件可在复跑时重新生成。下载量与是否复用有关：本次复用已有 R02，新增原始文件及说明共 94,035,172 字节，约 89.7 MiB，不含此前已有的数据；新机器若同时下载 R02 会更多。

完成后检查 `--evidence-dir` 中的 `registration_additions.json`，将所需 `inputs` 和 `profiles` 合入本机 `.local/workbench.json`，保留原有登记及环境设置。模板和字段解释见 [工作台说明](../apps/workbench/README.md)。数据准备成功不表示已完成质控运行，应在工作台查看适用性计划后另行运行。

## 指纹、标注派生与冻结来源

每份原始记录有 `expected_sha256`。标注的 `annotation.expected_sha256` 固定实际使用的表；派生表另用 `source_expected_sha256` 固定其源文件。三份新增派生表及对应 `*_annotation_derivation.json` 保存来源 hash、派生 hash、转换方法和限制。

- R03：从 EDF+ 提取起点和时长，依据运行 03 协议将 T0/T1/T2 解码为休息/左握拳/右握拳。
- Sleep-EDF：PSG 与 Hypnogram 起始时钟一致；原始 154 个区间全部保存在抽取记录中。派生表保留与 79,500 秒波形相交的 153 行，排除超出波形的末尾 `?` 区间并记录原因；R&K 3、4 保持独立，不自动改成 AASM N3。
- CHB-MIT：仅解析 `chb01_03.edf` 对应的官方 summary 段，生成独立 `clinical_events_tsv`。发作秒数相对该 EDF 起点，既不用于监督 M03–M06，也不用于调整质量阈值。

计划冻结输入/标注指纹、配置、`data_tags`、`input_provenance` 和 `input_data_usage`，实际结果保存相应来源与执行证据。之后修改登记，不会用当前元信息补写旧任务缺失的历史来源。

## 已完成核验与限制

本次数据准备的机器可读证据包括 `download_manifest.json`（逐文件 URL、大小、SHA256）、`official_hash_verification.json`（9 项官方清单匹配，含复用 R02）、`technical_inspection.json`、`collection_summary.json` 和 `validation.json`。各数据目录的 `_provenance/` 另存本地指纹及来源说明。

2026-10-29 的独立读取器核验额外比较了新增四份记录的**完整默认选定窗口**：BrainElecQC 与 MNE 解码后以 V 比较，四份记录的最大绝对差均为 0，原文件指纹不变，所选通道身份保留。Sleep-EDF 比较 2 条 EEG 加 1 条同采样率 EOG；CHB-MIT 保留两条同名导联的独立身份。这证明本轮窗口的解码、电压标定和索引一致，不证明检测准确率、临床泛化或整夜运行能力。准备脚本自身的 0.1 秒探针不能替代这项完整窗口核验。

本次本地证据在仓库所在工作区的 `work/ephys_expansion_20261029/`，不随代码仓库分发：`datasets/` 保存准备证据，`independent-reader-validation.json` 保存完整窗口比较，`workbench-acceptance.json` 保存实际工作台运行证据。详细运行结果与未验证项目见 [运行验收记录](runtime-validation.md)。

## 再补充三份实际记录

[追加准备脚本](../scripts/public_examples/prepare_additional_examples.py) 准备S002R01、S002R04和SC4011。S002R01优先复用已有原始公开文件；另外下载S002R04、SC4011波形及配套Hypnogram，并保存官方说明、许可、校验和及派生记录。三个输入都有可直接采用的选道、窗口和标注配置；不需要重新手填64个EEG通道。脚本不改工作台登记，也不猜坐标、参考或处理史。

```bash
python scripts/public_examples/prepare_additional_examples.py \
  --repo-root "$PWD" \
  --data-root "$HOME/ephys-qc-data/public-eeg" \
  --evidence-dir "$HOME/ephys-qc-data/additional-preparation"

python scripts/public_examples/validate_recommended_examples.py \
  --repo-root "$PWD" \
  --registration "$HOME/ephys-qc-data/additional-preparation/registration_additions.json" \
  --output "$HOME/ephys-qc-data/additional-recommended-validation"
```

可加 `--existing-s002r01 /absolute/path/to/S002R01.edf` 复用原始文件；不加则下载官方原件。验证命令在科学环境中真正运行每份记录的完整推荐计划及默认MNE平线增强，生成独立HTML/JSON报告；不连接或重启主服务，不修改`.local`。输出目录必须是新的，旧验证不覆盖；`--input-id`可限定某一记录。

本轮共追加3份登记、覆盖2名新的参与者，4个波形/分期原文件与官方SHA256清单一致。实际新增下载56,736,191字节（约54.1 MiB），其中包括调整场景前已取得但最终未登记的S002R03原件2,555,616字节；该文件和先前准备证据保留。最终运行的是R04想象任务。新机器只按最终脚本准备时，不会下载这份额外R03。

追加证据根目录为工作区的 `work/ephys_additional_examples_20261029/`：`datasets/registration_additions.json` 是最终登记草稿，`datasets/official_hash_verification.json` 保存官方指纹匹配，`preparation_history.json`保留范围调整及下载统计。SC4011的原波形84,060秒，分期派生只保留波形内区间，保留原R&K标签和超界排除记录；原始Hypnogram不变。

三份默认窗口均已在独立目录执行推荐流程并生成报告，没有失败模块，原始文件和标注SHA256前后不变，总质量分保持null。结果均为`partial`：未知参考/未声明比较组限制M05，缺少ECG/原始EMG等辅助证据限制M06；R01的短尾窗及SC4011的100Hz采样还限制部分谱分析。SC4011源文件3个未选择的辅助通道单位未知，读取器保留结构警告，不能把这项警告隐去。R04任务事件和SC4011的REM覆盖核验成功，均未作为检测真值。

最终三份运行的精确路径、所用推荐策略版本、计划标识、模块状态和原始文件指纹集中在 `final-validation-summary.json`。首次R04使用较宽的`motor`背景标签，随后改为明确的`motor_imagery`并单独重跑；前次结果保留，最终摘要只引用修正后的R04。这里的真实运行证明工程链路可执行，不证明伪迹准确率、临床可靠性或整夜处理能力。

## 代表性覆盖扩充：新增15份

本轮在原11份记录外新增15份：12份EDF（含2份复用已有公开原件）和3份真实连续SET。固定记录级窗口、来源版本和SHA256见 `datasets/coverage-cases.json`；两个HMC登记ID归入同一官方数据集版本，不重复统计数据集。

| 新增记录 | 默认原始时间/s | EEG/采样率 | 来源背景 |
| --- | --- | --- | --- |
| `eegmmidb-s003r01` | 0–61 | 64/160 Hz | EEGMMIDB · S003R01 睁眼静息 |
| `eegmmidb-s003r02` | 0–61 | 64/160 Hz | EEGMMIDB · S003R02 闭眼静息 |
| `eegmmidb-s004r02` | 0–61 | 64/160 Hz | EEGMMIDB · S004R02 闭眼静息 |
| `eegmmidb-s005r03` | 0–120 | 64/160 Hz | EEGMMIDB · S005R03 真实左右握拳 |
| `eegmmidb-s006r04` | 0–120 | 64/160 Hz | EEGMMIDB · S006R04 想象左右握拳 |
| `eegmmidb-s007r05` | 0–120 | 64/160 Hz | EEGMMIDB · S007R05 真实双拳或双足运动 |
| `eegmmidb-s008r06` | 0–120 | 64/160 Hz | EEGMMIDB · S008R06 想象双拳或双足运动 |
| `chbmit-chb02-16` | 120–240 | 23/256 Hz | CHB-MIT · chb02_16 临床发作 |
| `chbmit-chb03-01` | 350–470 | 23/256 Hz | CHB-MIT · chb03_01 临床发作 |
| `hmc-sn061` | 1830–1950 | 4/256 Hz | HMC · SN061 N3睡眠与辅助导联 |
| `sleep-edfx-sc4021` | 24990–25110 | 2/100 Hz | Sleep-EDF · SC4021 R&K深睡 |
| `ds004504-sub001` | 0–120 | 19/500 Hz | OpenNeuro · sub-001 阿尔茨海默病闭眼静息 |
| `ds004504-sub037` | 0–120 | 19/500 Hz | OpenNeuro · sub-037 健康对照闭眼静息 |
| `ds004504-sub066` | 0–120 | 19/500 Hz | OpenNeuro · sub-066 额颞叶痴呆闭眼静息 |
| `physiomotion-sub1-run01` | 300–420 | 59/1000 Hz | PhysioMotion · sub-1 run-01 人工伪迹标签 |


### 固定版本准备与复跑

新增12份EDF及配套资料使用[准备器](../scripts/public_examples/prepare_coverage_examples.py)和[固定源清单](../scripts/public_examples/coverage_examples_sources.json)。源清单包含35个对象、373,439,679字节，保存官方PhysioNet校验值或OpenNeuro固定Git版本的annex指纹。现有文件校验失败时拒绝覆盖。原始、派生标注和运行报告分别保存。

```bash
python scripts/public_examples/prepare_coverage_examples.py \
  --repo-root "$PWD" \
  --data-root /path/to/public-coverage-data \
  --evidence-dir /path/to/public-coverage-preparation

python scripts/public_examples/prepare_clinical_set_examples.py \
  --output /path/to/public-coverage-data/ds004504-1.0.8
```

第一条生成 `additions.json`（11份）与 `physiomotion-additions.json`（1份）；第二条生成3份SET的 `additions.json`。准备器只下载/核验、派生标注和验证计划，不执行质检，不修改工作台配置。第一条支持 `--offline` 核验现有文件，`--reuse-eegmmidb-dir`可复用含S003R01/R02的目录。各登记文件可分别交给 `scripts/validate_data_coverage.py`，也可人工核对ID后合并。原11份记录仍按本文前述说明准备。

### 新增来源及解释边界

[ds004504 v1.0.8](https://openneuro.org/datasets/ds004504/versions/1.0.8)采用固定提交 `73b1b04c0a8e45e96c6f0682cc077a7919480fc4`，许可CC0。本轮取未清洗的subject目录：sub-001为来源AD组，sub-037为对照组，sub-066为FTD组。未取derivatives作为干净真值；原始目录不含来源设备自动伪迹标签。README与逐记录侧车对参考和滤波的描述不一致，因此参考及处理史保留未核实，未启用比较组。来源诊断分组仅用于报告背景。[固定版本说明](https://github.com/OpenNeuroDatasets/ds004504/tree/73b1b04c0a8e45e96c6f0682cc077a7919480fc4)

[PhysioMotion ds006386 v1.0.1](https://openneuro.org/datasets/ds006386/versions/1.0.1)采用固定提交 `647f61744019ad41801598384bb461b7fdc06560`，许可CC0。取sub-1/run-01及人工CSV。CSV有382行，其中默认300–420秒与26行眼部伪迹标签相交；标签是ALL或双极导联，原始59道为单电极。登记使用独立 `quality_reference`，状态为 `montage_alignment_pending`；不送入检测器或M07，不计算通道级准确率。来源channels.tsv单位写V，而EDF物理头为uV；读取遵循EDF标定，已独立核验，不重复按侧车缩放。[数据描述论文](https://doi.org/10.1038/s41597-026-07120-7)

新的EEGMMIDB R05/R06分别为双拳/双足真实运动与想象，不能沿用R03/R04的左右手含义。HMC SN061默认窗为来源N3；Sleep-EDF SC4021默认窗保持原R&K的stage 3与4，不自动合并为AASM N3。CHB-MIT新增两个来源患者的含发作记录，发作标签仍独立于质量判断。

### 本轮结果入口

26份默认窗口均已实际采用推荐方案运行；机器可读摘要见[覆盖基线](../profiles/data-coverage-baseline.json)，完整证据位于本地工作区 `work/ephys_coverage_20261029/`。15份新增记录另做完整选区独立读取核对：12EDF采用MNE对照平台读取器，3SET采用SciPy读取原始内嵌数值后按EEGLAB单位对照平台结果；逐道逐点一致，源文件未变。该结果验证解码与工程链路，不验证自然伪迹准确率。
