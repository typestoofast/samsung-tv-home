import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('stage_app', ROOT / 'tools/stage-app.py')
stage_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage_app)


class StageAppTest(unittest.TestCase):
    def plan(self):
        return {'schemaVersion': 1, 'unresolved': [], 'shortcuts': [
            {'key': 'hdmi-4', 'label': 'Apple TV', 'kind': 'hdmi', 'port': 4,
             'sourceName': 'Apple TV', 'logo': 'appletv'},
            {'key': 'app-0', 'label': 'Stremio', 'kind': 'app',
             'appId': 'other.installation', 'logo': 'stremio'},
        ]}

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

    def test_generated_home_replaces_owner_devices_and_keeps_logo_attribution(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'build'
            stage_app.stage_home(self.plan(), Path(directory), out)
            page = (out / 'index.html').read_text()
            self.assertEqual(page.count('class="destination '), 2)
            self.assertIn('data-port="4"', page)
            self.assertIn('data-app-id="other.installation"', page)
            self.assertNotIn('IkWsFHtOY9', page)
            self.assertNotIn('assets/steam.svg', page)
            self.assertTrue((out / 'assets/hdmi-4.svg').is_file())
            self.assertIn('stremio-brand', (out / 'assets/SOURCES.json').read_text())
            self.assertTrue((out / 'THIRD_PARTY_NOTICES.md').is_file())

    def test_unresolved_or_duplicate_routes_never_create_a_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'build'
            for issue in ('unresolved', 'port', 'key', 'app'):
                with self.subTest(issue=issue):
                    plan = self.plan()
                    if issue == 'unresolved':
                        plan['unresolved'] = [{'code': 'missing_name'}]
                    elif issue == 'port':
                        plan['shortcuts'][0]['port'] = True
                    elif issue == 'key':
                        plan['shortcuts'][1]['key'] = 'hdmi-4'
                    else:
                        plan['shortcuts'][1]['appId'] = '<script>'
                    with self.assertRaises(ValueError):
                        stage_app.stage_home(plan, Path(directory), out)
                    self.assertFalse(out.exists())

    def test_custom_local_logo_and_html_labels_are_packaged_without_remote_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'device.png').write_bytes((ROOT / 'app/icon.png').read_bytes())
            plan = self.plan()
            plan['shortcuts'][0].update(label='Console "A" <HDMI>', sourceName='Console "A" <HDMI>',
                logo={'file': 'device.png', 'source': 'https://example.com/brand', 'license': 'Test asset'})
            out = root / 'build'
            stage_app.stage_home(plan, root, out)
            page = (out / 'index.html').read_text()
            self.assertIn('aria-label="Console &quot;A&quot; &lt;HDMI&gt;"', page)
            self.assertNotIn('<HDMI>', page)
            self.assertIn('src="assets/hdmi-4.png"', page)
            self.assertNotIn('https://example.com', page)
            self.assertIn('https://example.com/brand', (out / 'assets/SOURCES.json').read_text())

    def test_custom_artwork_requires_local_png_and_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'device.png').write_bytes((ROOT / 'app/icon.png').read_bytes())
            for changes in ({'file': '../device.png'}, {'file': '/tmp/device.png'},
                            {'source': 'http://example.com'}, {'license': ''}, {'file': 'missing.svg'}):
                with self.subTest(changes=changes):
                    plan = self.plan()
                    plan['shortcuts'][0]['logo'] = dict(
                        {'file': 'device.png', 'source': 'https://example.com/brand', 'license': 'Test'}, **changes)
                    with self.assertRaises(ValueError):
                        stage_app.stage_home(plan, root, root / 'build')
                    self.assertFalse((root / 'build').exists())

    def test_more_than_four_shortcuts_use_two_rows_and_duplicate_logos_get_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = {'schemaVersion': 1, 'unresolved': [], 'shortcuts': [
                {'key': 'app-' + str(i), 'label': 'Player ' + str(i), 'kind': 'app',
                 'appId': 'test.player' + str(i), 'logo': 'steam'} for i in range(6)]}
            out = root / 'build'
            stage_app.stage_home(plan, root, out, diagnostics=True)
            page = (out / 'index.html').read_text()
            self.assertIn('class="destinations multiline"', page)
            self.assertEqual(page.count('class="destination-label"'), 6)
            self.assertIn('timing-config.js', page)

    def test_invalid_png_pixels_and_ambiguous_source_names_block_staging(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = self.plan()
            plan['shortcuts'][1] = dict(plan['shortcuts'][0], key='hdmi-2', port=2, label='Other Apple TV')
            with self.assertRaisesRegex(ValueError, 'Identical HDMI'):
                stage_app.stage_home(plan, root, root / 'build')
            good = (ROOT / 'app/icon.png').read_bytes()
            for data in (good[:33], good[:-12], good[:50] + b'broken' + good[56:]):
                (root / 'broken.png').write_bytes(data)
                plan = self.plan()
                plan['shortcuts'][0]['logo'] = {'file': 'broken.png', 'source': 'https://example.com', 'license': 'Test'}
                with self.assertRaises(ValueError):
                    stage_app.stage_home(plan, root, root / 'build')
                self.assertFalse((root / 'build').exists())


if __name__ == '__main__':
    unittest.main()
