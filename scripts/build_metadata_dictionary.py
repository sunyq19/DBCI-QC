"""Render the bilingual design dictionary; this is not an intake API migration."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / 'specs/metadata-fields.v1.json'


def render(spec, lang):
    en = lang == 'en'
    pick = lambda zh, english: english if en else zh
    lines = [pick('# 数据字段字典', '# Data field dictionary'), '',
             pick('项目技术规范 · 版本 metadata-fields/1 · 2026-10-31 · 设计约定',
                  'Project technical specification · Version metadata-fields/1 · 2026-10-31 · Design contract'), '',
             pick('本字典规定跨物种电生理数据的字段语义。字段可描述的数据范围不等于当前软件可执行范围；新字段尚未整体接入上传表单或运行API。',
                  'This dictionary defines cross-species electrophysiology metadata. Representable data are not necessarily executable inputs; the new fields are not yet integrated as a whole into intake forms or the runtime API.'), '',
             pick('[总则](/standards/overview) · [方法适用规则](/standards/applicability) · [当前实现](/standards/implementation)',
                  '[General requirements](/standards/overview) · [Method applicability](/standards/applicability) · [Current implementation](/standards/implementation)'), '',
             pick('## 1 组织与粒度', '## 1 Organization and scope'), '',
             pick('字段分为受试对象、信号与文件、通道与采集、实验与状态、处理与来源五组。subject表示对象；session表示一次采集会话；recording表示记录；stream表示独立数据流；channel/electrode/channel_group分别表示通道、接触点和比较组；interval表示时段；analysis表示本次选区。会话级背景不得覆盖逐通道或逐时段的不同事实。',
                  'Five groups describe the subject, signal/files, channels/acquisition, experiment/state, and processing/provenance. Scope identifies the subject, acquisition session, recording, independent stream, channel, electrode contact, comparison group, time interval or analysis selection. Session-level context must not overwrite channel- or interval-specific facts.'), '',
             pick('通道数由通道集合生成；年龄组由年龄和已声明物种规则生成。格式、物种、记录位置、信号对象和设备技术是独立字段。新增方法按所需前提扩展，不增加“物种×疾病×格式”的组合标签。',
                  'Channel counts derive from channel collections; age groups derive from age and declared species-specific rules. Format, species, recording site, signal object and hardware technology are independent. Add method prerequisites without creating species-by-disease-by-format categories.'), '',
             pick('## 2 通用字段值约定', '## 2 Common value contract'), '',
             pick('每个字段值应携带value、status、source和confirmation。known表示存在明确声明，不代表科学真值；unknown表示未提供或尚未提取；not_applicable须说明原因；conflict应保留各来源候选值，未解决前不得选择其一驱动方法。unknown/not_applicable/conflict的规范化value为null。',
                  'Each value carries value, status, source and confirmation. known means explicitly declared, not independently proven; unknown means missing or unextracted; not_applicable requires a reason; conflict retains source alternatives and must not silently select one for execution. The normalized value is null for unknown, not_applicable and conflict.'), '',
             pick('source应记录类型（file_header、sidecar、provider_document、manual、derived）、文件或资料引用和字段位置；派生值另记转换规则及版本。confirmation为unreviewed或confirmed，表示是否经过确认，不把“确认”当作医学或实验真值。空列表只有在已检查相应范围后才表示未发现。',
                  'source records kind (file_header, sidecar, provider_document, manual or derived), reference and field locator; derived values also retain transformation and version. confirmation is unreviewed or confirmed and does not establish clinical or experimental truth. Empty lists establish absence only within an explicitly inspected scope.'), '',
             pick('缺项动作按方法解释：block_reading为无法可靠读取；block_registration为无法建立记录身份；block_execution为无法执行所请求选区；restrict_method只限制依赖该字段的方法；restrict_interpretation限制解释；retain_unknown保留未知。它们是目标约定，当前实际限制见实现范围。',
                  'Missing actions are method-scoped: block_reading prevents reliable decoding; block_registration prevents a stable record identity; block_execution prevents execution of the requested selection; restrict_method disables dependent methods only; restrict_interpretation limits interpretation; retain_unknown preserves missing context. These are design requirements; current behavior is listed separately.'), '',
             pick('qc_use取reader（读取）、routing（对象/路线选择）、technical（方法技术前提）、context（解释与验证分层）或provenance（追溯）。context字段未经独立验证不得自动改变阈值、扣分或清洗。',
                  'qc_use is reader, routing, technical, context or provenance. Context fields support interpretation and validation strata; they must not automatically alter thresholds, scores or cleaning without independent validation.'), '',
             pick('## 3 年龄与物种', '## 3 Age and species'), '',
             pick('年龄应保留lower/upper边界、day/week/month/year单位、birth/gestational/other/unknown参考起点、recording/session_start/experiment_start/source_unspecified时间语境及source_text。精确值两端相同；单侧未知用null，不得两端均空。区间须非负且lower≤upper。月与年保留原单位，不随意折算为固定天数。',
                  'Age retains lower/upper bounds, day/week/month/year unit, birth/gestational/other/unknown reference, recording/session_start/experiment_start/source_unspecified time context, and source_text. Exact ages have equal bounds; a missing bound is null, but both cannot be missing. Bounds are nonnegative and ordered. Preserve months and years rather than inventing exact day conversions.'), '',
             pick('孕期年龄应另记来源的起算定义；不得混淆出生后年龄、孕周和矫正年龄。只有发育阶段时允许仅保存life_stage；未经验证不自动建立跨物种“成年”分界。来源未明确物种时保留未知，即使外部格式存在兼容性默认值，也应将其记录为默认来源而非确认事实。',
                  'Gestational ages retain the source definition of their origin; do not conflate postnatal, gestational and corrected age. A life_stage-only declaration is allowed. Do not invent cross-species adult cutoffs. Missing species remains unknown; compatibility defaults from external formats are recorded as defaults, not confirmed facts.'), '']
    for index, group in enumerate(spec['groups'], 4):
        lines += [f"## {index} {group['title'][lang]}", '',
                  pick('| 字段 | 定义与值类型 | 粒度 | 缺项动作 | 用途 |', '| Field | Definition and value type | Scope | Missing action | Use |'),
                  '| --- | --- | --- | --- | --- |']
        for f in group['fields']:
            lines.append(f"| `{f['id']}` · {f['label'][lang]} | {f['definition'][lang]} `{f['value_type']}` | `{f['scope']}` | `{f['missing_action']}` | `{f['qc_use']}` |")
        lines.append('')
    lines += [pick('## 9 复合值结构', '## 9 Compound value structures'), '',
              pick('以下是值的结构摘要；对应字段仍需遵守第2章的来源和状态约定。原始来源文本应保留。',
                   'The following summaries describe values; field instances still follow the provenance/status contract in section 2. Preserve original source text.'), '',
              '| Type | Structure |', '| --- | --- |']
    for kind, structure in spec['value_types'].items():
        lines.append(f'| `{kind}` | `{structure}` |')
    lines += ['', pick('## 10 维护与映射', '## 10 Maintenance and mapping'), '',
              pick('权威字段清单为仓库specs/metadata-fields.v1.json；本页中英文由scripts/build_metadata_dictionary.py生成。字段ID、定义、单位、粒度或缺项含义改变时应更新字典版本及迁移说明。对当前API的兼容映射须另行实现和测试；不得把本清单直接当成已接受的上传JSON。',
                   'The authoritative catalog is specs/metadata-fields.v1.json; scripts/build_metadata_dictionary.py generates both languages. Changes to IDs, meaning, units, scope or missing semantics require a dictionary version and migration record. Runtime API mappings require separate implementation and tests; this catalog is not an accepted upload JSON schema.'), '',
              pick('BIDS映射按participants、recording JSON、channels、electrodes、coordsystem和events分层；NWB映射按Subject、ElectricalSeries、electrodes、device和时间对象分层。源字段不适配本字典时保留原值、限定解释，不静默丢弃。',
                   'BIDS mappings distinguish participants, recording JSON, channels, electrodes, coordsystem and events. NWB mappings distinguish Subject, ElectricalSeries, electrodes, devices and time objects. Preserve source values with explicit limits when a mapping is incomplete.'), '',
              '[BIDS 1.11.2](https://bids-specification.readthedocs.io/en/v1.11.2/) · [NWB 2.11.0](https://github.com/NeurodataWithoutBorders/nwb-schema/blob/2.11.0/core/nwb.file.yaml)', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    spec = json.loads(SPEC.read_text())
    ids = [f['id'] for group in spec['groups'] for f in group['fields']]
    if len(ids) != len(set(ids)):
        raise SystemExit('Duplicate field ID')
    for lang, path in [('zh-CN', ROOT/'docs/metadata-fields.md'), ('en', ROOT/'docs/en/metadata-fields.md')]:
        output = render(spec, lang)
        if args.check:
            if not path.is_file() or path.read_text() != output:
                raise SystemExit('Dictionary document differs from catalog: ' + str(path))
        else:
            path.write_text(output, encoding='utf-8')
    print(f'{len(ids)} field definitions; bilingual documents ' + ('match' if args.check else 'generated'))


if __name__ == '__main__':
    main()
