"""M01: Source identity, companion manifest and structural inspection."""
from pathlib import Path

from ..annotations import file_sha256

from .context import ModuleContext


def run(context: ModuleContext) -> dict:
    """Execute this module; return its result row and save its named evidence."""
    record = context.record
    result = context.result
    row = context.row
    source = context.source
    source_context = context.source_context
    state = context.state
    save = context.save
    if not source.is_file():
        raise ValueError("This workbench requires an existing registered source file")
    digest = source_context['sha256'] if source_context else file_sha256(source)
    result["source_sha256"] = digest
    if record.get("expected_sha256") and digest != record["expected_sha256"]:
        raise ValueError("Source SHA-256 disagrees with the registered input")
    from ..readers import open_reader
    from ..source_selection import reader_kwargs
    state["reader"] = source_context['reader'] if source_context else open_reader(source, str(record["id"]), **reader_kwargs(record.get('metadata', {})))
    state['reader'].assert_unchanged()
    state["description"] = state["reader"].describe()
    manifest = state['description']['source_files']
    if record.get('expected_source_files') is not None:
        expected = {str(Path(item['path']).resolve()): item['sha256'] for item in record['expected_source_files']}
        observed = {item['path']: item['sha256'] for item in manifest}
        if len(expected) != len(record['expected_source_files']) or expected != observed:
            raise ValueError('Source package files/hashes disagree with the registered input')
    elif record.get('metadata', {}).get('source_files'):
        expected = {item['name']: item['sha256'] for item in record['metadata']['source_files']}
        observed = {item['name']: item['sha256'] for item in manifest}
        if expected != observed:
            raise ValueError('Source package files/hashes disagree with the inspected metadata')
    result['source_files'] = [{k: v for k, v in item.items() if k != 'path'} for item in manifest]
    if state['description']['format'] == 'NWB':
        actual = state['reader'].metadata()
        result['source_signal'] = {key: actual.get(key) for key in
                                   ('selected_stream_id', 'nwb', 'capabilities', 'acquisition', 'clock')}
    if state['description']['format'] in {'EDF', 'BDF'}:
        if source_context and 'header' in source_context:
            header = source_context['header']
        else:
            from brainelecqc.eeg.header_qc import inspect_input_header
            header = inspect_input_header(source, expected_sha256=digest)
            if source_context is not None:
                source_context['header'] = header
    else:
        header = {'status': 'pass', 'format': state['description']['format'],
                  'structural_checks': 'format reader decoded metadata and validated companion references',
                  'adc_endpoint_calibration': 'unavailable', 'scientific_validity': 'not_assessed'}
    # Teacher header auto-points are not propagated into platform scoring.
    save("M01_input.json", {"source_sha256": digest, "header": header,
                            "streams": state["description"]["streams"],
                            "reader_version": state["description"]["reader_version"],
                            'reader_id': state['description']['reader_id'],
                            'backend_version': state['description'].get('backend_version'),
                            'source_files': result['source_files'], 'clock': state['description']['clock'],
                            'annotations': state['description']['annotations'],
                            "warnings": state["description"]["warnings"],
                            **({'source_signal': result['source_signal']} if 'source_signal' in result else {})})
    row["summary"] = {"source_sha256": digest, "stream_count": len(state["description"]["streams"]),
                      "header_signal_count": state["description"]["header_channel_count"],
                      "header_status": header["status"],
                      "reader_warnings": state["description"]["warnings"]}
    if state["description"]["warnings"] or header["status"] != "pass":
        row.update(status="partial", reason="可读取，但存在需要复核的格式、时间或结构警告")

    return row
