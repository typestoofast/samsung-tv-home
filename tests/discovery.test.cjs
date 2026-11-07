const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../tools/discover-inputs.js'), 'utf8');

function fixture(options = {}) {
  const calls = [];
  const logs = [];
  const reads = { sources: [], apps: [] };
  const timers = new Map();
  let next = 1;
  function request(api, success, error) {
    calls.push(api);
    reads[api].push({ success, error });
    if (options.throws === api) throw { name: 'SecurityError', message: 'Read access denied' };
  }
  const window = {
    tizen: options.absent ? undefined : {
      systeminfo: { getPropertyValue(property, success, error) {
        assert.equal(property, 'VIDEOSOURCE'); request('sources', success, error);
      } },
      application: { getAppsInfo(success, error) { request('apps', success, error); } }
    },
    setTimeout(fn, delay) { assert.equal(delay, 8000); const id = next++; timers.set(id, fn); return id; },
    clearTimeout(id) { timers.delete(id); },
    console: { log(text) { logs.push(JSON.parse(text)); } },
    get localStorage() { throw new Error('Unexpected storage access'); },
    get fetch() { throw new Error('Unexpected network access'); }
  };
  vm.runInNewContext(source, { window });
  return {
    api: window.FourDiscovery, calls, logs, timers,
    success(api, data, index = 0) { reads[api][index].success(data); },
    fail(api, error, index = 0) { reads[api][index].error(error); },
    expire() { [...timers.values()].forEach(fn => fn()); },
    result() { return JSON.parse(JSON.stringify(window.FourDiscovery.result)); }
  };
}

test('automatic collection preserves unlabeled HDMI ports and copies only public app fields', () => {
  const f = fixture();
  f.success('sources', { connected: [{ type: 'HDMI', number: 3 }, { type: 'TV', number: 1 }],
    disconnected: [{ type: 'HDMI', number: 1, editName: ' Apple TV ' }] });
  assert.equal(f.api.result, null);
  f.success('apps', [{ id: 'stremio.app', name: 'Stremio', iconPath: '/icons/stremio.png', packageId: 'omit' }]);
  assert.deepEqual(f.result(), { schemaVersion: 1,
    sources: [{ port: 1, name: 'Apple TV', connected: false }, { port: 3, name: '', connected: true }],
    apps: [{ id: 'stremio.app', name: 'Stremio', iconPath: '/icons/stremio.png' }], errors: [] });
  assert.deepEqual(f.calls, ['sources', 'apps']);
  assert.equal(f.logs.length, 1);
  assert.equal(f.timers.size, 0);
});

test('one API failing preserves the other result and identifies its error', () => {
  for (const failed of ['sources', 'apps']) {
    const f = fixture();
    f.fail(failed, { name: 'UnknownError', message: 'Read failed' });
    if (failed === 'sources') f.success('apps', [{ id: 'one', name: 'One', iconPath: '' }]);
    else f.success('sources', { connected: [{ type: 'HDMI', number: 2 }], disconnected: [] });
    const result = f.result();
    assert.equal(result[failed].length, 0);
    assert.equal(result[failed === 'apps' ? 'sources' : 'apps'].length, 1);
    assert.deepEqual(result.errors, [{ api: failed, code: 'UnknownError', message: 'Read failed' }]);
  }
});

test('timeouts complete once and late or duplicate callbacks cannot mutate the export', () => {
  const f = fixture();
  f.success('sources', { connected: [{ type: 'HDMI', number: 1 }], disconnected: [] });
  f.expire();
  const result = f.result();
  assert.equal(result.errors[0].api, 'apps');
  assert.equal(result.errors[0].code, 'TimeoutError');
  f.success('apps', [{ id: 'late', name: 'Late', iconPath: '' }]);
  f.success('sources', { connected: [], disconnected: [] });
  f.fail('sources', { name: 'UnknownError' });
  assert.deepEqual(f.result(), result);
  assert.equal(f.logs.length, 1);
  assert.equal(f.timers.size, 0);
});

