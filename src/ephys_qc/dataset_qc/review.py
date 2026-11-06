"""D04: evidence-bound decisions and explicit retest differences.

Human dispositions never overwrite machine checks or EEG scores. A missing
check, a changed rule, or a scope reduction never counts as a repaired issue.
"""
from collections import Counter
import copy
import hashlib
import json

VERSION = 'dataset-review/1'
PROBLEMS = {'conflict', 'review', 'unassessed'}
DISPOSITIONS = {'needs_fix', 'restricted_use', 'follow_up', 'acceptable_difference'}
LABELS = {
    'pending': ('待处理', 'Pending'), 'needs_fix': ('需整改', 'Needs correction'),
    'restricted_use': ('限定用途', 'Restricted use'), 'follow_up': ('登记跟踪', 'Follow up'),
    'acceptable_difference': ('已说明差异', 'Explained difference'),
    'pending_review': ('待审核', 'Awaiting review'), 'blocked': ('需整改后复验', 'Correction and retest required'),
    'conditional': ('限定用途使用', 'Use with restrictions'), 'accepted': ('本次范围内已审核', 'Reviewed within this scope'),
    'resolved': ('复验已消除', 'Resolved on retest'), 'new': ('新增待处理', 'New finding'),
    'unchanged': ('仍存在', 'Still present'), 'changed': ('证据有变化', 'Evidence changed'),
    'not_rechecked': ('本次未复查', 'Not rechecked'), 'scope_changed': ('范围或规则改变', 'Scope or rules changed'),
}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()


def scope_id(manifest):
    # File hashes are expected to change after correction. Requirements and
    # record/group mappings must remain equal before calling an issue resolved.
    return digest({'consistency': manifest.get('consistency'),
                   'items': manifest.get('items'), 'recordings': manifest.get('recordings')})


def evidence_id(check, result):
    inventory = {f['path']: f for f in result.get('inventory', {}).get('files', [])}
    paths = set(check.get('files', []))
    for record in result.get('records', []):
        if record['id'] in check.get('records', []):
            paths.add(record['path'])
    files = [{k: inventory.get(p, {}).get(k) for k in ('path', 'status', 'sha256', 'size_bytes')}
             for p in sorted(paths)]
    return digest({'rule': result['rule_version'], 'check': check, 'files': files})


def retest_delta(before, after, before_manifest, after_manifest):
    compatible = before['rule_version'] == after['rule_version'] and scope_id(before_manifest) == scope_id(after_manifest)
    old = {c['id']: c for c in before['checks']}
    new = {c['id']: c for c in after['checks']}
    rows = []
    for key in sorted(old.keys() | new.keys()):
        a, b = old.get(key), new.get(key)
        if not ((a and a['status'] in PROBLEMS) or (b and b['status'] in PROBLEMS)):
            continue
        if not compatible:
            state = 'scope_changed'
        elif a and a['status'] in PROBLEMS and b and b['status'] == 'pass':
            state = 'resolved'
        elif not b or b['status'] == 'not_applicable':
            state = 'not_rechecked'
        elif not a or a['status'] not in PROBLEMS:
            state = 'new'
        elif evidence_id(a, before) == evidence_id(b, after):
            state = 'unchanged'
        else:
            state = 'changed'
        item = b or a
        rows.append({'check_id': key, 'module': item['module'], 'label': item['label'],
                     'label_en': item['label_en'], 'target': item['target'], 'change': state,
                     'before': a['status'] if a else None, 'after': b['status'] if b else None,
                     'records': item.get('records', [])})
    return {'compatible': compatible, 'counts': dict(Counter(r['change'] for r in rows)), 'rows': rows}


