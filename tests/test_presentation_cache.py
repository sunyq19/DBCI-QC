"""Display reuse must never change evidence or survive a source revision."""
import json
from pathlib import Path
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/workbench'))
from presentation_cache import cached, stamps


class PresentationCacheTests(unittest.TestCase):
    def test_disk_hit_and_source_revision(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); source=root/'source.json';source.write_text('{"x":1}')
            build=Mock(return_value=b'<html>first</html>')
            first=cached(root,'gallery',stamps([source]),build)
            self.assertEqual(cached(root,'gallery',stamps([source]),lambda:self.fail('must reuse disk')),first)
            source.write_text('{"x":222}')
            self.assertEqual(cached(root,'gallery',stamps([source]),lambda:b'new'),b'new')
            self.assertEqual(source.read_text(),'{"x":222}')
            self.assertEqual(cached(root,'other-window',stamps([source]),lambda:b'other'),b'other')

    def test_failed_waveform_is_not_cached_as_success(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(cached(Path(td),'focus:7',[1],lambda:None))
            self.assertEqual(cached(Path(td),'focus:7',[1],lambda:b'PNG'),b'PNG')

    def test_corrupt_cache_is_rebuilt(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);cached(root,'key',[1],lambda:b'old')
            path=next((root/'presentation-cache').glob('*.json'));path.write_text('{broken')
            self.assertEqual(cached(root,'key',[1],lambda:b'rebuilt'),b'rebuilt')

    def test_slow_gallery_does_not_block_a_waveform_cache(self):
        with tempfile.TemporaryDirectory() as td, ThreadPoolExecutor(2) as pool:
            started=threading.Event();release=threading.Event();root=Path(td)
            def slow():
                started.set();release.wait(3);return b'gallery'
            future=pool.submit(cached,root,'gallery',[1],slow)
            self.assertTrue(started.wait(1))
            try:
                fast=pool.submit(cached,root,'focus:7',[1],lambda:b'PNG')
                self.assertEqual(fast.result(timeout=1),b'PNG')
            finally:
                release.set()
            self.assertEqual(future.result(timeout=1),b'gallery')


if __name__=='__main__':unittest.main()
