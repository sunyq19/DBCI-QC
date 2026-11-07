"""D02/D03: explicit record bindings and declared comparison groups.

These are project consistency rules, not a full BIDS validator, identity proof,
or signal-quality score. No metadata is silently used to repair source files.
"""
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import re

from .inventory import inspect_package, _relative, _safe_file, _validate

RULE_VERSION = 'dataset-consistency/0.1.1'
MISSING = {'', 'n/a', 'na', 'unknown', 'none'}
UNITS = {'v': 'V', 'mv': 'mV', 'uv': 'uV', 'µv': 'uV', 'μv': 'uV', 'nv': 'nV',
         'volts': 'V', 'millivolts': 'mV', 'microvolts': 'uV', 'nanovolts': 'nV'}
CHECK_NAMES = {
    'files': ('应到文件', 'Expected files'), 'read': ('记录结构', 'Recording structure'),
    'binding': ('受试者与会话对应', 'Subject/session binding'), 'participants': ('受试者表对应', 'Participant index'),
    'sessions': ('会话表对应', 'Session index'), 'scans': ('记录表对应', 'Scan index'),
    'channel_schema': ('通道表字段', 'Channel table fields'), 'channel_names': ('通道名称与顺序', 'Channel names/order'),
    'units': ('物理单位', 'Physical units'), 'rates': ('采样率', 'Sampling rates'),
    'duration': ('记录时长', 'Recording duration'), 'events': ('事件时间与通道', 'Event time/channel'),
    'individual_channels': ('个体内通道配置', 'Within-subject channels'), 'individual_rates': ('个体内采样率', 'Within-subject sampling rates'),
    'individual_units': ('个体内单位', 'Within-subject units'), 'individual_reference': ('个体内参考', 'Within-subject reference'),
    'cohort_channels': ('组内通道配置', 'Within-group channels'), 'cohort_rates': ('组内采样率', 'Within-group sampling rates'),
    'cohort_units': ('组内单位', 'Within-group units'), 'cohort_reference': ('组内参考', 'Within-group reference'),
    'group_scope': ('比较组范围', 'Comparison-group scope'), 'duplicates': ('重复记录线索', 'Possible duplicate recordings'),
    'comparison': ('可比记录数量', 'Comparable recordings'), 'schema': ('组内配套表结构', 'Group table schema'),
}


def unit(value):
    text = str(value or '').strip()
    return None if text.lower() in MISSING else UNITS.get(text.lower(), text)


