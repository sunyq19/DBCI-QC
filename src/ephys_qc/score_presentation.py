"""Expandable provenance for saved scores. Never run or revise a QC calculation."""
from html import escape
from functools import lru_cache
import math


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def amount(value):
    if not number(value):
        return '—'
    if 0 < abs(value) < .01:
        return '<0.01'
    return f'{value:,.2f}'.rstrip('0').rstrip('.')


def points(value):
    return f'{value:.2f}' if number(value) else '—'


def measurement(row, english=False):
    """Describe the saved numerator and denominator with their original unit."""
    t = lambda zh, en: en if english else zh
    bad, total = row.get('candidate_amount'), row.get('assessed_amount')
    if not number(bad) or not number(total) or total <= 0:
        return row.get('reason') or t('未保存有效测量', 'No valid measurement stored')
    units = {
        'channel_samples': t('个采样点（各通道累加）', 'samples across channels'),
        'samples': t('个采样点', 'samples'),
        'seconds': t('秒', 'seconds'),
        'channel_seconds': t('通道秒', 'channel-seconds'),
        'channel_windows': t('个通道检查窗', 'channel-windows'),
        'channels': t('个通道', 'channels'),
        'epochs': t('个片段', 'epochs'),
    }
    if row.get('unit') == 'channel_block_seconds':
        return t('分段通道候选占比按时长汇总：', 'Duration-weighted channel candidates: ') + points(100 * bad / total) + '%'
    if row.get('unit') not in units:
        return row.get('reason') or t('见保存的检查依据', 'See saved evidence')
    numeric = row.get('id') in {'ieeg_numeric_integrity', 'neuropixels_numeric_integrity'}
    return (t('NaN / Inf：', 'NaN / Inf: ') if numeric else t('候选：', 'Flagged: ')) + f'{amount(bad)} / {amount(total)} ' + units[row['unit']]


_EN_NAMES = {
    'ieeg_numeric_integrity': 'Numerical validity',
    'neuropixels_numeric_integrity': 'Numerical validity',
    'ieeg_signal_stability': 'Signal stability',
    'neuropixels_channel_state': 'Channel status',
    'neuropixels_constant_channels': 'Fully constant channels',
    'spikeinterface_bad_channels': 'SpikeInterface AP channel outliers',
    'mne_amplitude_channels': 'MNE amplitude channel candidates',
    'mne_amplitude_time': 'MNE amplitude interval candidates',
    'ieeg_range_plateau': 'File-range endpoint plateaus',
    'fieldtrip_zvalue': 'FieldTrip jump intervals',
    'ieeg_group_outliers': 'Grouped contact amplitude outliers',
}


def name(row, english=False):
    return _EN_NAMES.get(row['id'], row.get('name', row['id'])) if english else row.get('name', row['id'])


@lru_cache(maxsize=8)
def module_names(modality):
    from .planning import catalog
    return {row['id']: row['name'] for row in catalog(modality)}


