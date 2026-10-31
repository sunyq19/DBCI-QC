"""Presentation hierarchy shared by toolkit clients; never selects algorithms."""
from .modalities import DESCRIPTIVE, route


def workflow(modality='scalp_eeg'):
    """Return a fresh hierarchy. Runtime dependencies remain in build_plan()."""
    route(modality)  # Reject an unknown route instead of borrowing EEG defaults.
    return {
        'schema_version': 'qc-workflow/1.0',
        'groups': [
            {'id': 'intake', 'label': '读取与确认', 'module_ids': ['M01', 'M02']},
            {'id': 'checks', 'label': '质量检查', 'module_ids': ['M03', 'M04', 'M05', 'M06', 'M07']},
            {'id': 'report', 'label': '结果与报告', 'module_ids': ['M08', 'M09']},
        ],
        'method_groups': [
            {'id': 'with_module', 'label': '基础方法'},
            {'id': 'conditional', 'label': '按条件启用'},
            {'id': 'manual_extension', 'label': '可选增强'},
        ],
        'default_selected_modules': ['M03', 'M04', 'M05'] if modality in DESCRIPTIVE
                                    else ['M03', 'M04', 'M05', 'M06', 'M07'],
    }
