"""Render bilingual EEG check terms from the packaged, versioned rule catalog."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'src/ephys_qc/specifications/eeg-basic.v1.json'


def render(catalog, lang):
    en = lang == 'en'
    text = lambda zh, english: english if en else zh
    kinds = {'required': text('基础项目', 'Core check'), 'conditional': text('条件项目', 'Conditional check'),
             'descriptive': text('描述项目', 'Descriptive check')}
    lines = [text('# EEG 检查词条与模块', '# EEG check terms and modules'), '',
             text(f'项目实施规程 · 版本 {catalog["version"]} · 对应规范 {catalog["specification_version"]}',
                  f'Project implementation procedure · Version {catalog["version"]} · Specification {catalog["specification_version"]}'), '',
             text('[EEG规范](/standards) · [来源依据](/standards/eeg-evidence) · [报告要求](/standards/eeg-report) · [字段字典](/standards/fields)',
                  '[EEG specification](/standards) · [Evidence sources](/standards/eeg-evidence) · [Report requirements](/standards/eeg-report) · [Field dictionary](/standards/fields)'), '',
             text('## 1 目录与解释', '## 1 Catalog and interpretation'), '',
             text('本目录规定人类连续头皮EEG基础技术质控的词条、测量口径及证据输出。12个词条对应现有9个模块，未增加12种算法。基础项目应在评价规程中交代是否执行；条件项目核对前提后执行；描述项目没有好坏阈值。项目要求与外部资料性来源分开，所有默认数值均应由实际运行参数核对。',
                  'This catalog specifies terms, measurements and evidence for basic technical QC of human continuous scalp EEG. Twelve terms map to the existing nine modules, not twelve additional algorithms. Core checks require an execution account; conditional checks require their prerequisites; descriptive checks have no quality cutoff. Project requirements are separate from informative external sources. Verify defaults against effective runtime parameters.'), '',
             text('词条映射不是合规认证。人类/头皮范围须有来源确认；当前运行字段未完整支持该确认。算法候选、人工结论与执行状态应分别读取。完整性问题可能使后续频谱或事件方法失败；失败项没有零噪声或正常结论。',
                  'Mapping is not certification. Human/scalp scope requires source confirmation, not yet fully captured by runtime fields. Read algorithm candidates, human decisions and execution states separately. Integrity issues can prevent spectral/event methods; failure does not imply zero noise or normality.'), '',
             text('| 词条 | 检查目的 | 类型 | 模块 |', '| Term | Purpose | Type | Module |'), '| --- | --- | --- | --- |']
    for c in catalog['checks']:
        lines.append(f'| [{c["id"]}](#{c["id"].lower()}) | {c["title"][lang]} | {kinds[c["kind"]]} | [{c["module_id"]}](/standards/modules/{c["module_id"]}) |')
    for c in catalog['checks']:
        lines += ['', f'## {c["id"]}', '', '**' + c['title'][lang] + '**', '',
                  text('### 适用与计算', '### Applicability and measurement'), '', c['applicability'][lang], '', c['measurement'][lang], '',
                  text('### 判据与报告', '### Decision basis and reporting'), '', c['decision_basis'][lang], '', c['report_content'][lang], '',
                  text('### 实现与依据', '### Implementation and evidence'), '',
                  f'[{c["module_id"]}](/standards/modules/{c["module_id"]}) · ' + ', '.join(c['source_ids']) + ' · ' + text('[依据定位](/standards/eeg-evidence)', '[Source locations](/standards/eeg-evidence)'), '',
                  text('产物：', 'Artifacts: ') + '、'.join('`'+a+'`' for a in c['artifacts']) + '.', '',
                  text('证据字段：', 'Evidence fields: ') + ', '.join('`'+f+'`' for f in c['evidence_fields']) + '.', '',
                  c['validation'][lang]]
    lines += ['', text('## 2 可选方法与词条关系', '## 2 Optional methods and terms'), '',
              text('可选方法补充已有词条的证据，不自动增加质量分或形成多数票真值。依赖、实际参数和失败原因保存在各扩展产物中；缺失原值明确标注，不从候选名单反推数值。',
                   'Optional methods add evidence to existing terms; they do not add score points or create ground truth by voting. Dependencies, effective parameters and failures remain in extension artifacts. Unexported measurements remain unavailable rather than reconstructed from candidate names.'), '',
              text('| 词条 | 已接入方法 | 解释边界 |', '| Term | Integrated method | Interpretation limit |'), '| --- | --- | --- |',
              text('| EEG-003 | MNE幅度；global AutoReject | 相邻差值与峰峰值不同；全局阈值是同选区探索估计，固定段非任务试次 |', '| EEG-003 | MNE amplitude; global AutoReject | Successive differences differ from peak-to-peak amplitude; global threshold is exploratory in-sample estimation, not task-trial validation |'),
              text('| EEG-007 | MNE桥接、LOF；mne-faster | 通道对非坏道数；桥接实际分界点、FASTER原始特征及z值未导出；FASTER为Python实现 |', '| EEG-007 | MNE bridging, LOF; mne-faster | Pairs are not bad-channel counts; actual bridge cutoff and FASTER raw features/z-scores are not exported; FASTER is a Python implementation |'),
              text('| EEG-009 | MNE高频包络；FieldTrip差分z值 | 通用高频/差分异常线索，不能自动确认肌电；FieldTrip通过Octave兼容运行 |', '| EEG-009 | MNE high-frequency envelope; FieldTrip differential z-value | Generic high-frequency/difference candidates do not confirm EMG; FieldTrip runs through Octave compatibility |'),
              text('| 处理影响评估 | ASR、CleanLine、Zapline-plus | 显式选择、临时副本、未导出清洗信号；改变功率不证明质量改善 |', '| Processing-effect evaluation | ASR, CleanLine, Zapline-plus | Explicit selection, temporary copy, no cleaned signal export; power changes do not prove quality improvement |'), '',
              text('PyPREP RANSAC、local AutoReject、ICLabel未接入。选用门槛与论文验证范围不是同一概念；例如FASTER低通道数仍需独立验证，详见来源依据。',
                   'PyPREP RANSAC, local AutoReject and ICLabel are not integrated. Execution gates differ from published validation coverage; low-channel-count FASTER needs independent validation. See evidence sources.'), '',
              text('## 3 版本与复核', '## 3 Versions and review'), '',
              text('本页由src/ephys_qc/specifications/eeg-basic.v1.json生成。新EEG报告保存eeg-rules.json原始目录字节及SHA-256、eeg-assessment.json逐项证据索引、方法产物和有效参数。目录变化须更新版本并重建中英文页面；既有报告不回填。整记录须保留每窗报告，不累加不同频率、通道或重叠窗的时间作为总污染率。',
                   'Generated from src/ephys_qc/specifications/eeg-basic.v1.json. New EEG reports preserve exact eeg-rules.json bytes/SHA-256, the eeg-assessment.json evidence index, method artifacts and effective parameters. Version catalog changes and regenerate both languages; do not backfill historical reports. Whole-record output retains window reports; durations from different frequencies/channels or overlapping windows are not additive total contamination.'), '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--check', action='store_true'); args = parser.parse_args()
    catalog = json.loads(CATALOG.read_text())
    for lang, path in [('zh', ROOT/'docs/eeg-checks.md'), ('en', ROOT/'docs/en/eeg-checks.md')]:
        expected = render(catalog, lang)
        if args.check:
            if not path.exists() or path.read_text() != expected:
                raise SystemExit(f'Stale generated document: {path.name} ({lang})')
        else:
            path.write_text(expected, encoding='utf-8')
    print('EEG check documents are synchronized.')


if __name__ == '__main__':
    main()