def breakdown(row, *, english=False, total_available=True, measurement_text=None, modality='scalp_eeg'):
    """Show the saved reducer and effective shares, including historical rules."""
    t = lambda zh, en: en if english else zh
    esc = lambda value: escape(str(value), quote=True)
    stability = row['id'] == 'ieeg_signal_stability'
    weighted = stability and row.get('aggregation') == 'weighted_child_mean'
    minimum = stability and not weighted
    union = row['id'] == 'neuropixels_channel_state'
    grouped = stability or union
    children = row.get('evidence_components', []) if grouped else [row]
    active = set(row.get('assessed_methods', []))
    rejected = {r['id']: r.get('reason', '') for r in row.get('unavailable_methods', []) if isinstance(r, dict)}
    if weighted:
        rule = t('子项按本次有效权重平均；受限项不计入。', 'Children use their effective weighted mean; unavailable results are excluded.')
    elif minimum:
        rule = t('取有效子项的最低分；同类证据不累加扣分。', 'Use the lowest valid child score; related deductions are not added.')
    elif union:
        rule = t('先合并候选通道；同一通道在同一窗口只计一次。', 'Union candidate channels first; each channel counts once per window.')
    else:
        rule = t('此项由下列检查结果计分。', 'This component uses the following check.')
    value, weight = row.get('value'), row.get('normalized_weight', 0)
    if row.get('automatically_excluded'):
        impact = t('本次权重为 0，不影响综合分。', 'Zero effective share; excluded from the total.')
    elif number(value) and number(weight) and weight > 0 and total_available:
        impact = t(f'本项扣 {amount(100-value)} 分 × 权重 {100*weight:.1f}% = 综合分扣 {amount((100-value)*weight)} 分。',
                   f'Component deduction {amount(100-value)} × share {100*weight:.1f}% = total deduction {amount((100-value)*weight)}.')
    elif number(value):
        impact = t(f'本项扣 {amount(100-value)} 分。', f'Component deduction: {amount(100-value)}.')
    else:
        impact = t('尚无有效分项得分。', 'No valid component score.')
    body = ''
    for child in children:
        valid = child.get('status') == 'computed' and number(child.get('value'))
        used = valid and (child['id'] in active if grouped else not row.get('automatically_excluded') and number(weight) and weight > 0)
        limiting = minimum and used and number(value) and value < 100 and math.isclose(child['value'], value, abs_tol=1e-9, rel_tol=0)
        if not used:
            share = '0%'
        elif weighted:
            share = f'{100*child.get("normalized_weight",0):.1f}%'
        elif grouped:
            # Union and historical minimum reducers have no per-child weights.
            share = '—'
        else:
            share = f'{100*weight:.1f}%'
        evidence = measurement_text if not grouped and measurement_text else measurement(child, english)
        if not used and child['id'] in rejected:
            evidence = rejected[child['id']]
        module = child.get('module_id')
        module_text = t('所属模块 ', 'Module ') + str(module) if module else t('历史结果未记录模块', 'Module not stored in this historical result')
        if module and not english and module in module_names(modality):
            module_text += ' · ' + module_names(modality)[module]
        if not used:
            evidence = t('权重设为 0；', 'Weight set to zero; ') + evidence if child.get('configured_weight') == 0 else t('本次未计入；', 'Excluded; ') + evidence
        body += (f'<tr data-score-method="{esc(child["id"])}"' + (' class="score-determining"' if limiting else '') + '>'
                 f'<th scope="row">{esc(name(child, english))}<small>{esc(module_text)}</small></th>'
                 f'<td class="score-child-points">{points(child.get("value"))}</td>'
                 + f'<td>{esc(share)}</td><td>{esc(evidence)}</td></tr>')
    if not children:
        body = '<tr><td colspan="4">' + t('这份历史报告未保存子模块明细；保留原分数。', 'Child evidence was not stored in this historical report; its score is retained.') + '</td></tr>'
    headers = [t('模块', 'Module'), t('得分', 'Score'), t('权重', 'Weight'), t('检查发现', 'Findings')]
    return (f'<div class="score-breakdown"><p class="score-rule">{esc(rule)}</p><p class="score-impact">{esc(impact)}</p>'
            '<div class="score-evidence-scroll"><table class="score-evidence"><thead><tr>'
            + ''.join('<th scope="col">'+esc(h)+'</th>' for h in headers)
            + '</tr></thead><tbody>'+body+'</tbody></table></div></div>')


def score_tree(rows, *, english=False, findings=None, names=None, weight_labels=None,
               measurements=None, total_available=True, modality='scalp_eeg'):
    """One compact disclosure per top-level component, with stable column widths."""
    from .score_registry import SPECS
    t = lambda zh, en: en if english else zh
    esc = lambda value: escape(str(value), quote=True)
    headings = [t('计分项', 'Component'), t('得分 / 100', 'Score / 100'), t('本次权重', 'Effective share'), t('检查发现', 'Findings')]
    html = '<div class="score-tree"><div class="score-tree-head">' + ''.join('<span>'+esc(h)+'</span>' for h in headings) + '</div>'
    for saved in rows:
        # Registry metadata only fills missing labels in historical reports.
        row = {**{k: v for k, v in SPECS.get(saved['id'], {}).items() if k in {'module_id', 'method_id'}}, **saved}
        title = (names or {}).get(row['id'], name(row, english))
        label = (weight_labels or {}).get(row['id'], f'{100*row.get("normalized_weight",0):.1f}%')
        finding = (findings or {}).get(row['id'])
        if finding is None:
            if row.get('automatically_excluded'):
                finding = t('无有效结果，本次不计入', 'No valid result; excluded')
            elif row['id'] == 'ieeg_signal_stability':
                limiting = next((r for r in row.get('evidence_components', []) if r['id'] == row.get('limiting_method')), None)
                finding = (name(limiting, english) + t('决定本项得分', ' determines this score')) if limiting else row.get('reason', '')
                if row.get('aggregation') == 'weighted_child_mean':
                    count = len(row.get('assessed_methods', []))
                    finding = t(f'{count} 项有效检查按权重平均', f'Weighted mean of {count} valid checks')
                if row.get('value') == 100:
                    finding = t('已完成的检查未产生扣分', 'No deductions from the checks performed')
            else:
                finding = measurement(row, english)
        html += (f'<details class="score-component" data-score-id="{esc(row["id"])}"><summary class="score-summary">'
                 f'<span class="score-name"><span class="score-toggle" aria-hidden="true"></span>{esc(title)}</span>'
                 f'<strong class="score-points">{points(row.get("value"))}</strong><span class="score-share">{esc(label)}</span>'
                 f'<span class="score-finding">{esc(finding)}</span></summary>'
                 + breakdown(row, english=english, total_available=total_available, measurement_text=(measurements or {}).get(row['id']), modality=modality) + '</details>')
    return html + '</div>'


