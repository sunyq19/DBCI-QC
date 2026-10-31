# 模块交接与独立调用

适用版本：1.0.0rc3.dev5；原头皮EEG调用保持兼容。核心交付物为 Python 工具包 `ephys_qc`；本地网站是使用该工具包的一个应用。模块执行不要求 HTTP 服务、浏览器、`.local/workbench.json` 或预登记数据目录。

## 1. 交付结构

| 层次 | 代码位置 | 职责 |
| --- | --- | --- |
| 对外接口 | `src/ephys_qc/toolkit.py` | 检查文件、准备已确认记录、规划和运行所选模块 |
| 模块实现 | `src/ephys_qc/modules/m01.py` 至 `m09.py` | 每个模块的实际计算调用、证据与分项摘要 |
| 模块注册与上下文 | `src/ephys_qc/modules/` | 模块入口、共享状态要求及计算上下文 |
| 读取器 | `src/ephys_qc/readers/` | 各格式解析，统一通道、单位、时钟和来源指纹 |
| 流水线 | `planning.py`、`runtime.py`、`whole_record.py` | 条件判断、依赖补齐、执行状态、单窗与整记录分块 |
| 方法与适配 | `method_registry.py`、`extensions.py`、`extra_methods.py` | 方法目录、开源算法适配与适用条件 |
| 命令行 | `src/ephys_qc/__main__.py` | `dbci-qc` / `python -m ephys_qc` |
| 可选工作台 | `apps/workbench/` | 上传、交互、任务管理、波形查看与版本化人工复核 |

