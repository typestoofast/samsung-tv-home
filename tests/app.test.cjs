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

function fixture() {
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
  const buttons = Object.fromEntries(['apple', 'switch', 'stremio', 'steam', 'samsung'].map(key => {
    const button = eventTarget({
      tagName: 'BUTTON', tabIndex: -1,
      getAttribute(name) { return name === 'data-key' ? key : null; },
      focus() { document.activeElement = button; document.emit('focusin', { target: button }); },
      click() { button.emit('click'); }
    });
    return [key, button];
  }));
  document.querySelectorAll = selector => {
    assert.equal(selector, '.destination');
    return ['apple', 'switch', 'stremio', 'steam'].map(key => buttons[key]);
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