CSS = '''
.score-tree{width:100%;margin:8px 0 18px;--score-columns:minmax(160px,1.5fr) minmax(92px,.8fr) minmax(92px,.8fr) minmax(0,3fr)}
.score-tree .score-tree-head,.score-tree details.score-component>summary.score-summary{display:grid;grid-template-columns:var(--score-columns);align-items:center;gap:16px;padding:13px 12px;font:400 13px/1.6 var(--font-ui,system-ui,sans-serif);margin:0;min-width:0}
.score-tree .score-tree-head{background:#f4f6f9;color:#5a6b80;border-bottom:1px solid #dfe5ed}
.score-tree details.score-component{margin:0;padding:0;border:0;border-bottom:1px solid #dfe5ed;border-radius:0;background:none;box-shadow:none}
.score-tree details.score-component>summary.score-summary{list-style:none;cursor:pointer;color:#243449;min-height:60px}
.score-tree details.score-component>summary.score-summary::-webkit-details-marker{display:none}
.score-tree details.score-component>summary.score-summary::after{content:none}
.score-tree details.score-component>summary.score-summary:hover{background:#f5f8fd;color:#2459bc}
.score-tree details.score-component>summary.score-summary:focus-visible{outline:2px solid #2459bc;outline-offset:-2px}
.score-tree .score-name{display:flex;align-items:center;gap:10px;font-weight:600;min-width:0}
.score-toggle{width:12px;flex:none;color:#7a899c;font-weight:400}.score-toggle::before{content:'+'}.score-component[open] .score-toggle::before{content:'−'}
.score-tree .score-points{font-size:18px;font-weight:600;font-variant-numeric:tabular-nums}.score-tree .score-share{font-variant-numeric:tabular-nums;color:#53677f}.score-tree .score-finding{min-width:0;overflow-wrap:anywhere}
.score-tree .score-breakdown{padding:14px 16px 18px 34px;background:#f7f9fc;border-top:1px solid #e7edf5}
.score-tree .score-breakdown p{margin:0 0 6px;font-size:12px;line-height:1.6}.score-tree .score-rule{color:#52637a}.score-tree .score-impact{color:#243449}
.score-tree .score-evidence-scroll{overflow-x:auto;margin-top:12px}.score-tree table.score-evidence{width:100%;min-width:600px;table-layout:fixed;border-collapse:collapse;margin:0;background:white;font-size:12px}
.score-tree table.score-evidence th,.score-tree table.score-evidence td{padding:10px 12px;border:0;border-bottom:1px solid #e4eaf2;vertical-align:top;text-align:left;white-space:normal;overflow-wrap:anywhere;font-size:12px}
.score-tree table.score-evidence thead th{color:#65758a;background:#edf2f8;font-weight:400}
.score-tree table.score-evidence th:nth-child(1){width:28%;font-weight:500}.score-tree table.score-evidence th:nth-child(2){width:13%}.score-tree table.score-evidence th:nth-child(3){width:13%}.score-tree table.score-evidence th:nth-child(4){width:46%}
.score-tree .score-evidence small{display:block;margin-top:3px;font-size:11px;color:#6d7d90}.score-tree .score-child-points{font-variant-numeric:tabular-nums;font-weight:600}
.score-tree table.score-evidence tr.score-determining{background:#edf4ff}.score-tree table.score-evidence tr.score-determining th{box-shadow:inset 3px 0 #2a62bc}
@media(max-width:680px){.score-tree{--score-columns:minmax(110px,1.4fr) minmax(70px,.8fr) minmax(80px,.8fr)}.score-tree .score-tree-head span:last-child{display:none}.score-tree .score-finding{grid-column:1/-1;padding-left:22px;font-size:12px}.score-tree details.score-component>summary.score-summary{gap:5px 12px;padding:12px 8px}.score-tree .score-breakdown{padding:12px 8px}.score-tree .score-points{font-size:16px}}
@media print{.score-tree .score-component::details-content{display:block!important;content-visibility:visible!important}.score-tree .score-breakdown{display:block!important;background:white;padding:8px 0}.score-tree .score-evidence-scroll{overflow:visible}.score-tree table.score-evidence{min-width:0}.score-tree details.score-component{break-inside:avoid}.score-toggle{display:none}.score-tree .score-tree-head,.score-tree details.score-component>summary.score-summary{padding:8px;font-size:10px;gap:8px}.score-tree .score-points{font-size:13px}.score-tree table.score-evidence td,.score-tree table.score-evidence th{font-size:9px;padding:6px}}
'''
