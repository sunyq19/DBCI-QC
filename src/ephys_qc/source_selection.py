"""Frozen NWB object selection, independent of waveform-window selection."""


def reader_kwargs(metadata):
    if metadata.get('format') != 'NWB':
        return {}
    selected = metadata.get('selected_stream_id')
    if selected is None:
        return {}
    if not isinstance(selected, str) or not selected.startswith('/'):
        raise ValueError('NWB信号选择必须是文件中列出的对象路径。')
    return {'stream_id': selected}


def require_selected_voltage(metadata):
    if metadata.get('format') != 'NWB':
        return
    if not metadata.get('selected_stream_id') or not metadata.get('channels'):
        raise ValueError('请先选择一个可读取的NWB连续电压信号；Units不是连续波形。')
    capabilities = metadata.get('capabilities', {})
    required = ('continuous_voltage', 'regular_sampling', 'voltage_calibration_verified', 'electrode_mapping_verified')
    if any(capabilities.get(key) is not True for key in required):
        raise ValueError('NWB所选信号尚未通过连续电压、规则时钟、单位和电极映射核验。')


def validate_frozen_stream(metadata, selection):
    require_selected_voltage(metadata)
    if metadata.get('format') == 'NWB':
        selected = metadata['selected_stream_id']
        if selection.get('stream_id', selected) != selected:
            raise ValueError('NWB信号已随记录冻结；切换信号须重新选择和确认记录。')
        selection['stream_id'] = selected
