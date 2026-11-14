"""Check the export uses runtime definitions, including a changed default weight."""
import sys, importlib, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path('../..').resolve()/'src'))
from ephys_qc import flow_contracts,ieeg_scoring,project_scoring
from ephys_qc.method_registry import methods
class SourceTests(unittest.TestCase):
 def test_exported_weight_changes_with_runtime(self):
  original=ieeg_scoring.default_config
  def changed(mode):
   value=original(mode);value['weights']={ieeg_scoring.NUMERIC:40,ieeg_scoring.STABILITY:60};return value
  try:
   with patch.object(ieeg_scoring,'default_config',changed):
    importlib.reload(flow_contracts)
    method=next(m for m in methods('ecog') if m['id']=='ecog_continuity')
    self.assertIn('40%',flow_contracts.method_entry(method,'ecog')['weight'])
  finally:importlib.reload(flow_contracts)
 def test_registry_capabilities_are_preserved(self):
  for mode,scope in flow_contracts.MODES.items():
   for method in methods(mode):
    result=flow_contracts.method_entry(method,scope)
    self.assertEqual(result['canOutputScore'],bool(method.get('scoring',{}).get('outputs')),method['id'])
 def test_new_methods_explain_denominators_and_do_not_enable_scores(self):
  eeg={m['id']:m for m in methods('scalp_eeg')}
  ransac=flow_contracts.method_entry(eeg['pyprep_ransac'],'eeg')
  local=flow_contracts.method_entry(eeg['autoreject_epochs'],'eeg')
  self.assertIn('候选通道数 / 实际完成预测的通道数',ransac['rule'])
  self.assertIn('超阈值通道片段数 / 实际受检通道片段数',local['rule'])
  for row in [ransac,local]:
   self.assertEqual(row['role'],'optional');self.assertIn('默认0%',row['weight'])
  for key in ['ica_iclabel','nwb_inspector']:
   row=flow_contracts.method_entry(eeg[key],'eeg')
   self.assertFalse(row['canOutputScore']);self.assertIn('没有质量分',row['limited'])
if __name__=='__main__':unittest.main()
