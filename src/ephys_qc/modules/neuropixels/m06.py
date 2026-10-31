"""M06 neuropixels: no artifact classification is implemented."""
def run(context):
    context.row.update(status='skipped', reason='neuropixels伪迹分类尚未接入；不迁移头皮阈值。')
    return context.row
