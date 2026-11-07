"""Stage a private Four build with input bindings and optional local timing."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('input_bindings', ROOT / 'tools/import-inputs.py')
input_bindings = importlib.util.module_from_spec(spec)
spec.loader.exec_module(input_bindings)
FILES = ('index.html', 'style.css', 'device.js', 'app.js', 'config.xml', 'icon.png')
LOGOS = ('appletv.svg', 'nintendoswitch.svg', 'stremio.svg', 'steam.svg')


def stage(records, out, diagnostics=False):
    mapping = input_bindings.bindings(records)
    out.mkdir(parents=True, exist_ok=False)
    for name in FILES:
        shutil.copy2(ROOT / 'app' / name, out / name)
    (out / 'assets').mkdir()
    for name in LOGOS:
        shutil.copy2(ROOT / 'app/assets' / name, out / 'assets' / name)
    (out / 'input-map.js').write_text('window.FourInputMap = ' + json.dumps(mapping, separators=(',', ':')) + ';\n')
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


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--model', choices=['QN65Q70TAFXZC'], required=True)
    parser.add_argument('--firmware', choices=['T-NKMAKUC-2743.0'], required=True)
    parser.add_argument('--diagnostics', action='store_true')
    args = parser.parse_args()
    stage(json.loads(args.inputs.read_text()), args.out, args.diagnostics)
    print('Staged ' + ('diagnostic' if args.diagnostics else 'normal') + ' build. Nothing installed or connected to the TV.')
