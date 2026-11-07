#!/usr/bin/env python3
"""Build unsigned Q70T Home packages or compare private routing snapshots offline."""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as E
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NS = 'http://tizen.org/ns/packages'
OWN = 'org.four.home.route'
STOCK = 'com.samsung.tv.csfs'
TABLES = ('managed_app', 'key_filter', 'task_filter')
IDENTITY = {'model': 'QN65Q70TAFXZC', 'firmware': 'T-NKMAKUC-2743.0', 'tizen': '5.5.0'}
HOME = (STOCK, 'XF86Home', None, None, '', 'launch', 'package:' + STOCK, 'entry_point:smarthub_key')
SOURCE = (STOCK, 'XF86Display', None, None, '', 'launch', 'package:' + STOCK, 'entry_point:source_key')
FOUR = HOME[:6] + ('package:' + OWN, 'entry_point:four_home')
VERSIONS = {'register': '0.2.1', 'apply': '0.2.2', 'restore': '0.2.3'}


def tables(report):
    if any(report.get(key) != value for key, value in IDENTITY.items()):
        raise ValueError('This model, firmware or Tizen version has not been tested.')
    result = {}
    for table, width in zip(TABLES, (3, 8, 7)):
        rows = report['tables'][table]
        if not isinstance(rows, list) or any(not isinstance(row, list) or len(row) != width
                or any(value is not None and not isinstance(value, str) for value in row) for row in rows):
            raise ValueError('Invalid snapshot table: ' + table)
        result[table] = Counter(tuple(row) for row in rows)
    return result


def baseline(report):
    original = tables(report)
    if [sum(original[t].values()) for t in TABLES] != [28, 70, 0]:
        raise ValueError('Expected the original 28 managed apps, 70 key rules and no task rules.')
    if Counter({r: n for r, n in original['managed_app'].items() if r[0] == STOCK}) != Counter({(STOCK, 'partial', None): 1}):
        raise ValueError('Samsung managed-app metadata differs.')
    if Counter({r: n for r, n in original['key_filter'].items() if r[0] == STOCK}) != Counter({HOME: 1, SOURCE: 1}):
        raise ValueError('Samsung Home or Source rule differs.')
    if any(row[0] == OWN for table in TABLES for row in original[table]):
        raise ValueError('Capture the original baseline before installing the route companion.')
    return original


def compare(original_report, current_report, state):
    expected = baseline(original_report)
    expected['managed_app'][(OWN, None, None)] += 1
    if state == 'apply':
        del expected['key_filter'][HOME]
        expected['key_filter'][FOUR] += 1
    actual = tables(current_report)
    for table in TABLES:
        if actual[table] != expected[table]:
            raise ValueError('Unexpected routing changes in ' + table)


def manifest(stage):
    E.register_namespace('', NS)
    def add(parent, tag, attrs=None, text=None):
        child = E.SubElement(parent, '{' + NS + '}' + tag, attrs or {})
        child.text = text
        return child
    root = E.Element('{' + NS + '}manifest', {'package': OWN, 'version': VERSIONS[stage], 'api-version': '5.0', 'type': 'tpk'})
    add(root, 'profile', {'name': 'tv'})
    add(root, 'label', text='Four Home route')
    add(root, 'description', text='Local Home shortcut for Four.')
    app = add(root, 'ui-application', {'appid': OWN, 'exec': 'FourRoute.dll', 'type': 'dotnet', 'multiple': 'false',
              'nodisplay': 'true', 'taskmanage': 'false', 'launch_mode': 'single'})
    add(app, 'label', text='Four Home route')
    add(app, 'icon', text='icon.png')
    privileges = add(root, 'privileges')
    add(privileges, 'privilege', text='http://tizen.org/privilege/appmanager.launch')
    if stage == 'register':
        add(root, 'app-context', {'appid': OWN})
    else:
        context = add(root, 'app-context', {'appid': STOCK, 'ui-type': 'partial'})
        for row in (FOUR if stage == 'apply' else HOME, SOURCE):
            rule = add(context, 'app-context-rule')
            add(rule, 'source', {'selector': 'key'}, row[1])
            add(rule, 'target', {'selector': 'app', 'request': 'launch', 'args': row[7]}, row[6].removeprefix('package:'))
    return E.tostring(root, encoding='utf-8', xml_declaration=True)


def build(report, out, dotnet):
    baseline(report)
    out.mkdir(parents=True, exist_ok=False)
    compiled = out / 'compiled'
    subprocess.run([dotnet, 'publish', str(ROOT / 'native/FourRoute.csproj'), '-c', 'Release', '-o', str(compiled), '--nologo'], check=True)
    for stage in VERSIONS:
        folder = out / stage
        (folder / 'bin').mkdir(parents=True)
        (folder / 'res').mkdir()
        for name in ('FourRoute.dll', 'FourRoute.deps.json', 'FourRoute.runtimeconfig.json'):
            shutil.copy2(compiled / name, folder / 'bin' / name)
        shutil.copy2(ROOT / 'app/icon.png', folder / 'res/icon.png')
        (folder / 'tizen-manifest.xml').write_bytes(manifest(stage))
        with zipfile.ZipFile(out / (stage + '.tpk'), 'w', zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(folder.rglob('*')):
                if path.is_file():
                    archive.write(path, path.relative_to(folder))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    build_parser = sub.add_parser('build')
    build_parser.add_argument('--baseline', type=Path, required=True)
    build_parser.add_argument('--out', type=Path, required=True)
    build_parser.add_argument('--dotnet', default='dotnet')
    check_parser = sub.add_parser('check')
    check_parser.add_argument('--baseline', type=Path, required=True)
    check_parser.add_argument('--current', type=Path, required=True)
    check_parser.add_argument('--state', choices=('apply', 'restore', 'register'), required=True)
    args = parser.parse_args()
    original = json.loads(args.baseline.read_text())
    if args.command == 'check':
        compare(original, json.loads(args.current.read_text()), args.state)
        print('Routing snapshot matches ' + args.state + '. Physical remote testing is still required.')
    else:
        build(original, args.out.resolve(), args.dotnet)
        print('Unsigned packages built. No TV connection or installation performed. Read docs/home-route.md.')


if __name__ == '__main__':
    main()
