"""Explicit child selection; absent core_methods retains legacy module recipes."""

CHECK_MODULES = frozenset({'M03', 'M04', 'M05', 'M06', 'M07'})


def selected(config, method_id):
    core = config.get('method_config', {}).get('core_methods')
    return core is None or method_id in core


def validate(config, catalog):
    methods = config.get('method_config', {})
    if 'core_methods' not in methods:
        return None
    core = methods['core_methods']
    known = {m['id']: m for m in catalog if m['module_id'] in CHECK_MODULES
             and not m.get('optional_extension') and m['implementation'] == 'available'}
    if not isinstance(core, list) or any(not isinstance(x, str) or x not in known for x in core):
        raise ValueError('core_methods只能选择当前模态已接入的基础检查。')
    methods['core_methods'] = sorted(set(core))
    return {known[x]['module_id'] for x in core}


def core_for_module(config, catalog, module_id):
    return [m['id'] for m in catalog if m['module_id'] == module_id
            and not m.get('optional_extension') and m['implementation'] == 'available'
            and selected(config, m['id'])]


def score_selected(spec, config, modality):
    """Score aliases resolve to the actual selected computation, not its parent."""
    if spec['reducer'] in {'ieeg_numeric', 'np_numeric', 'np_constant'}:
        prefix = 'neuropixels' if modality == 'extracellular' else modality
        return selected(config, prefix + '_continuity')
    if spec['reducer'] in {'core', 'prep'}:
        return selected(config, spec['method_id'])
    return True
