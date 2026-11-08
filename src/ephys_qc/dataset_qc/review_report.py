"""D04 presentation model and HTML report. Check evidence is never rewritten."""
from collections import Counter
from datetime import datetime
import re

from .review import LABELS

LAYOUT_VERSION = 'dataset-review-layout/2'


def report_content(case, language='zh-CN'):
    en = language == 'en'
    t = lambda zh, eng: eng if en else zh
    label = lambda key: LABELS.get(key, (key, key))[int(en)]
    previous = case.get('previous')
    final = case.get('final')
    summary = case['dataset_summary']
    counts = Counter(r['status'] for r in case['rows'])
    checks = summary.get('status_counts', {})
    # Aliases are local to this report; the complete identifiers remain in its appendix.
    record_ids = sorted({rid for r in case['rows'] + (previous or {}).get('rows', [])
                         for rid in r.get('records', [])})
    aliases = {rid: f'R{i:02}' for i, rid in enumerate(record_ids, 1)}
    def target_name(target):
        return aliases.get(target, target)
    suggestions = {
        'read': t('核对配套文件是否完整，并重新读取该记录。', 'Verify companion files and read the recording again.'),
        'units': t('核对源文件标定与通道表中的物理单位。', 'Reconcile source calibration with the channel-table units.'),
        'rates': t('核对文件头、通道表与配套说明中的采样率。', 'Reconcile sampling rates in the header, channel table and metadata.'),
    }
    priorities = {'needs_fix': 0, 'restricted_use': 1, 'pending': 2, 'follow_up': 3, 'acceptable_difference': 4}
    machine = {'conflict': t('资料不符', 'Mismatch'), 'review': t('待核对', 'Check needed'),
               'unassessed': t('未评', 'Unassessed'), 'pass': t('通过', 'Pass'),
               'not_applicable': t('不适用', 'Not applicable')}
    rows = []
    groups = {}
    for row in sorted(case['rows'], key=lambda r: (r['status'] == 'unassessed', priorities[r['disposition']], r['module'], r['code'], r['target'])):
        d = row.get('decision') or {}
        item = {**row, 'title': row['label_en'] if en else row['label'], 'short_target': target_name(row['target']),
                'machine': machine[row['status']], 'disposition_label': label(row['disposition']),
                'impact': d.get('impact') or t('尚未登记', 'Not recorded'),
                'action': d.get('action') or suggestions.get(row['code'], t('核对来源资料后记录处理意见。', 'Verify the source and record a decision.')),
                'owner': d.get('owner') or t('未指定', 'Unassigned'), 'note': d.get('note') or '',
                'reviewer': d.get('reviewer') or ''}
        rows.append(item)
        # Same labels alone are insufficient: keep different evidence messages and decisions separate.
        key = (row['module'], row['code'], row['status'], row['message'], row['disposition'])
        group = groups.setdefault(key, {'title': item['title'], 'module': row['module'], 'status': row['status'],
              'machine': item['machine'], 'message': row['message'], 'disposition': item['disposition_label'],
              'action': suggestions.get(row['code'], t('核对来源资料后记录处理意见。', 'Verify the source and record a decision.')),
              'rows': []})
        group['rows'].append(item)
    grouped = list(groups.values())
    for index, group in enumerate(grouped, 1):
        group['ref'] = f'F{index:02}'
        group['targets'] = list(dict.fromkeys(r['short_target'] for r in group['rows']))
    conflict = counts['conflict']; review = counts['review']; unknown = counts['unassessed']
    if conflict:
        headline = t(f'发现 {conflict} 项资料不一致', f'{conflict} metadata mismatches found')
        description = t('先核对原始资料，再确认使用范围。', 'Reconcile the source metadata before confirming the intended use.')
    elif review:
        headline = t(f'{review} 项检查需要核对', f'{review} checks need review')
        description = t('请结合原始资料确认检查结果。', 'Review these findings against the source records.')
    elif unknown:
        headline = t(f'{unknown} 项检查尚未评定', f'{unknown} checks remain unassessed')
        description = t('补齐所需信息或确认适用条件后复查。', 'Complete the required information or confirm applicability, then rerun.')
    else:
        headline = t('本次未发现待处理问题', 'No open findings in this run')
        description = t('人工审核结论单独记录。', 'The human review outcome is recorded separately.')
    delta = []
    for r in (previous or {}).get('rows', []):
        if r['change'] != 'unchanged':
            delta.append({**r, 'title': r['label_en'] if en else r['label'], 'short_target': target_name(r['target']),
                          'change_label': label(r['change']), 'before_label': machine.get(r['before'], t('无记录', 'Not recorded')),
                          'after_label': machine.get(r['after'], t('无记录', 'Not recorded'))})
    delta.sort(key=lambda r: ({'resolved': 0, 'new': 1, 'changed': 2}.get(r['change'], 3), r['module'], r['target']))
    stamp = str(case.get('checked_at', ''))
    try:
        parsed = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
        offset = parsed.utcoffset()
        stamp = parsed.strftime('%Y-%m-%d %H:%M') + (' UTC' if offset is not None and offset.total_seconds() == 0 else parsed.strftime(' %z').rstrip())
    except ValueError:
        pass
    records = []
    for rid, alias in aliases.items():
        entities = dict(re.findall(r'(?:^|_)(sub|ses|task|acq|run)-([^_]+)', rid))
        records.append({'alias': alias, 'id': rid, 'subject': entities.get('sub', '—'),
                        'context': ' / '.join(entities[k] for k in ('ses', 'task', 'acq', 'run') if k in entities) or rid})
    status_note = t(f"{case['summary']['reviewed']} 项已登记意见，{case['summary']['pending']} 项待处理。",
                    f"{case['summary']['reviewed']} decisions recorded; {case['summary']['pending']} pending.")
    if final:
        status_note = f"{final['reviewer']} · {final['purpose']}"
    return {'title': t('数据集质控报告', 'Dataset quality control report'),
            'subtitle': t('审核与复验', 'Dataset review and retest report'),
            'label': case['label'], 'headline': headline, 'description': description, 'outcome': label(case['outcome']),
            'status_note': status_note, 'rows': rows, 'groups': grouped, 'delta': delta, 'records': records,
            'priority_groups': [g for g in grouped if g['status'] != 'unassessed'],
            'unknown_groups': [g for g in grouped if g['status'] == 'unassessed'],
            'counts': {'conflict': conflict, 'review': review, 'unassessed': unknown, 'pass': checks.get('pass'),
                       'not_applicable': checks.get('not_applicable'), 'total': sum(checks.values()) if checks else None},
            'checked_at': stamp, 'layout_version': LAYOUT_VERSION,
            'demo': t('工程演示 · 公开数据副本', 'Engineering demo · Public-data copy') if case.get('engineering_demo') else '',
            'boundary': t('本报告检查数据资料的一致性与完整性，人工审核仅针对声明范围。工程演示不代表医院验收。',
                          'This report covers dataset metadata consistency and completeness. Human review is scope-specific; an engineering demo is not hospital acceptance.'),
            'count_note': t('数量按检查项统计；同一记录可能对应多项检查。未评不等于不合格。',
                            'Counts refer to checks, not recordings. One recording can have several checks. Unassessed does not mean failed.')}


def render_review_report(case, language='zh-CN', *, standalone=False):
    from .review_report_web import render_html
    return render_html(case, report_content(case, language), language, standalone=standalone)


def review_pdf(case, language='zh-CN'):
    from .review_report_pdf import render_pdf
    return render_pdf(case, report_content(case, language), language)
