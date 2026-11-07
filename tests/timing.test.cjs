const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../app/timing.js'), 'utf8');
const key = 'four.startup-timing.v1';

function fixture(options = {}) {
  const data = options.data || new Map();
  const calls = [];
  const events = new Map();
  const frames = [];
  let now = 10;
  let wall = 100000;
  function listen(name, fn) { calls.push(['listen', name]); events.set(name, fn); }
  const window = {
    FourTimingEnabled: options.enabled,
    document: { hidden: false, readyState: options.readyState || 'loading', addEventListener: listen },
    addEventListener: listen,
    requestAnimationFrame(fn) { calls.push(['raf']); frames.push(fn); },
    performance: options.noPerformance ? undefined : {
      now() { calls.push(['clock']); return now; }, timeOrigin: 99990
    },
    get localStorage() {
      calls.push(['storage']);
      if (options.unavailable) throw new Error('Storage unavailable');
      return {
        getItem(name) {
          calls.push(['read']);
          now += options.storageDelay || 0; wall += options.storageDelay || 0;
          return data.get(name) || null;
        },
        setItem(name, text) {
          calls.push(['write']);
          if (options.quota) throw new Error('Storage full');
          data.set(name, text);
        },
        removeItem(name) { data.delete(name); }
      };
    }
  };
  const DateMock = { now() { calls.push(['wall']); return wall; } };
  vm.runInNewContext(source, { window, Date: DateMock, console: {
    log() { throw new Error('Unexpected console output'); }, error() { throw new Error('Unexpected console output'); }
  }, setTimeout() { throw new Error('Unexpected timer'); }, fetch() { throw new Error('Unexpected network request'); } });
  return {
    api: window.FourTiming, window, calls, data, frames,
    emit(name) { events.get(name)?.(); },
    frame() { frames.shift()?.(); },
    advance(ms) { now += ms; wall += ms; },
    records() { return window.FourTiming.export().runs.at(-1)?.events || []; }
  };
}

test('default-off and non-boolean flags touch no clocks, storage, listeners, or frames', () => {
  for (const enabled of [undefined, false, 'true', 1]) {
    const f = fixture({ enabled });
    f.api.mark('sources-start');
    f.api.clear();
    assert.equal(f.api.export().enabled, false);
    assert.equal(f.api.export().runs.length, 0);
    assert.deepEqual(f.calls, []);
  }
});

test('opt-in traces document and source milestones with two distinct rendering opportunities', () => {
  const f = fixture({ enabled: true });
  f.advance(2); f.api.mark('handlers-ready');
  f.api.mark('sources-start');
  f.emit('DOMContentLoaded');
  f.advance(3); f.api.mark('sources-ready');
  f.emit('load');
  assert.equal(f.records().at(-1).name, 'document-loaded');
  f.advance(16); f.frame();
  assert.equal(f.records().at(-1).name, 'load-frame-1');
  f.advance(16); f.frame();
  assert.equal(f.records().at(-1).name, 'load-frame-2');
  assert.equal(f.records().at(-1).atMs, 47);
  assert.equal(f.records().at(-1).wallMs, 100037);
  assert.equal(f.frames.length, 0);
  const stored = JSON.parse(f.data.get(key));
  assert.equal(stored.runs[0].timeOriginMs, 99990);
  assert.equal(stored.runs[0].clock, 'performance');
});

test('hiding cancels stale frame marks and visible return records its own pair', () => {
  const f = fixture({ enabled: true });
  f.emit('load');
  f.window.document.hidden = true; f.emit('visibilitychange');
  f.frame();
  assert.equal(f.records().some(event => event.name === 'load-frame-1'), false);
  f.window.document.hidden = false; f.emit('visibilitychange');
  f.frame(); f.frame();
  assert.deepEqual(Array.from(f.records().slice(-3), event => event.name),
    ['visibility-visible', 'visible-frame-1', 'visible-frame-2']);
});

test('script-start is captured before reading stored history', () => {
  const f = fixture({ enabled: true, storageDelay: 100 });
  assert.equal(f.records()[0].atMs, 10);
  assert.equal(f.records()[0].wallMs, 100000);
  f.api.mark('handlers-ready');
  assert.equal(f.records()[1].atMs, 110);
});

test('clearing a trace cancels a pending rendering callback', () => {
  const f = fixture({ enabled: true });
  f.emit('load');
  f.api.clear();
  f.frame();
  assert.equal(f.data.has(key), false);
  assert.equal(f.records().length, 0);
});

test('event limit stops storage writes and frame scheduling while preserving startup', () => {
  const f = fixture({ enabled: true });
  for (let i = 0; i < 200; i++) { f.advance(1); f.api.mark('sources-start'); }
  assert.equal(f.records().length, 48);
  assert.equal(f.records()[0].name, 'script-start');
  assert.equal(f.calls.filter(call => call[0] === 'write').length, 48);
  const count = f.calls.length;
  f.emit('visibilitychange');
  f.api.mark('sources-error');
  assert.equal(f.calls.length, count);
});

test('history persists across documents and stays inside run and byte limits', () => {
  const data = new Map();
  for (let i = 0; i < 12; i++) {
    const f = fixture({ enabled: true, data });
    for (let j = 0; j < 60; j++) f.api.mark('sources-ready');
    assert.ok(f.data.get(key).length * 2 <= 24576);
  }
  const history = JSON.parse(data.get(key));
  assert.ok(history.runs.length <= 5);
  assert.ok(history.runs.length >= 2);
  assert.ok(history.runs.every(run => run.events.length <= 48));
});

test('only the fixed event schema survives history and new marker input', () => {
  const data = new Map([[key, JSON.stringify({ version: 1, runs: [{
    startedAtMs: 1, timeOriginMs: null, clock: 'elapsed-wall', secret: 'discard',
    events: [{ name: 'sources-ready', atMs: 2, wallMs: 3, secret: 'discard' },
      { name: 'arbitrary user text', atMs: 3, wallMs: 4 }]
  }] })]]);
  const f = fixture({ enabled: true, data });
  f.api.mark('arbitrary user text');
  f.api.mark('sources-error', 'private failure details');
  const serialized = JSON.stringify(f.api.export());
  assert.doesNotMatch(serialized, /discard|arbitrary|private/);
  const exported = f.api.export();
  exported.runs[0].events.length = 0;
  assert.equal(f.api.export().runs[0].events.length, 1);
});

test('corrupt, oversized, unavailable, and full storage never break recording', () => {
  for (const options of [
    { data: new Map([[key, '{invalid']]) },
    { data: new Map([[key, 'x'.repeat(25000)]]) },
    { unavailable: true }, { quota: true }
  ]) {
    const f = fixture({ enabled: true, ...options });
    f.api.mark('sources-error');
    f.emit('load'); f.frame(); f.frame();
    assert.equal(f.records().at(-1).name, 'load-frame-2');
    assert.equal(f.api.export().runs.length, 1);
  }
});

test('complete documents and missing performance API have explicit fallback semantics', () => {
  const f = fixture({ enabled: true, noPerformance: true, readyState: 'complete' });
  f.advance(20); f.frame(); f.frame();
  f.emit('DOMContentLoaded'); f.emit('load');
  assert.equal(f.api.export().runs[0].clock, 'elapsed-wall');
  assert.equal(f.api.export().runs[0].timeOriginMs, null);
  assert.equal(f.records().filter(event => event.name === 'document-loaded').length, 1);
  assert.equal(f.records().at(-1).atMs, 20);
  f.api.clear();
  assert.equal(f.data.has(key), false);
  assert.equal(f.records().length, 0);
});