def build_case(result, manifest, saved=None, *, inherited=None, previous=None):
    saved = saved or {}
    decisions = saved.get('decisions', {})
    inherited = inherited or {}
    rows = []
    for c in result['checks']:
        if c['status'] not in PROBLEMS:
            continue
        identity = evidence_id(c, result)
        decision = decisions.get(c['id']) or inherited.get(c['id'])
        if decision and decision.get('evidence_id') != identity:
            decision = None
        rows.append({**copy.deepcopy(c), 'evidence_id': identity,
                     'decision': copy.deepcopy(decision), 'disposition': decision['disposition'] if decision else 'pending'})
    counts = Counter(r['disposition'] for r in rows)
    proposal = ('blocked' if counts['needs_fix'] else 'pending_review' if counts['pending'] else
                'conditional' if counts['restricted_use'] else 'accepted')
    final = saved.get('final')
    return {'schema_version': VERSION, 'rule_version': result['rule_version'],
            'result_hash': digest(result), 'scope_id': scope_id(manifest), 'scope': result['scope'],
            'revision': saved.get('revision', 0), 'rows': rows, 'summary': {
                'findings': len(rows), 'reviewed': len(rows) - counts['pending'], 'pending': counts['pending'],
                'needs_fix': counts['needs_fix'], 'restricted_use': counts['restricted_use'],
                'unassessed': sum(r['status'] == 'unassessed' for r in rows)},
            'proposed_outcome': proposal, 'final': copy.deepcopy(final),
            'outcome': final['outcome'] if final else 'pending_review',
            'dataset_summary': copy.deepcopy(result['summary']), 'previous': previous,
            'interpretation': 'local_project_review_not_hospital_acceptance_or_authenticated_signature'}


def apply_changes(case, saved, body, timestamp):
    if not isinstance(body, dict) or set(body) - {'expected_revision', 'result_hash', 'reviewer', 'changes', 'finalize', 'purpose'}:
        raise ValueError('审核请求字段无效。')
    if type(body.get('expected_revision')) is not int or body['expected_revision'] != case['revision']:
        raise ValueError('审核版本已改变，请刷新后重试。')
    if body.get('result_hash') != case['result_hash']:
        raise ValueError('检查结果已改变，请刷新后重试。')
    def text(value, label, *, maximum=2000, required=True):
        if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
            raise ValueError(label + '不能为空或过长。')
        return value.strip()
    reviewer = text(body.get('reviewer'), '审核人', maximum=100)
    changes = body.get('changes', [])
    if not isinstance(changes, list) or len(changes) > 500:
        raise ValueError('每次最多处理 500 个检查项。')
    if type(body.get('finalize', False)) is not bool:
        raise ValueError('请明确是否确认本次结论。')
    if not changes and not body.get('finalize'):
        raise ValueError('请选择需要处理的检查项。')
    rows = {r['id']: r for r in case['rows']}
    decisions = {r['id']: copy.deepcopy(r['decision']) for r in case['rows'] if r['decision']}
    seen = set()
    for item in changes:
        if not isinstance(item, dict) or set(item) != {'check_id', 'evidence_id', 'disposition', 'note', 'impact', 'action', 'owner'}:
            raise ValueError('处理记录字段无效。')
        key = item['check_id']
        if not isinstance(key, str) or key not in rows or key in seen:
            raise ValueError('检查项不存在或重复。')
        seen.add(key)
        if item['evidence_id'] != rows[key]['evidence_id']:
            raise ValueError('证据已改变，请刷新。')
        disposition = item['disposition']
        if disposition not in DISPOSITIONS:
            raise ValueError('请选择处理方式。')
        decisions[key] = {'evidence_id': item['evidence_id'], 'disposition': disposition,
                          'note': text(item['note'], '处理依据'), 'impact': text(item['impact'], '影响或允许的用途'),
                          'action': text(item['action'], '下一步', required=disposition in {'needs_fix', 'restricted_use', 'follow_up'}),
                          'owner': text(item['owner'], '负责人', maximum=100, required=disposition != 'acceptable_difference'),
                          'reviewer': reviewer, 'recorded_at': timestamp}
    output = {'revision': case['revision'] + 1, 'result_hash': case['result_hash'], 'decisions': decisions,
              'recorded_at': timestamp, 'reviewer': reviewer, 'final': None}
    if body.get('finalize'):
        counts = Counter(decisions.get(r['id'], {}).get('disposition', 'pending') for r in case['rows'])
        outcome = ('blocked' if counts['needs_fix'] else 'pending_review' if counts['pending'] else
                   'conditional' if counts['restricted_use'] else 'accepted')
        if outcome == 'pending_review':
            raise ValueError('仍有未处理项；请说明其影响和处理方式后再确认结论。')
        output['final'] = {'outcome': outcome, 'reviewer': reviewer, 'recorded_at': timestamp,
                           'purpose': text(body.get('purpose'), '本次审核用途'), 'revision': output['revision']}
    return output
