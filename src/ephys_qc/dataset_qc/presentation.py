"""Actionable display of dataset findings; does not change QC classifications."""
from collections import defaultdict

# title, meaning, next step, suggested owner (zh / en).
COPY = {
    'bids_validator': (
        ('BIDS 格式与配套说明', 'BIDS format and companion metadata'),
        ('以下是文件组织及说明字段的检查；重复发现已按规则合并，不代表所有信号损坏。', 'Repeated format and metadata findings are grouped by rule, not counted as corrupted signals.'),
        ('先处理错误，再核对建议；按数据声明的 BIDS 版本复核适用性。', 'Review errors before recommendations and check applicability to the declared BIDS version.'),
        ('资料管理员', 'Dataset coordinator')),
    'channel_schema': (
        ('通道表需要核对', 'Channel table needs review'),
        ('配套通道表无法建立唯一的通道对应关系，关联核对暂未完成。', 'The channel table does not establish a unique mapping; dependent comparisons were not completed.'),
        ('核对重复名称或缺失字段；信号检查结果仍可查看。', 'Check repeated names or missing fields; signal reports remain available.'),
        ('数据提供方', 'Data provider')),
    'read': (
        ('记录暂时无法读取', 'Recordings could not be read'),
        ('这些记录尚不能进入信号检查。', 'Signal checks cannot start for these recordings.'),
        ('请数据提供方核对主文件和配套文件，确认导出完整后重新检查。', 'Ask the data provider to verify the recording and companion files, then rerun after a complete export.'),
        ('数据提供方', 'Data provider')),
    'files': (
        ('文件缺失或与清单不符', 'Files are missing or differ from the inventory'),
        ('本次收到的文件与约定资料没有完全对应。', 'The received files do not fully match the expected inventory.'),
        ('核对应有清单，补齐或确认文件版本后重新检查。', 'Verify the inventory, supply missing files or confirm versions, then rerun.'),
        ('数据提供方', 'Data provider')),
    'units': (
        ('单位标注不一致', 'Unit labels differ'),
        ('文件头与配套表的单位标注不同；尚不能据此认定波形错误。', 'Unit labels differ between the header and accompanying table; this alone does not establish an incorrect waveform.'),
        ('请数据提供方核对原始单位、标定系数和导出说明，再决定是否需要修正。', 'Ask the data provider to verify source units, calibration factors and export notes before deciding whether a correction is needed.'),
        ('数据提供方', 'Data provider')),
    'rates': (
        ('采样率记录不一致', 'Sampling-rate descriptions differ'),
        ('文件与配套资料对采样率的描述不同。', 'The recording and accompanying metadata describe different sampling rates.'),
        ('核对采集或转换记录，确认正确采样率后重新检查。', 'Verify acquisition or conversion records, confirm the correct sampling rate, then rerun.'),
        ('数据提供方', 'Data provider')),
    'binding': (
        ('编号或配套文件对应不一致', 'Identifiers or companion-file assignments differ'),
        ('记录与配套资料中的受试者、会话或记录编号未对应。', 'Subject, session or recording identifiers do not match the declared assignment.'),
        ('核对编号与配套关系，确认没有放错文件。', 'Verify identifiers and companion-file assignments.'),
        ('资料管理员', 'Dataset coordinator')),
    'duplicates': (
        ('记录内容可能重复', 'Recordings may contain duplicate content'),
        ('检测到相同内容的记录，是否重复纳入需要确认。', 'Identical content was detected; whether it is an unintended duplicate requires confirmation.'),
        ('核对采集批次和用途；确认前保留原文件。', 'Check acquisition sessions and intended use; retain the originals until confirmed.'),
        ('资料管理员', 'Dataset coordinator')),
}


def attention_groups(checks, records):
    buckets = defaultdict(list)
    for check in checks:
        if check['status'] in ('conflict', 'review'):
            buckets[(check['code'], check['status'])].append(check)
    groups = []
    for (code, status), rows in buckets.items():
        ids = {r['id'] for r in rows}
        affected = [r for r in records if ids.intersection(r['finding_ids'])]
        copy = COPY.get(code)
        if code == 'units' and status == 'review':
            copy = (('单位信息需要补充', 'Unit information needs confirmation'),
                    ('部分通道缺少可核对的单位信息。', 'Some channels lack verifiable unit information.'),
                    COPY['units'][2], COPY['units'][3])
        if code == 'rates' and status == 'review':
            copy = (('采样率信息需要补充', 'Sampling-rate information needs confirmation'),
                    ('部分通道缺少可核对的采样率信息。', 'Some channels lack verifiable sampling-rate information.'),
                    COPY['rates'][2], COPY['rates'][3])
        if copy is None:
            copy = ((rows[0].get('label', code) + '需要核对', rows[0].get('label_en', code) + ' needs review'),
                    ('此检查需要结合原始资料进一步确认。', 'This check needs further review against the source information.'),
                    ('查看具体记录与证据，请资料负责人核对。', 'Review the affected records and evidence with the dataset coordinator.'),
                    ('资料管理员', 'Dataset coordinator'))
        detail = []
        if code == 'units':
            pairs = sorted({(str(c.get('file')), str(c.get('table'))) for row in rows
                            for c in (row.get('observed') or {}).get('conflicts', [])})
            if pairs:
                detail = [{'file_unit': a, 'table_unit': b} for a, b in pairs]
        groups.append({'id': code + '-' + status, 'code': code, 'status': status,
                       'title': copy[0][0], 'title_en': copy[0][1],
                       'meaning': copy[1][0], 'meaning_en': copy[1][1],
                       'next_step': copy[2][0], 'next_step_en': copy[2][1],
                       'owner': copy[3][0], 'owner_en': copy[3][1],
                       'record_ids': [r['id'] for r in affected], 'record_count': len(affected),
                       'subjects': sorted({r['subject'] for r in affected}),
                       'check_ids': [r['id'] for r in rows], 'unit_labels': detail})
    return sorted(groups, key=lambda g: (0 if g['code'] in ('read', 'files') else 1, g['code'], g['status']))
