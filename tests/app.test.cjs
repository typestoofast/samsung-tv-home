const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../app/app.js'), 'utf8');

const inputs = [
  { number: 3, name: 'Apple TV' },
  { number: 4, name: 'Switch 2' },
  { number: 2, name: 'Steam' }
];

function eventTarget(properties = {}) {
  const listeners = new Map();
  return Object.assign(properties, {
    addEventListener(name, callback) {
      if (!listeners.has(name)) listeners.set(name, []);
      listeners.get(name).push(callback);
    },
    emit(name, event = {}) {
      for (const callback of listeners.get(name) || []) callback(event);
    }
  });
}

function fixture(config = null) {
  const definitions = config || [
    { key: 'apple', label: 'Apple TV', kind: 'hdmi' },
    { key: 'switch', label: 'Switch 2', kind: 'hdmi' },
    { key: 'stremio', label: 'Stremio', kind: 'app', appId: 'IkWsFHtOY9.Stremio' },
    { key: 'steam', label: 'Steam', kind: 'hdmi' }
  ];
  const calls = [];
  const reads = [];
  const actions = [];
  const classes = new Set();
  const status = { textContent: '' };
  const document = eventTarget({
    hidden: false,
    body: { classList: {
      add(name) { classes.add(name); },
      remove(name) { classes.delete(name); },
      contains(name) { return classes.has(name); }
    } }
  });
  const buttons = Object.fromEntries([...definitions, { key: 'samsung' }].map(definition => {
    const key = definition.key;
    const attributes = { 'data-key': key, 'aria-label': definition.label, 'data-kind': definition.kind,
      'data-app-id': definition.appId, 'data-port': definition.port, 'data-source-name': definition.sourceName };
    const button = eventTarget({
      tagName: 'BUTTON', tabIndex: -1,
      getAttribute(name) { return attributes[name] ?? null; },
      focus() { document.activeElement = button; document.emit('focusin', { target: button }); },
      click() { button.emit('click'); }
    });
    return [key, button];
  }));
  document.querySelectorAll = selector => {
    assert.equal(selector, '.destination');
    return definitions.map(item => buttons[item.key]);
  };
  document.getElementById = id => id === 'status' ? status : buttons[id];
  function action(kind, value, done) {
    calls.push([kind, value]);
    actions.push({ done, active: true });
  }
  const device = {
    available: true,
    sources(done) {
      for (const read of reads) read.active = false;
      reads.push({ done, active: true });
    },
    match(key, list) {
      const names = { apple: 'Apple TV', switch: 'Switch 2', steam: 'Steam' };
      const matches = list.filter(input => input.name === names[key]);
      return matches.length === 1 ? matches[0].number : null;
    },
    input(port, done) { action('input', port, done); },
    launch(id, done) { action('launch', id, done); },
    cancel() {
      for (const request of [...reads, ...actions]) request.active = false;
    }
  };
  vm.runInNewContext(source, { window: { FourDevice: device, document }, document });
  return {
    calls, reads, status,
    focused() { return document.activeElement.getAttribute('data-key'); },
    busy() { return classes.has('busy'); },
    click(key) { buttons[key].click(); },
    key(keyCode) { document.emit('keydown', { keyCode, preventDefault() {} }); },
    visibility(hidden) { document.hidden = hidden; document.emit('visibilitychange'); },
    discover(index, error = null, list = inputs) {
      const read = reads[index];
      assert.ok(read, 'Expected a source read');
      if (!read.active) return;
      read.active = false;
      read.done(error, list);
    },
    complete(index, error = null) {
      const request = actions[index];
      assert.ok(request, 'Expected a device action');
      if (!request.active) return;
      request.active = false;
      request.done(error);
    }
  };
}

test('an HDMI click during initial discovery waits and opens the selected input once', () => {
  const f = fixture();
  assert.equal(f.reads.length, 1);
  f.click('apple');
  assert.equal(f.busy(), true);
  assert.deepEqual(f.calls, []);
  f.click('apple');
  assert.equal(f.reads.length, 1);
  f.discover(0);
  assert.deepEqual(f.calls, [['input', 3]]);
  assert.equal(f.busy(), true);
  f.complete(0);
  assert.equal(f.busy(), false);
  assert.equal(f.status.textContent, '');
});