九个模块独立成文件，作为同一工具包统一发布和版本管理。模块可以组合使用，依赖关系由计划表达；当前不将九个模块分别发布为九个安装包。BrainElecQC 等计算依赖仍需单独安装，见[安装说明](../README.md#安装与启动)和[第三方说明](../THIRD_PARTY_NOTICES.md)。

## 1.1 流程、模块与方法

工作台与工具包采用同一层级：**流程阶段 → 职责模块 → 具体方法**。格式由读取器处理，模态由已确认记录决定，不需要建立四套网站流程。

| 阶段 | 模块 | 产出 |
| --- | --- | --- |
| 读取与确认 | M01 接入、M02 计划 | 已核验的数据、选道与冻结配置 |
| 质量检查 | M03 完整性、M04 频谱、M05 通道、M06 伪迹、M07 事件 | 分项观察量、候选位置与未评原因 |
| 结果与报告 | M08 汇总、M09 报告 | 可追溯的分项报告与复核入口 |

模块内的方法按启用方式分为基础方法、按条件启用、可选增强。基础方法随选中的模块运行，仍须通过输入校验；条件方法检查其采样率、时长、参考组或辅助信号；可选增强须在配置中启用。分组不是执行顺序或质量等级，实际执行依赖和未评原因以 `build_plan()` 为准。

`from ephys_qc.toolkit import workflow` 可获取上述阶段、方法分组与模态默认模块列表；`catalog(modality)` 返回模块的输入、输出、依赖和方法来源。两者都不读取信号或修改分析配置。工作台调用同一份 `workflow`，工具箱浏览不改变当前任务。默认展示已接入方法，待开发项通过接入状态筛选查阅。

ECoG、sEEG、Neuropixels 的 M03–M05 共用 `modules/continuous/` 中的完整性、Welch 频谱和逐通道统计内核，各模态入口仍独立核验身份与参数。合并只复用相同计算，不迁移阈值或合并解释。头皮 EEG 的 PREP、伪迹线索及可选增强保留各自方法与条件。读取器和 M01/M02/M07/M08/M09 继续共享。

## 2. Python 调用

```python
from ephys_qc.toolkit import (
    inspect_recording, prepare_recording, build_plan, run_module,
)

source = "/path/to/record.edf"
metadata = inspect_recording(source)
# 先核对 metadata 中的源通道索引、单位与采样率，再填写选道。

record = prepare_recording(
    source,
    record_id="record-001",
    modality="scalp_eeg",       # 使用者确认，不从扩展名推断
    reference_scheme="unknown",
    qc_config={
        "selection": {
            "eeg_indices": [0, 1],
            "reference_indices": {},
            "start_seconds": 0,
            "duration_seconds": 10,
        },
        "method_config": {"comparison_groups": None},
    },
)

plan = build_plan(record, selected_modules=["M03"])
result = run_module("M03", record, "/path/to/new-qc-output")
print(result["status"], result["selected_modules"])
```

以上索引和时长仅为调用示例，必须按实际数据修改。`prepare_recording` 冻结技术信息与主/配套文件指纹，核对明确给出的模态、选道和配置，不执行质量算法。未知单位、跨采样流或不支持的模态不能通过默认推断进入检测。

| 接口 | 输入 | 输出 |
| --- | --- | --- |
| `catalog(modality="scalp_eeg")` / `list_readers()` | 可选模态，支持`scalp_eeg`、`ecog`、`seeg`或`extracellular` | 模块方法或读取器目录 |
| `inspect_recording(path)` | 本机主文件路径 | 技术元数据，不确认模态和质量 |
| `prepare_recording(path, ..., qc_config=...)` | 显式模态、记录 ID、选道与配置 | 可保存为 JSON 的记录及来源指纹 |
| `recommend(record, qc_config=None)` | 已确认记录及可选配置 | 推荐理由、适用性、可采用的方法与配置 |
| `build_plan(record, selected_modules, qc_config=None)` | 已确认记录、明确模块列表、可选覆盖配置 | 冻结检查计划 |
| `run_modules(record, output_dir, selected_modules, ...)` | 同上，另加新输出目录 | 管线结果、分项状态、证据与报告 |
| `run_module(module_id, record, output_dir, ...)` | 单个目标模块 | 该模块及必要依赖组成的管线结果 |

**单个目标模块仍需要数据入口和结果出口。** 请求 M03 时实际运行 M01、M02、M03、M08、M09；请求 M06 还会补上 M03。以结果中的 `selected_modules` 为准，未选且非依赖的计算模块不执行。多模块调用使用 `run_modules(record, output_dir, ["M03", "M04"])`。

`emit(module_id, status, message)` 为可选进度回调。结果可能为 `completed`、`partial`、`failed`；部分模块失败会记录在结果中而非抛出异常，调用方须检查总状态和各模块状态。缺条件、未评、失败与信号质量合格是不同含义，总分仍为 `null`。

## 3. 模块内部接口

```python
from ephys_qc.modules import module_specs, get_handler

specs = module_specs()
handler = get_handler("M03")  # ephys_qc.modules.m03.run
```

每个模块实现 `run(context)`。`ModuleContext` 包含已冻结记录与计划、配置、读取器/信号状态、当前模块结果、汇总结果、输出位置及证据保存回调；`module_specs()` 提供入口和所需/产生的状态。该接口用于开发新模块或适配宿主，字段定义以源码为准。

一般集成使用第2节的工具包接口，由执行器完成单位核验、依赖、来源检查和错误收集。直接调用内部 `run(context)` 需要集成方自行建立完整上下文，不能跳过前置模块后把任意数组作为已核验输入。

## 4. 命令行

完成安装后，以下命令与 `python -m ephys_qc` 等价：

```bash
dbci-qc catalog
dbci-qc inspect /path/to/record.edf

dbci-qc prepare /path/to/record.edf --id record-001 --modality scalp_eeg \
  --config /path/to/config.json --output /path/to/new-record.json

dbci-qc plan --record /path/to/new-record.json --modules M03 M04
dbci-qc run --record /path/to/new-record.json --modules M03 M04 \
  --output /path/to/new-qc-output
```

`config.json` 对应第2节的 `qc_config` 对象。`prepare` 不覆盖已有记录文件；`run` 仅接受全新输出目录，不覆盖失败任务或已完成报告。标准输出为 JSON，后端日志写入标准错误。退出码：0为命令完成（仍可能有未评项），1为运行失败/中断或存在失败模块，2为输入、配置、依赖或文件错误。

每次运行先保存 `request.json`，随后产生 `result.json` 和 `artifacts/`；整记录模式另含逐窗产物和覆盖记录。新入口不修改源文件，也不隐式更新已冻结指纹。源文件改变须重新登记，不沿用旧记录身份。进度回调不代替持久化结果。

## 5. 可运行示例与安装包

无需下载数据即可验证交接流程：

```bash
python examples/headless_qc.py --output /path/to/new-demo
```

示例现场生成两个通道、10秒的合成 EDF，并在一个通道中设置恒值区间，调用 M03 及必要依赖，输出报告。它只验证工程调用和已知故障路径，不是自然伪迹准确率基准。生成文件位于指定目录，不纳入仓库。

构建安装包：

```bash
python -m pip wheel --no-deps . --wheel-dir /path/to/wheels
```

wheel 包含 `ephys_qc` 模块与命令行入口，不包含网站、原始数据、第三方安装包或本机配置。接收方在已准备科学依赖的环境安装该 wheel 后，可在仓库外调用工具包。示例脚本和开发文档随源码交接。

## 6. 宿主接入边界

网站、后续 Linxi 插件或其他平台均应调用同一工具包，负责把宿主输入转换为已确认记录和配置，将进度事件、结果及产物引用映射回宿主。不得在宿主内复制另一套检测逻辑。

当前模块包交付检测、证据与报告。网站中的上传隔离、输入修订、交互式波形和版本化人工复核仍属于 `apps/workbench`，不随 wheel 提供；接收方若需要这些交互，应另行接入应用层。当前没有完成 Linxi 宿主安装验收。

## ECoG 路线

使用`catalog("ecog")`或`dbci-qc catalog --modality ecog`查看独立方法。`prepare_recording(..., modality="ecog", qc_config=...)`使用相同原生索引接口；`selection.eeg_indices`在此表示ECoG分析触点，不意味着头皮EEG。方法参数放在`method_config.ecog`，不接收头皮专属检测参数。独立入口位于`src/ephys_qc/modules/ecog/`，M03–M05调用`modules/continuous/`共享计算内核；M01/M02/M07/M08/M09共享数据与报告接口。M06保持未接入。

```json
{"selection":{"eeg_indices":[0,1],"reference_indices":{},"start_seconds":0,"duration_seconds":120},"method_config":{"ecog":{"psd_window_seconds":4,"line_frequencies_hz":[50,60]},"comparison_groups":null}}
```

示例索引必须由实际文件与来源说明确认，不能直接复制到别的记录。详见[ECoG技术约定](ecog/qc-standards.md)。

## sEEG 与 Neuropixels 电压

`sEEG`使用`modality="seeg"`和`method_config.seeg`；已支持的SpikeGLX AP/LF或有明确Neuropixels设备证据的NWB连续电压使用`modality="extracellular"`和`method_config.neuropixels`。模块分别位于`modules/seeg/`和`modules/neuropixels/`，共用`modules/continuous/`内的描述量计算函数。读取器独立于模块，SpikeGLX的命令行入口是已有同名META配套的`.ap.bin`或`.lf.bin`；网页入口为二者打包的ZIP。

AP默认Welch窗口0.1秒、LF为1秒；这是频谱描述配置，不是判坏阈值。参数名称及基本结构与ECoG相同，但不接受其他模态的配置键或头皮算法参数。`selection.eeg_indices`是保留兼容的分析通道字段，在此指深部触点或探针神经通道；同步字不能加入。模块M01/M02再次读取源声明，不能仅凭改登记信息将AP变成LF或将sEEG改为ECoG。

三个基础模块给出原值和未评范围，不自动分类坏道，不计算已校准总分。NP2只有合成解码测试；spike sorting、unit quality、漂移、相位校正及跨流同步尚未接入。完整约定见[sEEG](seeg/qc-standards.md)、[Neuropixels](neuropixels/qc-standards.md)和[接入设计](multimodal-extension.md)。

NWB 2/HDF5由独立读取器接入。多ElectricalSeries文件须选定一个流，选择随记录版本、计划和运行冻结；改变流须重新确认并生成计划，不能沿用旧流通道索引。其他NWB电压依来源确认EEG/ECoG/sEEG，普通LFP或Units不能直接进入Neuropixels路线。当前Neuropixels电压配置版本为`neuropixels-voltage/2`；旧`neuropixels-raw/1`只解释已有历史任务，不追溯修改旧结果。具体字段以工具包与读取器接口为准，样例见[NWB来源与核对](nwb-testing.md)。


NWB可先调用`inspect_recording(path)`查看`available_streams`，再以`inspect_recording(path, stream_id="/acquisition/ElectricalSeries")`读取被选流的元数据。准备记录时向`prepare_recording(..., stream_id=...)`传递同一对象路径。命令行对应`dbci-qc inspect record.nwb --stream /acquisition/ElectricalSeries`和`prepare`命令的`--stream`参数；具体路径必须来自该文件的实际读取结果，不能根据示例猜测。
