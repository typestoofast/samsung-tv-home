"""Stage a private Four build with input bindings and optional local timing."""
import argparse
import html
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('input_bindings', ROOT / 'tools/import-inputs.py')
input_bindings = importlib.util.module_from_spec(spec)
spec.loader.exec_module(input_bindings)
spec = importlib.util.spec_from_file_location('home_config', ROOT / 'tools/home-config.py')
home_config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(home_config)
FILES = ('index.html', 'style.css', 'device.js', 'app.js', 'config.xml', 'icon.png')
LOGOS = ('appletv.svg', 'nintendoswitch.svg', 'stremio.svg', 'steam.svg')


def diagnostics_files(out, diagnostics):
    if diagnostics:
        shutil.copy2(ROOT / 'app/timing.js', out / 'timing.js')
        (out / 'timing-config.js').write_text('window.FourTimingEnabled = true;\n')
        page = out / 'index.html'
        html = page.read_text()
        marker = '  <link rel="icon"'
        if html.count(marker) != 1:
            raise ValueError('The timing script insertion point changed. Do not package this staging directory.')
        html = html.replace(marker, '  <script src="timing-config.js"></script>\n  <script src="timing.js"></script>\n' + marker)
        page.write_text(html)


def base_files(out):
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name in FILES:
        shutil.copy2(ROOT / 'app' / name, out / name)
    (out / 'assets').mkdir()


def stage(records, out, diagnostics=False):
    mapping = input_bindings.bindings(records)
    base_files(out)
    for name in LOGOS:
        shutil.copy2(ROOT / 'app/assets' / name, out / 'assets' / name)
    (out / 'input-map.js').write_text('window.FourInputMap = ' + json.dumps(mapping, separators=(',', ':')) + ';\n')
    diagnostics_files(out, diagnostics)


def stage_home(plan, directory, out, diagnostics=False):
    shortcuts = home_config.validate(plan, directory)
    base_files(out)
    buttons, sources = [], []
    logo_counts = {}
    for item in shortcuts:
        path = str(item['logoPath'])
        logo_counts[path] = logo_counts.get(path, 0) + 1
    for index, item in enumerate(shortcuts):
        image = item['key'] + item['logoPath'].suffix.lower()
        shutil.copy2(item['logoPath'], out / 'assets' / image)
        sources.append(dict(item['attribution'], file=image))
        attributes = {
            'class': 'destination ' + item['style'], 'data-key': item['key'],
            'data-kind': item['kind'], 'aria-label': item['label'],
            'tabindex': '0' if index == 0 else '-1',
        }
        if item['kind'] == 'hdmi':
            attributes.update({'data-port': str(item['port']), 'data-source-name': item['sourceName']})
        else:
            attributes['data-app-id'] = item['appId']
        attrs = ' '.join(name + '="' + html.escape(value, quote=True) + '"' for name, value in attributes.items())
        caption = ''
        if logo_counts[str(item['logoPath'])] > 1:
            caption = '<span class="destination-label">' + html.escape(item['label']) + '</span>'
        buttons.append('      <button ' + attrs + '><img src="assets/' + image +
                       '" alt="" width="240" height="240">' + caption + '</button>')
    page = out / 'index.html'
    content = page.read_text()
    start = content.index('    <nav class="destinations"')
    end = content.index('    </nav>', start) + len('    </nav>')
    nav_class = 'destinations multiline' if len(shortcuts) > 4 else 'destinations'
    nav = '    <nav class="' + nav_class + '" aria-label="Your shortcuts">\n' + '\n'.join(buttons) + '\n    </nav>'
    page.write_text(content[:start] + nav + content[end:])
    (out / 'input-map.js').write_text('window.FourInputMap = {};\n')
    (out / 'assets/SOURCES.json').write_text(json.dumps(sources, indent=2) + '\n')
    shutil.copy2(ROOT / 'THIRD_PARTY_NOTICES.md', out / 'THIRD_PARTY_NOTICES.md')
    shutil.copy2(ROOT / 'app/assets/SIMPLE-ICONS-LICENSE.md', out / 'assets/SIMPLE-ICONS-LICENSE.md')
    diagnostics_files(out, diagnostics)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--inputs', type=Path, help='Legacy Q70T export for the original four shortcuts')
    source.add_argument('--home', type=Path, help='Resolved, private agent setup plan')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--model', choices=['QN65Q70TAFXZC'])
    parser.add_argument('--firmware', choices=['T-NKMAKUC-2743.0'])
    parser.add_argument('--diagnostics', action='store_true')
    args = parser.parse_args()
    if args.home:
        stage_home(json.loads(args.home.read_text()), args.home.parent, args.out, args.diagnostics)
    else:
        if not args.model or not args.firmware:
            parser.error('--inputs requires the tested --model and --firmware')
        stage(json.loads(args.inputs.read_text()), args.out, args.diagnostics)
    print('Staged ' + ('diagnostic' if args.diagnostics else 'normal') + ' build. Nothing installed or connected to the TV.')