test('generated shortcuts use the detected port and installed app ID, not the example household', () => {
  const f = fixture([
    { key: 'hdmi-1', label: 'PlayStation 5', kind: 'hdmi', port: 1, sourceName: 'PlayStation 5' },
    { key: 'app-0', label: 'Stremio', kind: 'app', appId: 'different.Stremio' }
  ]);
  f.click('app-0');
  assert.deepEqual(f.calls, [['launch', 'different.Stremio']]);
  f.complete(0);
  f.discover(0, null, [{ number: 1, name: '' }]);
  f.click('hdmi-1');
  assert.deepEqual(f.calls[1], ['input', 1]);
});

test('live names follow a moved device and reject ambiguous or contradictory saved bindings', () => {
  const config = [{ key: 'hdmi-3', label: 'Apple TV', kind: 'hdmi', port: 3, sourceName: 'Apple TV' }];
  const moved = fixture(config);
  moved.discover(0, null, [{ number: 1, name: 'Apple TV' }, { number: 3, name: 'Console' }]);
  moved.click('hdmi-3');
  assert.deepEqual(moved.calls, [['input', 1]]);
  for (const list of [
    [{ number: 1, name: 'Apple TV' }, { number: 3, name: 'Apple TV' }],
    [{ number: 3, name: 'Other device' }]
  ]) {
    const f = fixture(config);
    f.discover(0, null, list);
    f.click('hdmi-3');
    assert.deepEqual(f.calls, []);
    assert.match(f.status.textContent, /could not be found/);
  }
});

test('six shortcuts navigate both rows, edges, and Samsung Home', () => {
  const f = fixture(Array.from({ length: 6 }, (_, index) => ({
    key: 'app-' + index, label: 'App ' + index, kind: 'app', appId: 'installed.' + index
  })));
  f.key(37);
  assert.equal(f.focused(), 'app-0');
  f.key(40);
  assert.equal(f.focused(), 'app-4');
  f.key(39);
  f.key(39);
  assert.equal(f.focused(), 'app-5');
  f.key(38);
  assert.equal(f.focused(), 'app-1');
  f.key(39);
  f.key(39);
  f.key(39);
  assert.equal(f.focused(), 'app-3');
  f.key(40);
  assert.equal(f.focused(), 'samsung');
  f.key(38);
  assert.equal(f.focused(), 'app-3');
});

test('Back cancels a queued HDMI selection and allows a new selection', () => {
  for (const keyCode of [27, 10009]) {
    const f = fixture();
    f.click('apple');
    assert.equal(f.busy(), true);
    f.key(keyCode);
    assert.equal(f.busy(), false);
    f.discover(0);
    assert.deepEqual(f.calls, []);
    f.click('switch');
    assert.equal(f.reads.length, 2);
    f.discover(1);
    assert.deepEqual(f.calls, [['input', 4]]);
  }
});

test('Stremio opens during discovery and a source error cannot reset its pending launch', () => {
  const f = fixture();
  f.click('stremio');
  assert.deepEqual(f.calls, [['launch', 'IkWsFHtOY9.Stremio']]);
  assert.equal(f.busy(), true);
  const opening = f.status.textContent;
  f.discover(0, 'Source read failed');
  assert.equal(f.busy(), true);
  assert.equal(f.status.textContent, opening);
  f.click('steam');
  assert.equal(f.calls.length, 1);
  f.complete(0);
  assert.equal(f.busy(), false);
  assert.equal(f.status.textContent, '');
});

test('a warm return uses verified inputs while its refresh is still pending', () => {
  const f = fixture();
  f.discover(0);
  f.visibility(true);
  f.visibility(false);
  assert.equal(f.reads.length, 2);
  f.click('steam');
  assert.deepEqual(f.calls, [['input', 2]]);
  assert.equal(f.reads[1].active, true);
  assert.equal(f.busy(), true);
  f.discover(1);
  assert.deepEqual(f.calls, [['input', 2]]);
  assert.equal(f.busy(), true);
  f.complete(0);
  assert.equal(f.busy(), false);
});

test('visibility changes discard a queued selection before the next source read completes', () => {
  const f = fixture();
  f.click('apple');
  assert.equal(f.busy(), true);
  f.visibility(true);
  assert.equal(f.busy(), false);
  f.visibility(false);
  assert.equal(f.reads.length, 2);
  f.discover(0);
  f.discover(1);
  assert.deepEqual(f.calls, []);
  assert.equal(f.busy(), false);
  f.click('steam');
  assert.deepEqual(f.calls, [['input', 2]]);
});
