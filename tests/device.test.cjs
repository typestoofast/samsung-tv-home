const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../app/device.js'), 'utf8');

function fixture(getSource) {
  const calls = [];
  const timers = new Map();
  let next = 1;
  let discovered, selected, launchSuccess;
  const window = { tizen: {
    systeminfo: { getPropertyValue(name, done) { discovered = done; } },
    tvwindow: { setSource(input, done) { calls.push(['source', input.number]); selected = done; } },
    application: { launch(id, done) { calls.push(['launch', id]); launchSuccess = done; } }
  } };
  if (getSource) window.tizen.tvwindow.getSource = getSource;
  vm.runInNewContext(source, { window, setTimeout(fn) { const id = next++; timers.set(id, fn); return id; }, clearTimeout(id) { timers.delete(id); } });
  return {
    api: window.FourDevice, calls,
    discover(data) { discovered(data); },
    select(data) { selected(data); },
    launched() { launchSuccess(); },
    expire() { [...timers.values()].forEach(fn => fn()); }
  };
}

function ready(f) {
  f.api.sources(() => {});
  f.discover({ connected: [{ type: 'HDMI', number: 2, editName: 'Steam' }], disconnected: [] });
}

test('input selection hands off to the TV viewer after selecting the requested port', () => {
  const f = fixture(() => ({ type: 'HDMI', number: 1 })); ready(f);
  let finished = false;
  f.api.input(2, error => { assert.equal(error, null); finished = true; });
  assert.deepEqual(f.calls, [['source', 2]]);
  f.select({ type: 'HDMI', number: 2 });
  assert.deepEqual(f.calls[1], ['launch', 'org.tizen.tv-viewer']);
  f.launched(); assert.equal(finished, true);
});

test('reopening the current HDMI input launches the viewer without selecting it again', () => {
  const f = fixture(type => { assert.equal(type, 'MAIN'); return { type: 'HDMI', number: 2 }; });
  ready(f);
  let finished = false;
  f.api.input(2, error => { assert.equal(error, null); finished = true; });
  assert.deepEqual(f.calls, [['launch', 'org.tizen.tv-viewer']]);
  assert.equal(finished, false);
  f.launched();
  assert.equal(finished, true);
});

test('missing, failed, or non-HDMI current-source reads preserve normal input selection', () => {
  for (const getSource of [undefined, () => { throw new Error('Read failed'); }, () => null, () => ({ type: 'TV', number: 2 })]) {
    const f = fixture(getSource); ready(f);
    let finished = false;
    f.api.input(2, error => { assert.equal(error, null); finished = true; });
    assert.deepEqual(f.calls, [['source', 2]]);
    f.select({ type: 'HDMI', number: 2 });
    assert.deepEqual(f.calls[1], ['launch', 'org.tizen.tv-viewer']);
    f.launched();
    assert.equal(finished, true);
  }
});

test('the current-input shortcut keeps timeout and stale-callback protection', () => {
  for (const mode of ['cancel', 'expire']) {
    const f = fixture(() => ({ type: 'HDMI', number: 2 })); ready(f);
    const results = [];
    f.api.input(2, error => results.push(error));
    if (mode === 'cancel') f.api.cancel(); else f.expire();
    f.launched();
    assert.equal(results.length, mode === 'cancel' ? 0 : 1);
    if (mode === 'expire') assert.match(results[0], /did not respond/);
    assert.deepEqual(f.calls, [['launch', 'org.tizen.tv-viewer']]);
  }
});

test('cancelled or timed-out source callbacks never launch a viewer later', () => {
  for (const mode of ['cancel', 'expire']) {
    const f = fixture(); ready(f);
    const errors = [];
    f.api.input(2, error => errors.push(error));
    if (mode === 'cancel') f.api.cancel(); else f.expire();
    f.select({ type: 'HDMI', number: 2 });
    assert.deepEqual(f.calls, [['source', 2]]);
    assert.equal(errors.length, mode === 'cancel' ? 0 : 1);
  }
});

test('unexpected selected input is reported without launching the viewer', () => {
  const f = fixture(); ready(f);
  let result;
  f.api.input(2, error => { result = error; });
  f.select({ type: 'HDMI', number: 4 });
  assert.match(result, /different input/);
  assert.equal(f.calls.length, 1);
});

test('missing port never sends a source-change request', () => {
  const f = fixture(); ready(f);
  let result;
  f.api.input(3, error => { result = error; });
  assert.match(result, /unavailable/);
  assert.equal(f.calls.length, 0);
});

test('label discovery rejects ambiguous matches and avoids guessing port numbers', () => {
  const f = fixture();
  assert.equal(f.api.match('apple', [{ name: 'Apple TV', number: 3 }]), 3);
  assert.equal(f.api.match('switch', [{ name: 'Nintendo Switch', number: 4 }]), 4);
  assert.equal(f.api.match('steam', [{ name: 'Steam', number: 2 }, { name: 'Steam', number: 1 }]), null);
  assert.equal(f.api.match('apple', [{ name: 'HDMI 1', number: 1 }]), null);
});