test('missing APIs and synchronous exceptions return separate errors without hanging', () => {
  const absent = fixture({ absent: true });
  assert.deepEqual(absent.result().errors.map(error => error.api), ['sources', 'apps']);
  assert.ok(absent.result().errors.every(error => error.code === 'NotSupportedError'));
  assert.equal(absent.timers.size, 0);
  const f = fixture({ throws: 'sources' });
  f.success('apps', []);
  assert.equal(f.result().errors[0].code, 'SecurityError');
  assert.equal(f.timers.size, 0);
});

test('both silent APIs reach one bounded completion with two timeout errors', () => {
  const f = fixture();
  f.expire();
  assert.deepEqual(f.result().errors.map(error => [error.api, error.code]),
    [['sources', 'TimeoutError'], ['apps', 'TimeoutError']]);
  assert.equal(f.logs.length, 1);
  assert.equal(f.timers.size, 0);
});

test('duplicate ports merge without selecting conflicting labels and corrupt ports are omitted', () => {
  const f = fixture();
  f.success('sources', {
    connected: [{ type: 'HDMI', number: 2, editName: 'Steam' }, { type: 'HDMI', number: 2, editName: 'Steam' },
      { type: 'HDMI', number: '3' }, null, { type: 'HDMI', number: 1.5 }, { type: 'HDMI', number: 0 }],
    disconnected: [{ type: 'HDMI', number: 2, editName: 'Apple TV' },
      { type: 'HDMI', number: 2, editName: 'Steam' }, { type: 'HDMI', number: 4 }]
  });
  f.success('apps', []);
  assert.deepEqual(f.result().sources, [{ port: 2, name: '', connected: true }, { port: 4, name: '', connected: false }]);
  assert.deepEqual(f.result().errors.map(error => error.code).sort(), ['ConflictingData', 'InvalidData']);
});

test('duplicate apps collapse by ID and preserve IDs when names or icons are missing', () => {
  const f = fixture();
  f.success('sources', { connected: [], disconnected: [] });
  f.success('apps', [{ id: 'b', name: 'Beta', iconPath: '/b' }, { id: 'b', name: 'Beta', iconPath: '/b' },
    { id: 'b', name: 'Other', iconPath: '/b' }, { id: 'b', name: 'Beta', iconPath: '/b' },
    { id: 'a' }, { id: '__proto__', name: 'Literal ID', iconPath: '' }, null, { id: '' }]);
  assert.deepEqual(f.result().apps, [{ id: '__proto__', name: 'Literal ID', iconPath: '' },
    { id: 'a', name: '', iconPath: '' }, { id: 'b', name: '', iconPath: '/b' }]);
  assert.ok(f.result().errors.some(error => error.api === 'apps' && error.code === 'ConflictingData'));
  assert.ok(f.result().errors.some(error => error.api === 'apps' && error.code === 'InvalidData'));
});

test('malformed API payloads report data errors and preserve any valid source list', () => {
  const f = fixture();
  f.success('sources', { connected: [{ type: 'HDMI', number: 4 }], disconnected: 'invalid' });
  f.success('apps', {});
  assert.equal(f.result().sources[0].port, 4);
  assert.deepEqual(f.result().errors.map(error => error.api), ['sources', 'apps']);
  assert.ok(f.result().errors.every(error => error.code === 'InvalidData'));
});

test('later collections refresh the export and require a callback', () => {
  const f = fixture();
  f.success('sources', { connected: [], disconnected: [] }); f.success('apps', []);
  let result, count = 0;
  f.api.collect(value => { result = JSON.parse(JSON.stringify(value)); count++; });
  f.success('apps', [], 1);
  f.success('sources', { connected: [{ type: 'HDMI', number: 1 }], disconnected: [] }, 1);
  assert.equal(count, 1);
  assert.equal(result.sources[0].port, 1);
  assert.equal(f.result().sources[0].port, 1);
  assert.equal(f.logs.length, 1);
  assert.throws(() => f.api.collect(), /callback/);
});
