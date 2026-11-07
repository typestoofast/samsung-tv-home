"""Validate a resolved home plan and prepare its local shortcut artwork."""
import hashlib
import json
from pathlib import Path
import re
import struct
from urllib.parse import urlparse
import zlib

ROOT = Path(__file__).resolve().parents[1]
BUNDLED = {
    'appletv': ('appletv.svg', 'apple'),
    'nintendoswitch': ('nintendoswitch.svg', 'switch'),
    'stremio': ('stremio.svg', 'stremio'),
    'steam': ('steam.svg', 'steam'),
}


def text(value, field, limit=160):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(field + ' must be nonempty text within ' + str(limit) + ' characters')
    if any(ord(char) < 32 for char in value):
        raise ValueError(field + ' contains a control character')
    return value.strip()


def validate_png(data):
    if len(data) < 33 or data[:16] != b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR':
        raise ValueError('Custom logo is not a PNG with an IHDR header')
    width, height, depth, color, compression, filtering, interlace = struct.unpack('>IIBBBBB', data[16:29])
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
    depths = {0: (1, 2, 4, 8, 16), 2: (8, 16), 3: (1, 2, 4, 8), 4: (8, 16), 6: (8, 16)}
    if not (1 <= width <= 1024 and 1 <= height <= 1024):
        raise ValueError('Custom logo dimensions must be between 1 and 1024 pixels')
    if color not in channels or depth not in depths[color] or compression or filtering or interlace:
        raise ValueError('Convert the custom logo to a non-interlaced PNG with a standard color format')
    position, pixels, palette, ended = 8, bytearray(), False, False
    while position < len(data):
        if position + 12 > len(data):
            raise ValueError('Custom logo contains a truncated PNG chunk')
        size, tag = struct.unpack('>I4s', data[position:position + 8])
        end = position + 8 + size
        if end + 4 > len(data) or zlib.crc32(data[position + 4:end]) != struct.unpack('>I', data[end:end + 4])[0]:
            raise ValueError('Custom logo has a corrupt PNG chunk')
        chunk = data[position + 8:end]
        if tag == b'IDAT':
            pixels.extend(chunk)
        elif tag in (b'acTL', b'fcTL', b'fdAT'):
            raise ValueError('Custom logos must be still images, not animated PNGs')
        elif tag == b'PLTE':
            if not size or size % 3 or size > 768:
                raise ValueError('Custom logo has an invalid PNG palette')
            palette = True
        elif tag == b'IEND':
            ended = size == 0 and end + 4 == len(data)
            break
        elif tag == b'IHDR':
            if position != 8 or size != 13:
                raise ValueError('Custom logo has a duplicate PNG header')
        elif not tag[0] & 32:
            raise ValueError('Custom logo uses an unsupported critical PNG chunk')
        position = end + 4
    if not ended or not pixels or (color == 3 and not palette):
        raise ValueError('Custom logo has no complete PNG image')
    stride = (width * channels[color] * depth + 7) // 8 + 1
    expected = height * stride
    try:
        decoder = zlib.decompressobj()
        raw = decoder.decompress(pixels, expected + 1)
    except zlib.error as error:
        raise ValueError('Custom logo has corrupt compressed pixels') from error
    if (len(raw) != expected or not decoder.eof or decoder.unused_data or
            any(raw[row * stride] > 4 for row in range(height))):
        raise ValueError('Custom logo has invalid PNG pixel data')


def artwork(logo, directory):
    if isinstance(logo, str) and logo in BUNDLED:
        filename, style = BUNDLED[logo]
        path = ROOT / 'app/assets' / filename
        sources = json.loads((ROOT / 'app/assets/SOURCES.json').read_text())
        source = next(item for item in sources if item['file'] == filename)
        return path, style, dict(source, license='See THIRD_PARTY_NOTICES.md')
    if not isinstance(logo, dict):
        raise ValueError('Every shortcut needs a bundled logo key or a sourced local PNG')
    filename = text(logo.get('file'), 'logo.file', 240)
    relative = Path(filename)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Custom logo paths must stay within the home plan directory')
    path = (directory / relative).resolve()
    if not path.is_relative_to(directory.resolve()) or path.suffix.lower() != '.png':
        raise ValueError('Custom logos must be local PNG files within the home plan directory')
    if not path.is_file() or path.stat().st_size > 262144:
        raise ValueError('Custom logo is missing or exceeds 256 KiB')
    data = path.read_bytes()
    validate_png(data)
    source = text(logo.get('source'), 'logo.source', 2048)
    url = urlparse(source)
    if url.scheme != 'https' or not url.netloc or url.username or url.password:
        raise ValueError('Custom logos need an HTTPS attribution source without credentials')
    license_text = text(logo.get('license'), 'logo.license', 1000)
    return path, '', {'url': source, 'license': license_text,
                      'sha256': hashlib.sha256(data).hexdigest()}


def validate(plan, directory):
    if not isinstance(plan, dict) or type(plan.get('schemaVersion')) is not int or plan['schemaVersion'] != 1:
        raise ValueError('Unsupported home plan schemaVersion')
    if plan.get('unresolved') != []:
        raise ValueError('Resolve every setup issue before staging the home screen')
    shortcuts = plan.get('shortcuts')
    if not isinstance(shortcuts, list) or not 1 <= len(shortcuts) <= 8:
        raise ValueError('Choose between one and eight shortcuts')
    keys, targets, labels, names = set(), set(), set(), set()
    result = []
    for shortcut in shortcuts:
        if not isinstance(shortcut, dict):
            raise ValueError('Each shortcut must be an object')
        key = text(shortcut.get('key'), 'key', 40)
        if not re.fullmatch(r'[a-z][a-z0-9-]*', key) or key in keys:
            raise ValueError('Shortcut keys must be unique lowercase identifiers')
        keys.add(key)
        label = text(shortcut.get('label'), 'label', 80)
        if label.casefold() in labels:
            raise ValueError('Shortcut labels must distinguish the destinations')
        labels.add(label.casefold())
        item = {'key': key, 'label': label, 'kind': shortcut.get('kind')}
        if item['kind'] == 'hdmi':
            port = shortcut.get('port')
            if type(port) is not int or not 1 <= port <= 16:
                raise ValueError('HDMI port must be an observed integer from 1 to 16')
            item.update(port=port, sourceName=text(shortcut.get('sourceName'), 'sourceName', 160))
            name = ' '.join(item['sourceName'].split()).casefold()
            if name in names:
                raise ValueError('Identical HDMI source names are still ambiguous; changing display labels does not resolve them')
            names.add(name)
            target = ('hdmi', port)
        elif item['kind'] == 'app':
            app_id = text(shortcut.get('appId'), 'appId')
            if not re.fullmatch(r'[A-Za-z0-9_.-]+', app_id):
                raise ValueError('App ID must be copied from the installed-app inventory')
            item['appId'] = app_id
            target = ('app', app_id)
        else:
            raise ValueError('Shortcut kind must be hdmi or app')
        if target in targets:
            raise ValueError('Two shortcuts refer to the same destination')
        targets.add(target)
        path, style, attribution = artwork(shortcut.get('logo'), directory)
        item.update(logoPath=path, style=style, attribution=attribution)
        result.append(item)
    return result