def numeric(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def entities(path):
    result = {}
    for part in Path(path).parts:
        for key, value in re.findall(r'(?:^|_)(sub|ses|task|acq|run)-([^_.]+)', part):
            result.setdefault(key, set()).add(value)
    return result


def validate_consistency(manifest):
    _validate(manifest)
    config = manifest.get('consistency')
    if not isinstance(config, dict) or config.get('schema_version') != 'dataset-consistency-plan/1':
        raise ValueError('需要明确的 dataset-consistency-plan/1 一致性配置。')
    records, groups = config.get('records'), config.get('groups')
    if not isinstance(records, list) or not records or not isinstance(groups, list) or not groups:
        raise ValueError('请声明记录对应关系和比较组。')
    expected = {f['path'] for f in manifest['files']}
    recording_paths = {r['path'] for r in manifest['recordings']}
    ids, paths, group_ids = set(), set(), set()
    for group in groups:
        if not isinstance(group, dict) or not isinstance(group.get('id'), str) or not group['id'] or group['id'] in group_ids:
            raise ValueError('比较组 ID 必须唯一。')
        group_ids.add(group['id'])
        for key in ('same_channels', 'same_rates', 'same_units', 'same_reference'):
            if type(group.get(key)) is not bool:
                raise ValueError('比较组必须显式声明四项一致性要求。')
    for r in records:
        if not isinstance(r, dict) or not isinstance(r.get('id'), str) or not r['id'] or r['id'] in ids:
            raise ValueError('记录 ID 必须唯一。')
        ids.add(r['id'])
        if r.get('path') not in recording_paths or r['path'] in paths:
            raise ValueError('一致性配置必须逐一对应清单中的记录。')
        paths.add(r['path'])
        if r.get('group') not in group_ids or r.get('processing') not in {'raw', 'derived'}:
            raise ValueError('每份记录须明确比较组及原始/派生状态。')
        if any(not isinstance(r.get(key), str) or not r[key] for key in ('subject', 'session', 'modality')):
            raise ValueError('每份记录须声明受试者、会话和模态。')
        refs = [r.get(key) for key in ('channels_tsv', 'participants_tsv', 'sessions_tsv', 'scans_tsv') if r.get(key)]
        metadata = r.get('metadata_json', [])
        if not isinstance(metadata, list): raise ValueError('metadata_json 须为显式按继承顺序排列的列表。')
        refs += metadata
        events = r.get('events')
        if events:
            if not isinstance(events, dict) or events.get('mode') not in {'seconds', 'indices'}:
                raise ValueError('事件表需声明秒或样本索引模式。')
            refs.append(events.get('path'))
            if events['mode'] == 'indices' and events.get('origin') not in {None, 0, 1}:
                raise ValueError('样本索引起点须为 0、1 或未知。')
        if any(_relative(p) not in expected for p in refs):
            raise ValueError('配套表须列入独立应有清单。')
    if paths != recording_paths:
        raise ValueError('一致性配置不能遗漏清单中的记录。')
    if group_ids != {r['group'] for r in records}: raise ValueError('比较组不能是空组。')
    return config


class Checks:
    def __init__(self): self.rows = []

    def add(self, module, code, status, target, message, *, records=(), files=(), observed=None):
        identity = json.dumps([module, code, target], ensure_ascii=False)
        self.rows.append({'id': hashlib.sha256(identity.encode()).hexdigest()[:16], 'module': module,
                          'code': code, 'label': CHECK_NAMES[code][0], 'label_en': CHECK_NAMES[code][1],
                          'status': status, 'target': target, 'message': message,
                          'records': list(records), 'files': list(dict.fromkeys(files)), 'observed': observed})


def _load(root, path, inventory, cache, kind):
    if not path: return None
    if inventory.get(path, {}).get('status') != 'present': return None
    if path in cache: return cache[path]
    source = _safe_file(root, path)
    if source is None or source.stat().st_size > 32 * 1024 * 1024:
        cache[path] = {'error': 'table_size_or_path'}; return cache[path]
    try:
        if kind == 'json':
            value = json.loads(source.read_text(encoding='utf-8-sig'))
            if not isinstance(value, dict): raise ValueError('object required')
        else:
            with source.open(encoding='utf-8-sig', newline='') as handle:
                reader = csv.DictReader(handle, delimiter='\t')
                fields = reader.fieldnames
                if not fields or len(fields) != len(set(fields)): raise ValueError('duplicate/missing columns')
                rows = list(reader)
                if any(None in row or any(v is None for v in row.values()) for row in rows): raise ValueError('row width')
                value = {'fields': fields, 'rows': rows}
        cache[path] = value
    except (OSError, ValueError, UnicodeError, csv.Error):
        cache[path] = {'error': 'invalid_table'}
    return cache[path]


def _identity(root, r, inventory, cache, checks):
    rid = r['id']; expected = {'sub': r['subject'].removeprefix('sub-'), 'ses': r['session'].removeprefix('ses-')}
    record_entities = entities(r['path'])
    expected.update({k:next(iter(v)) for k,v in record_entities.items() if len(v)==1 and k in {'task','acq','run'}})
    paths = [r['path']] + [r[k] for k in ('channels_tsv',) if r.get(k)] + ([r['events']['path']] if r.get('events') else []) + r.get('metadata_json', [])
    conflicts = [p for p in paths if any(k in entities(p) and entities(p)[k] != {v} for k, v in expected.items())]
    seen = entities(r['path'])
    status = 'conflict' if conflicts else ('pass' if 'sub' in seen and ('ses' in seen or r['session'] == 'none') else 'unassessed')
    checks.add('D02', 'binding', status, rid, '按声明核对路径中的受试者/会话标识，不证明真实身份。', records=[rid], files=paths,
               observed={'conflicting_paths': conflicts})
    for field, code, column, value in [('participants_tsv', 'participants', 'participant_id', r['subject']),
                                      ('sessions_tsv', 'sessions', 'session_id', r['session'])]:
        path = r.get(field); table = _load(root, path, inventory, cache, 'tsv')
        if table is None: status, msg = 'unassessed', '未提供或未验证对应表。'
        elif 'error' in table or column not in table['fields']: status, msg = 'conflict', '表结构缺少所需标识列。'
        else:
            count = sum(row[column] == value for row in table['rows'])
            status, msg = ('pass', '所选对象在对应表中唯一存在。') if count == 1 else ('conflict', '所选对象缺失或重复。')
        checks.add('D02', code, status, rid, msg, records=[rid], files=[path] if path else [])
    path = r.get('scans_tsv'); table = _load(root, path, inventory, cache, 'tsv')
    if table is None:
        checks.add('D02', 'scans', 'unassessed', rid, '未提供或未验证记录表。', records=[rid]); return
    if 'error' in table or 'filename' not in table['fields']:
        status, msg = 'conflict', '记录表缺少 filename 列。'
    else:
        try:
            names = [_relative((Path(path).parent / row['filename']).as_posix()) for row in table['rows']]
            status = 'pass' if names.count(r['path']) == 1 else 'conflict'
            msg = '核对记录表是否唯一指向当前主文件。'
        except ValueError:
            status, msg = 'conflict', '记录表含不安全或无法解析的相对路径。'
    checks.add('D02', 'scans', status, rid, msg, records=[rid], files=[path])


def _rate_equal(a, b, *, fmt=None):
    if a is None or b is None or a <= 0 or b <= 0: return False
    if math.isclose(a, b, rel_tol=1e-7, abs_tol=1e-6): return True
    # Project profile: BrainVision conversion may round microsecond intervals
    # to integers. Allow half a microsecond, not an arbitrary percent tolerance.
    return fmt == 'BrainVision' and abs(1e6 / a - 1e6 / b) <= .500001


def _record(root, r, meta, inventory, cache, checks):
    rid, channel_path = r['id'], r.get('channels_tsv')
    _identity(root, r, inventory, cache, checks)
    table = _load(root, channel_path, inventory, cache, 'tsv')
    desc, errors = {}, []
    for path in r.get('metadata_json', []):
        value = _load(root, path, inventory, cache, 'json')
        if value is None or 'error' in value: errors.append(path)
        else: desc.update(value)
    fact = {k: r[k] for k in ('id', 'path', 'subject', 'session', 'modality', 'processing', 'group')}
    fact.update(channel_names=None, units=None, rates=None, reference=None, channel_fields=None,
                header_status='readable' if meta else 'unavailable', duration_seconds=meta.get('duration_seconds') if meta else None)
    reference = desc.get('EEGReference', desc.get('iEEGReference'))
    fact['reference'] = reference if reference and str(reference).lower() not in MISSING else None
    valid = table is not None and 'error' not in table and {'name', 'type', 'units'} <= set(table.get('fields', []))
    if valid:
        rows = table['rows']; names = [row['name'] for row in rows]
        valid = bool(rows) and all(names) and len(set(names)) == len(names)
    if not valid:
        duplicate_names = sorted(k for k, n in Counter(row.get('name', '') for row in (table or {}).get('rows', [])).items() if k and n > 1)
        explanation = ('通道表名称重复：' + '、'.join(duplicate_names) + '；不能按名称唯一对应。') if duplicate_names else '通道表需有唯一非空 name，以及 type、units 列。'
        checks.add('D02', 'channel_schema', 'unassessed' if table is None else 'conflict', rid,
                   explanation, records=[rid], files=[channel_path] if channel_path else [], observed={'duplicate_names': duplicate_names})
        for code in ('channel_names', 'units', 'rates'):
            checks.add('D02', code, 'unassessed', rid, '通道表缺失或结构无效，未作比较。', records=[rid])
    else:
        fact.update(channel_names=names, channel_fields=table['fields'],
                    units={row['name']: unit(row['units']) for row in rows if row['type'].upper() not in {'MISC','TRIG','STIM'}},
                    rates={row['name']: numeric(row.get('sampling_frequency', desc.get('SamplingFrequency'))) for row in rows})
        checks.add('D02', 'channel_schema', 'pass', rid, '通道表字段与名称唯一性通过。', records=[rid], files=[channel_path])
        channels = meta.get('channels', []) if meta else []
        header_names = [ch['name'] for ch in channels]; index = {ch['name']: ch for ch in channels}
        names_status = 'unassessed' if not meta else ('conflict' if set(names) != set(header_names) or len(set(header_names)) != len(header_names)
                                                    else ('review' if names != header_names else 'pass'))
        checks.add('D02', 'channel_names', names_status, rid, '名称集合必须对应；顺序变化单独提示，按名称配对比较。', records=[rid], files=[r['path'], channel_path],
                   observed={'file_count': len(header_names) if meta else None, 'table_count': len(names),
                             'only_in_table': sorted(set(names)-set(header_names)) if meta else [],
                             'only_in_file': sorted(set(header_names)-set(names)) if meta else []})
        unit_bad, unit_missing, rate_bad, rate_missing = [], [], [], []
        for row in rows:
            name = row['name']; ch = index.get(name)
            if not ch:
                unit_missing.append(name); rate_missing.append(name); continue
            declared = unit(row['units']); stored = unit(ch.get('source_unit', ch.get('unit')))
            if declared is None and row['type'].upper() in {'MISC', 'TRIG', 'STIM'}: pass
            elif declared is None or stored is None: unit_missing.append(name)
            elif declared != stored: unit_bad.append({'channel': name, 'file': stored, 'table': declared})
            a, b = numeric(ch.get('sampling_rate_hz')), fact['rates'][name]
            if a is None or b is None: rate_missing.append(name)
            elif not _rate_equal(a, b, fmt=meta.get('format')): rate_bad.append({'channel': name, 'file_hz': a, 'table_hz': b})
        if meta and numeric(desc.get('SamplingFrequency')) is not None:
            a = numeric(desc['SamplingFrequency'])
            if any(not _rate_equal(a, numeric(ch.get('sampling_rate_hz')), fmt=meta.get('format')) for ch in channels):
                rate_bad.append({'json_hz': a, 'source': r.get('metadata_json', [])})
        for code, bad, missing in [('units', unit_bad, unit_missing), ('rates', rate_bad, rate_missing)]:
            status = 'unassessed' if not meta else 'conflict' if bad else 'review' if missing else 'pass'
            checks.add('D02', code, status, rid,
                       '按文件中的原始标定单位核对，不将软件换算后的 V 当作源单位。' if code == 'units' else '核对文件头、通道表及显式配套 JSON；BrainVision 允许半微秒采样间隔舍入。',
                       records=[rid], files=[r['path'], channel_path]+r.get('metadata_json', []), observed={'conflicts': bad, 'unknown_channels': missing})
    duration, fs = numeric(desc.get('RecordingDuration')), numeric(desc.get('SamplingFrequency'))
    if errors:
        status, msg = 'unassessed', '声明的配套 JSON 缺失或无效。'
    elif not meta or duration is None:
        status, msg = 'unassessed', '文件不可读取或配套表未声明时长。'
    else:
        header_duration = meta['duration_seconds']; rates = {numeric(c.get('sampling_rate_hz')) for c in meta['channels']}
        clock = next(iter(rates)) if len(rates) == 1 else None
        # When both clocks are declared, compare represented sample counts.
        difference = abs(duration * fs - header_duration * clock) if fs and clock else abs(duration-header_duration)
        tolerance = 1.01 if fs and clock else max(1/(clock or 1), 1e-6)
        status, msg = ('pass' if duration >= 0 and difference <= tolerance else 'conflict'), '双时钟已知时按样本数核对时长，允许一个样本的端点差。'
    checks.add('D02', 'duration', status, rid, msg, records=[rid], files=[r['path']]+r.get('metadata_json', []),
               observed={'file_seconds': fact['duration_seconds'], 'json_seconds': duration})
    _events(root, r, meta, inventory, cache, checks, fact)
    return fact


def _events(root, r, meta, inventory, cache, checks, fact):
    rid, event = r['id'], r.get('events')
    if not event:
        checks.add('D02', 'events', 'not_applicable', rid, '本检查方案未要求该记录的外部事件表。', records=[rid]); return
    table = _load(root, event['path'], inventory, cache, 'tsv')
    if table is None or not meta:
        checks.add('D02', 'events', 'unassessed', rid, '事件表未验证或记录不可读取，时间范围未评。', records=[rid], files=[event['path']]); return
    if 'error' in table:
        checks.add('D02', 'events', 'conflict', rid, '事件表结构无效。', records=[rid], files=[event['path']]); return
    required = {'onset', 'duration'} if event['mode'] == 'seconds' else {event.get('start_column', 'indStart'), event.get('stop_column', 'indStop')}
    if not required <= set(table['fields']):
        checks.add('D02', 'events', 'conflict', rid, '事件表缺少本方案要求的时间列。', records=[rid], files=[event['path']]); return
    bad, outside, missing = [], [], []
    names = set(fact.get('channel_names') or [])
    duration = meta['duration_seconds']; rates = {c['sampling_rate_hz'] for c in meta['channels']}
    fs = next(iter(rates)) if len(rates) == 1 else None
    origin = event.get('origin'); unknown_origin = event['mode'] == 'indices' and origin is None
    for i, row in enumerate(table['rows'], 2):
        if event['mode'] == 'seconds':
            start, length = numeric(row.get('onset')), numeric(row.get('duration'))
            if start is None or length is None:
                # BIDS permits n/a duration; preserve unassessed rather than invent zero.
                missing.append(i); continue
            stop = start + length
            if length < 0: bad.append(i)
            # Pre-recording and overlapping events can be legitimate BIDS events.
            if start < 0: outside.append(i)
            if start > duration or stop > duration + (1/fs if fs else 1e-6): bad.append(i)
        else:
            start, stop = numeric(row.get(event.get('start_column', 'indStart'))), numeric(row.get(event.get('stop_column', 'indStop')))
            if start is None or stop is None or fs is None: missing.append(i); continue
            if start != int(start) or stop != int(stop) or stop < start: bad.append(i)
            lower = 0 if origin is None else origin
            upper = duration * fs + (1 if origin is None else origin)
            if start < lower or stop > upper: bad.append(i)
            channel = row.get(event.get('channel_column', 'strChannelName'))
            if channel and names and channel not in names: bad.append(i)
    status = 'conflict' if bad else 'review' if outside or unknown_origin else 'unassessed' if missing else 'pass'
    checks.add('D02', 'events', status, rid,
               '检查数值、先后关系、范围及事件通道；负起点保留复核。索引起点未知时只做宽界检查，不猜测 0/1 起点。',
               records=[rid], files=[r['path'], event['path']], observed={'rows': len(table['rows']), 'invalid_rows': sorted(set(bad)),
               'pre_recording_rows': outside, 'unassessed_rows': missing, 'sample_origin': origin if event['mode'] == 'indices' else None})


def _compare(facts, target, module, policy, checks):
    ids = [r['id'] for r in facts]
    prefix = 'individual_' if module == 'D02' else 'cohort_'
    if len(facts) < 2:
        checks.add(module, 'comparison', 'unassessed', target, '只有一份记录，无法验证重复记录间一致性。', records=ids); return
    for field, key in [('channel_names', 'channels'), ('rates', 'rates'), ('units', 'units'), ('reference', 'reference')]:
        if not policy['same_' + key]:
            checks.add(module, prefix+key, 'not_applicable', target, '本比较组允许该项差异。', records=ids); continue
        values = [r[field] for r in facts]
        if any(v is None or (isinstance(v, dict) and (not v or any(x is None for x in v.values()))) for v in values):
            checks.add(module, prefix+key, 'unassessed', target, '部分记录缺少可比较字段。', records=ids); continue
        if key == 'channels': signatures = [sorted(v) for v in values]
        elif key in {'rates','units'}:
            signatures = [dict(sorted(v.items())) for v in values] if module=='D02' or policy['same_channels'] else [sorted(set(v.values())) for v in values]
        else: signatures = values
        same = all(value == signatures[0] for value in signatures[1:])
        status = 'pass' if same else 'conflict'
        if same and key == 'channels' and any(v != values[0] for v in values[1:]): status = 'review'
        checks.add(module, prefix+key, status, target, '按明确比较组核对；通道名称相同而顺序不同列为复核。', records=ids,
                   observed={'values': [{'record': r['id'], 'value': v} for r,v in zip(facts, signatures)]})


def evaluate_dataset(root, manifest, *, progress=None):
    config = validate_consistency(manifest); root = Path(root)
    notify = progress or (lambda *_: None)
    notify('D01', 'running'); metadata = {}
    inventory = inspect_package(root, manifest, metadata_sink=metadata)
    files = {f['path']: f for f in inventory['files']}
    checks = Checks()
    for row in inventory['items']:
        status = {'present':'pass', 'missing':'conflict', 'mismatch':'conflict','unsafe':'conflict','unknown':'unassessed','not_applicable':'not_applicable'}[row['status']]
        checks.add('D01','files',status,row['id'],f"{row['present_count']}/{row['expected_count']} 个应有文件已核对。",files=row.get('files', []))
    by_path = {r['path']:r['id'] for r in config['records']}
    for row in inventory['recordings']:
        status = 'pass' if row['status']=='readable' else 'conflict' if row.get('reason')=='incomplete_sample_frame' else 'unassessed'
        checks.add('D01','read',status,by_path[row['path']], '结构可读取；电压标定及配套表另行核对。' if status=='pass' else
                   '二进制末尾不是完整采样帧，未丢弃尾部数据。' if status=='conflict' else '当前读取器无法完成结构检查。', records=[by_path[row['path']]],files=[row['path']])
    notify('D01','completed'); notify('D02','running')
    cache = {}; facts = [_record(root,r,metadata.get(r['path']),files,cache,checks) for r in config['records']]
    within = defaultdict(list)
    for fact in facts: within[(fact['subject'],fact['session'],fact['group'])].append(fact)
    for key, rows in within.items():
        if len({(r['processing'], r['modality']) for r in rows}) > 1:
            checks.add('D02','group_scope','conflict',' / '.join(key),'原始/派生或不同模态混入同组，停止个体内比较。', records=[r['id'] for r in rows])
        else:
            _compare(rows,' / '.join(key),'D02',dict.fromkeys(['same_channels','same_rates','same_units','same_reference'],True),checks)
    notify('D02','completed'); notify('D03','running')
    groups=[]
    for group in config['groups']:
        rows = [f for f in facts if f['group']==group['id']]
        scopes = {(r['processing'],r['modality']) for r in rows}
        if len(scopes)>1:
            checks.add('D03','group_scope','conflict',group['id'],'原始/派生或不同模态混入同组，停止该组比较。',records=[r['id'] for r in rows])
        else:
            _compare(rows,group['id'],'D03',group,checks)
            fields = [r['channel_fields'] for r in rows]
            status = 'unassessed' if any(v is None for v in fields) else 'pass' if all(set(v)==set(fields[0]) for v in fields) else 'review'
            checks.add('D03','schema',status,group['id'],'核对同组通道表字段；可选列差异保留复核。',records=[r['id'] for r in rows])
        groups.append({'id':group['id'],'label':group.get('label',group['id']),'subjects':len({r['subject'] for r in rows}),
                       'records':len(rows),'policy':group,'record_ids':[r['id'] for r in rows],
                       'channel_counts':sorted({len(r['channel_names']) for r in rows if r['channel_names'] is not None})})
    duplicates=defaultdict(list)
    for r in config['records']:
        meta=metadata.get(r['path']); sources=meta.get('source_files',[]) if meta else []
        signal=next((s for s in sources if s.get('role')=='signal'),None)
        path=(Path(r['path']).parent/signal['name']).as_posix() if signal else r['path']
        digest=files.get(path,{}).get('sha256')
        if digest and files[path]['status']=='present':duplicates[digest].append(r['id'])
    repeated=[ids for ids in duplicates.values() if len(ids)>1]
    checks.add('D03','duplicates','review' if repeated else 'pass','dataset','相同文件内容仅作为重复线索，不据此判定受试者身份。',observed={'groups':repeated})
    # Source changes during the pass invalidate the result; never label a mixed snapshot complete.
    for path in cache:
        source=_safe_file(root,path)
        if source is None or not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest()!=files[path]['sha256']:
            raise ValueError('检查过程中配套表发生变化，请保留来源并重新检查。')
    counts=Counter(c['status'] for c in checks.rows)
    subjects=[]
    for subject in sorted({r['subject'] for r in facts}):
        ids={r['id'] for r in facts if r['subject']==subject}
        relevant=[c for c in checks.rows if c['module']=='D02' and ids.intersection(c['records'])]
        subjects.append({'id':subject,'records':len(ids),'sessions':len({r['session'] for r in facts if r['subject']==subject}),
                         'status_counts':dict(Counter(c['status'] for c in relevant))})
    result={'schema_version':'dataset-qc-result/1','rule_version':RULE_VERSION,'checked_at':inventory['checked_at'],
            'scope':manifest['scope'],'source':manifest.get('source',{}),'inventory':inventory,'checks':checks.rows,
            'records':facts,'subjects':subjects,'groups':groups,'summary':{'subjects':len(subjects),'records':len(facts),
            'expected_files':inventory['summary']['expected_files'],'present_files':inventory['summary']['present_files'],
            'status_counts':dict(counts),'groups':len(groups)},'status':'needs_attention' if any(counts[s] for s in ('conflict','review','unassessed')) else 'checked',
            'modules':[{'id':mid,'status':'completed','counts':dict(Counter(c['status'] for c in checks.rows if c['module']==mid))} for mid in ('D01','D02','D03')],
            'limits':['真实身份核验未执行','信号质量评分未执行','不是完整 BIDS 合规校验','本地报告，未执行脱敏审查']}
    notify('D03','completed')
    return result
