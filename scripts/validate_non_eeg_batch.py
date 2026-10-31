"""Replay a documented local sample batch through the unchanged workbench API.

The configuration is local and contains cases with upload/source paths, explicit
modality and channel selection. It may include expected reader rejections.
This checks engineering coverage, not clinical accuracy. No source edits or
algorithm tuning are performed. Run with the project's scientific Python.
"""
import argparse
import hashlib
import html
import http.client
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback
from urllib.parse import quote, urlsplit
import urllib.error
import urllib.request

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))


def digest(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def save(p, x):
    p.write_text(json.dumps(x, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def independent_readback(case):
    """Compare bounded native windows to direct binary arithmetic, not a second wrapper."""
    import numpy as np
    from ephys_qc.readers import open_reader
    p = Path(case['source_path'])
    reader = open_reader(p, 'independent-check')
    try:
        desc = reader.describe()
        indices = case['eeg_indices']
        stream = next(s for s in desc['streams'] if set(indices) <= {c['source_index'] for c in s['channels']})
        segment = stream['segments'][0]
        by_index = {c['source_index']: c['channel_id'] for c in stream['channels']}
        selected = list(reversed(indices))  # Also exercise non-default channel order.
        channel_ids = [by_index[i] for i in selected]
        first, stop = segment['start_sample'], segment['stop_sample']
        starts = sorted({first, (first + stop) // 2, stop - 32})
        checks = []
        if p.suffix.lower() == '.edf':
            with p.open('rb') as f:
                head = f.read(256)
                n = int(head[252:256]); header_size = int(head[184:192])
                block = f.read(256 * n)
            def fields(offset, width):
                return [block[offset*n+i*width:offset*n+(i+1)*width].decode('latin1').strip() for i in range(n)]
            per_record = np.array(list(map(int, fields(216, 8))))
            offsets = np.r_[0, np.cumsum(per_record[:-1])]
            record_bytes = int(2 * per_record.sum())
            pmin, pmax = np.array(list(map(float, fields(104, 8)))), np.array(list(map(float, fields(112, 8))))
            dmin, dmax = np.array(list(map(float, fields(120, 8)))), np.array(list(map(float, fields(128, 8))))
            units = fields(96, 8)
            unit_scale = {'V': 1., 'mV': 1e-3, 'uV': 1e-6, 'µV': 1e-6, 'nV': 1e-9}
            def direct(start, end):
                output = []
                with p.open('rb') as f:
                    for i in selected:
                        integers = []
                        for sample in range(start, end):
                            rec, within = divmod(sample, int(per_record[i]))
                            f.seek(header_size + rec * record_bytes + 2 * (int(offsets[i]) + within))
                            integers.append(int.from_bytes(f.read(2), 'little', signed=True))
                        gain = (pmax[i] - pmin[i]) / (dmax[i] - dmin[i])
                        output.append((np.array(integers, dtype=float) * gain + pmin[i] - dmin[i] * gain) * unit_scale[units[i]])
                return np.array(output)
        else:
            meta = {k.removeprefix('~'): v for k, v in (line.split('=', 1) for line in p.with_suffix('.meta').read_text().splitlines())}
            assert meta['imDatPrb_type'] == '0', 'Independent reference here is explicitly NP1 only'
            imro = [list(map(int, x.split())) for x in re.findall(r'\(([^()]*)\)', meta['imroTbl'])[1:]]
            gains = {row[0]: row[4 if '.lf.' in p.name else 3] for row in imro}
            origin = int(meta['firstSample'])
            def direct(start, end):
                raw = np.memmap(p, mode='r', dtype='<i2').reshape(-1, int(meta['nSavedChans']))
                integers = np.array(raw[start-origin:end-origin, selected].T, dtype=float)
                return integers * np.array([float(meta['imAiRangeMax']) / int(meta['imMaxInt']) / gains[i] for i in selected])[:, None]
        for start in starts:
            expected = direct(start, start + 32)
            actual = reader.read_window(stream['stream_id'], segment['segment_id'], channel_ids, start, start + 32, 'physical')
            error = float(np.max(np.abs(actual - expected)))
            assert np.allclose(actual, expected, rtol=1e-12, atol=1e-15), error
            checks.append({'start_sample': start, 'sample_count': 32, 'channel_count': len(selected), 'max_abs_error_volts': error})
        reader.assert_unchanged(hashes=True)
        return {'passed': True, 'channel_order': 'reverse_source_selection', 'checks': checks,
                'scope': 'three bounded windows, not every value or amplifier calibration'}
    finally:
        reader.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--base', default='http://127.0.0.1:8769')
    args = p.parse_args()
    parsed = urlsplit(args.base)
    assert parsed.scheme == 'http' and parsed.hostname in {'127.0.0.1', 'localhost'}
    assert not args.output.exists(), 'Use a new evidence directory'
    args.output.mkdir(parents=True)
    cases = json.loads(args.config.read_text())['cases']
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def call(path, body=None, raw=False):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(args.base + path, data=data, headers={'Content-Type': 'application/json'})
        with opener.open(request, timeout=120) as response:
            content = response.read()
        return content if raw else json.loads(content)

    def upload(path):
        conn = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=180)
        try:
            conn.putrequest('POST', '/api/v1/intakes')
            conn.putheader('Content-Type', 'application/octet-stream')
            conn.putheader('X-Filename', quote(path.name))
            conn.putheader('Content-Length', str(path.stat().st_size))
            conn.endheaders()
            with path.open('rb') as f:
                for b in iter(lambda: f.read(1024 * 1024), b''):
                    conn.send(b)
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    summary = {'date': '2026-10-31', 'baseline_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
               'health': call('/api/v1/health'), 'scientific_accuracy_validated': False, 'cases': []}
    for case in cases:
        folder = args.output / case['id']
        folder.mkdir()
        row = {'id': case['id'], 'label': case['label'], 'modality': case['modality'],
               'expected': case['expected'], 'sample_folder': case['sample_folder'],
               'source_url': case['source_url'], 'selection_basis': case['selection_basis'],
               'selected_indices': case['eeg_indices'], 'notes': case['notes']}
        source, package = Path(case['source_path']), Path(case['upload'])
        hashes = {str(x): digest(x) for x in {source, package}}
        assert hashes[str(source)] == case['source_sha256']
        save(folder / 'case.json', case)
        print('START', case['id'], flush=True)
        try:
            code, intake = upload(package)
            row['upload_http_status'] = code
            save(folder / 'intake.json', intake)
            if case['expected'] == 'reader_rejection':
                assert code == 400 and 'EDF+D' in json.dumps(intake, ensure_ascii=False), (code, intake)
                row.update(outcome='unsupported', error=intake, report_created=False)
            else:
                assert code in {200, 201} and intake['status'] == 'needs_confirmation', (code, intake)
                assert intake['sha256'] == hashes[str(package)]
                row['automatic_suggestions'] = intake['suggestions']
                row['independent_readback'] = independent_readback(case)
                save(folder / 'independent-readback.json', row['independent_readback'])
                body = {'confirmed': True, 'modality': case['modality'], 'reference_scheme': 'unknown',
                        'eeg_indices': case['eeg_indices'], 'reference_indices': {},
                        'context_tags': {'disease': case['disease'], 'age_group': 'unknown', 'task': case['task']},
                        'label': case['label'] + ' · 20261031扩展验证', 'source_note': case['source_note']}
                record = call('/api/v1/intakes/' + intake['id'] + '/confirm', body)['input']
                save(folder / 'confirmed-record.json', record)
                request = {'input_id': record['id'], 'qc_config': {'scope': 'recording', 'recording_options': {'window_seconds': case['window_seconds']}}}
                rec = call('/api/v1/recommend', request)
                save(folder / 'recommendation.json', rec)
                assert rec['can_apply'], rec
                request.update(selected_modules=rec['selected_modules'], qc_config=rec['qc_config'])
                plan = call('/api/v1/plan', request)
                save(folder / 'plan.json', plan)
                assert plan['plan_id'] == rec['plan_id']
                job = call('/api/v1/jobs', {**request, 'plan_id': plan['plan_id']})
                row.update(job_id=job['id'], input_id=record['id'])
                save(folder / 'job-submitted.json', job)
                print('JOB', case['id'], job['id'], flush=True)
                deadline = time.monotonic() + 900
                while job['status'] in {'queued', 'running'}:
                    assert time.monotonic() < deadline, 'Job exceeded 900 seconds; inspect saved job id'
                    time.sleep(1)
                    job = call('/api/v1/jobs/' + job['id'])
                save(folder / 'job-final.json', job)
                assert job['status'] == 'completed', job
                result = call('/api/v1/jobs/' + job['id'] + '/result')
                save(folder / 'result.json', result)
                assert result['source_sha256'] == intake['source_sha256']
                assert result['score']['value'] is None
                assert all(x['status'] != 'failed' for x in result['modules'])
                assert result['coverage']['execution_percent'] == 100
                assert result['plan_id'] == plan['plan_id']
                assert plan['qc_config']['selection']['eeg_indices'] == case['eeg_indices']
                report = call('/api/v1/jobs/' + job['id'] + '/report', raw=True)
                assert b'<html' in report and len(report) > 1000
                # File-opened report navigation must still reach the local API.
                # This is a linked local copy, not an offline evidence archive.
                local_report = re.sub(r'((?:href|src)=["\x27])/(?!/)',
                                      lambda m: m[1] + args.base.rstrip('/') + '/', report.decode('utf-8'))
                (folder / 'report.html').write_text(local_report)
                (Path(case['sample_folder']) / '质控报告.html').write_text(local_report)
                row.update(outcome='reported', report_created=True, report_url=args.base + '/api/v1/jobs/' + job['id'] + '/report',
                           execution_status=result['status'], analysis_profile=result['analysis_profile'],
                           selected_channel_count=len(case['eeg_indices']), coverage=result['coverage'],
                           continuity_evidence=[{'window_id': w['id'], **m['summary']['candidate_evidence']}
                                                for w in result.get('windows', []) for m in w['modules']
                                                if m['id'] == 'M03' and m.get('summary', {}).get('candidate_evidence')],
                           module_states={m['id']: {'status': m['status'], 'reason': m.get('reason', '')} for m in result['modules']})
        except Exception as exc:
            row.update(outcome='unexpected_failure', error=f'{type(exc).__name__}: {exc}')
            (folder / 'error.txt').write_text(traceback.format_exc())
        row['source_unchanged'] = all(digest(Path(path)) == checksum for path, checksum in hashes.items())
        assert row['source_unchanged']
        save(folder / 'acceptance.json', row)
        summary['cases'].append(row)
        save(args.output / 'acceptance.json', summary)
        text = '本次测试：2026-10-31\n代码版本：' + summary['baseline_commit'] + '\n'
        if row['outcome'] == 'reported':
            text += f"结果：已生成报告，覆盖本地文件全程；分析 {row['selected_channel_count']} 道。\n报告：质控报告.html\n在线报告：{row['report_url']}\n"
            text += '报告中的逐窗详情链接需要本机质控台运行。\n'
            limited = sum(x.get('omitted_interval_count', 0) for x in row.get('continuity_evidence', []))
            if limited:
                text += f'连续性模块已扫描全部样本；候选明细达到每窗存储上限，有 {limited} 个区间未保存位置，完整计数仍在报告中。这些候选不等于伪迹。\n'
        else:
            text += '结果：当前不能生成质控报告。\n原因：' + json.dumps(row.get('error'), ensure_ascii=False) + '\n'
        text += '\n' + case['notes'] + '\n\n此处只验证读取、选择、推荐及报告流程；不证明临床准确率。总分未校准。\n'
        (Path(case['sample_folder']) / '本次测试.txt').write_text(text)
        print('DONE', case['id'], row['outcome'], flush=True)
    summary['reported'] = sum(x['outcome'] == 'reported' for x in summary['cases'])
    summary['unsupported'] = sum(x['outcome'] == 'unsupported' for x in summary['cases'])
    summary['unexpected_failures'] = sum(x['outcome'] == 'unexpected_failure' for x in summary['cases'])
    save(args.output / 'acceptance.json', summary)
    esc = lambda x: html.escape(str(x), quote=True)
    rows = ''.join('<tr><td>' + esc(x['label']) + '</td><td>' + esc(x['modality']) + '</td><td>' + esc(x['outcome']) + '</td><td>' +
                   (f'<a href="{esc(x["id"])}/report.html">报告</a>' if x.get('report_created') else 'EDF+D 尚不支持' if x['outcome'] == 'unsupported' else esc(x.get('error'))) + '</td></tr>' for x in summary['cases'])
    (args.output / 'index.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>非EEG样例验证</title><style>body{font:16px/1.7 system-ui;margin:48px;color:#17354c}table{border-collapse:collapse}td,th{padding:12px 24px;border-bottom:1px solid #d6e3ee;text-align:left}a{color:#1769aa}</style><h1>非 EEG 样例验证 · 2026-10-31</h1><p>现有模块，未修改算法或阈值。通道与模态依据来源人工核对；报告完成不代表临床质量合格。</p><p>报告 ' + str(summary['reported']) + ' 份；读取不支持 ' + str(summary['unsupported']) + ' 份；其他失败 ' + str(summary['unexpected_failures']) + ' 份。</p><table><tr><th>样例</th><th>模态</th><th>结果</th><th>查看</th></tr>' + rows + '</table><p><a href="acceptance.json">完整核对记录</a></p></html>')
    print(json.dumps({k: summary[k] for k in ['reported', 'unsupported', 'unexpected_failures']}, ensure_ascii=False), flush=True)
    if summary['unexpected_failures']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
