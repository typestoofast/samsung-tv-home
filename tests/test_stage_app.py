import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('stage_app', ROOT / 'tools/stage-app.py')
stage_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage_app)


class StageAppTest(unittest.TestCase):
    def records(self):
        return [{'EditName': name, 'SourceType': port}
                for name, port in [('Apple TV', 13), ('Switch 2', 14), ('Steam', 15)]]

    def test_normal_build_has_bindings_without_timing_or_private_work_files(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'build'
            stage_app.stage(self.records(), out)
            self.assertNotIn('timing.js', (out / 'index.html').read_text())
            self.assertFalse((out / 'timing.js').exists())
            self.assertEqual(len(list((out / 'assets').iterdir())), 4)
            self.assertIn('"apple":{"port":1', (out / 'input-map.js').read_text())
            self.assertEqual({p.name for p in out.iterdir()}, set(stage_app.FILES) | {'assets', 'input-map.js'})

    def test_diagnostics_are_explicit_and_do_not_modify_source(self):
        original = (ROOT / 'app/index.html').read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'build'
            stage_app.stage(self.records(), out, diagnostics=True)
            html = (out / 'index.html').read_text()
            self.assertLess(html.index('timing-config.js'), html.index('timing.js'))
            self.assertLess(html.index('timing.js'), html.index('style.css'))
            self.assertIn('FourTimingEnabled = true', (out / 'timing-config.js').read_text())
            self.assertEqual(original, (ROOT / 'app/index.html').read_bytes())

    def test_bad_bindings_and_existing_output_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'build'
            with self.assertRaises(ValueError):
                stage_app.stage([], out)
            self.assertFalse(out.exists())
            out.mkdir()
            with self.assertRaises(FileExistsError):
                stage_app.stage(self.records(), out)


if __name__ == '__main__':
    unittest.main()
