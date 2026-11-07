import copy
import importlib.util
from pathlib import Path
import unittest
import xml.etree.ElementTree as E

spec = importlib.util.spec_from_file_location('home_route', Path(__file__).parents[1] / 'tools/home-route.py')
route = importlib.util.module_from_spec(spec)
spec.loader.exec_module(route)


class HomeRouteTest(unittest.TestCase):
    def setUp(self):
        self.original = dict(route.IDENTITY, tables={
            'managed_app': [[route.STOCK, 'partial', None]] + [['fixture.' + str(i), None, None] for i in range(27)],
            'key_filter': [list(route.HOME), list(route.SOURCE)] + [
                ['fixture.' + str(i), 'key' + str(i), None, None, '', 'launch', 'package:fixture', None] for i in range(68)],
            'task_filter': [],
        })
        self.current = copy.deepcopy(self.original)
        self.current['tables']['managed_app'].append([route.OWN, None, None])

    def test_apply_changes_only_short_home(self):
        self.current['tables']['key_filter'][0] = list(route.FOUR)
        route.compare(self.original, self.current, 'apply')
        self.current['tables']['key_filter'][1][-1] = 'wrong_source_entry'
        with self.assertRaisesRegex(ValueError, 'key_filter'):
            route.compare(self.original, self.current, 'apply')

    def test_restore_requires_original_home(self):
        route.compare(self.original, self.current, 'restore')
        self.current['tables']['key_filter'][0] = list(route.FOUR)
        with self.assertRaises(ValueError):
            route.compare(self.original, self.current, 'restore')

    def test_duplicate_or_missing_rule_is_rejected(self):
        for edit in ('duplicate', 'remove'):
            current = copy.deepcopy(self.current)
            if edit == 'duplicate':
                current['tables']['key_filter'].append(list(route.HOME))
            else:
                current['tables']['key_filter'].pop()
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                route.compare(self.original, current, 'restore')

    def test_other_firmware_is_rejected(self):
        self.original['firmware'] = 'T-NKMDEUC-2743.0'
        with self.assertRaisesRegex(ValueError, 'not been tested'):
            route.baseline(self.original)

    def test_parallel_home_or_task_rule_is_rejected(self):
        for table, row in [('key_filter', list(route.FOUR)),
                           ('task_filter', [route.OWN, 'app', 'stopped', 'launch', 'app', 'Q70Home001.Home', None])]:
            current = copy.deepcopy(self.current)
            row[0] = route.OWN
            current['tables'][table].append(row)
            with self.subTest(table=table), self.assertRaises(ValueError):
                route.compare(self.original, current, 'restore')

    def test_modified_stock_metadata_is_rejected(self):
        self.original['tables']['managed_app'][0][1] = 'fullscreen'
        with self.assertRaises(ValueError):
            route.baseline(self.original)

    def test_each_package_has_one_context_and_preserves_source(self):
        ns = {'p': route.NS}
        for stage in route.VERSIONS:
            root = E.fromstring(route.manifest(stage))
            contexts = root.findall('p:app-context', ns)
            self.assertEqual(len(contexts), 1)
            if stage == 'register':
                self.assertEqual(contexts[0].attrib, {'appid': route.OWN})
                self.assertEqual(len(contexts[0]), 0)
            else:
                rules = contexts[0].findall('p:app-context-rule', ns)
                self.assertEqual(len(rules), 2)
                self.assertEqual(rules[1].find('p:source', ns).text, 'XF86Display')
                self.assertEqual(rules[1].find('p:target', ns).text, route.STOCK)
                self.assertEqual(rules[1].find('p:target', ns).get('args'), 'entry_point:source_key')
                self.assertIsNone(rules[0].find('p:source', ns).get('override'))


if __name__ == '__main__':
    unittest.main()
